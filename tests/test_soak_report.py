"""Pin the contract of ``scripts/SOAK-REPORT.command``.

Per ``docs/handoff/PH11_QA_SWEEP_BRIEF.md`` §9 the postmortem reporter
ships with 3 unit cases covering:

1. empty soak — script bails out cleanly with exit 2 and a placeholder
   markdown header (so the operator notices the misconfiguration)
2. one-hour soak — markdown renders with one table row; verdict is
   "blocked — only 1/72 samples recorded"
3. multi-hour soak with one ERROR spike — the spike shows up in the
   hard-fail thresholds table, the verdict flips to "blocked — hard-fail
   criterion hit"
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "SOAK-REPORT.command"


def _run_report(tmp_repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "TARS_SOAK_REPO": str(tmp_repo),
        },
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    (tmp_path / ".soak").mkdir()
    return tmp_path


def _make_record(
    ts: str,
    *,
    p50: int = 50,
    p95: int = 100,
    new_errors: int = 0,
    rss: int = 512,
    fd: int = 256,
    consec: int = 0,
    any_fail: int = 0,
) -> str:
    return json.dumps(
        {
            "ts": ts,
            "base_url": "http://127.0.0.1:8765",
            "probes": [
                {"path": "/api/health", "code": 200, "latency_ms": p50},
                {"path": "/api/pairing/devices", "code": 200, "latency_ms": p50},
                {"path": "/api/voice/health", "code": 200, "latency_ms": p50},
                {"path": "/api/vault/status", "code": 200, "latency_ms": p95},
            ],
            "qa_probe": {"code": 200, "latency_ms": 25},
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "new_errors": new_errors,
            "rss_mb": rss,
            "fd_count": fd,
            "wal_bytes": 4096,
            "consec_failures": consec,
            "any_fail": any_fail,
        }
    )


# ── 1. empty soak ───────────────────────────────────────────────────────────


def test_empty_soak_exits_two_with_placeholder(tmp_repo: Path):
    # No hourly.log at all → script must bail cleanly.
    result = _run_report(tmp_repo)
    assert result.returncode == 2, (
        f"expected exit 2 for empty soak; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "No hourly records found" in result.stdout
    assert "blocked (no data)" in result.stdout


# ── 2. one-hour soak ────────────────────────────────────────────────────────


def test_one_hour_soak_renders_table_and_blocks(tmp_repo: Path):
    log = tmp_repo / ".soak" / "hourly.log"
    log.write_text(_make_record("2026-05-19T00:00:00Z") + "\n")

    result = _run_report(tmp_repo)

    assert result.returncode == 0  # the report itself always exits 0
    out = result.stdout
    # Verdict block
    assert "**blocked**" in out, f"expected blocked verdict; got:\n{out[:500]}"
    assert "1 / 72" in out  # hours recorded vs target
    # Hour-by-hour table contains exactly one data row
    table_rows = [
        line for line in out.splitlines()
        if line.startswith("| 2026-05-19T")
    ]
    assert len(table_rows) == 1, f"expected 1 data row, got {len(table_rows)}: {table_rows}"


# ── 3. multi-hour soak with one ERROR spike ─────────────────────────────────


def test_multi_hour_with_error_spike_flips_verdict(tmp_repo: Path):
    log = tmp_repo / ".soak" / "hourly.log"
    lines = []
    for hour in range(10):
        ts = f"2026-05-19T{hour:02d}:00:00Z"
        # Hour 5 spikes new_errors way above threshold (default 100/hour)
        if hour == 5:
            lines.append(_make_record(ts, new_errors=250, any_fail=1, consec=1))
        else:
            lines.append(_make_record(ts))
    log.write_text("\n".join(lines) + "\n")

    result = _run_report(tmp_repo)
    out = result.stdout

    # Verdict must call out the hard-fail
    assert "**blocked**" in out
    assert "hard-fail criterion hit" in out

    # ERROR-per-hour row in the threshold table shows the spike & a FAIL marker
    err_row = next(
        line for line in out.splitlines()
        if "ERROR lines / hour" in line
    )
    assert "250" in err_row, f"spike value missing from threshold table: {err_row}"
    assert "FAIL" in err_row, f"FAIL marker missing on spiked row: {err_row}"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists()
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    with SCRIPT.open() as f:
        first = f.readline()
    assert first.startswith("#!")
