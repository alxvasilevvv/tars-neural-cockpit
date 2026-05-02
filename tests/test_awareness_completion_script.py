"""Pin the contract of ``scripts/awareness-completion.bash``.

Companion to ``tests/test_planner_completion_script.py`` and
``tests/test_playbooks_completion_script.py``. We do not invoke
the bash completion machinery from pytest (that would require a
real subshell with the script sourced); instead we assert
structural properties of the file:

1. It exists, is executable, and starts with a `#!` shebang.
2. It enumerates every subcommand the CLI's ``_DISPATCH`` map
   actually supports (no drift between the script and the code).
3. It enumerates the flags each snapshot subcommand declares in
   ``_build_arg_parser`` so a freshly-added flag in the parser
   shows up in tab-completion next time someone updates the
   script.
4. It passes ``bash -n`` (parse-only).
5. **Two-level positional completion** for the ``snapshot``
   subcommand: positional 0 = pack slug (live query), positional
   1 = source id (live, scoped to the chosen pack).
6. The ``--quiet`` flag is invoked **before** the subcommand in
   the live query (the same bug that was fixed in PR #130 for
   the planner / playbooks scripts; pin so a future "consistency
   pass" doesn't accidentally re-introduce it).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMPLETION = REPO / "scripts" / "awareness-completion.bash"


@pytest.fixture(scope="module")
def script() -> str:
    return COMPLETION.read_text(encoding="utf-8")


def test_completion_script_exists_and_is_executable():
    assert COMPLETION.exists(), "scripts/awareness-completion.bash missing"
    mode = COMPLETION.stat().st_mode
    assert mode & 0o100, f"completion script is not executable (mode={oct(mode)})"
    with COMPLETION.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"missing shebang: {first!r}"


def test_completion_script_parses_with_bash_n():
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
    from backend.core.domains.awareness_cli import _DISPATCH

    m = re.search(r'_TARS_AWARENESS_CMDS="([^"]+)"', script)
    assert m, "_TARS_AWARENESS_CMDS variable not found in script"
    advertised = set(m.group(1).split())
    actual = set(_DISPATCH.keys())
    missing = actual - advertised
    extra = advertised - actual
    assert not missing, f"completion script missing subcommands: {sorted(missing)}"
    assert not extra, f"completion script lists unknown subcommands: {sorted(extra)}"


def test_completion_script_advertises_snapshot_flags(script: str):
    """Both snapshot subcommands accept the same trace-propagation
    flags (``--thread-id`` / ``--trace-id``). The script groups
    them under a single ``snapshot|snapshot-all)`` case branch
    (DRY); pin the combined branch so a future flag addition
    surfaces here, not as a silently-missing tab completion.
    """

    pattern = re.compile(
        r"(?ms)snapshot\|snapshot-all\)\s*\n\s*flags=\"([^\"]*)\""
    )
    m = pattern.search(script)
    assert m, (
        "combined case branch for ``snapshot|snapshot-all)`` not "
        "found in script"
    )
    advertised = set(m.group(1).split())
    expected = {"--thread-id", "--trace-id"}
    missing = expected - advertised
    assert not missing, (
        f"snapshot|snapshot-all flag table is missing: "
        f"{sorted(missing)}"
    )


def test_completion_script_handles_list_subcommand_with_no_flags(script: str):
    """The ``list`` subcommand has no per-subcommand flags (only
    inherits the global ``--quiet``). Pin the explicit empty
    case branch so a future "add --pack to list" parser change
    surfaces as a test failure instead of silently missing
    tab completion.
    """

    pattern = re.compile(
        r"(?ms)^\s*list\)\s*\n\s*flags=\"([^\"]*)\""
    )
    m = pattern.search(script)
    assert m, "case branch for 'list' not found in script"
    assert m.group(1).strip() == "", (
        "list subcommand should currently have no per-subcommand "
        "flags; if you added one to cli._build_arg_parser, update "
        "this test AND the script's case branch"
    )


def test_completion_script_caches_pack_slugs_and_sources_separately(script: str):
    """Two-level positional completion needs two caches (one for
    the catalogue of pack slugs, one keyed-by-slug for the
    per-pack source ids). Pin the variable pair so a future
    "simplify to one cache" change doesn't accidentally pollute
    pack B's source list with pack A's cached values.
    """

    assert "_TARS_AWARENESS_SLUGS_VAL" in script
    assert "_TARS_AWARENESS_SLUGS_EXP" in script
    assert "_TARS_AWARENESS_SOURCES_KEY" in script, (
        "the source cache must store the slug it was built for so "
        "completing slug A then slug B doesn't silently reuse A's data"
    )
    assert "_TARS_AWARENESS_SOURCES_VAL" in script
    assert "_TARS_AWARENESS_SOURCES_EXP" in script
    assert "now + 5" in script, (
        "5-second TTL mirrors planner / playbooks scripts; pin so the "
        "operator's mental model stays uniform"
    )


def test_completion_script_passes_quiet_before_subcommand(script: str):
    """``--quiet`` is the GLOBAL flag — it must come BEFORE the
    subcommand. The same bug landed in the planner + playbooks
    scripts and was fixed in PR #130; pin both invocations here
    so a future "consistency pass" doesn't re-introduce it.
    """

    # Both query helpers must invoke the CLI with --quiet first.
    pattern = re.compile(
        r"backend\.core\.domains\.awareness_cli --quiet (list|snapshot)"
    )
    matches = pattern.findall(script)
    assert len(matches) >= 2, (
        "both _slugs and _sources helpers must invoke "
        "``backend.core.domains.awareness_cli --quiet …`` "
        "(--quiet BEFORE the subcommand). Found: "
        f"{matches}"
    )

    # And explicitly NOT the wrong order (`list --quiet`).
    bad_pattern = re.compile(
        r"backend\.core\.domains\.awareness_cli list --quiet"
    )
    assert not bad_pattern.search(script), (
        "found the buggy ``list --quiet`` order — --quiet is global "
        "and must come BEFORE the subcommand (see PR #130)"
    )


def test_completion_script_implements_two_level_positional_for_snapshot(
    script: str,
):
    """``snapshot`` takes two positionals (``<slug> <source_id>``);
    the script must distinguish the first positional (live slug
    query) from the second (live source-id query, scoped to the
    chosen slug). Pin the gating logic so a future "simplify"
    doesn't collapse them and break the operator's tab-complete
    workflow.
    """

    # We pin the existence of the case branch that handles snapshot
    # with the per-positional-index split.
    snapshot_branch = re.search(
        r"(?ms)snapshot\)\s*\n.+?(?=^\s*esac|^\s*\w+\))",
        script,
    )
    assert snapshot_branch, "snapshot positional branch not found"
    body = snapshot_branch.group(0)
    assert "positional_idx -eq 0" in body, (
        "snapshot must check positional_idx == 0 for the first "
        "positional (slug)"
    )
    assert "positional_idx -eq 1" in body, (
        "snapshot must check positional_idx == 1 for the second "
        "positional (source_id)"
    )
    assert "_tars_awareness_sources" in body, (
        "snapshot's positional 1 must call _tars_awareness_sources "
        "with the already-typed slug to scope source-id completion"
    )


def test_completion_script_skips_flag_values_when_counting_positionals(
    script: str,
):
    """The positional counter walks ``COMP_WORDS`` left-to-right
    and must skip flag VALUES (e.g. when the user typed
    ``snapshot --thread-id thr_42 traders``, ``thr_42`` is not a
    positional). Pin the inner case statement that handles this
    so a future "simplify positional counting" doesn't silently
    miscount when --thread-id / --trace-id appear before the
    positionals.
    """

    # The script must inspect the flag word and skip the next
    # token when the flag takes a value.
    pattern = re.compile(
        r"--thread-id\|--trace-id\)\s*\n\s*\(\(i\+\+\)\)",
        re.MULTILINE,
    )
    assert pattern.search(script), (
        "positional counter must skip the value of --thread-id / "
        "--trace-id (advance the loop counter)"
    )
