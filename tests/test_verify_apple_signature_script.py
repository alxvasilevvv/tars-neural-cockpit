"""Pin the contract of ``scripts/VERIFY-APPLE-SIGNATURE.command``.

We cannot exercise the real signing pipeline from pytest — that requires
a signed `.app` bundle on a Mac with the Apple developer keychain
unlocked. Instead we cover the parts that are deterministic and
mistake-prone:

1. Argument validation — missing arg / nonexistent path / non-.app
   non-.dmg target all exit non-zero with clear stderr.
2. Platform guard — on non-Darwin the script exits 2 immediately.
3. Static spec contract — header documents §6.2's three gates verbatim
   so the script and the brief never drift silently.
4. Structural sanity — script is executable, shebanged, passes ``bash -n``.

Mac-only behaviour (real `codesign`/`spctl`/`stapler` invocations,
`.dmg` auto-mount) is intentionally **not** asserted here — that's
covered by the operator's run on a clean machine per brief §6.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "VERIFY-APPLE-SIGNATURE.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "VERIFY-APPLE-SIGNATURE.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents §6.2 three gates verbatim ───────────────


def test_header_documents_three_gates_from_brief():
    body = SCRIPT.read_text(encoding="utf-8")
    # The brief §6.2 names the three commands by their canonical invocation.
    # The script header MUST reference each so future doc + script edits
    # don't drift apart silently.
    for required in (
        "codesign --verify --deep --strict",
        "spctl --assess --type execute",
        "stapler validate",
    ):
        assert required in body, (
            f"header missing brief §6.2 invocation: {required!r}"
        )


def test_header_documents_pass_signals_from_brief():
    body = SCRIPT.read_text(encoding="utf-8")
    # Pass-signal strings the script greps for to declare success;
    # also documented in the brief §6.2 expected output. Drift here
    # = false negatives on a real GA cut.
    for required in (
        "valid on disk",
        "satisfies its Designated Requirement",
        "source=Notarized Developer ID",
        "The validate action worked",
    ):
        assert required in body, (
            f"header missing brief §6.2 pass signal: {required!r}"
        )


def test_exit_code_contract_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    # The 0/1/2 contract is what the operator-facing release runbook
    # depends on. Pin it.
    assert "0  all three gates green" in body
    assert "1  one or more gates red" in body
    assert "2  prerequisite missing" in body


# ── runtime behaviour ───────────────────────────────────────────────────────


def _run(*args: str, env_extra=None) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="argument-validation path only meaningful on macOS",
)
def test_missing_argument_exits_two_with_usage():
    result = _run()
    assert result.returncode == 2
    assert "missing argument" in result.stderr.lower()
    assert "Usage" in result.stderr


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="path-validation only meaningful on macOS",
)
def test_nonexistent_target_exits_two(tmp_path: Path):
    result = _run(str(tmp_path / "does-not-exist.app"))
    assert result.returncode == 2
    assert "target not found" in result.stderr


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="extension-validation only meaningful on macOS",
)
def test_wrong_extension_exits(tmp_path: Path):
    # An existing but non-.app/non-.dmg target should be rejected at the
    # case-switch (exit 2) — we accept either 2 (prereq missing) or 1
    # (gate red) depending on whether codesign tries to evaluate it.
    target = tmp_path / "not-an-app.txt"
    target.write_text("hello")
    result = _run(str(target))
    assert result.returncode in (1, 2), (
        f"expected exit 1 or 2 for wrong extension, got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_platform_guard_on_non_darwin():
    # We cannot fake `uname -s` from inside the script via env, so this
    # case is only structurally asserted: the guard exists with exit 2.
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'if [ "$(uname -s)" != "Darwin" ]; then' in body
    # Followed quickly by exit 2.
    guard_section = body.split('if [ "$(uname -s)"', 1)[1].split("fi", 1)[0]
    assert "exit 2" in guard_section
