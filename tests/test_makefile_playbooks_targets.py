"""Pin the contract of the playbooks Make targets.

Companion to ``tests/test_makefile_planner_targets.py`` and
``tests/test_makefile_awareness_targets.py``. The playbooks CLI
lives at ``backend.core.playbooks.cli``; the Make targets are
thin wrappers around its six subcommands.

What we lock in:

1. Every playbook-related target name is on the ``.PHONY`` line.
2. Each declared target has a ``## help`` comment so it appears
   in ``make help``.
3. Targets that take positional ARGS guard against empty ARGS.
4. The ``PLAYBOOKS`` macro points at the canonical CLI module
   so a future module move surfaces here, not in production.
5. ``playbooks-validate-all`` is wired into ``gate-control-tower``
   so a malformed playbook fails the gate (the operator-facing
   contract that the validator catches authoring errors).

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


_PLAYBOOK_TARGETS = (
    "playbooks",
    "playbooks-list",
    "playbooks-show",
    "playbooks-run",
    "playbooks-validate",
    "playbooks-validate-all",
    "playbooks-reload",
)


def test_playbook_targets_listed_in_phony(makefile: str):
    phony = re.search(r"\.PHONY:\s*((?:[^\n]*\\\n)*[^\n]*)", makefile)
    assert phony, ".PHONY line not found"
    phony_targets = set(phony.group(1).replace("\\\n", " ").split())
    missing = set(_PLAYBOOK_TARGETS) - phony_targets
    assert not missing, f".PHONY missing playbook targets: {sorted(missing)}"


@pytest.mark.parametrize("target", _PLAYBOOK_TARGETS)
def test_playbook_target_has_help_comment(makefile: str, target: str):
    pattern = re.compile(
        rf"^{re.escape(target)}:\s*[^#]*##\s*(\S.*)$",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, f"target {target!r} missing ## help text"
    assert len(m.group(1).strip()) >= 5


@pytest.mark.parametrize(
    "target",
    ["playbooks-show", "playbooks-run", "playbooks-validate"],
)
def test_args_required_targets_guard_against_empty_args(
    makefile: str, target: str
):
    """``show`` / ``run`` / ``validate`` all take a single positional
    ``<id>``; running them without ARGS would otherwise burrow into
    argparse with a confusing error. Pin the standard guard pattern
    used everywhere else in the Makefile.
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
        f"{target!r} should exit 2 on missing ARGS"
    )


def test_playbooks_macro_points_at_canonical_cli(makefile: str):
    m = re.search(r"PLAYBOOKS\s*\?=\s*(.+?)$", makefile, re.MULTILINE)
    assert m, "PLAYBOOKS macro not declared"
    assert "backend.core.playbooks.cli" in m.group(1), (
        "PLAYBOOKS macro must point at backend.core.playbooks.cli"
    )


def test_playbooks_validate_all_wired_into_control_tower(makefile: str):
    """The CI gate must include ``playbooks-validate-all`` so a
    malformed playbook (action without slug, unknown ``on_error``,
    etc.) fails the gate instead of waiting for a cron job to hit
    the runner at 5am. Pin this so a future "tighten the gate"
    refactor doesn't quietly drop validate-all.
    """

    m = re.search(
        r"^gate-control-tower:[^\n]*\n((?:\t[^\n]*\n)+)",
        makefile,
        re.MULTILINE,
    )
    assert m, "gate-control-tower target not found"
    recipe = m.group(1)
    assert "playbooks-validate-all" in recipe, (
        "gate-control-tower must include $(MAKE) playbooks-validate-all"
    )


def test_playbooks_run_target_threads_optional_mode_and_context(makefile: str):
    """The ``playbooks-run`` recipe must surface ``MODE=`` and
    ``CONTEXT=`` as optional standalone vars (the cron-friendly
    pattern), not require them to be wedged inside ``ARGS=``. Pin
    the inner forwarding so a future "simplification" doesn't
    silently drop the cron contract that reads:

        make playbooks-run ARGS=<id> MODE=autopilot CONTEXT='<json>'
    """

    pattern = re.compile(
        r"^playbooks-run:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "playbooks-run recipe not found"
    recipe = m.group(1)
    assert '$(MODE)' in recipe, (
        "playbooks-run must read MODE= so cron commands stay legible"
    )
    assert '$(CONTEXT)' in recipe, (
        "playbooks-run must read CONTEXT= for sidecar JSON tweaks"
    )
    assert '--mode' in recipe, "playbooks-run must forward MODE via --mode"
    assert '--context' in recipe, (
        "playbooks-run must forward CONTEXT via --context"
    )


def test_playbooks_list_passes_args_directly(makefile: str):
    """``playbooks-list`` takes no positional but optionally accepts
    ``ARGS=--pack=<pack>`` for filtering. The recipe should
    forward ``$(ARGS)`` directly (no guard, no inner parse). Pin
    the canonical pattern for "no positional, ARGS optional"
    targets so a copy-paste of the show / run / validate guards
    doesn't accidentally make ``--pack`` mandatory.
    """

    pattern = re.compile(
        r"^playbooks-list:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "playbooks-list recipe not found"
    recipe = m.group(1)
    assert '[ -z "$(ARGS)" ]' not in recipe, (
        "playbooks-list must NOT guard against empty ARGS — "
        "no-pack listing is the default lane"
    )
    assert "$(PLAYBOOKS) list $(ARGS)" in recipe, (
        "playbooks-list must forward $(ARGS) directly"
    )


def test_playbooks_validate_all_takes_no_args(makefile: str):
    """``validate-all`` is parameter-free by design — the whole
    point is to walk every playbook on disk. Pin that the recipe
    doesn't accept ARGS (so a typo like
    ``make playbooks-validate-all ARGS=foo`` is silently dropped
    rather than mistaken for a positional id).
    """

    pattern = re.compile(
        r"^playbooks-validate-all:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(makefile)
    assert m, "playbooks-validate-all recipe not found"
    recipe = m.group(1)
    assert "$(ARGS)" not in recipe, (
        "playbooks-validate-all must not pass ARGS so a typo "
        "doesn't get mistaken for a playbook id"
    )
    assert "validate-all" in recipe, (
        "playbooks-validate-all recipe must invoke the validate-all "
        "subcommand (not 'validate')"
    )
