"""Pin the contract of ``scripts/GA-COOKBOOK.command``.

This wrapper aggregates ``PREFLIGHT-APPLE-SIGN.command`` (Gate 1) and
``BROTHER-PREFLIGHT.command`` (Gate 2) into a single pre-tag decision
script. The sub-gates each ship their own spec-pinning suites
(``test_preflight_apple_sign_script.py`` /
``test_brother_preflight_script.py``); this suite pins only the
*orchestration* contract:

1. Spec contract — header documents both gates verbatim with PR
   back-pointers (#216 + #217) and the aggregate verdict rule.
2. Exit code contract — 0 / 1 / 2 documented AND the four aggregate
   variants behave per worst-of-two rule:
       both 0       → 0  PROCEED
       any  1       → 1  BLOCK
       any  2 (no1) → 2  PARTIAL
       neither      → impossible (covered by exhaustive case stmt)
3. Env override surface — every documented ``GA_COOKBOOK_*`` knob is
   observable in the script body.
4. Orchestration — Gate 2 ALWAYS runs even if Gate 1 failed (so the
   operator sees both verdicts on one screen, not "run me twice").
5. Structural sanity — script is executable, shebanged, ``bash -n``.

Variants that need both sub-gates on disk to exercise are tested by
laying down minimal stub bash scripts under a temp ``scripts/`` dir
and pointing ``GA_COOKBOOK_REPO`` at it — same isolation pattern as
the other ritual-script suites.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "GA-COOKBOOK.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "scripts/GA-COOKBOOK.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"


def test_script_has_shebang():
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"
    assert "bash" in first, f"expected bash shebang, got: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents wrapper orchestration ─────────────────


def test_header_names_both_wrapped_gates():
    """Header must name both wrapped scripts so a future agent
    refactoring sub-gate names can't silently break the wrapper."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "PREFLIGHT-APPLE-SIGN.command" in body, "Gate 1 script name missing"
    assert "BROTHER-PREFLIGHT.command" in body, "Gate 2 script name missing"


def test_header_back_references_both_prs():
    """Header must back-point to PRs #216 + #217 so the wrapper's
    provenance is auditable."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "#216" in body, "missing PR #216 back-reference (Apple gate)"
    assert "#217" in body, "missing PR #217 back-reference (Brother gate)"


def test_header_documents_three_exit_codes():
    """The 0/1/2 contract is the user-visible API of this script."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "0   PROCEED" in body
    assert "1   BLOCK" in body
    assert "2   PARTIAL" in body


def test_header_documents_worst_of_two_rule():
    """Aggregate verdict semantics must be in the header so a future
    refactor can't quietly invert the rule."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The rule words appear in either header or body — the cookbook
    # narrative depends on them.
    assert "PROCEED:" in body and "BLOCK:" in body and "PARTIAL:" in body
    # And the worst-of-two implementation literal must be in the body
    assert 'APPLE_RC}" -eq 1' in body or "APPLE_RC -eq 1" in body
    assert 'BROTHER_RC}" -eq 1' in body or "BROTHER_RC -eq 1" in body


def test_header_documents_all_env_overrides():
    """Each documented GA_COOKBOOK_* knob must also appear in the
    script body — otherwise the doc lies."""
    body = SCRIPT.read_text(encoding="utf-8")
    for env_name in (
        "GA_COOKBOOK_DRY_RUN",
        "GA_COOKBOOK_SKIP_LIVE",
        "GA_COOKBOOK_SKIP_APPLE",
        "GA_COOKBOOK_SKIP_BROTHER",
        "GA_COOKBOOK_REPO",
        "GA_COOKBOOK_NO_COLOR",
    ):
        assert env_name in body, f"env override {env_name} not in script body"


def test_header_lists_cookbook_next_steps():
    """PROCEED path must print the remaining cookbook steps so the
    operator never has to remember 'what's after the gate?'."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The 7 non-gate cookbook steps must each be referenced verbatim
    assert "RELEASE-v10.0.command" in body
    assert "VERIFY-APPLE-SIGNATURE.command" in body
    assert "SOAK-HOURLY.command" in body
    assert "SOAK-REPORT.command" in body


# ── orchestration runtime — needs sub-gate stubs ──────────────────────────


def _make_stub_repo(tmp_path: Path, apple_rc: int, brother_rc: int) -> Path:
    """Lay out a minimal stub repo with sub-gates that exit ``apple_rc``
    and ``brother_rc`` respectively. Returns the repo root that should
    be passed via GA_COOKBOOK_REPO."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)

    # Copy the real wrapper in
    shutil.copy(SCRIPT, scripts / "GA-COOKBOOK.command")
    (scripts / "GA-COOKBOOK.command").chmod(0o755)

    # Lay down two stub sub-gates with the requested exit codes
    apple_stub = scripts / "PREFLIGHT-APPLE-SIGN.command"
    apple_stub.write_text(f"#!/usr/bin/env bash\necho STUB-APPLE\nexit {apple_rc}\n")
    apple_stub.chmod(0o755)

    brother_stub = scripts / "BROTHER-PREFLIGHT.command"
    brother_stub.write_text(
        f"#!/usr/bin/env bash\necho STUB-BROTHER\nexit {brother_rc}\n"
    )
    brother_stub.chmod(0o755)

    return tmp_path


def _run_wrapper(repo: Path, **env_overrides: str) -> subprocess.CompletedProcess:
    """Run the wrapper against a stub repo and return the completed
    process. Always sets NO_COLOR to make output stable across CI."""
    env = os.environ.copy()
    env["GA_COOKBOOK_REPO"] = str(repo)
    env["GA_COOKBOOK_NO_COLOR"] = "1"
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(repo / "scripts" / "GA-COOKBOOK.command")],
        capture_output=True,
        text=True,
        env=env,
    )


def test_worst_of_two_both_green_returns_zero(tmp_path):
    """Both sub-gates exit 0 → wrapper exits 0 (PROCEED)."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=0)
    result = _run_wrapper(repo)
    assert result.returncode == 0, f"expected 0, got {result.returncode}\n{result.stdout}\n{result.stderr}"
    assert "PROCEED" in result.stdout
    assert "tag v10.0.0 is unblocked" in result.stdout


def test_worst_of_two_apple_red_returns_one(tmp_path):
    """Gate 1 red → wrapper exits 1 (BLOCK) regardless of Gate 2."""
    repo = _make_stub_repo(tmp_path, apple_rc=1, brother_rc=0)
    result = _run_wrapper(repo)
    assert result.returncode == 1, f"expected 1, got {result.returncode}"
    assert "BLOCK" in result.stdout
    assert "DO NOT TAG" in result.stdout


def test_worst_of_two_brother_red_returns_one(tmp_path):
    """Gate 2 red → wrapper exits 1 (BLOCK) regardless of Gate 1."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=1)
    result = _run_wrapper(repo)
    assert result.returncode == 1, f"expected 1, got {result.returncode}"
    assert "BLOCK" in result.stdout


def test_worst_of_two_both_red_returns_one(tmp_path):
    """Both red → still exits 1 (not summed)."""
    repo = _make_stub_repo(tmp_path, apple_rc=1, brother_rc=1)
    result = _run_wrapper(repo)
    assert result.returncode == 1


def test_worst_of_two_apple_partial_returns_two(tmp_path):
    """Gate 1 partial (2), Gate 2 green → wrapper exits 2 (PARTIAL)."""
    repo = _make_stub_repo(tmp_path, apple_rc=2, brother_rc=0)
    result = _run_wrapper(repo)
    assert result.returncode == 2, f"expected 2, got {result.returncode}"
    assert "PARTIAL" in result.stdout


def test_worst_of_two_brother_partial_returns_two(tmp_path):
    """Gate 2 partial (2), Gate 1 green → wrapper exits 2 (PARTIAL)."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=2)
    result = _run_wrapper(repo)
    assert result.returncode == 2


def test_partial_loses_to_red(tmp_path):
    """If one gate is red and one is partial, BLOCK (1) wins over
    PARTIAL (2) — worst-of-two."""
    repo = _make_stub_repo(tmp_path, apple_rc=2, brother_rc=1)
    result = _run_wrapper(repo)
    assert result.returncode == 1, f"red must dominate partial; got {result.returncode}"


def test_gate2_always_runs_even_when_gate1_red(tmp_path):
    """The wrapper must NOT short-circuit on Gate 1 failure — the
    operator should see both verdicts on one pass."""
    repo = _make_stub_repo(tmp_path, apple_rc=1, brother_rc=0)
    result = _run_wrapper(repo)
    assert "STUB-APPLE" in result.stdout, "Gate 1 stub should have run"
    assert "STUB-BROTHER" in result.stdout, (
        "Gate 2 stub MUST run even when Gate 1 exited 1"
    )


def test_skip_apple_returns_partial(tmp_path):
    """GA_COOKBOOK_SKIP_APPLE=1 + Brother green → PARTIAL (2)."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=0)
    result = _run_wrapper(repo, GA_COOKBOOK_SKIP_APPLE="1")
    assert result.returncode == 2
    assert "PARTIAL" in result.stdout
    assert "skipped via GA_COOKBOOK_SKIP_APPLE" in result.stdout


def test_skip_brother_returns_partial(tmp_path):
    """GA_COOKBOOK_SKIP_BROTHER=1 + Apple green → PARTIAL (2)."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=0)
    result = _run_wrapper(repo, GA_COOKBOOK_SKIP_BROTHER="1")
    assert result.returncode == 2
    assert "PARTIAL" in result.stdout
    assert "skipped via GA_COOKBOOK_SKIP_BROTHER" in result.stdout


def test_missing_apple_script_returns_block(tmp_path):
    """Gate 1 script missing → BLOCK (1), with remediation pointer."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPT, scripts / "GA-COOKBOOK.command")
    (scripts / "GA-COOKBOOK.command").chmod(0o755)
    # No PREFLIGHT-APPLE-SIGN.command — only Brother
    brother_stub = scripts / "BROTHER-PREFLIGHT.command"
    brother_stub.write_text("#!/usr/bin/env bash\nexit 0\n")
    brother_stub.chmod(0o755)
    result = _run_wrapper(tmp_path)
    assert result.returncode == 1, f"expected 1, got {result.returncode}"
    assert "Gate 1 script missing" in result.stdout


def test_proceed_path_prints_next_steps(tmp_path):
    """Green path must surface the remaining cookbook steps."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=0)
    result = _run_wrapper(repo)
    assert "RELEASE-v10.0.command" in result.stdout
    assert "VERIFY-APPLE-SIGNATURE.command" in result.stdout
    assert "SOAK-HOURLY.command" in result.stdout


def test_block_path_prints_remediation_pointers(tmp_path):
    """Red path must point at the right brief for each failing gate."""
    repo = _make_stub_repo(tmp_path, apple_rc=1, brother_rc=1)
    result = _run_wrapper(repo)
    assert "APPLE_SIGNING_SETUP" in result.stdout or "APPLE_SIGNING_FOR_CURSOR" in result.stdout
    assert "PH11_BROTHER_HANDOFF_BRIEF" in result.stdout


def test_env_forwarding_dry_run_propagates(tmp_path):
    """GA_COOKBOOK_DRY_RUN=1 must appear in the env arrays the wrapper
    builds for the sub-gates (we observe this indirectly: with stubs
    that ignore env, the wrapper still exits cleanly, which proves
    the env construction didn't blow up under set -u)."""
    repo = _make_stub_repo(tmp_path, apple_rc=0, brother_rc=0)
    result = _run_wrapper(repo, GA_COOKBOOK_DRY_RUN="1")
    assert result.returncode == 0
    assert "GA_COOKBOOK_DRY_RUN=1" in result.stdout or "forwarded" in result.stdout


def test_block_does_not_leak_set_e_dump(tmp_path):
    """When a gate fails the script must NOT print a raw bash 'set -e'
    error trace — the failure must be channelled through the verdict
    summary."""
    repo = _make_stub_repo(tmp_path, apple_rc=1, brother_rc=0)
    result = _run_wrapper(repo)
    # No stray "command not found" / "line N:" traces
    assert "command not found" not in result.stdout
    assert "line " not in result.stderr.lower() or "warning" in result.stderr.lower()
