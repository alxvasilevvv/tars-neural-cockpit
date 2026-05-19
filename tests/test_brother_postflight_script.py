"""Pin the contract of ``scripts/BROTHER-POSTFLIGHT.command``.

Same pattern as ``test_brother_preflight_script.py`` /
``test_ga_cookbook_script.py`` / ``test_download_and_verify_release_script.py``:
the real post-tag brother coord verification requires a freshly-cut
v10 GA tag + live meeet.world infra + 24-72 h elapsed-time window so
real drift can manifest, plus a brother-side reconcile endpoint that
is currently TBD (per brief §3.A4's two-path resolution). We can't
fake any of that convincingly from pytest, and trying would relitigate
curl + meeet.world API contracts.

What we CAN pin (and DO):

1. Meta — script exists, is executable, shebanged, passes ``bash -n``.
2. Spec contract — header documents the 6 post-tag syncs verbatim, the
   0/1/2 exit code contract, the deltas from PREFLIGHT (5 regression
   syncs + 1 elevated reconcile-execution sync; drops preflight's
   ph3-pair-ttl ack), the hard deps, and every env override knob.
   Brief + script can't drift silently.
3. Sync count = 6 — pinned via a structural assertion on the ``hdr "Sync N — …"``
   lines (refactor that adds/removes a sync without updating tests
   fails CI).
4. Dry-run paths — three variants pinned with deterministic exit codes:
     a) SKIP_LIVE + no reconcile resolution → BLOCK rc=1 (Sync 5 red)
     b) SKIP_LIVE + BROTHER_RECONCILE_URL set → PARTIAL rc=2
     c) pure dry-run + BROTHER_RECONCILE_URL set → PROCEED rc=0
5. Differential framing from PREFLIGHT — pin that POSTFLIGHT does NOT
   include ``BROTHER_PAIR_TTL_ACK`` (the only sync preflight skipped
   that postflight intentionally drops; would be a silent-drift hint
   if a future refactor re-adds it).

Mac-only / live-infra behaviour (real ``probe-meeet-billing.command``
+ real ``curl https://meeet.world/billing/tars`` + real reconcile
script execution) is intentionally NOT asserted here — that's covered
by the operator's post-launch run per brief §6.

The script's verdict mapping for the post-tag context:
- 0 = brother coord clean → close v10 GA dock-down arc
- 1 = regression detected → BLOCK comms; decide rollback A/B/C
- 2 = partial verdict → defer comms until probes can re-run live
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "BROTHER-POSTFLIGHT.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "BROTHER-POSTFLIGHT.command must exist"
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


def test_header_names_seventh_implementer_follow_up():
    """Brief and script can't drift on the wave-position marker."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "W310-aj" in body, "wave-id missing from header"
    assert "SEVENTH implementer follow-up" in body
    assert "Symmetric" in body and "counterpart" in body
    assert "BROTHER-PREFLIGHT" in body, "must back-reference #217 preflight"
    assert "#217" in body
    assert "PR #198" in body, "must back-reference brother handoff brief"


def test_header_documents_six_post_tag_syncs_verbatim():
    body = SCRIPT.read_text(encoding="utf-8")
    why_block = body.split("Per brief §7 the 6 post-tag syncs", 1)[1].split(
        "Differences from PREFLIGHT", 1
    )[0]
    for marker in (
        "Sync 1.  Re-verify A1 ingest endpoint still healthy (regression)",
        "Sync 2.  Re-verify A2 /operator balance shape (regression)",
        "Sync 3.  Re-verify A5 auth + billing e2e smoke (regression)",
        "Sync 4.  Re-verify A3 (top-up checkout URL) still 200/301/302",
        "Sync 5.  RUN A4 reconciliation script (not just existence-check)",
        "Sync 6.  Re-run scripts/acceptance_tars_meeet.sh against live",
    ):
        assert marker in why_block, f"sync missing from header: {marker!r}"


def test_header_enumerates_deltas_from_preflight():
    """Brief and script can't drift on what makes postflight DIFFERENT
    from preflight (6 vs 7 syncs; exec vs existence; regression framing;
    no PROCEED→RELEASE call)."""
    body = SCRIPT.read_text(encoding="utf-8")
    deltas_section = body.split("Differences from PREFLIGHT", 1)[1].split(
        "Each sync runs in sequence", 1
    )[0]
    for marker in (
        "6 syncs (not 7)",
        "drops PREFLIGHT Sync 6 (BROTHER_PAIR_TTL_ACK)",
        "Sync 5 EXECUTES instead of checks",
        "All probes are regression-tagged",
        'No "next steps print PROCEED → RELEASE-v10.0.command"',
    ):
        assert marker in deltas_section, f"delta missing from header: {marker!r}"


def test_exit_code_contract_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "0   all 6 syncs green" in body, "exit-0 contract missing"
    assert "1   one or more syncs red" in body, "exit-1 contract missing"
    assert "2   neither green nor red" in body, "exit-2 contract missing"
    # Post-tag specific framing: red verdict gates LAUNCH COMMS, not tag
    # cut (tag is already cut by the time this runs).
    assert "BLOCK launch comms" in body
    assert "rollback path per brief §6" in body
    # Three rollback letter-options appear in the header — but split across
    # line wraps, so check each anchor token independently rather than the
    # cross-line phrase.
    assert "A hotfix" in body, "rollback option A (hotfix) not documented"
    assert "partial rollback" in body, "rollback option B not documented"
    assert "C full revert" in body, "rollback option C not documented"


def test_env_overrides_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    for var in (
        "BROTHER_POSTFLIGHT_DRY_RUN",
        "BROTHER_POSTFLIGHT_SKIP_LIVE",
        "BROTHER_POSTFLIGHT_REPO",
        "BROTHER_RECONCILE_URL",
        "BROTHER_POSTFLIGHT_NO_COLOR",
    ):
        assert var in body, f"env override not documented in header: {var}"


def test_does_not_document_pair_ttl_ack_knob():
    """POSTFLIGHT explicitly DROPS PREFLIGHT's BROTHER_PAIR_TTL_ACK
    sync — ph3-pair-ttl is heads-up only and only matters pre-tag.
    If a future refactor re-adds it, this test fires and forces a
    re-think (silent re-addition would muddy the postflight semantic)."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Header mentions BROTHER_PAIR_TTL_ACK only in the explanatory
    # "drops PREFLIGHT Sync 6" delta block. The literal knob must NOT
    # be wired into the runtime (no `if [ "${BROTHER_PAIR_TTL_ACK:-}" =`
    # condition anywhere outside the header comment).
    code_section = body.split("set -u", 1)[1]
    assert "BROTHER_PAIR_TTL_ACK" not in code_section, (
        "postflight runtime must not honour BROTHER_PAIR_TTL_ACK (it's a "
        "pre-tag-only ack, intentionally dropped from post-tag verdict)"
    )


def test_hard_deps_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    for dep in (
        "scripts/probe-meeet-billing.command",
        "scripts/CHECK-MEEET-LIVE.command",
        "scripts/smoke_billing_tars_backend.sh",
        "scripts/acceptance_tars_meeet.sh",
        "scripts/reconcile-meeet-billing.py",
    ):
        assert dep in body, f"hard dep not documented in header: {dep}"


def test_fails_safely_not_silently():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "Fails safely, not silently" in body


# ── structural: sync count pinned at 6 ──────────────────────────────────────


def test_runtime_has_exactly_six_sync_headers():
    """Pin the structural sync count so a refactor can't silently add
    a 7th sync (would shift the / 6 denominator) or drop a sync."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The runtime hdr lines look like:  hdr "Sync N — …: …"
    sync_headers = [
        line
        for line in body.splitlines()
        if line.lstrip().startswith('hdr "Sync ')
    ]
    assert len(sync_headers) == 6, (
        f"expected exactly 6 sync headers, got {len(sync_headers)}:\n"
        + "\n".join(sync_headers)
    )


def test_summary_denominator_matches_sync_count():
    """The Passed/Failed/Skipped denominator must be ``/ 6`` everywhere
    so a refactor that adds/removes a sync doesn't desync the verdict
    math from the actual sync count."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The three echo lines that print Passed/Failed/Skipped each end ``/ 6``.
    for needle in (
        'Passed:   ${C_GRN}${PASSED}${C_RST} / 6',
        'Failed:   ${C_RED}${FAILED}${C_RST} / 6',
        'Skipped:  ${C_YEL}${SKIPPED}${C_RST} / 6',
    ):
        assert needle in body, f"summary denominator drift: {needle!r}"


# ── runtime behaviour (dry-run paths) ──────────────────────────────────────


def _run(
    *args: str, env_extra=None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
    # Default to NO_COLOR + REPO=our repo so smoke is deterministic.
    env["BROTHER_POSTFLIGHT_NO_COLOR"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        cwd=str(cwd) if cwd else str(REPO),
        capture_output=True,
        text=True,
    )


def test_dry_run_skip_live_no_reconcile_blocks(tmp_path):
    """Variant A: SKIP_LIVE + no reconcile resolution.

    On a stub repo with no scripts/reconcile-meeet-billing.py AND
    BROTHER_RECONCILE_URL unset, Sync 5 goes red → BLOCK rc=1. This
    pins the post-tag intolerance for unresolved §3.A4 ownership:
    pre-tag it was an open question (preflight Sync 5 red was a soft
    flag), post-tag it's a HARD red because ledger drift accrues
    silently every day this remains unresolved."""
    stub_repo = tmp_path / "stub-repo-noresolve"
    (stub_repo / "scripts").mkdir(parents=True)
    # Don't lay reconcile-meeet-billing.py — the absence is the test.

    result = _run(
        env_extra={
            "BROTHER_POSTFLIGHT_REPO": str(stub_repo),
            "BROTHER_POSTFLIGHT_DRY_RUN": "1",
            "BROTHER_POSTFLIGHT_SKIP_LIVE": "1",
        }
    )
    assert result.returncode == 1, (
        f"SKIP_LIVE + no reconcile owner must BLOCK rc=1; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "BLOCK LAUNCH COMMS" in result.stdout
    assert "Sync 5 (A4 reconcile exec) — red (no owner)" in result.stdout
    assert "rollback path per" in result.stdout
    # Runtime BLOCK panel uses title-case + period after the letter.
    assert "A. Hotfix" in result.stdout
    assert "B. Partial rollback" in result.stdout
    assert "C. Full revert" in result.stdout


def test_dry_run_skip_live_with_reconcile_url_is_partial(tmp_path):
    """Variant B: SKIP_LIVE + BROTHER_RECONCILE_URL set.

    Sync 5 passes via brother URL (HEAD probe mocked in dry-run);
    Syncs 1-4+6 skipped → PARTIAL rc=2. Pins the "operator deliberately
    skipped live probes; defer launch comms" semantic."""
    stub_repo = tmp_path / "stub-repo-url"
    (stub_repo / "scripts").mkdir(parents=True)

    result = _run(
        env_extra={
            "BROTHER_POSTFLIGHT_REPO": str(stub_repo),
            "BROTHER_POSTFLIGHT_DRY_RUN": "1",
            "BROTHER_POSTFLIGHT_SKIP_LIVE": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/admin/reconcile/status",
        }
    )
    assert result.returncode == 2, (
        f"SKIP_LIVE + URL must PARTIAL rc=2; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "PARTIAL VERDICT" in result.stdout
    assert "Sync 5 (A4 reconcile exec) — green (dry-run, brother URL)" in result.stdout
    assert "Defer launch comms" in result.stdout
    assert "Passed:   1 / 6" in result.stdout
    assert "Skipped:  5 / 6" in result.stdout


def test_dry_run_full_with_reconcile_url_is_proceed(tmp_path):
    """Variant C: pure dry-run (no SKIP_LIVE) + BROTHER_RECONCILE_URL set.

    All 6 syncs green via dry-run mocks. Pins the PROCEED happy-path."""
    stub_repo = tmp_path / "stub-repo-full"
    (stub_repo / "scripts").mkdir(parents=True)
    # Lay stubs for the 4 primitive scripts so the runtime sees them
    # as present (without -x check passing the dry-run still records
    # which scripts ran; we want all 6 syncs to count green).
    for primitive in (
        "probe-meeet-billing.command",
        "CHECK-MEEET-LIVE.command",
        "smoke_billing_tars_backend.sh",
        "acceptance_tars_meeet.sh",
    ):
        stub = stub_repo / "scripts" / primitive
        stub.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                # Stub primitive — never invoked because dry-run short-circuits.
                exit 0
                """
            ),
            encoding="utf-8",
        )
        # Only `.command` files need +x for the runtime guard;
        # the `.sh` ones are invoked via `bash`.
        if primitive.endswith(".command"):
            stub.chmod(0o755)

    result = _run(
        env_extra={
            "BROTHER_POSTFLIGHT_REPO": str(stub_repo),
            "BROTHER_POSTFLIGHT_DRY_RUN": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/admin/reconcile/status",
        }
    )
    assert result.returncode == 0, (
        f"full dry-run + URL must PROCEED rc=0; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "PROCEED" in result.stdout
    assert "brother coord side of v10.0.0 GA healthy post-launch" in result.stdout
    assert "Passed:   6 / 6" in result.stdout
    assert "Failed:   0 / 6" in result.stdout
    assert "Skipped:  0 / 6" in result.stdout
    # PROCEED next-steps must include symmetry note + cron suggestion.
    assert "Schedule a T+72h re-run via cron" in result.stdout
    assert "GA-COOKBOOK (#218)" in result.stdout
    assert "DOWNLOAD-AND-VERIFY-RELEASE (#219)" in result.stdout


def test_dry_run_does_not_call_release_v10_in_next_steps(tmp_path):
    """Differential check from PREFLIGHT: PROCEED next-steps must NOT
    suggest running ``RELEASE-v10.0.command`` (preflight does; postflight
    runs AFTER the tag is already cut)."""
    stub_repo = tmp_path / "stub-repo-no-release-call"
    (stub_repo / "scripts").mkdir(parents=True)
    # Lay stubs so the primitive-existence guards in Syncs 1/2/3/6 pass
    # and the PROCEED block is exercised. Stubs are inert in dry-run.
    for primitive in (
        "probe-meeet-billing.command",
        "CHECK-MEEET-LIVE.command",
        "smoke_billing_tars_backend.sh",
        "acceptance_tars_meeet.sh",
    ):
        stub = stub_repo / "scripts" / primitive
        stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        if primitive.endswith(".command"):
            stub.chmod(0o755)

    result = _run(
        env_extra={
            "BROTHER_POSTFLIGHT_REPO": str(stub_repo),
            "BROTHER_POSTFLIGHT_DRY_RUN": "1",
            "BROTHER_RECONCILE_URL": "https://meeet.world/admin/reconcile/status",
        }
    )
    assert result.returncode == 0, (
        f"dry-run + full stubs + URL must PROCEED rc=0; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    # The PROCEED block must reference the POST-tag motion (announce,
    # close arc) — NOT the pre-tag motion (cut release).
    assert "RELEASE-v10.0.command" not in result.stdout, (
        "POSTFLIGHT PROCEED next-steps must not direct operator to re-cut "
        "the release — tag is already live by the time this runs"
    )
    assert "Post '✓ brother postflight green" in result.stdout
    assert "Close the v10 GA dock-down arc" in result.stdout


def test_reconcile_url_takes_precedence_over_local_py(tmp_path):
    """Pin priority order: if BROTHER_RECONCILE_URL is set AND a TARS-
    side reconcile-meeet-billing.py exists, the URL path wins. Reasoning:
    in the post-tag state we trust the explicit operator-set URL over
    silent file presence (operator may have moved ownership to brother
    after preflight passed via TARS path)."""
    stub_repo = tmp_path / "stub-repo-both-paths"
    (stub_repo / "scripts").mkdir(parents=True)
    # Lay a TARS-side reconcile script so both paths are viable.
    tars_reconcile = stub_repo / "scripts" / "reconcile-meeet-billing.py"
    tars_reconcile.write_text(
        textwrap.dedent(
            """\
            # Stub: would error if invoked (we want to confirm URL path is
            # chosen and Python is NOT invoked).
            raise SystemExit("should not be invoked — URL path must win")
            """
        ),
        encoding="utf-8",
    )

    result = _run(
        env_extra={
            "BROTHER_POSTFLIGHT_REPO": str(stub_repo),
            "BROTHER_POSTFLIGHT_DRY_RUN": "1",
            "BROTHER_POSTFLIGHT_SKIP_LIVE": "1",  # focus the test on Sync 5
            "BROTHER_RECONCILE_URL": "https://meeet.world/admin/reconcile/status",
        }
    )
    # Sync 5 should report the brother URL path (not the TARS-side path).
    assert "green (dry-run, brother URL)" in result.stdout, (
        f"BROTHER_RECONCILE_URL must take precedence over local .py; "
        f"got:\n{result.stdout}"
    )
    # And specifically NOT the TARS-side message.
    assert "green (dry-run, TARS script)" not in result.stdout


# ── platform sanity ────────────────────────────────────────────────────────


def test_repo_root_resolution_via_env_override():
    """Pin that BROTHER_POSTFLIGHT_REPO override works — needed for cron
    runs from /tmp where ``dirname(BASH_SOURCE)/..`` resolves wrong."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The first line of section 0 that sets REPO_ROOT must honour the env var.
    assert (
        'REPO_ROOT="${BROTHER_POSTFLIGHT_REPO:-$(cd "$(dirname '
        '"${BASH_SOURCE[0]}")/.." && pwd)}"'
    ) in body, "REPO_ROOT resolution structure drifted"


def test_curl_dependency_check_skippable_via_dry_run():
    """In dry-run, the curl-on-PATH guard must NOT fire so Linux CI
    without curl can exercise the spec contract."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Locate the platform sanity block: gated on DRY_RUN != 1.
    assert 'if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" != "1" ]; then' in body
    # And inside that block: the curl check.
    lines = body.splitlines()
    start = next(
        i
        for i, ln in enumerate(lines)
        if ln.strip() == 'if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" != "1" ]; then'
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "fi")
    sanity_block = "\n".join(lines[start + 1 : end])
    assert "command -v curl" in sanity_block, "curl-on-PATH guard moved out of dry-run gate"


# ── verdict-summary box drift catch ────────────────────────────────────────


def test_verdict_summary_box_present():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "BROTHER POSTFLIGHT VERDICT" in body, "verdict box header missing"


def test_postflight_proceed_next_step_includes_cron_pointer():
    """Pin the suggestion to schedule a T+72h cron re-run — this is the
    "slow-rot" insurance that distinguishes postflight from preflight."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "Schedule a T+72h re-run via cron" in body
    assert ".postflight/daily.log" in body, "cron log path drifted"
