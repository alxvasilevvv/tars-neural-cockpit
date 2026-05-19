"""Pin the contract of ``scripts/SOAK-HOURLY.command``.

Per ``docs/handoff/PH11_QA_SWEEP_BRIEF.md`` §9 the hourly probe ships
with 4 unit cases covering:

1. all 4 probes succeed → JSON record written, no abort
2. probes fail → ``any_fail=1`` and consec counter increments
3. log-append shape — record is exactly one line of valid JSON containing
   the documented field set
4. 3 consecutive fails → script exits 1 (abort)

We do **not** boot the real backend. A tiny stdlib HTTP server with
configurable status codes is enough to exercise the script end-to-end,
and keeps the test hermetic on CI.
"""

from __future__ import annotations

import json
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "SOAK-HOURLY.command"


# ── fake backend ────────────────────────────────────────────────────────────


def _make_handler(status_map: dict[str, int]):
    """Build a request handler that maps URL paths to status codes."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — http.server signature
            code = status_map.get(self.path, 404)
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, fmt, *args):  # silence access log noise
            pass

    return _Handler


def _pick_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def fake_backend():
    """Yield a (base_url, set_routes) tuple. Caller mutates ``routes``."""

    routes: dict[str, int] = {
        "/api/health": 200,
        "/api/pairing/status": 200,
        "/api/voice/health": 200,
        "/api/vault/status": 200,
        "/api/qa/probe": 200,
    }
    port = _pick_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(routes))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", routes
    finally:
        server.shutdown()
        server.server_close()


# ── helpers ─────────────────────────────────────────────────────────────────


def _run_hourly(tmp_repo: Path, base_url: str, *, env_overrides=None) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "TARS_SOAK_BASE_URL": base_url,
        "TARS_SOAK_PROBE_TIMEOUT": "2",
        # Forces the script to treat tmp_repo as repo root → .soak/ lands here.
        "TARS_SOAK_REPO": str(tmp_repo),
    }
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """A throwaway repo skeleton just rich enough for the script to behave."""

    # Tiny backend.log so the offset-tracking branch executes.
    (tmp_path / "backend.log").write_text("INFO startup ok\n")
    return tmp_path


# ── 1. all probes succeed ───────────────────────────────────────────────────


def test_all_probes_succeed_appends_clean_record(tmp_repo: Path, fake_backend):
    base_url, _routes = fake_backend
    result = _run_hourly(tmp_repo, base_url)

    assert result.returncode == 0, f"unexpected non-zero exit: {result.stderr}"
    log = (tmp_repo / ".soak" / "hourly.log").read_text().strip()
    assert log, "hourly.log should have exactly one line after one run"
    record = json.loads(log)
    assert record["any_fail"] == 0
    assert record["consec_failures"] == 0
    # All 4 mandatory probes recorded
    paths = [p["path"] for p in record["probes"]]
    assert paths == [
        "/api/health",
        "/api/pairing/status",
        "/api/voice/health",
        "/api/vault/status",
    ]
    for probe in record["probes"]:
        assert 200 <= probe["code"] < 300


# ── 2. probes fail → any_fail and consec increments ─────────────────────────


def test_probes_fail_marks_any_fail_and_increments_consec(tmp_repo: Path, fake_backend):
    base_url, routes = fake_backend
    # Flip one of the four to 500
    routes["/api/vault/status"] = 500
    result = _run_hourly(tmp_repo, base_url)
    assert result.returncode == 0, "single failed probe must NOT abort yet"
    log_lines = (tmp_repo / ".soak" / "hourly.log").read_text().strip().splitlines()
    assert len(log_lines) == 1
    record = json.loads(log_lines[0])
    assert record["any_fail"] == 1
    assert record["consec_failures"] == 1
    consec_file = (tmp_repo / ".soak" / "consec_failures").read_text().strip()
    assert consec_file == "1"


# ── 3. record shape contract ────────────────────────────────────────────────


def test_record_shape_contract(tmp_repo: Path, fake_backend):
    base_url, _routes = fake_backend
    _run_hourly(tmp_repo, base_url)
    record = json.loads((tmp_repo / ".soak" / "hourly.log").read_text().strip())
    # Document the keys that downstream tooling (SOAK-REPORT.command,
    # eventual dashboards) is allowed to depend on.
    required_keys = {
        "ts",
        "base_url",
        "probes",
        "qa_probe",
        "latency_p50_ms",
        "latency_p95_ms",
        "new_errors",
        "rss_mb",
        "fd_count",
        "wal_bytes",
        "consec_failures",
        "any_fail",
    }
    assert required_keys.issubset(record.keys()), \
        f"missing required keys: {required_keys - set(record.keys())}"
    # Timestamp is ISO-8601 UTC ("Z" suffix)
    assert record["ts"].endswith("Z") and "T" in record["ts"]
    # Probes is a list of length 4
    assert isinstance(record["probes"], list) and len(record["probes"]) == 4


# ── 4. 3 consecutive fails → exit 1 ─────────────────────────────────────────


def test_three_consecutive_failures_abort(tmp_repo: Path, fake_backend):
    base_url, routes = fake_backend
    routes["/api/health"] = 503
    # First run: consec=1 → exit 0
    r1 = _run_hourly(tmp_repo, base_url)
    assert r1.returncode == 0
    # Second run: consec=2 → exit 0
    r2 = _run_hourly(tmp_repo, base_url)
    assert r2.returncode == 0
    # Third run: consec=3 → exit 1 (abort)
    r3 = _run_hourly(tmp_repo, base_url, env_overrides={"TARS_SOAK_MAX_FAILS": "3"})
    assert r3.returncode == 1, (
        f"expected abort on 3rd consec fail; got exit={r3.returncode}\n"
        f"stdout={r3.stdout}\nstderr={r3.stderr}"
    )
    assert "ABORT" in r3.stderr
    # And the consec counter is persisted at 3
    consec_file = (tmp_repo / ".soak" / "consec_failures").read_text().strip()
    assert consec_file == "3"


# ── meta: file is executable & shebanged ────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists()
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    with SCRIPT.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"missing shebang: {first!r}"
