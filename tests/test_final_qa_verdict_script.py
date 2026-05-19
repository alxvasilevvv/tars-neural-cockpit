"""Spec-contract tests for scripts/FINAL-QA-VERDICT.command (W310-am).

Pins meta + spec contract + structural invariants + runtime behaviour
under all 4 matrix variants (dry-run, sibling-missing, sibling-green-
with-skips, sibling-failing). Uses a stub-sibling pattern identical to
the test suites for #218 / #219 / #220 / #221 / #222 — lays a minimal
fake FINAL-QA-GATE.command in a tmp dir + points
``FINAL_QA_VERDICT_REPO`` at it, so the wrapper is exercised end-to-end
on Linux CI without needing a real pytest / SMOKE-TEST / perf / codesign
pipeline behind it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "FINAL-QA-VERDICT.command"

PROCEED = 0
BLOCK = 1
PARTIAL = 2


# ── Helpers ──────────────────────────────────────────────────────────


def _header() -> str:
    """Return the contiguous leading comment header (shebang + #-lines)."""
    out = []
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            out.append(line)
            continue
        if line.startswith("set -u"):
            break
    return "\n".join(out)


def _runtime_body() -> str:
    """Return the script body AFTER the leading header (for structural checks)."""
    text = SCRIPT.read_text(encoding="utf-8")
    idx = text.find("set -u")
    assert idx > 0, "expected `set -u` to mark end of header block"
    return text[idx:]


def _run_wrapper(
    *,
    repo: Path,
    env_extras: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    """Invoke FINAL-QA-VERDICT.command with FINAL_QA_VERDICT_REPO=repo."""
    env = os.environ.copy()
    env.setdefault("FINAL_QA_VERDICT_NO_COLOR", "1")
    env["FINAL_QA_VERDICT_REPO"] = str(repo)
    if env_extras:
        env.update(env_extras)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _make_stub_sibling(repo: Path, body: str) -> Path:
    """Lay a minimal stub scripts/FINAL-QA-GATE.command in `repo` and return its path."""
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    sibling = repo / "scripts" / "FINAL-QA-GATE.command"
    sibling.write_text(body, encoding="utf-8")
    sibling.chmod(0o755)
    return sibling


def _stub_body(passed: int, skipped: int, failed: int, *,
               passed_lines: list[str] | None = None,
               skipped_lines: list[str] | None = None,
               failed_lines: list[str] | None = None,
               exit_rc: int = 0) -> str:
    """Produce a stub-sibling script body that prints a parseable go/no-go block.

    Each row in the per-status arrays is emitted as a single-quoted ``echo``
    so the stub stays parseable under bash regardless of parens/quotes in
    the human-readable suffix (e.g. "(TARS.app not installed)").
    """
    passed_lines = passed_lines or [f"  ✓ {i+1}/8 stub-step" for i in range(passed)]
    skipped_lines = skipped_lines or [f"  ⚠ {i+1}/8 skipped" for i in range(skipped)]
    failed_lines = failed_lines or [f"  ✗ {i+1}/8 fail" for i in range(failed)]

    def _to_echoes(lines: list[str]) -> str:
        # Use single quotes so parens etc. stay literal. If line contains
        # a single quote, escape it the bash way: '\'' .
        out = []
        for ln in lines:
            ln_escaped = ln.replace("'", "'\\''")
            out.append(f"  echo '{ln_escaped}'")
        return "\n".join(out)

    pass_block = _to_echoes(passed_lines)
    skip_block = _to_echoes(skipped_lines)
    fail_block = _to_echoes(failed_lines)
    verdict_word = "GO" if exit_rc == 0 else "NO-GO"
    return f"""#!/usr/bin/env bash
LOG="${{FINAL_QA_VERDICT_LOG:-${{FINAL_QA_VERDICT_REPO:-${{REPO:-$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)}}}}/.FINAL-QA-GATE.txt}}"
{{
  echo "=== FINAL-QA-GATE.command at stub-stamp ==="
  echo "=================================================="
  echo "FINAL-QA-GATE — go/no-go report"
  echo "=================================================="
  echo "Passed:  {passed}"
{pass_block}
  echo "Skipped: {skipped}"
{skip_block}
  echo "Failed:  {failed}"
{fail_block}
  echo ""
  echo "=== {verdict_word} ==="
}} | tee "${{LOG}}"
exit {exit_rc}
"""


# ── 1. Meta / file structure ─────────────────────────────────────────


def test_script_exists() -> None:
    assert SCRIPT.exists(), f"missing {SCRIPT}"


def test_script_is_executable() -> None:
    mode = SCRIPT.stat().st_mode
    assert mode & 0o111, f"script not executable: {oct(mode)}"


def test_script_has_bash_shebang() -> None:
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first == "#!/usr/bin/env bash", f"unexpected shebang: {first!r}"


def test_bash_n_syntax_ok() -> None:
    rc = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert rc.returncode == 0, f"bash -n failed: {rc.stderr}"


# ── 2. Spec-contract: header pins the contract ──────────────────────


def test_header_names_tenth_implementer_follow_up() -> None:
    h = _header()
    assert "W310-am" in h, "missing W310-am sub-wave marker"
    assert "TENTH implementer follow-up" in h, "missing TENTH marker"


def test_header_documents_cookbook_uniform_contract() -> None:
    h = _header()
    # The header MUST enumerate which scripts share the 0/1/2 contract,
    # so future drift (e.g. accidentally returning rc=3) is visible in
    # the header source.
    for marker in ("#214", "#215", "#216", "#217", "#218", "#219", "#220", "#221", "#222"):
        assert marker in h, f"header missing back-reference to {marker}"
    assert "0/1/2 PROCEED" in h, "header must document 0/1/2 contract"
    assert "PARTIAL" in h, "header must document PARTIAL semantics"
    assert "destructively HARMLESS" in h, (
        "header must framing-pin destructively-harmless invariant"
    )


def test_header_documents_what_wrapper_adds() -> None:
    h = _header()
    # Three explicit value-adds over W267 sibling.
    assert "Three-way verdict" in h, "header must document three-way verdict mapping"
    assert "Demotes any SKIPPED" in h or "skipped" in h.lower(), (
        "header must document AMBER demotion for skipped steps"
    )
    assert "per-step remediation pointers" in h, (
        "header must document per-step remediation block"
    )


def test_header_documents_all_env_knobs() -> None:
    h = _header()
    for env in (
        "FINAL_QA_VERDICT_DRY_RUN",
        "FINAL_QA_VERDICT_REPO",
        "FINAL_QA_VERDICT_GATE_SCRIPT",
        "FINAL_QA_VERDICT_LOG",
        "FINAL_QA_VERDICT_NO_COLOR",
    ):
        assert env in h, f"header missing env knob: {env}"


def test_header_documents_exit_contract() -> None:
    h = _header()
    assert re.search(r"0\s*=\s*PROCEED", h), "header missing 0=PROCEED"
    assert re.search(r"1\s*=\s*BLOCK", h), "header missing 1=BLOCK"
    assert re.search(r"2\s*=\s*PARTIAL", h), "header missing 2=PARTIAL"


def test_header_references_sibling_w267_script() -> None:
    h = _header()
    assert "FINAL-QA-GATE.command" in h, (
        "header must name the W267 sibling it wraps"
    )
    assert "W267" in h, "header must back-reference W267 lineage"


# ── 3. Structural drift-guards ──────────────────────────────────────


def test_runtime_resolves_sibling_via_env_override() -> None:
    body = _runtime_body()
    # Both knobs must be honored — covered by header but pin in runtime
    # too so refactors can't drop either one silently.
    assert "FINAL_QA_VERDICT_REPO" in body, "runtime must honor REPO override"
    assert "FINAL_QA_VERDICT_GATE_SCRIPT" in body, (
        "runtime must honor GATE_SCRIPT override"
    )


def test_runtime_parses_skipped_count() -> None:
    body = _runtime_body()
    # Wrapper's whole point: read SKIPPED from sibling log and demote
    # to PARTIAL. If this regex disappears, the wrapper false-greens.
    assert "Skipped:" in body, "runtime must parse Skipped: line from sibling log"
    assert "SKIPPED_COUNT" in body, "runtime must track SKIPPED_COUNT"


def test_runtime_demotes_skipped_to_partial() -> None:
    body = _runtime_body()
    # Find the SKIPPED → AMBER mapping in runtime.
    pattern = r'SKIPPED_COUNT["\s}]*!?=?\s*"?0"?\s*\]?\s*;?\s*then.*?RC_PARTIAL=1'
    assert re.search(pattern, body, re.DOTALL), (
        "runtime must set RC_PARTIAL=1 when SKIPPED_COUNT != 0"
    )


def test_runtime_does_not_call_destructive_operations() -> None:
    """Wrapper must remain destructively harmless — no system mutation.

    Scan strips out string-content from ``echo "..."`` lines first so
    operator-informational hints like ``echo "  3) Cut tag: bash
    scripts/RELEASE-v10.0.command"`` don't false-trigger as actual
    invocations. Only NON-echoed shell calls count.
    """
    body = _runtime_body()
    # Strip echo-string content (single + double quoted) so "bash ..." inside
    # human-readable hints doesn't trigger an invocation regex.
    stripped = re.sub(r'echo\s+"[^"]*"', 'echo "<stripped>"', body)
    stripped = re.sub(r"echo\s+'[^']*'", "echo '<stripped>'", stripped)
    # Also strip printf "..." content.
    stripped = re.sub(r'printf\s+"[^"]*"', 'printf "<stripped>"', stripped)
    forbidden_patterns = [
        r"\brm\s+-rf\b",
        r"\bgit\s+tag\s+v",
        r"\bgit\s+push\s+origin\s+v",
        r"\bdefaults\s+write\b",
        r"\blaunchctl\s+(load|unload|bootout|bootstrap)\b",
        r"\bkillall\s+",
        r"\bpkill\s+",
        r"\bmv\s+/Applications/TARS\.app\b",
        r"\bcodesign\s+--remove",
        # Crucially: must NOT invoke RELEASE-v10.0.command. It's purely
        # a verdict producer, not a release driver. Operator decides.
        # (Hint strings echoed for the operator are fine — those get
        # stripped above before this check runs.)
        r"bash[^|;\n]*RELEASE-v10\.0\.command",
    ]
    for pat in forbidden_patterns:
        m = re.search(pat, stripped)
        assert m is None, (
            f"destructive op in runtime (matched {pat!r}): "
            f"{m.group(0) if m else ''!r}"
        )


def test_runtime_does_not_modify_sibling_script() -> None:
    body = _runtime_body()
    # Backwards-compat invariant: wrapper must not patch / overwrite
    # / chmod the sibling. RELEASE-v10.0.command still calls
    # FINAL-QA-GATE.command unchanged today.
    for pat in (r"sed\s+-i.*FINAL-QA-GATE", r"echo.*>\s*[^|].*FINAL-QA-GATE",
                r"chmod.*FINAL-QA-GATE"):
        m = re.search(pat, body)
        assert m is None, f"runtime mutates sibling: matched {pat!r}"


# ── 4. Runtime: dry-run baseline ────────────────────────────────────


def test_dry_run_no_sibling_invocation_exits_partial(tmp_path: Path) -> None:
    """With DRY_RUN=1 and no sibling on disk, exit PARTIAL (2)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    rc = _run_wrapper(
        repo=repo,
        env_extras={"FINAL_QA_VERDICT_DRY_RUN": "1"},
    )
    assert rc.returncode == PARTIAL, (
        f"expected rc={PARTIAL} PARTIAL, got rc={rc.returncode}\n"
        f"stdout:\n{rc.stdout}\nstderr:\n{rc.stderr}"
    )
    assert "VERDICT: PARTIAL" in rc.stdout
    assert "[dry-run]" in rc.stdout
    assert "would invoke" in rc.stdout


# ── 5. Runtime: missing sibling → BLOCK ─────────────────────────────


def test_sibling_missing_exits_block(tmp_path: Path) -> None:
    """Without DRY_RUN and without a sibling on disk, exit BLOCK (1).

    Differs from #222's graceful AMBER fallback for SMOKE-TEST.command,
    because here the wrapped script IS the gate (not one of 4 gates).
    Cannot make a GA decision without it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == BLOCK, (
        f"expected rc={BLOCK} BLOCK, got rc={rc.returncode}\n{rc.stdout}"
    )
    assert "VERDICT: BLOCK" in rc.stdout
    assert "sibling not found" in rc.stdout
    assert "W267" in rc.stdout, "remediation must back-ref W267 sibling"


# ── 6. Runtime: stub sibling — all-green PROCEED ────────────────────


def test_stub_all_green_exits_proceed(tmp_path: Path) -> None:
    """8 passed + 0 skipped + 0 failed sibling → PROCEED (0)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(repo, _stub_body(passed=8, skipped=0, failed=0))
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == PROCEED, (
        f"expected rc={PROCEED} PROCEED, got rc={rc.returncode}\n{rc.stdout}"
    )
    assert "VERDICT: PROCEED" in rc.stdout
    assert "passed:  8" in rc.stdout
    assert "GA-COOKBOOK.command (#218)" in rc.stdout, (
        "PROCEED block must enumerate cookbook next steps with PR refs"
    )
    assert "RELEASE-TAG-GUARD.command (#221)" in rc.stdout
    assert "RELEASE-v10.0.command" in rc.stdout, (
        "PROCEED block must name the destructive command for copy-paste"
    )


# ── 7. Runtime: stub sibling — skipped step demotes to PARTIAL ──────


def test_stub_skipped_step_demotes_to_partial(tmp_path: Path) -> None:
    """7 passed + 1 skipped + 0 failed sibling → PARTIAL (2), not PROCEED.

    This is the KEY value-add over the W267 sibling: catches the
    false-green case where codesign_check returns 0 (no .app installed)
    AND simultaneously pushes a record into SKIPPED, so the operator
    can read 'GO' without verifying signing.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(
        repo,
        _stub_body(
            passed=7, skipped=1, failed=0,
            skipped_lines=["  ⚠ 4/8 codesign (TARS.app not installed)"],
        ),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == PARTIAL, (
        f"expected rc={PARTIAL} PARTIAL, got rc={rc.returncode}\n{rc.stdout}"
    )
    assert "VERDICT: PARTIAL" in rc.stdout
    assert "skipped: 1" in rc.stdout
    assert "4/8 codesign" in rc.stdout, (
        "PARTIAL block must name the skipped step verbatim from sibling log"
    )
    assert "TARS.app not installed" in rc.stdout
    # PARTIAL block must explicitly warn against auto-running release.
    assert "Do NOT auto-run RELEASE-v10.0" in rc.stdout


# ── 8. Runtime: stub sibling — failure → BLOCK ──────────────────────


def test_stub_failure_exits_block_with_remediation(tmp_path: Path) -> None:
    """6 passed + 0 skipped + 2 failed sibling → BLOCK (1) with names."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(
        repo,
        _stub_body(
            passed=6, skipped=0, failed=2,
            failed_lines=["  ✗ 1/8 pytest", "  ✗ 7/8 json/yaml"],
            exit_rc=1,
        ),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == BLOCK, (
        f"expected rc={BLOCK} BLOCK, got rc={rc.returncode}\n{rc.stdout}"
    )
    assert "VERDICT: BLOCK" in rc.stdout
    assert "failed:  2" in rc.stdout
    assert "1/8 pytest" in rc.stdout, "BLOCK block must name failed steps verbatim"
    assert "7/8 json/yaml" in rc.stdout
    # Remediation pointers must be present.
    for pointer in (
        "1/8 pytest", "2/8 smoke", "3/8 perf", "4/8 codesign",
        "5/8 .command bash -n", "6/8 doc render",
        "7/8 json/yaml", "8/8 version consistency",
    ):
        assert pointer in rc.stdout, (
            f"BLOCK block missing remediation pointer for: {pointer}"
        )
    assert "Do NOT run RELEASE-v10.0" in rc.stdout


# ── 9. Runtime: worst-of-two — skipped AND failed → BLOCK ───────────


def test_failure_beats_skipped_for_verdict(tmp_path: Path) -> None:
    """Skipped AND failed → BLOCK (failure wins over partial)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(
        repo,
        _stub_body(passed=5, skipped=2, failed=1, exit_rc=1),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == BLOCK, (
        f"failure must beat skipped: expected rc={BLOCK}, got {rc.returncode}\n"
        f"{rc.stdout}"
    )


# ── 10. Runtime: custom gate_script + custom log override ───────────


def test_custom_gate_script_override(tmp_path: Path) -> None:
    """FINAL_QA_VERDICT_GATE_SCRIPT pointing elsewhere must be honored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    sibling = custom_dir / "MY-GATE.sh"
    sibling.write_text(
        _stub_body(passed=8, skipped=0, failed=0),
        encoding="utf-8",
    )
    sibling.chmod(0o755)
    rc = _run_wrapper(
        repo=repo,
        env_extras={"FINAL_QA_VERDICT_GATE_SCRIPT": str(sibling)},
    )
    assert rc.returncode == PROCEED, (
        f"custom gate script not honored: rc={rc.returncode}\n{rc.stdout}"
    )
    assert str(sibling) in rc.stdout, "wrapper banner must echo resolved gate script"


def test_custom_log_override(tmp_path: Path) -> None:
    """FINAL_QA_VERDICT_LOG pointing elsewhere must be honored.

    Important when sibling writes log to a non-default location (e.g. CI
    container with a separate workspace mount).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    # Sibling writes its log to a custom path; wrapper reads from there.
    custom_log = tmp_path / "elsewhere" / "QA.log"
    custom_log.parent.mkdir(parents=True)
    sibling_body = f"""#!/usr/bin/env bash
LOG="{custom_log}"
{{
  echo "=== FINAL-QA-GATE.command ==="
  echo "FINAL-QA-GATE — go/no-go report"
  echo "Passed:  8"
  echo "Skipped: 0"
  echo "Failed:  0"
  echo "=== GO ==="
}} | tee "${{LOG}}"
exit 0
"""
    _make_stub_sibling(repo, sibling_body)
    rc = _run_wrapper(
        repo=repo,
        env_extras={"FINAL_QA_VERDICT_LOG": str(custom_log)},
    )
    assert rc.returncode == PROCEED, (
        f"custom log override broke parsing: rc={rc.returncode}\n{rc.stdout}"
    )


# ── 11. Runtime: stale log between runs — wrapper reads LATEST block ─


def test_stale_log_reads_only_latest_block(tmp_path: Path) -> None:
    """Sibling appends across runs — wrapper must parse the LAST block only.

    Catches the regression where wrapper grabs an old PROCEED count
    from a stale earlier run and false-greens a current BLOCK run.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    log = repo / ".FINAL-QA-GATE.txt"

    # Simulate an old PROCEED run in the log.
    stale_block = """\
=== FINAL-QA-GATE.command at OLD-stamp ===
FINAL-QA-GATE — go/no-go report
Passed:  8
Skipped: 0
Failed:  0
=== GO ===
"""
    log.write_text(stale_block, encoding="utf-8")

    # Now lay a NEW sibling that fails — it appends to the same log.
    _make_stub_sibling(
        repo,
        _stub_body(passed=6, skipped=0, failed=2,
                   failed_lines=["  ✗ 1/8 pytest", "  ✗ 7/8 json/yaml"],
                   exit_rc=1),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == BLOCK, (
        f"wrapper read stale PROCEED block instead of fresh BLOCK: "
        f"rc={rc.returncode}\n{rc.stdout}"
    )
    assert "failed:  2" in rc.stdout


# ── 12. Verdict-block UX semantics ──────────────────────────────────


def test_proceed_block_lists_full_cookbook_chain(tmp_path: Path) -> None:
    """PROCEED block must enumerate the 8-step cookbook with PR refs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(repo, _stub_body(passed=8, skipped=0, failed=0))
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == PROCEED
    # Cross-reference the cookbook PRs the operator should run next.
    for label in (
        "GA-COOKBOOK.command (#218)",
        "RELEASE-TAG-GUARD.command (#221)",
        "DOWNLOAD-AND-VERIFY-RELEASE.command (#219)",
        "POST-INSTALL-SMOKE.command (#222)",
        "SOAK-REPORT.command (#214)",
        "BROTHER-POSTFLIGHT.command (#220)",
    ):
        assert label in rc.stdout, f"PROCEED block missing cookbook PR ref: {label}"


def test_block_pointers_back_reference_brief(tmp_path: Path) -> None:
    """BLOCK block must reference sibling W267 brief lines for traceability."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(
        repo, _stub_body(passed=0, skipped=0, failed=1, exit_rc=1),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == BLOCK
    assert "FINAL-QA-GATE.command header" in rc.stdout, (
        "BLOCK block must point operator at sibling header for fuller context"
    )


def test_partial_block_explains_all_skip_causes(tmp_path: Path) -> None:
    """PARTIAL block must enumerate the 4-ish skip causes for triage."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_stub_sibling(
        repo,
        _stub_body(passed=7, skipped=1, failed=0,
                   skipped_lines=["  ⚠ 4/8 codesign (TARS.app not installed)"]),
    )
    rc = _run_wrapper(repo=repo)
    assert rc.returncode == PARTIAL
    for cause in (
        "dry-run mode",
        "TARS.app not installed",
        "spctl unavailable",
        "non-macOS host",
        "sibling log missing",
    ):
        assert cause in rc.stdout, (
            f"PARTIAL block missing skip-cause explanation: {cause}"
        )


# ── 13. Banner sanity — echoes resolved paths ────────────────────────


def test_banner_echoes_resolved_paths(tmp_path: Path) -> None:
    """Wrapper banner must echo repo/gate/log paths for operator triage."""
    repo = tmp_path / "repo"
    repo.mkdir()
    rc = _run_wrapper(
        repo=repo,
        env_extras={"FINAL_QA_VERDICT_DRY_RUN": "1"},
    )
    assert str(repo) in rc.stdout, "banner must echo resolved repo"
    assert "scripts/FINAL-QA-GATE.command" in rc.stdout, (
        "banner must echo resolved sibling path"
    )
    assert ".FINAL-QA-GATE.txt" in rc.stdout, (
        "banner must echo resolved log path"
    )
