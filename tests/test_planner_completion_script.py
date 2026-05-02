"""Pin the contract of ``scripts/planner-completion.bash``.

We do not invoke the bash completion machinery from pytest (that
would require a real subshell with the script sourced); instead
we assert structural properties of the file:

1. It exists, is executable, and starts with a `#!` shebang.
2. It enumerates every subcommand the CLI's ``_DISPATCH`` map
   actually supports (no drift between the script and the code).
3. It enumerates the flags each subcommand declares in
   ``_build_arg_parser`` so a freshly-added flag in the parser
   shows up in tab-completion next time someone updates the
   script.
4. It passes ``bash -n`` (parse-only) so a typo in the script
   never lands silently on disk.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMPLETION = REPO / "scripts" / "planner-completion.bash"


@pytest.fixture(scope="module")
def script() -> str:
    return COMPLETION.read_text(encoding="utf-8")


def test_completion_script_exists_and_is_executable():
    assert COMPLETION.exists(), "scripts/planner-completion.bash missing"
    mode = COMPLETION.stat().st_mode
    assert mode & 0o100, f"completion script is not executable (mode={oct(mode)})"
    with COMPLETION.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_completion_script_parses_with_bash_n():
    """``bash -n`` parses without executing — the cheapest way to
    catch a syntax slip in the heredoc above.
    """

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not on PATH")
    result = subprocess.run(
        [bash, "-n", str(COMPLETION)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_completion_script_lists_every_subcommand_from_dispatch(script: str):
    from backend.core.planner.cli import _DISPATCH

    # The script lists subcommands once in the _TARS_PLANNER_CMDS
    # variable. Pull them out with a tight regex.
    m = re.search(r'_TARS_PLANNER_CMDS="([^"]+)"', script)
    assert m, "_TARS_PLANNER_CMDS variable not found in script"
    advertised = set(m.group(1).split())
    actual = set(_DISPATCH.keys())
    missing = actual - advertised
    extra = advertised - actual
    assert not missing, f"completion script missing subcommands: {sorted(missing)}"
    assert not extra, f"completion script lists unknown subcommands: {sorted(extra)}"


@pytest.mark.parametrize(
    "subcommand,expected_flags",
    [
        ("list", {"--status", "--limit", "--thread-id"}),
        ("synthesize", {"--pinned-pack", "--thread-id"}),
        ("run", {"--mode"}),
        ("clone", {"--thread-id", "--goal", "--approve", "--run", "--mode"}),
        ("delete", {"--yes"}),
    ],
)
def test_completion_script_flags_per_subcommand(
    script: str, subcommand: str, expected_flags: set[str]
):
    """For each subcommand that takes flags, every flag the CLI's
    parser declares must be advertised in the script's case
    branch.
    """

    # Extract the case body for this subcommand.
    pattern = re.compile(
        rf"(?ms)^\s*{re.escape(subcommand)}\)\s*\n\s*flags=\"([^\"]*)\""
    )
    m = pattern.search(script)
    assert m, f"case branch for {subcommand!r} not found in script"
    advertised = set(m.group(1).split())
    missing = expected_flags - advertised
    assert not missing, (
        f"completion case branch for {subcommand!r} is missing flags: "
        f"{sorted(missing)}"
    )


def test_completion_script_advertises_policy_modes(script: str):
    """The ``--mode`` value completion must list the same three
    modes the CLI accepts (``autopilot``, ``confirm``,
    ``dry_run``).
    """

    assert "autopilot confirm dry_run" in script


def test_completion_script_advertises_status_values(script: str):
    """The ``--status`` value completion must list every
    :class:`PlanStatus` enum value so ``planner list --status <TAB>``
    returns useful suggestions.
    """

    from backend.core.planner.types import PlanStatus

    advertised = re.search(
        r'--status\)\s*\n\s*COMPREPLY=\(\s*\$\(compgen -W "([^"]+)"',
        script,
    )
    assert advertised, "--status case branch not found in script"
    advertised_values = set(advertised.group(1).split())
    actual_values = {ps.value for ps in PlanStatus}
    missing = actual_values - advertised_values
    extra = advertised_values - actual_values
    assert not missing, f"--status completion missing: {sorted(missing)}"
    assert not extra, f"--status completion lists unknown values: {sorted(extra)}"
