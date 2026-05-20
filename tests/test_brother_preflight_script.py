"""Pin the contract of ``scripts/BROTHER-PREFLIGHT.command``.

Same motion as ``test_preflight_apple_sign_script.py`` / 
``test_verify_apple_signature_script.py``: the script wraps probes
against the live meeet.world backend (sync 1+2+3+7), a live HTTPS curl
(sync 4), and operator env vars (sync 5+6). We can't fake the live
backend convincingly from pytest, so what we DO pin:

1. Spec contract — header documents all 7 syncs verbatim with the §<N>
   pointer that maps each sync to PR #198 brief §<N>.<X>. Brief and
   script can't drift silently.
2. Exit code contract — 0 / 1 / 2 documented AND the three observable
   variants (red, partial, green) actually produce the expected exit
   codes under ``BROTHER_PREFLIGHT_DRY_RUN=1`` matrix.
3. Env override surface — every documented env knob is observable in
   the script body so future agents can't quietly drop one.
4. Structural sanity — script is executable, shebanged, passes
   ``bash -n``.

Live network behaviour (sync 4 curl, sync 1/2/3/7 probe scripts hitting
api.meeet.world) is intentionally NOT asserted here — that's covered by
the operator's pre-tag-cut run per brief §7.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "BROTHER-PREFLIGHT.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "BROTHER-PREFLIGHT.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents brief §7 verbatim ──────────────────────


def test_header_documents_all_seven_syncs():
    """Header must enumerate Sync 1..7 in order with their §<X> pointer.
    If a sync gets dropped or renumbered, this test catches it before
    the operator runs the script blind against the live backend."""
    body = SCRIPT.read_text(encoding="utf-8")
    for n in range(1, 8):
        assert f"Sync {n}." in body, f"header missing 'Sync {n}.' enumeration"


def test_header_pins_brief_198_anchor_per_sync():
    """Each sync must reference the primitive it wraps (script name or
    curl invocation) so brief and script can't drift silently."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Sync 1 → probe-meeet-billing
    assert "probe-meeet-billing.command" in body
    # Sync 2 → CHECK-MEEET-LIVE
    assert "CHECK-MEEET-LIVE.command" in body
    # Sync 3 → smoke_billing_tars_backend
    assert "smoke_billing_tars_backend.sh" in body
    # Sync 4 → curl to meeet.world/billing/tars
    assert "meeet.world/billing/tars" in body
    # Sync 5 → reconcile-meeet-billing.py owner check
    assert "reconcile-meeet-billing.py" in body
    # Sync 6 → BROTHER_PAIR_TTL_ACK env var
    assert "BROTHER_PAIR_TTL_ACK" in body
    # Sync 7 → acceptance_tars_meeet
    assert "acceptance_tars_meeet.sh" in body


def test_header_pins_pr_198_back_pointer():
    """Spec contract: this script implements PR #198 brief §7. If anyone
    renumbers the brief, this anchor surfaces the drift in CI."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "PR #198" in body, "header must back-link to brief PR #198"
    assert "§7" in body, "header must back-link to brief §7"


def test_exit_code_contract_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "0   all 7 syncs green" in body
    assert "1   one or more syncs red" in body
    assert "2   neither green nor red" in body


def test_env_overrides_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    for var in (
        "BROTHER_PREFLIGHT_DRY_RUN",
        "BROTHER_PREFLIGHT_SKIP_LIVE",
        "BROTHER_PREFLIGHT_REPO",
        "BROTHER_RECONCILE_URL",
        "BROTHER_PAIR_TTL_ACK",
        "BROTHER_PREFLIGHT_NO_COLOR",
    ):
        assert var in body, f"env override not documented in header: {var}"


def test_pair_ttl_framed_as_v102_not_v10_blocker():
    """Brief §3.ph3-pair-ttl explicitly says 'NOT v10 GA — heads-up
    only'. The script must mirror that framing verbatim so an operator
    reading the help text doesn't accidentally treat Sync 6 as a hard
    blocker."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "NOT v10 GA" in body
    assert "heads-up only" in body


# ── runtime behaviour ──────────────────────────────────────────────────────


def _stub_repo_no_reconcile(tmp_path: Path) -> Path:
    stub = tmp_path / "stub"
    (stub / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, stub / "scripts" / SCRIPT.name)
    return stub


def _run(env_extra=None) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "BROTHER_PREFLIGHT_NO_COLOR": "1",
    }
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def test_dry_run_skip_live_no_reconcile_owner_is_red(tmp_path: Path):
    """Skip-live + no reconcile owner: Sync 5 RED → BLOCK (exit 1).

    Uses an isolated stub repo so this stays red after
    ``scripts/reconcile-meeet-billing.py`` lands on main."""
    stub = _stub_repo_no_reconcile(tmp_path)
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_PREFLIGHT_SKIP_LIVE": "1",
            "BROTHER_PREFLIGHT_REPO": str(stub),
        }
    )
    assert result.returncode == 1, (
        f"expected exit 1 (red); got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "BLOCK v10.0.0 GA TAG" in result.stdout
    assert "Sync 5 (A4 reconcile)" in result.stdout
    assert "red (no owner)" in result.stdout


def test_dry_run_skip_live_with_tars_reconcile_script_is_partial():
    """On main, TARS ships reconcile-meeet-billing.py — skip-live without
    live probes is PARTIAL (exit 2), not BLOCK."""
    if not (REPO / "scripts" / "reconcile-meeet-billing.py").exists():
        import pytest

        pytest.skip("reconcile script not present on this checkout")
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_PREFLIGHT_SKIP_LIVE": "1",
        }
    )
    assert result.returncode == 2, (
        f"expected exit 2 (partial); got {result.returncode}\n"
        f"stdout=\n{result.stdout}"
    )
    assert "PARTIAL" in result.stdout


def test_dry_run_skip_live_with_owners_is_partial():
    """SKIP_LIVE=1 with reconcile owner + pair-ttl ack: no reds, but
    5 live syncs still skipped → partial verdict, exit 2."""
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_PREFLIGHT_SKIP_LIVE": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/ops/reconcile",
            "BROTHER_PAIR_TTL_ACK": "yes",
        }
    )
    assert result.returncode == 2, (
        f"expected exit 2 (partial); got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "PARTIAL VERDICT" in result.stdout
    assert "Sync 5 (A4 reconcile) — green (brother owns)" in result.stdout
    assert "Sync 6 (ph3-pair-ttl) — green (ack recorded)" in result.stdout


def test_full_dry_run_with_owners_is_green():
    """Pure dry-run (no SKIP_LIVE) + reconcile owner + ack: all 7 syncs
    mocked-pass, verdict = PROCEED, exit 0. This is what CI exercises so
    the script doesn't bit-rot."""
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/ops/reconcile",
            "BROTHER_PAIR_TTL_ACK": "yes",
        }
    )
    assert result.returncode == 0, (
        f"expected exit 0 (green); got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "PROCEED" in result.stdout
    assert "brother coord side of v10.0.0 GA clear" in result.stdout


def test_full_dry_run_without_owners_is_red(tmp_path: Path):
    """Pure dry-run with NO reconcile owner declared: Sync 5 stays red,
    verdict = BLOCK, exit 1. This is the most common operator footgun
    (forgot to set BROTHER_RECONCILE_URL) and must be loudly flagged."""
    stub = _stub_repo_no_reconcile(tmp_path)
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_PREFLIGHT_REPO": str(stub),
        }
    )
    assert result.returncode == 1
    assert "BLOCK v10.0.0 GA TAG" in result.stdout
    assert "Sync 5 (A4 reconcile)" in result.stdout


def test_green_path_prints_next_step_cookbook():
    """On PROCEED, the script must point the operator at the remaining
    three rituals (#216 pre-flight, RELEASE script, #215 verify-sig,
    #214 soak) so the cookbook is discoverable from the script itself."""
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/ops/reconcile",
            "BROTHER_PAIR_TTL_ACK": "yes",
        }
    )
    assert result.returncode == 0
    for ritual in (
        "PREFLIGHT-APPLE-SIGN.command",
        "RELEASE-v10.0.command",
        "VERIFY-APPLE-SIGNATURE.command",
        "SOAK-HOURLY.command",
        "SOAK-REPORT.command",
    ):
        assert ritual in result.stdout, (
            f"green-path next-steps missing ritual pointer: {ritual}"
        )


def test_red_path_prints_remediation_pointers(tmp_path: Path):
    """On BLOCK, the failed sync must surface the brief §<N>.<X>
    remediation pointer so the operator can fix without re-reading
    the brief."""
    stub = _stub_repo_no_reconcile(tmp_path)
    result = _run(
        env_extra={
            "BROTHER_PREFLIGHT_DRY_RUN": "1",
            "BROTHER_PREFLIGHT_REPO": str(stub),
        }
    )
    assert result.returncode == 1
    assert "remediation:" in result.stdout
    # Sync 5 red MUST cite brief §3.A4 with the two remediation paths.
    assert "§3.A4" in result.stdout
    assert "BROTHER_RECONCILE_URL" in result.stdout
    assert "reconcile-meeet-billing.py" in result.stdout


def test_required_primitives_exist_on_main():
    """Spec contract: the four primitive scripts wrapped by syncs
    1/2/3/7 must exist in the repo. If anyone removes one in a
    refactor, this test surfaces the drift immediately."""
    for primitive in (
        "scripts/probe-meeet-billing.command",
        "scripts/CHECK-MEEET-LIVE.command",
        "scripts/smoke_billing_tars_backend.sh",
        "scripts/acceptance_tars_meeet.sh",
    ):
        assert (REPO / primitive).exists(), (
            f"primitive script missing — brief §5 listed it as wrappable: {primitive}"
        )


def test_pair_ttl_ack_skip_does_not_block_when_only_skip():
    """Sync 6 alone skipped (no live skip, no reds) is the ONLY allowed
    'clean' partial — brief §3.ph3-pair-ttl explicitly defers it to
    v10.2. Verify the ALLOWED_SKIPS=1 logic is in place."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "ALLOWED_SKIPS=1" in body, (
        "Sync 6 SKIP-PENDING tolerance lost — brief §3.ph3-pair-ttl "
        "says this sync is NOT a v10 GA blocker"
    )


def test_record_function_appends_per_sync_row():
    """Verdict summary must aggregate per-sync rows so the operator
    gets a one-screen pass/fail breakdown, not a wall of probe output."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"record\(\)\s*\{", body), "record() helper missing"
    # Verdict block must echo RESULTS so per-sync rows actually reach
    # the operator.
    assert 'echo "${RESULTS}"' in body
