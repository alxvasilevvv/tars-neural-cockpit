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
    "planner-clone",
    "planner-rerun",
    "planner-replay-run",
    "planner-repush-run",
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
    [
        "planner-runs",
        "planner-show",
        "planner-full",
        "planner-clone",
        "planner-rerun",
        "planner-replay-run",
        "planner-repush-run",
    ],
)
def test_args_required_targets_guard_against_empty_args(
    makefile: str, target: str
):
    """``planner-runs`` / ``planner-show`` / ``planner-full`` /
    ``planner-clone`` / ``planner-rerun`` / ``planner-replay-run`` /
    ``planner-repush-run`` are useless without their positional
    args; the recipe must short-circuit with an error message
    instead of letting the CLI emit a confusing argparse failure.
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


def test_planner_clone_target_supports_optional_target_thread(
    makefile: str,
):
    """``planner-clone`` must accept ``ARGS="<plan_id>"`` for a
    bare clone *and* ``ARGS="<plan_id> <target_thread>"`` to
    rebind the clone to a different chat thread (cron / fleet
    forks of a known-good plan into a per-tenant thread).

    The recipe parses ARGS positionally via ``set --`` so:

    - ``ARGS=pln_abc`` shells into ``clone pln_abc`` (no ``--thread-id``
      means the CLI keeps the source thread).
    - ``ARGS="pln_abc thr_xyz"`` shells into
      ``clone pln_abc --thread-id thr_xyz``.

    Pin both branches plus the inner ``[ -z "$plan_id" ]`` re-guard
    so a stray empty positional doesn't slip through to the CLI.
    """

    pattern = re.compile(
        r"^planner-clone:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "planner-clone recipe not found"
    recipe = m.group(1)
    # Splits ARGS into positional words.
    assert "set -- $(ARGS)" in recipe, (
        "planner-clone must use ``set -- $(ARGS)`` to split the "
        "positional plan_id / target_thread cleanly"
    )
    # Inner re-guard catches the edge case where ARGS expanded
    # to whitespace-only after macro expansion.
    assert 'if [ -z "$$plan_id" ]' in recipe, (
        "planner-clone must re-check $plan_id post-split so a "
        "stray empty positional doesn't reach the CLI"
    )
    # Branch-with-thread must forward --thread-id.
    assert 'clone "$$plan_id" --thread-id "$$target_thread"' in recipe, (
        "planner-clone must forward the optional second positional "
        "as ``--thread-id <target_thread>`` to the CLI"
    )
    # Branch-without-thread must call clone with just the plan_id.
    assert 'clone "$$plan_id"' in recipe, (
        "planner-clone must shell into ``clone <plan_id>`` when no "
        "target_thread is supplied"
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


def test_planner_replay_run_target_wires_export_with_trace_id(
    makefile: str,
):
    """``planner-replay-run`` must shell into the meeet ``replay_cli``
    with ``--trace-id <run_trace>`` plus an ``--export`` path so a
    single past run's events land in a JSONL file ready for backfill
    or audit. The recipe parses ARGS positionally as ``<plan_id>
    <run_trace>``; the plan_id is informational (used in the default
    filename) but still required so the operator can grep the
    output by plan.

    Pin: positional split, both-required guard, default OUT path
    based on ``MEEET_REPLAY_DIR``, optional ``OUT=`` override, and
    the ``backend.core.meeet.replay_cli`` invocation.
    """

    pattern = re.compile(
        r"^planner-replay-run:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "planner-replay-run recipe not found"
    recipe = m.group(1)
    # Splits ARGS into positional words.
    assert "set -- $(ARGS)" in recipe, (
        "planner-replay-run must use ``set -- $(ARGS)`` to split "
        "<plan_id> and <run_trace>"
    )
    # Both positionals required (plan_id is informational but
    # still required so the export filename is meaningful).
    assert (
        '[ -z "$$plan_id" ] || [ -z "$$run_trace" ]'
        in recipe
    ), (
        "planner-replay-run must require both <plan_id> and "
        "<run_trace> positionals"
    )
    # OUT= override path.
    assert 'out_path="$(OUT)"' in recipe, (
        "planner-replay-run must let operators override the export "
        "path via ``OUT=<path>``"
    )
    # Default OUT directory uses MEEET_REPLAY_DIR macro.
    assert '"$(MEEET_REPLAY_DIR)"' in recipe, (
        "planner-replay-run must default the export dir to "
        "``$(MEEET_REPLAY_DIR)`` so cron jobs land files in a "
        "predictable place"
    )
    assert (
        '"$(MEEET_REPLAY_DIR)/$$plan_id-$$run_trace.jsonl"'
        in recipe
    ), (
        "planner-replay-run default filename must be "
        "<dir>/<plan_id>-<run_trace>.jsonl so operators can grep "
        "by either id"
    )
    # The CLI invocation must use the meeet replay_cli module
    # with --trace-id (not the planner CLI — different module).
    assert "backend.core.meeet.replay_cli" in recipe, (
        "planner-replay-run must shell into the meeet replay_cli "
        "(not the planner CLI) so it queries the meeet store"
    )
    assert '--trace-id "$$run_trace"' in recipe, (
        "planner-replay-run must forward the second positional as "
        "``--trace-id <run_trace>`` so only that run's events are "
        "exported"
    )
    assert '--export "$$out_path"' in recipe, (
        "planner-replay-run must use ``--export <out_path>`` to "
        "write the JSONL file (not the default replay/push branch)"
    )


def test_planner_repush_run_target_wires_replay_cli_with_repush_trace(
    makefile: str,
):
    """``planner-repush-run`` must shell into the meeet ``replay_cli``
    with ``--repush-trace <run_trace>`` (not ``--trace-id`` —
    that's the export-only filter; ``--repush-trace`` is the one
    that actually re-emits upstream).

    Pin: bare ARGS shells without ``--limit``; LIMIT= variable
    forwards as ``--limit <N>``. The recipe is a single
    positional argument so we don't need ``set --`` /
    inner-positional re-guards (unlike ``planner-replay-run``
    which takes two).
    """

    pattern = re.compile(
        r"^planner-repush-run:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "planner-repush-run recipe not found"
    recipe = m.group(1)
    # Both branches must call replay_cli with --repush-trace.
    assert "backend.core.meeet.replay_cli --repush-trace $(ARGS)" in recipe, (
        "planner-repush-run must shell into the meeet replay_cli "
        "with --repush-trace (NOT --trace-id, which is export-only)"
    )
    # Optional LIMIT branch must forward --limit $(LIMIT).
    assert "--limit $(LIMIT)" in recipe, (
        "planner-repush-run must forward the optional LIMIT= "
        "variable as ``--limit $(LIMIT)``"
    )
    # The two-branch shape (with-LIMIT vs without) must guard on
    # MAKE-level ``-n "$(LIMIT)"`` so the bare invocation doesn't
    # get a stray ``--limit`` with empty value.
    assert '[ -n "$(LIMIT)" ]' in recipe, (
        "planner-repush-run must check ``[ -n \"$(LIMIT)\" ]`` "
        "before forwarding the flag"
    )


def test_planner_replay_run_uses_meeet_replay_dir_macro(makefile: str):
    """The Makefile must declare ``MEEET_REPLAY_DIR`` with a
    sensible default (``.meeet-replays``) and the
    ``planner-replay-run`` recipe must reference it. Operators
    can still override via ``MEEET_REPLAY_DIR=…`` on the make
    command line (Makefile ``?=`` semantics) or via env.
    """

    m = re.search(
        r"^MEEET_REPLAY_DIR\s*\?=\s*(.+?)$",
        makefile,
        re.MULTILINE,
    )
    assert m, (
        "MEEET_REPLAY_DIR macro must be declared with ``?=`` so "
        "operators can override it from env / command line"
    )
    default = m.group(1).strip()
    assert default == ".meeet-replays", (
        f"MEEET_REPLAY_DIR default should be ``.meeet-replays``, "
        f"got {default!r}"
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
