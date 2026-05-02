"""Pin the contract of ``scripts/playbooks-completion.bash``.

Companion to ``tests/test_planner_completion_script.py``. We do
not invoke the bash completion machinery from pytest (that would
require a real subshell with the script sourced); instead we
assert structural properties of the file:

1. It exists, is executable, and starts with a `#!` shebang.
2. It enumerates every subcommand the CLI's ``_DISPATCH`` map
   actually supports (no drift between the script and the code).
3. It enumerates the flags each subcommand declares in
   ``_build_arg_parser`` so a freshly-added flag in the parser
   shows up in tab-completion next time someone updates the
   script.
4. It passes ``bash -n`` (parse-only) so a typo in the script
   never lands silently on disk.
5. ``--mode`` value completion lists the same three policy
   modes the CLI accepts.
6. ``--context-file`` triggers file-path completion (the
   canonical use case is a cron-baked sidecar JSON).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMPLETION = REPO / "scripts" / "playbooks-completion.bash"


@pytest.fixture(scope="module")
def script() -> str:
    return COMPLETION.read_text(encoding="utf-8")


def test_completion_script_exists_and_is_executable():
    assert COMPLETION.exists(), "scripts/playbooks-completion.bash missing"
    mode = COMPLETION.stat().st_mode
    assert mode & 0o100, f"completion script is not executable (mode={oct(mode)})"
    with COMPLETION.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_completion_script_parses_with_bash_n():
    """``bash -n`` parses without executing — the cheapest way to
    catch a syntax slip.
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
    from backend.core.playbooks.cli import _DISPATCH

    m = re.search(r'_TARS_PLAYBOOKS_CMDS="([^"]+)"', script)
    assert m, "_TARS_PLAYBOOKS_CMDS variable not found in script"
    advertised = set(m.group(1).split())
    actual = set(_DISPATCH.keys())
    missing = actual - advertised
    extra = advertised - actual
    assert not missing, f"completion script missing subcommands: {sorted(missing)}"
    assert not extra, f"completion script lists unknown subcommands: {sorted(extra)}"


@pytest.mark.parametrize(
    "subcommand,expected_flags",
    [
        ("list", {"--pack", "--refresh"}),
        ("show", {"--refresh"}),
        (
            "run",
            {
                "--mode",
                "--context",
                "--context-file",
                "--thread-id",
                "--trace-id",
            },
        ),
    ],
)
def test_completion_script_flags_per_subcommand(
    script: str, subcommand: str, expected_flags: set[str]
):
    """For each subcommand that takes flags, every flag the CLI's
    parser declares must be advertised in the script's case
    branch.
    """

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
    ``dry_run``). Pin so a future Policy mode addition surfaces
    here, not as a silently-missing tab completion.
    """

    assert "autopilot confirm dry_run" in script


def test_completion_script_uses_file_completion_for_context_file(script: str):
    """``--context-file`` is the canonical cron-friendly path: an
    operator running tab-completion on it should get filesystem
    paths, not free-form completion. Pin the ``compgen -f``
    invocation in the dedicated case branch so a future
    "simplification" doesn't accidentally collapse it into the
    free-form fallback.
    """

    # Allow any number of comment / whitespace lines between the
    # ``--context-file)`` label and the ``COMPREPLY=`` assignment
    # (the script keeps a multi-line comment explaining *why*
    # we use ``compgen -f``).
    pattern = re.compile(
        r"--context-file\)(?:\s|\n|#[^\n]*\n)*COMPREPLY=\(\s*\$\(compgen -f",
        re.MULTILINE,
    )
    assert pattern.search(script), (
        "--context-file case branch must use ``compgen -f`` for "
        "file-path completion"
    )


def test_completion_script_caches_playbook_ids(script: str):
    """Pin the 5-second cache contract: back-to-back tabs
    shouldn't re-shell into Python. The fixture is symmetric to
    the planner script (same 5s window, same cache_val /
    cache_exp variable pair), so a future "let's cache for 60s"
    or "drop the cache entirely" change ought to be deliberate
    and pin-test-driven.
    """

    assert "_TARS_PLAYBOOKS_CACHE_VAL" in script
    assert "_TARS_PLAYBOOKS_CACHE_EXP" in script
    assert "now + 5" in script, (
        "playbook-id cache TTL should be 5 seconds (mirrors the "
        "planner script)"
    )


def test_completion_script_completes_playbook_ids_only_for_id_taking_subcommands(
    script: str,
):
    """``show`` / ``run`` / ``validate`` take a single positional
    playbook_id; ``list``, ``validate-all``, ``reload`` do not.
    Pin the case statement that gates the live id lookup so a
    future "complete playbook ids everywhere" change doesn't
    silently shell out to Python on every tab inside
    ``validate-all``.
    """

    pattern = re.compile(
        r"case\s+\"\$sub\"\s+in\s*\n\s*show\|run\|validate\)",
        re.MULTILINE,
    )
    assert pattern.search(script), (
        "live playbook-id completion must be scoped to "
        "``show|run|validate`` only"
    )
