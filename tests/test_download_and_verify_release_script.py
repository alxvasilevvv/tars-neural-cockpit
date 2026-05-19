"""Pin the contract of ``scripts/DOWNLOAD-AND-VERIFY-RELEASE.command``.

Same pattern as ``test_preflight_apple_sign_script.py`` and
``test_ga_cookbook_script.py``: the real post-release verification
requires a live GH release with a signed-and-notarized ``.dmg``
attached, plus ``codesign``/``spctl``/``stapler`` (Xcode CLT, macOS
only) to actually verify it. We can't fake any of that convincingly
from pytest, and trying would just relitigate gh + Apple security
APIs.

What we CAN pin (and DO):

1. Meta — script exists, is executable, shebanged, passes ``bash -n``.
2. Spec contract — header documents the 7-step manual flow it
   collapses, the 0/1/2 exit code contract, the sibling helper
   (``VERIFY-APPLE-SIGNATURE.command``) it composes, and every env
   override knob. Brief + script can't drift silently.
3. Composition — the script invokes
   ``scripts/VERIFY-APPLE-SIGNATURE.command`` (PR #215). Exit 2 with a
   useful remediation pointer when that sibling is missing on disk
   (the path the wrapper takes if #215 hasn't landed yet).
4. Dry-run + all skips — with ``DOWNLOAD_VERIFY_DRY_RUN=1
   DOWNLOAD_VERIFY_SKIP_PLATFORM=1 DOWNLOAD_VERIFY_SKIP_TOOLS=1`` and
   a stub sibling on disk, the script runs end-to-end with no network
   or keychain access, exits 0, and emits the ``PROCEED`` verdict.
   This is what Linux CI exercises so the script doesn't bit-rot.
5. Platform guard structure — pin that the macOS guard exists, fires
   with ``exit 2`` on non-Darwin without the skip knob, and is
   bypassable for CI smoke only.

Mac-only behaviour (real ``gh release download`` against the live
v10.0.0 release, real ``codesign``/``spctl``/``stapler`` invocations)
is intentionally NOT asserted here — that's covered by the operator's
post-release run per the GA cookbook §6.3.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "DOWNLOAD-AND-VERIFY-RELEASE.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "DOWNLOAD-AND-VERIFY-RELEASE.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents the manual flow being collapsed ─────────


def test_header_documents_seven_step_manual_flow():
    """The 'why this exists' block must enumerate the 7-step manual
    chore the wrapper replaces, so future readers see at a glance
    what's being automated."""
    body = SCRIPT.read_text(encoding="utf-8")
    why_block = body.split("Why this exists", 1)[1].split("This wrapper", 1)[0]
    # Pin the 7 numbered steps verbatim — drift here means the brief
    # narrative is desyncing from what the wrapper actually replaces.
    for marker in (
        "1. ssh / walk to a clean Mac",
        "2. open https://github.com",
        "3. click the right",
        "4. wait for download",
        "5. drop it somewhere predictable",
        "6. open Terminal",
        "7. bash scripts/VERIFY-APPLE-SIGNATURE.command",
    ):
        assert marker in why_block, f"manual-flow step missing from header: {marker!r}"


def test_header_documents_wrapper_seven_step_collapse():
    """The 'which:' block must enumerate the 7 ops the wrapper
    performs in their place — symmetric to the manual flow."""
    body = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "Detects host arch",
        "Resolves owner/repo via `gh repo view",
        "Confirms the release exists",
        "Downloads the arch-matched",
        "Computes + prints the SHA-256",
        "Invokes the sibling `scripts/VERIFY-APPLE-SIGNATURE.command`",
        "Cleans up the tmp dir on success",
    ):
        assert marker in body, f"wrapper step missing from header: {marker!r}"


def test_header_documents_sibling_composition():
    """Hard-dep on PR #215 must be explicit so an operator on a clone
    where #215 hasn't landed sees a remediation pointer instead of a
    silent file-not-found."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "VERIFY-APPLE-SIGNATURE.command" in body
    assert "PR #215" in body, "header must name the hard-dep PR"
    assert "Fails safely, not silently" in body


def test_exit_code_contract_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    # 0 = green; 1 = sig red; 2 = prereq missing.
    assert "0  release found + asset downloaded + signature gates green" in body
    assert "1  signature verification failed" in body
    assert "2  prerequisite missing" in body


def test_env_overrides_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    for var in (
        "RELEASE_TAG",
        "GH_REPO",
        "RELEASE_ARCH",
        "DOWNLOAD_VERIFY_KEEP",
        "DOWNLOAD_VERIFY_DRY_RUN",
        "DOWNLOAD_VERIFY_REPO",
        "DOWNLOAD_VERIFY_NO_COLOR",
        "DOWNLOAD_VERIFY_TMP_DIR",
        "DOWNLOAD_VERIFY_SKIP_PLATFORM",
        "DOWNLOAD_VERIFY_SKIP_TOOLS",
    ):
        assert var in body, f"env override not documented in header: {var}"


def test_default_release_tag_matches_ga_target():
    """``RELEASE_TAG`` default must equal the canonical GA tag the
    rest of the W310 fleet aims at (v10.0.0). Drift here would mean
    the wrapper silently tries to verify the wrong release."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'RELEASE_TAG="${RELEASE_TAG:-v10.0.0}"' in body


# ── runtime behaviour ───────────────────────────────────────────────────────


def _run(
    *args: str, env_extra=None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    """Invoke the script with a sanitized env, optional overrides, and
    an optional working dir (useful when the test needs the script to
    pick up a stub VERIFY sibling in a temp tree)."""
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )


def _make_stub_sibling(tmp_path: Path) -> Path:
    """Build a minimal repo layout the wrapper will accept: a
    ``scripts/`` dir with a stub VERIFY-APPLE-SIGNATURE.command that
    just exits 0. Returns the repo root (the path you set as
    ``DOWNLOAD_VERIFY_REPO``)."""
    repo = tmp_path / "stub-repo"
    (repo / "scripts").mkdir(parents=True)
    sibling = repo / "scripts" / "VERIFY-APPLE-SIGNATURE.command"
    sibling.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            # Stub sibling for pytest. Real script lives in PR #215.
            echo "[stub VERIFY-APPLE-SIGNATURE called with: $*]"
            exit 0
            """
        ),
        encoding="utf-8",
    )
    sibling.chmod(0o755)
    return repo


# ---- composition: missing sibling → exit 2 with remediation ---------------


def test_missing_sibling_exits_two_with_pr215_pointer(tmp_path):
    """If ``scripts/VERIFY-APPLE-SIGNATURE.command`` isn't on disk,
    wrapper must exit 2 and point at PR #215 — not silently 404 or
    proceed without verification."""
    empty_repo = tmp_path / "no-sibling"
    (empty_repo / "scripts").mkdir(parents=True)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(empty_repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
        }
    )
    assert result.returncode == 2, (
        f"missing-sibling path must exit 2; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "sibling helper missing" in result.stdout
    assert "PR #215" in result.stdout


# ---- dry-run + all skips: end-to-end green smoke -------------------------


def test_dry_run_with_all_skips_and_stub_sibling_is_green(tmp_path):
    """Fully-mocked path that the Linux CI runner can exercise: stub
    the sibling on disk, skip the macOS platform guard, skip the
    gh+shasum tool presence check, and dry-run the download +
    verification. Must exit 0 with the ``PROCEED`` verdict."""
    repo = _make_stub_sibling(tmp_path)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
            "GH_REPO": "alxvasilevvv/tars-neural-cockpit",
        }
    )
    assert result.returncode == 0, (
        f"dry-run-with-all-skips should be green; got {result.returncode}\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "PROCEED" in result.stdout
    assert "dry-run; no real download or verify performed" in result.stdout
    assert "[dry-run] download skipped" in result.stdout
    assert (
        "[dry-run] would invoke: bash" in result.stdout
        and "VERIFY-APPLE-SIGNATURE.command" in result.stdout
    )


def test_dry_run_default_arch_is_uname_m_resolved(tmp_path):
    """Pin that arch is auto-resolved from ``uname -m`` (with the
    canonical ``arm64→aarch64`` mapping). The wrapper relies on this
    mapping to pick the right .dmg from the release."""
    repo = _make_stub_sibling(tmp_path)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
            "GH_REPO": "alxvasilevvv/tars-neural-cockpit",
        }
    )
    assert result.returncode == 0
    machine = platform.machine()
    expected = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64"}.get(machine)
    if expected:
        assert f"arch: {expected}" in result.stdout, (
            f"auto-arch mapping wrong for uname -m={machine!r}; "
            f"expected {expected!r} in stdout"
        )


def test_release_arch_override_wins_over_uname(tmp_path):
    """``RELEASE_ARCH=<x>`` must override uname-detected arch — gives
    the operator a way to pull an aarch64 .dmg on an Intel mac for
    forensics."""
    repo = _make_stub_sibling(tmp_path)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
            "GH_REPO": "alxvasilevvv/tars-neural-cockpit",
            "RELEASE_ARCH": "x86_64",
        }
    )
    assert result.returncode == 0
    assert "arch: x86_64" in result.stdout


def test_release_tag_override_propagates(tmp_path):
    """``RELEASE_TAG=v10.0.1`` must surface in both header banner and
    the assumed asset name during dry-run, so the operator can sanity-
    check they're aiming at the right tag before going live."""
    repo = _make_stub_sibling(tmp_path)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
            "GH_REPO": "alxvasilevvv/tars-neural-cockpit",
            "RELEASE_TAG": "v10.0.1",
        }
    )
    assert result.returncode == 0
    assert "tag v10.0.1" in result.stdout
    # In dry-run we synthesize asset name TARS_<ver>_<arch>.dmg
    assert re.search(r"\[dry-run\] asset assumed: TARS_10\.0\.1_\S+\.dmg", result.stdout)


# ---- platform guard ------------------------------------------------------


@pytest.mark.skipif(
    platform.system() == "Darwin",
    reason="non-Darwin guard only triggers off macOS",
)
def test_non_darwin_without_skip_exits_two(tmp_path):
    """On a Linux runner without the skip knob, the platform guard
    must fire BEFORE the wrapper touches gh / sibling / tmp dirs."""
    repo = _make_stub_sibling(tmp_path)
    result = _run(
        env_extra={
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_TOOLS": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
            # NOTE: NOT setting SKIP_PLATFORM.
        }
    )
    assert result.returncode == 2
    assert "must run on macOS" in result.stdout
    assert "DOWNLOAD_VERIFY_SKIP_PLATFORM=1 to bypass" in result.stdout


def test_platform_guard_structure_present():
    """Pin that the platform guard exists, fires with ``exit 2`` BEFORE
    any real work, and is gated on the documented skip knob — so a
    refactor can't accidentally drop the guard or change the exit code."""
    body = SCRIPT.read_text(encoding="utf-8")
    # The guard checks both the OS and the skip knob in one expression.
    guard_line = (
        'if [ "$(uname -s)" != "Darwin" ] && '
        '[ "${DOWNLOAD_VERIFY_SKIP_PLATFORM:-0}" != "1" ]; then'
    )
    assert guard_line in body, "platform guard structure drifted"
    # Extract the guard block line-by-line until the matching ``fi``
    # (substring splitting at "fi" would falsely cut at "verification"
    # in one of the note lines).
    lines = body.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == guard_line.strip())
    end = next(
        i for i in range(start + 1, len(lines)) if lines[i].strip() == "fi"
    )
    guard_section = "\n".join(lines[start + 1 : end])
    assert "exit 2" in guard_section, (
        f"platform-guard branch must exit 2 before any real work; "
        f"got:\n{guard_section}"
    )


# ---- tool dependency check -----------------------------------------------


def test_tool_dependency_loop_skippable():
    """Pin that the gh + shasum presence loop is gated on the
    ``DOWNLOAD_VERIFY_SKIP_TOOLS`` knob — Linux CI without gh can
    smoke the spec contract without installing it."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'if [ "${DOWNLOAD_VERIFY_SKIP_TOOLS:-0}" != "1" ]; then' in body
    assert "for tool in gh shasum; do" in body


@pytest.mark.skipif(
    shutil.which("gh") is not None,
    reason="this test requires gh to be ABSENT to exercise the missing-tool path",
)
def test_missing_gh_without_skip_tools_exits_two(tmp_path):
    """Without ``SKIP_TOOLS=1`` and ``gh`` not on PATH, wrapper must
    exit 2 with the GitHub-CLI remediation pointer."""
    repo = _make_stub_sibling(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/nonexistent",
            "DOWNLOAD_VERIFY_REPO": str(repo),
            "DOWNLOAD_VERIFY_SKIP_PLATFORM": "1",
            "DOWNLOAD_VERIFY_DRY_RUN": "1",
            "DOWNLOAD_VERIFY_NO_COLOR": "1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "missing required tool: gh" in result.stdout
    assert "brew install gh" in result.stdout


# ---- cleanup discipline ---------------------------------------------------


def test_cleanup_function_pins_keep_semantics():
    """``DOWNLOAD_VERIFY_KEEP=1`` must short-circuit cleanup — pin the
    structure so a refactor can't silently delete a downloaded .dmg
    the operator wanted to drag-install."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "cleanup() {" in body
    # Extract the cleanup() function body line-by-line until the closing
    # ``}`` at column 0. Substring splitting at "}" would falsely cut
    # at "${KEEP}" / "${TMP_DIR}" variable references.
    lines = body.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "cleanup() {")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].rstrip() == "}")
    cleanup_section = "\n".join(lines[start + 1 : end])
    assert 'if [ "${KEEP}" = "1" ]; then' in cleanup_section
    assert "leaving" in cleanup_section, (
        "cleanup KEEP branch must surface the retained path to the operator"
    )


def test_red_path_force_keeps_for_forensics():
    """On signature-verification RED (verifier rc=1), wrapper must
    force ``KEEP=1`` so the .dmg sticks around for forensics —
    otherwise rollback evidence vanishes with the trap."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Extract just the ``1)`` branch of the post-verify case statement,
    # line-by-line until its closing ``;;``. (substring splitting on
    # ``1)`` would falsely match anywhere a "1)" pair occurred earlier.)
    lines = body.splitlines()
    # Locate the case dispatch first.
    case_start = next(i for i, ln in enumerate(lines) if ln.strip() == "case \"${VERIFY_RC}\" in")
    # Find the "1)" arm within that case block.
    arm_start = next(
        i for i in range(case_start, len(lines)) if lines[i].strip() == "1)"
    )
    arm_end = next(
        i for i in range(arm_start + 1, len(lines)) if lines[i].strip() == ";;"
    )
    red_branch = "\n".join(lines[arm_start + 1 : arm_end])
    assert "KEEP=1" in red_branch, (
        "red-path branch must force-keep the .dmg for rollback forensics"
    )
    assert "exit 1" in red_branch
    assert "PR #199" in red_branch, "red verdict must point at rollback brief"
