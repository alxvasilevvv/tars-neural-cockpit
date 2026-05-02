"""Pin the contract of the planner Make targets.

Specifically:

1. The Makefile declares every planner-related target name in
   its ``.PHONY`` line so ``make`` does not silently treat one
   as a file lookup if a name happens to clash.
2. Each declared planner target has a ``## help`` comment so it
   shows up in ``make help``.
3. ``planner-smoke`` is wired into ``gate-control-tower`` so the
   release readiness gate covers it end-to-end.
4. ``planner-runs`` and ``planner-show`` enforce the
   ``ARGS=<plan_id>`` invariant (otherwise they would silently
   shell into ``cli runs`` / ``cli show`` with no positional
   arg and produce a confusing argparse error).
5. The ``PLANNER`` macro points at ``backend.core.planner.cli``
   so the targets share the same code path as
   ``python -m backend.core.planner.cli`` — no parallel
   reimplementation.

We do NOT actually shell out to ``make`` here (that would
require a real environment with the venv on PATH); we just
parse the Makefile as text, which is enough to catch the
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


_PLANNER_TARGETS = (
    "planner",
    "planner-stats",
    "planner-list",
    "planner-runs",
    "planner-show",
    "planner-full",
    "planner-rerun",
    "planner-smoke",
)


def test_planner_targets_listed_in_phony(makefile: str):
    # The .PHONY line(s) may continue with ``\``; collapse them
    # to a single string before scanning.
    phony = re.search(
        r"\.PHONY:\s*((?:[^\n]*\\\n)*[^\n]*)",
        makefile,
    )
    assert phony, ".PHONY line not found in Makefile"
    phony_targets = set(phony.group(1).replace("\\\n", " ").split())
    missing = set(_PLANNER_TARGETS) - phony_targets
    assert not missing, (
        f".PHONY missing planner targets: {sorted(missing)}"
    )


@pytest.mark.parametrize("target", _PLANNER_TARGETS)
def test_planner_target_has_help_comment(makefile: str, target: str):
    """Every planner-* target should expose its description via
    the ``## help text`` convention so ``make help`` lists it.
    """

    pattern = re.compile(
        rf"^{re.escape(target)}:\s*[^#]*##\s*(\S.*)$",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, f"target {target!r} missing ## help text"
    # Help text should be non-trivial (>= 5 chars).
    assert len(m.group(1).strip()) >= 5, (
        f"help text for {target!r} too short: {m.group(1)!r}"
    )


def test_gate_control_tower_includes_planner_smoke(makefile: str):
    """The release-readiness gate must cover ``planner-smoke``
    so a planner regression cannot land silently while other
    cockpit checks stay green.
    """

    # Find the gate-control-tower recipe (recipe lines start with
    # tabs and continue until the next non-tab block).
    pattern = re.compile(
        r"^gate-control-tower:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "gate-control-tower recipe not found"
    recipe = m.group(1)
    assert "planner-smoke" in recipe, (
        "gate-control-tower does not invoke planner-smoke; "
        "the planner CLI will not be covered by the release gate."
    )


@pytest.mark.parametrize(
    "target",
    ["planner-runs", "planner-show", "planner-full", "planner-rerun"],
)
def test_args_required_targets_guard_against_empty_args(
    makefile: str, target: str
):
    """``planner-runs`` / ``planner-show`` / ``planner-full`` /
    ``planner-rerun`` are useless without a plan_id; the recipe
    must short-circuit with an error message instead of letting
    the CLI emit a confusing argparse failure.
    """

    pattern = re.compile(
        rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, f"recipe for {target!r} not found"
    recipe = m.group(1)
    # The guard line uses ``[ -z "$(ARGS)" ]`` to detect missing
    # ARGS and prints a usage hint before exit 2.
    assert '[ -z "$(ARGS)" ]' in recipe, (
        f"{target!r} recipe missing ARGS guard"
    )
    assert "exit 2" in recipe, (
        f"{target!r} recipe should exit 2 on missing ARGS for shell-friendly chaining"
    )


def test_planner_macro_points_at_canonical_cli_module(makefile: str):
    """The ``PLANNER`` macro must invoke
    ``backend.core.planner.cli`` (not any parallel script) so
    every Makefile target shares the same code path the
    operator's tab-completion already covers.
    """

    m = re.search(
        r"PLANNER\s*\?=\s*(.+?)$",
        makefile,
        re.MULTILINE,
    )
    assert m, "PLANNER macro not declared in Makefile"
    assert "backend.core.planner.cli" in m.group(1), (
        "PLANNER macro must point at backend.core.planner.cli"
    )


def test_planner_rerun_target_wires_clone_with_approve_and_run(
    makefile: str,
):
    """``planner-rerun`` must shell into ``clone <id> --approve --run``
    so a single Make invocation reproduces the cockpit's one-click
    Rerun button (cron / fleet workflows depend on this parity).
    The optional ``MODE=`` variable, when present, must reach the
    CLI as ``--mode <value>`` so the operator can pin policy mode.
    """

    pattern = re.compile(
        r"^planner-rerun:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "planner-rerun recipe not found"
    recipe = m.group(1)
    # Default branch (no MODE) must call clone with --approve --run.
    assert "clone $(ARGS) --approve --run" in recipe, (
        "planner-rerun must invoke `clone $(ARGS) --approve --run` "
        "to mirror the cockpit's one-click Rerun behaviour"
    )
    # Optional MODE branch must forward --mode "$(MODE)".
    assert '--mode "$(MODE)"' in recipe, (
        "planner-rerun must forward the optional MODE= variable as "
        "`--mode \"$(MODE)\"` so operators can pin policy mode"
    )


def test_planner_smoke_recipe_uses_quiet_flag(makefile: str):
    """``planner-smoke`` is invoked from ``gate-control-tower``
    so it should print one short success line on stdout, not
    spam the gate log with full plan dumps. We pin that by
    requiring ``--quiet`` on the cli invocations.
    """

    pattern = re.compile(
        r"^planner-smoke:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "planner-smoke recipe not found"
    recipe = m.group(1)
    assert "--quiet" in recipe, "planner-smoke should pass --quiet to the CLI"
