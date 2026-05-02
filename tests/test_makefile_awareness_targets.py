"""Pin the contract of the awareness Make targets.

Companion to ``tests/test_makefile_planner_targets.py``. The
awareness CLI lives at ``backend.core.domains.awareness_cli``; the
Make targets are thin wrappers around its three subcommands
(``list`` / ``snapshot`` / ``snapshot-all``). What we lock in:

1. Every awareness-related target name is on the ``.PHONY`` line.
2. Each declared target has a ``## help`` comment so it appears
   in ``make help``.
3. Targets that take positional ARGS guard against empty ARGS
   (``planner-runs`` / etc. precedent — exit 2 with usage line).
4. The ``AWARENESS`` macro points at the canonical CLI module
   so a future move (e.g. to ``backend/core/awareness/cli.py``)
   doesn't silently leave the Makefile pointing at the wrong path.

We do NOT shell into ``make`` — that requires a full venv on
PATH. Parsing the Makefile as text is enough to catch the
common drift bugs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = REPO / "Makefile"


@pytest.fixture(scope="module")
def makefile() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


_AWARENESS_TARGETS = (
    "awareness",
    "awareness-list",
    "awareness-snapshot",
    "awareness-snapshot-all",
)


def test_awareness_targets_listed_in_phony(makefile: str):
    phony = re.search(
        r"\.PHONY:\s*((?:[^\n]*\\\n)*[^\n]*)",
        makefile,
    )
    assert phony, ".PHONY line not found in Makefile"
    phony_targets = set(phony.group(1).replace("\\\n", " ").split())
    missing = set(_AWARENESS_TARGETS) - phony_targets
    assert not missing, (
        f".PHONY missing awareness targets: {sorted(missing)}"
    )


@pytest.mark.parametrize("target", _AWARENESS_TARGETS)
def test_awareness_target_has_help_comment(makefile: str, target: str):
    pattern = re.compile(
        rf"^{re.escape(target)}:\s*[^#]*##\s*(\S.*)$",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, f"target {target!r} missing ## help text"
    assert len(m.group(1).strip()) >= 5, (
        f"help text for {target!r} too short: {m.group(1)!r}"
    )


@pytest.mark.parametrize(
    "target",
    ["awareness-snapshot", "awareness-snapshot-all"],
)
def test_args_required_targets_guard_against_empty_args(
    makefile: str, target: str
):
    """Snapshot targets are useless without their positional args
    (``<slug>`` for snapshot-all, ``<slug> <source_id>`` for
    snapshot). The recipe must short-circuit with an error line
    + exit 2 instead of letting argparse emit a confusing
    ``required arguments`` failure deep in the call stack.
    """

    pattern = re.compile(
        rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, f"recipe for {target!r} not found"
    recipe = m.group(1)
    assert '[ -z "$(ARGS)" ]' in recipe, (
        f"{target!r} recipe missing ARGS guard"
    )
    assert "exit 2" in recipe, (
        f"{target!r} recipe should exit 2 on missing ARGS for shell-friendly chaining"
    )


def test_awareness_macro_points_at_canonical_cli_module(makefile: str):
    """The ``AWARENESS`` macro must invoke
    ``backend.core.domains.awareness_cli`` (not any parallel
    script) so every Makefile target shares the same code path
    that operator scripting + tests already cover.
    """

    m = re.search(
        r"AWARENESS\s*\?=\s*(.+?)$",
        makefile,
        re.MULTILINE,
    )
    assert m, "AWARENESS macro not declared in Makefile"
    assert "backend.core.domains.awareness_cli" in m.group(1), (
        "AWARENESS macro must point at backend.core.domains.awareness_cli"
    )


def test_awareness_snapshot_target_uses_set_dash_dash_for_positionals(
    makefile: str,
):
    """``awareness-snapshot`` takes two positionals (``<slug>
    <source_id>``); the recipe must use ``set -- $(ARGS)`` to
    split them safely (not ``$(word 1, $(ARGS))`` etc., which
    breaks on certain shells). Pin the load-bearing branches of
    the parse:

    - ``set -- $(ARGS)`` to split.
    - Inner re-guard for both positionals
      (``[ -z \"$$slug\" ] || [ -z \"$$source_id\" ]``).
    - Forwards ``snapshot \"$$slug\" \"$$source_id\"`` to the CLI.
    """

    pattern = re.compile(
        r"^awareness-snapshot:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "awareness-snapshot recipe not found"
    recipe = m.group(1)
    assert "set -- $(ARGS)" in recipe, (
        "awareness-snapshot must use ``set -- $(ARGS)`` to split "
        "<slug> and <source_id>"
    )
    assert (
        '[ -z "$$slug" ] || [ -z "$$source_id" ]'
        in recipe
    ), (
        "awareness-snapshot must require both positionals via "
        "the inner re-guard"
    )
    assert 'snapshot "$$slug" "$$source_id"' in recipe, (
        "awareness-snapshot must forward both positionals to the "
        "CLI's ``snapshot <slug> <source_id>`` subcommand"
    )


def test_awareness_snapshot_all_passes_slug_directly(makefile: str):
    """``awareness-snapshot-all`` takes a single positional so
    no ``set --`` split is needed — the recipe should pass
    ``$(ARGS)`` directly to the CLI's ``snapshot-all`` subcommand.
    """

    pattern = re.compile(
        r"^awareness-snapshot-all:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "awareness-snapshot-all recipe not found"
    recipe = m.group(1)
    assert "$(AWARENESS) snapshot-all $(ARGS)" in recipe, (
        "awareness-snapshot-all must shell into ``snapshot-all "
        "$(ARGS)`` (single positional, no set-- needed)"
    )
