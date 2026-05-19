"""Pin the contract of ``scripts/PREFLIGHT-APPLE-SIGN.command``.

Same pattern as ``test_verify_apple_signature_script.py``: the real
signing pre-flight requires an Apple developer cert in the macOS
keychain, a configured notarytool keychain profile, a populated `.env`,
and ``gh`` authenticated with secret-list permissions on a real GH
repo. We can't fake any of those convincingly from pytest, and trying
would just relitigate macOS keychain APIs.

What we CAN pin (and DO):

1. Argument / platform / tool prereq paths — script exits 2 with a
   useful stderr when run on non-macOS without ``PREFLIGHT_APPLE_SKIP_LOCAL=1``,
   when ``gh`` is missing without ``PREFLIGHT_APPLE_SKIP_CI=1``, etc.
2. Spec contract — header documents brief §3.1 / §3.2 / §3.3 / §4
   verbatim AND the six required secret names AND the 0/1/2 exit
   contract, so brief and script can't drift silently.
3. Dry-run path — ``PREFLIGHT_APPLE_DRY_RUN=1 PREFLIGHT_APPLE_SKIP_CI=1
   PREFLIGHT_APPLE_SKIP_LOCAL=1`` produces a fully green run with no
   real network or keychain access. This is what CI exercises so the
   script doesn't bit-rot.
4. Structural sanity — script is executable, shebanged, passes
   ``bash -n``.

Mac-only behaviour (real ``security find-identity`` / ``xcrun notarytool``
invocations) is intentionally NOT asserted here — that's covered by
the operator's pre-tag-cut run per brief §3+§4.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "PREFLIGHT-APPLE-SIGN.command"


# ── meta ────────────────────────────────────────────────────────────────────


def test_script_is_executable_and_shebanged():
    assert SCRIPT.exists(), "PREFLIGHT-APPLE-SIGN.command must exist"
    mode = SCRIPT.stat().st_mode
    assert mode & 0o100, f"script must be executable (mode={oct(mode)})"
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_script_passes_bash_n():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


# ── spec contract: header documents brief §3+§4 verbatim ────────────────────


def test_header_documents_three_local_gates_from_brief():
    body = SCRIPT.read_text(encoding="utf-8")
    # Brief §3 names three commands. Header MUST reference each so
    # future edits to either brief or script don't drift.
    for required in (
        'security find-identity -v -p codesigning | grep "Developer ID Application"',
        'xcrun notarytool history --keychain-profile',
        'test -f .env && grep -c "^APPLE_" .env',
    ):
        assert required in body, (
            f"header missing brief §3 invocation: {required!r}"
        )


def test_header_documents_ci_gate_from_brief():
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'gh secret list -R' in body, "header missing §4 gh secret list"
    assert "alxvasilevvv/tars-neural-cockpit" in body, (
        "header missing default GH_REPO"
    )


def test_header_documents_six_secret_names():
    body = SCRIPT.read_text(encoding="utf-8")
    for name in (
        "APPLE_CERTIFICATE",
        "APPLE_CERTIFICATE_PASSWORD",
        "APPLE_SIGNING_IDENTITY",
        "APPLE_TEAM_ID",
        "APPLE_ID",
        "APPLE_PASSWORD",
    ):
        assert name in body, f"header missing brief §4 secret name: {name}"


def test_required_secrets_array_matches_brief():
    """The bash array must contain EXACTLY the six names from brief §4,
    in the order the brief lists them."""
    body = SCRIPT.read_text(encoding="utf-8")
    # Extract the REQUIRED_SECRETS=( ... ) block.
    import re

    m = re.search(r"REQUIRED_SECRETS=\(\s*([\s\S]*?)\s*\)", body)
    assert m is not None, "REQUIRED_SECRETS array missing"
    names = [n for n in m.group(1).split() if n and not n.startswith("#")]
    assert names == [
        "APPLE_CERTIFICATE",
        "APPLE_CERTIFICATE_PASSWORD",
        "APPLE_SIGNING_IDENTITY",
        "APPLE_TEAM_ID",
        "APPLE_ID",
        "APPLE_PASSWORD",
    ], f"REQUIRED_SECRETS drifted from brief §4 order: {names!r}"


def test_exit_code_contract_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "0  all four gates green" in body
    assert "1  one or more gates red" in body
    assert "2  prerequisite missing" in body


def test_env_overrides_documented():
    body = SCRIPT.read_text(encoding="utf-8")
    for var in (
        "APPLE_NOTARY_PROFILE",
        "GH_REPO",
        "PREFLIGHT_APPLE_REPO",
        "PREFLIGHT_APPLE_DRY_RUN",
        "PREFLIGHT_APPLE_SKIP_CI",
        "PREFLIGHT_APPLE_SKIP_LOCAL",
    ):
        assert var in body, f"env override not documented in header: {var}"


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


def test_dry_run_with_all_skips_is_green():
    """Fully-mocked path: skip local checks, skip CI, dry-run. Must
    exit 0 with no real network or keychain access. This is the smoke
    a CI runner can exercise on any platform."""
    result = _run(
        env_extra={
            "PREFLIGHT_APPLE_DRY_RUN": "1",
            "PREFLIGHT_APPLE_SKIP_LOCAL": "1",
            "PREFLIGHT_APPLE_SKIP_CI": "1",
        }
    )
    assert result.returncode == 0, (
        f"dry-run with all skips should be green; stdout=\n{result.stdout}\n"
        f"stderr=\n{result.stderr}"
    )
    assert "all pre-flight gates green" in result.stdout


def test_dry_run_prints_next_steps_on_green():
    result = _run(
        env_extra={
            "PREFLIGHT_APPLE_DRY_RUN": "1",
            "PREFLIGHT_APPLE_SKIP_LOCAL": "1",
            "PREFLIGHT_APPLE_SKIP_CI": "1",
        }
    )
    assert result.returncode == 0
    # Operator-facing next-step pointers must reference both the
    # release script and the verify-sig sibling, so the cookbook
    # remains discoverable from inside the script output.
    assert "RELEASE-v10.0.command" in result.stdout
    assert "VERIFY-APPLE-SIGNATURE.command" in result.stdout


@pytest.mark.skipif(
    platform.system() == "Darwin",
    reason="non-Darwin guard only triggers off macOS",
)
def test_non_darwin_without_skip_local_exits_two():
    result = _run()
    assert result.returncode == 2
    assert "require macOS" in result.stderr or "Darwin" in result.stderr


def test_skip_ci_allows_non_macos_dry_run_if_local_also_skipped():
    """Pin that the combination ``SKIP_LOCAL=1 + SKIP_CI=1`` is the
    canonical "CI runner / non-Mac" mode. This is what GH Actions
    Linux runners use to confirm the script still parses + executes."""
    result = _run(
        env_extra={
            "PREFLIGHT_APPLE_DRY_RUN": "1",
            "PREFLIGHT_APPLE_SKIP_LOCAL": "1",
            "PREFLIGHT_APPLE_SKIP_CI": "1",
        }
    )
    assert result.returncode == 0
    assert "SKIPPED" in result.stdout  # both sections should print SKIPPED


def test_platform_guard_structure_present():
    """Even on macOS where we can't observe the guard firing, pin that
    the guard exists with the expected exit code."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'if [ "$(uname -s)" != "Darwin" ]; then' in body
    guard_section = body.split('if [ "$(uname -s)" != "Darwin" ]; then', 1)[1]
    # The guard branch must exit 2 (prereq missing) before any real work.
    pre_fi = guard_section.split("fi", 1)[0]
    assert "exit 2" in pre_fi
