"""Pin the contract of ``scripts/RELEASE-TAG-GUARD.command``.

Same pattern as ``test_brother_postflight_script.py`` /
``test_brother_preflight_script.py`` / ``test_ga_cookbook_script.py``:
real tag-cut gating requires a 72-hour soak window's worth of hourly
JSON records, live GitHub Actions, real network access to the origin
remote, and a clean main branch in a checkout that we don't have to
fake. We can't reproduce any of that convincingly from pytest, and
trying would relitigate gh + git + SOAK-REPORT contracts.

What we CAN pin (and DO):

1. Meta — script exists, is executable, shebanged, passes ``bash -n``.
2. Spec contract — header documents the 5 gates verbatim, the 0/1/2
   exit code contract, the "wrapper does NOT push the tag itself"
   destructively-harmless framing, the hard deps, the 4 known
   SOAK-REPORT verdict signatures, and every env override knob.
3. Gate count = 5 — pinned via a structural assertion on the
   ``hdr "Gate N — …"`` lines.
4. Dry-run + stub-repo paths — multiple matrix variants pinned with
   deterministic exit codes:
     a) no soak report file → BLOCK rc=1
     b) soak report = AUTHORISED + clean repo on main + no tag + gh
        skipped → PARTIAL rc=2
     c) soak report = AUTHORISED + dirty tree → BLOCK rc=1
     d) soak report = AUTHORISED + wrong branch → BLOCK rc=1
     e) soak report = AUTHORISED + tag already exists locally → BLOCK
        rc=1
     f) soak report = BLOCKED (incomplete window) → BLOCK rc=1
     g) soak report = BLOCKED (hard-fail) → BLOCK rc=1
     h) soak report = unrecognised → BLOCK rc=1
5. PROCEED next-steps contract — when all gates green, the verdict
   must print the exact ``bash scripts/RELEASE-v10.0.command`` line
   for operator copy-paste, AND must remind the operator about the
   downstream Gate B (#219) + Postflight (#220) steps.
6. Destructively-harmless invariant — the script must NOT contain any
   ``git tag`` / ``git push`` invocation in its runtime body. Silent-
   drift guard against a future refactor that accidentally promotes
   this wrapper from "verify" to "execute".

Mac-only / live-infra behaviour (real ``gh run list`` against a real
v10 SHA + real ``git ls-remote origin`` round-trips) is intentionally
NOT asserted here — that's covered by the operator's pre-tag run per
the W310-l brief §4.7.

The script's verdict mapping for the tag-cut context:
- 0 = all 5 gates green → safe to tag v10.0.0; next is RELEASE-v10.0
- 1 = ≥1 gate red → DO NOT TAG; fix gate + re-run
- 2 = prereq missing (no gh) OR dry-run → defer tag decision
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "RELEASE-TAG-GUARD.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "RELEASE-TAG-GUARD.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents the W310-ak position ───────────────────


def test_header_names_eighth_implementer_follow_up():
    """Brief and script can't drift on the wave-position marker."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "W310-ak" in body, "wave-id missing from header"
    assert "EIGHTH" in body or "eighth" in body, (
        "8th-implementer-follow-up marker missing from header"
    )


def test_header_documents_all_5_gates_verbatim():
    body = SCRIPT.read_text(encoding="utf-8")
    # The header's "What this script does" section enumerates each gate
    # by name so the operator + reviewer have a single source of truth.
    for anchor in [
        "Gate 1 — SOAK-REPORT verdict",
        "Gate 2 — git HEAD on `main`",
        "Gate 3 — working tree clean",
        "Gate 4 — tag does NOT already",  # line wraps to "exist"
        "Gate 5 — last CI run on main",   # line wraps to "HEAD is `success`"
    ]:
        assert anchor in body, f"gate anchor missing from header: {anchor!r}"


def test_header_documents_exit_contract():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "0  PROCEED" in body, "exit 0 contract not documented"
    assert "1  BLOCK" in body, "exit 1 contract not documented"
    assert "2  PARTIAL" in body, "exit 2 contract not documented"


def test_header_documents_destructively_harmless_framing():
    """The whole point of this wrapper is that it does NOT push.
    Header MUST make that crystal clear so no future refactor "improves"
    it into an executor."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "destructively HARMLESS" in body or "destructively harmless" in body, (
        "destructively-harmless framing missing"
    )
    # Header should explicitly name the three things the wrapper does
    # NOT do:
    assert "does NOT push" in body or "does not push" in body, (
        "missing 'does NOT push a tag' invariant in header"
    )
    assert "does NOT call RELEASE-v10.0" in body or "does NOT modify git state" in body, (
        "missing 'does NOT call RELEASE-v10.0' OR 'does NOT modify git state' invariant"
    )


def test_header_documents_all_4_soak_verdict_signatures():
    body = SCRIPT.read_text(encoding="utf-8")
    # The 4 signatures emitted by SOAK-REPORT.command that we recognise.
    # Use anchor tokens (not full strings) so header line-wrapping
    # doesn't break the spec contract.
    for sig in [
        "GA tag **authorised**",
        "GA tag **blocked**",     # covers both "— only" and "— hard-fail"
        "hard-fail",              # specifically anchors the hard-fail variant
        "Go / no-go: blocked",    # covers the no-data variant
        "(no data)",
    ]:
        assert sig in body, f"soak verdict signature missing from header: {sig!r}"


def test_header_documents_all_env_knobs():
    body = SCRIPT.read_text(encoding="utf-8")
    for knob in [
        "TAG_GUARD_DRY_RUN",
        "TAG_GUARD_SKIP_GH",
        "TAG_GUARD_REPO",
        "TARS_TAG_GUARD_REPORT",
        "TAG_GUARD_TAG",
        "TAG_GUARD_BRANCH",
        "TAG_GUARD_NO_COLOR",
    ]:
        assert knob in body, f"env knob missing from header: {knob}"


def test_header_back_references_sibling_wrappers():
    body = SCRIPT.read_text(encoding="utf-8")
    # The wrapper is symmetric with #218, #219, #220 — header should say so.
    for ref in ["#218", "#219", "#220"]:
        assert ref in body, f"missing back-reference to sibling wrapper PR {ref}"


# ── structural: exactly 5 gates in the runtime body ────────────────────────


def test_runtime_has_exactly_5_gate_headers():
    body = SCRIPT.read_text(encoding="utf-8")
    # The runtime uses `hdr "Gate N — ..."` to print each gate header.
    # Count those specifically (not the comment-section enumeration).
    gate_headers = re.findall(r'^\s*hdr "Gate \d', body, flags=re.MULTILINE)
    assert len(gate_headers) == 5, (
        f"expected exactly 5 runtime gate headers, found {len(gate_headers)}: "
        f"{gate_headers}"
    )


# ── destructively-harmless invariant: no git tag / git push in runtime ──────


def test_runtime_does_not_call_git_tag():
    """Silent-drift guard: if a future PR adds `git tag` to this script,
    the script stops being a verification gate and starts being an
    executor. That's the wrong wrapper. Different concern; needs its
    own PR with its own confirm semantics."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Split off the header docstring/comments — only inspect the runtime
    # body (everything from `set -u` onwards).
    runtime_start = body.find("set -u")
    assert runtime_start > 0, "could not locate runtime section"
    runtime = body[runtime_start:]
    # Allowed READ-ONLY git tag invocations: `git tag -d` (in a comment
    # only — should not appear in actual bash code), `git rev-parse
    # --verify --quiet refs/tags/`. We forbid the CREATION patterns:
    # `git tag v...`, `git tag -s v...`, `git tag -a v...`.
    for forbidden in [
        re.compile(r'^\s*git tag\s+(-[sa]\s+)?["\']?v\d', re.MULTILINE),
        re.compile(r'^\s*git push\s+(--delete\s+)?origin\s+["\']?v\d', re.MULTILINE),
    ]:
        match = forbidden.search(runtime)
        assert match is None, (
            f"runtime body contains forbidden tag-mutation: {match.group(0)!r} "
            f"— this wrapper must stay read-only"
        )


def test_runtime_uses_ls_remote_not_fetch():
    """Gate 4 must check remote tag existence via the READ-ONLY
    `git ls-remote` — NOT `git fetch --tags`, which mutates local
    refs. Pin so we don't drift."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "git ls-remote --tags origin" in body, (
        "Gate 4 must use `git ls-remote --tags origin` (read-only)"
    )
    runtime_start = body.find("set -u")
    runtime = body[runtime_start:]
    assert "git fetch" not in runtime, (
        "runtime must NOT call `git fetch` — that mutates local refs"
    )


# ── stub-repo runtime helpers ──────────────────────────────────────────────


def _make_stub_repo(tmp_path: Path, *, init_git: bool = True) -> Path:
    """Create a minimal stub repo with the script copied in.

    By default initialises a real git repo on a `main` branch with one
    commit so `git symbolic-ref --short HEAD` returns `main` and
    `git status --porcelain` is empty.
    """
    repo = tmp_path / "stub_repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / "scripts" / "RELEASE-TAG-GUARD.command").write_text(
        SCRIPT.read_text(encoding="utf-8")
    )
    (repo / "scripts" / "RELEASE-TAG-GUARD.command").chmod(0o755)

    if init_git:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test",
        }
        subprocess.run(
            ["git", "init", "-b", "main", "."],
            cwd=repo,
            env=env,
            check=True,
            capture_output=True,
        )
        # Create one commit so HEAD resolves.
        (repo / "README.md").write_text("stub\n")
        subprocess.run(["git", "add", "."], cwd=repo, env=env, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "stub"],
            cwd=repo,
            env=env,
            check=True,
            capture_output=True,
        )
    return repo


def _write_soak_report(repo: Path, verdict_kind: str) -> Path:
    """Write a minimal SOAK-REPORT markdown matching one of the 4
    known signatures."""
    qa_dir = repo / "docs" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    report = qa_dir / "SOAK_v10.0.0.md"

    if verdict_kind == "authorised":
        report.write_text(
            "# Soak Report — v10.0.0\n\n"
            "## 1. Verdict\n\n"
            "GA tag **authorised** — proceed to `scripts/RELEASE-v10.0.command`.\n"
        )
    elif verdict_kind == "blocked_incomplete":
        report.write_text(
            "# Soak Report — v10.0.0\n\n"
            "## 1. Verdict\n\n"
            "GA tag **blocked** — only 24/72 hourly samples recorded. Wait for full window.\n"
        )
    elif verdict_kind == "blocked_hardfail":
        report.write_text(
            "# Soak Report — v10.0.0\n\n"
            "## 1. Verdict\n\n"
            "GA tag **blocked** — hard-fail criterion hit (see thresholds table below). Restart soak from T-0 after fix.\n"
        )
    elif verdict_kind == "no_data":
        report.write_text(
            "# Soak Report — v10.0.0\n\n"
            "> **No hourly records found** at `.soak/hourly.log`.\n\n"
            "**Go / no-go: blocked (no data).**\n"
        )
    elif verdict_kind == "unrecognised":
        report.write_text(
            "# Soak Report — v10.0.0\n\n"
            "## 1. Verdict\n\n"
            "Some hand-edited text that doesn't match any known signature.\n"
        )
    else:
        raise ValueError(f"unknown verdict_kind: {verdict_kind}")

    # Commit so the stub repo's working tree stays clean by default.
    # Tests that want to assert "dirty tree" behaviour will add a NEW
    # untracked file AFTER calling this helper.
    if (repo / ".git").exists():
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test",
        }
        subprocess.run(
            ["git", "add", "docs"],
            cwd=repo, env=env, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "stub: soak report"],
            cwd=repo, env=env, check=True, capture_output=True,
        )
    return report


def _run(repo: Path, **env_overrides: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "TAG_GUARD_REPO": str(repo),
        # By default skip gh (we don't have an authenticated gh in CI).
        "TAG_GUARD_SKIP_GH": "1",
        # NO_COLOR for deterministic stdout matching.
        "TAG_GUARD_NO_COLOR": "1",
    }
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(repo / "scripts" / "RELEASE-TAG-GUARD.command")],
        env=env,
        capture_output=True,
        text=True,
        cwd=repo,
        timeout=30,
    )


# ── runtime: gate 1 (verdict) variants ─────────────────────────────────────


def test_runtime_no_soak_report_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    # No soak report on disk.
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK with no report, got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "soak report not found" in result.stdout
    assert "BLOCK" in result.stdout


def test_runtime_authorised_clean_repo_gh_skipped_returns_partial(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    result = _run(repo)
    # gh skipped → Gate 5 amber → rc=2 PARTIAL, NOT rc=1 BLOCK
    assert result.returncode == 2, (
        f"expected rc=2 PARTIAL (gh skipped), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "soak verdict = AUTHORISED" in result.stdout
    assert "PARTIAL" in result.stdout


def test_runtime_authorised_dirty_tree_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    # Make the tree dirty.
    (repo / "dirty.txt").write_text("uncommitted\n")
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (dirty tree), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "uncommitted changes" in result.stdout
    assert "stash" in result.stdout


def test_runtime_authorised_wrong_branch_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    # Switch to a feature branch.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test",
    }
    subprocess.run(
        ["git", "checkout", "-b", "feature/foo"],
        cwd=repo, env=env, check=True, capture_output=True,
    )
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (wrong branch), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "feature/foo" in result.stdout
    assert "checkout main" in result.stdout


def test_runtime_authorised_tag_already_exists_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test",
    }
    subprocess.run(
        ["git", "tag", "v10.0.0"],
        cwd=repo, env=env, check=True, capture_output=True,
    )
    result = _run(repo, TAG_GUARD_DRY_RUN="1")
    # With DRY_RUN=1, remote check is skipped, so only local existence
    # triggers the BLOCK.
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (tag exists locally), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "already exists" in result.stdout
    assert "git tag -d v10.0.0" in result.stdout


def test_runtime_blocked_incomplete_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "blocked_incomplete")
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (incomplete window), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "INCOMPLETE WINDOW" in result.stdout
    assert "72 samples accumulate" in result.stdout


def test_runtime_blocked_hardfail_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "blocked_hardfail")
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (hard-fail), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "HARD-FAIL CRITERION HIT" in result.stdout
    assert "cursor/soak-v10-fix" in result.stdout


def test_runtime_no_data_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "no_data")
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (no data), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "NO DATA" in result.stdout
    assert "SOAK-HOURLY" in result.stdout


def test_runtime_unrecognised_verdict_returns_block(tmp_path):
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "unrecognised")
    result = _run(repo)
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (unrecognised verdict), got rc={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "UNRECOGNISED" in result.stdout
    assert "re-render" in result.stdout.lower()


# ── runtime: PROCEED path semantics ─────────────────────────────────────────


def test_runtime_all_green_path_prints_release_v10_next_command(tmp_path):
    """When all 5 gates are green, the PROCEED block must name
    `bash scripts/RELEASE-v10.0.command` verbatim for operator
    copy-paste.

    We force the all-green path by combining: AUTHORISED verdict,
    clean tree on main, no v10.0.0 tag, AND TAG_GUARD_DRY_RUN=1 which
    causes Gate 5 to be stubbed-green-as-amber. But amber alone gives
    rc=2 PARTIAL. To actually reach the PROCEED block we need
    TAG_GUARD_DRY_RUN=0 with gh present. Since CI may not have gh, we
    instead pin the PROCEED-block CONTENT by inspecting the source:
    if the verdict-print block contains the right strings, the
    operator-visible behaviour is correct.
    """
    body = SCRIPT.read_text(encoding="utf-8")
    # Find the PROCEED block (between "PROCEED (rc=0)" and "exit 0").
    proceed_start = body.find("PROCEED (rc=0)")
    proceed_end = body.find("exit 0", proceed_start)
    assert proceed_start > 0 and proceed_end > proceed_start, (
        "could not locate PROCEED block in script"
    )
    proceed_block = body[proceed_start:proceed_end]
    # Must print the exact next command.
    assert "bash scripts/RELEASE-v10.0.command" in proceed_block, (
        "PROCEED block must print the exact RELEASE-v10.0 invocation "
        "for operator copy-paste"
    )
    # Must remind operator about Gate B (#219) downstream.
    assert "DOWNLOAD-AND-VERIFY-RELEASE" in proceed_block, (
        "PROCEED block must remind operator about downstream Gate B "
        "(DOWNLOAD-AND-VERIFY-RELEASE)"
    )
    # Must remind operator about Postflight (#220) at T+24h.
    assert "BROTHER-POSTFLIGHT" in proceed_block, (
        "PROCEED block must remind operator about Postflight at T+24h"
    )


def test_runtime_block_path_explicitly_warns_against_release_v10(tmp_path):
    """When ANY gate is red, the BLOCK block must say 'do NOT run
    RELEASE-v10.0.command yet' so the operator can't accidentally
    barrel through."""
    repo = _make_stub_repo(tmp_path)
    # No report → guaranteed BLOCK on Gate 1.
    result = _run(repo)
    assert result.returncode == 1
    assert "do NOT run RELEASE-v10.0.command yet" in result.stdout, (
        "BLOCK block must explicitly tell operator NOT to run RELEASE-v10.0"
    )


# ── runtime: PARTIAL path semantics ────────────────────────────────────────


def test_runtime_partial_explicitly_says_do_not_tag(tmp_path):
    """When gh is skipped (PARTIAL), the verdict must still warn
    against auto-running RELEASE-v10.0 — yellow != green."""
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    result = _run(repo)  # TAG_GUARD_SKIP_GH=1 set by default in _run
    assert result.returncode == 2
    assert "PARTIAL" in result.stdout
    assert "do NOT auto-run RELEASE-v10.0" in result.stdout, (
        "PARTIAL block must explicitly warn against auto-running RELEASE-v10.0"
    )


# ── runtime: custom tag override (re-usability for v10.0.1 etc.) ───────────


def test_runtime_custom_tag_name_routes_through_gate_4(tmp_path):
    """The TAG_GUARD_TAG override must propagate to Gate 4: a tag
    named "v10.0.1" already existing must trigger the BLOCK with the
    custom name (not the default v10.0.0)."""
    repo = _make_stub_repo(tmp_path)
    _write_soak_report(repo, "authorised")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test",
    }
    subprocess.run(
        ["git", "tag", "v10.0.1"],
        cwd=repo, env=env, check=True, capture_output=True,
    )
    result = _run(repo, TAG_GUARD_TAG="v10.0.1", TAG_GUARD_DRY_RUN="1")
    assert result.returncode == 1, (
        f"expected rc=1 BLOCK (custom tag v10.0.1 exists), got rc={result.returncode}\n"
        f"stdout: {result.stdout}"
    )
    assert "v10.0.1" in result.stdout, (
        "custom tag name must appear in verdict output"
    )
