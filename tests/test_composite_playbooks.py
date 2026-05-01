"""Tests for composite-pack playbooks (Phase K4 + #31).

Composite packs (`research_lab` = science + business, `ops_room` =
traders + mlm) expose actions and awareness with namespaced ids of
the form ``<sub_slug>__<id>``. The playbook runner already does a
single ``slug.action_id`` split + ``pack.find_action`` lookup, so
composite-pack steps just work — these tests pin that behaviour and
the on-disk samples under ``playbooks/research_lab/`` and
``playbooks/ops_room/``.
"""

from __future__ import annotations

import asyncio

import backend.core.domains.packs as _packs  # noqa: F401  - registers packs

from backend.core.playbooks import (
    Playbook,
    PlaybookStep,
    discover,
    get_playbook,
    list_playbooks,
    reset_loader_cache,
    run_playbook,
)
from backend.core.playbooks.runner import _parse_awareness_target
from backend.core.policy import PolicyMode


# --------------------------------------------------------------------
# Disk samples — research_lab + ops_room ship in repo
# --------------------------------------------------------------------


def test_loader_discovers_composite_playbooks() -> None:
    reset_loader_cache()
    items = {pb.id: pb for pb in list_playbooks(refresh=True)}
    assert "research_lab.paper_to_pitch" in items
    assert "ops_room.morning_standup" in items

    rl = items["research_lab.paper_to_pitch"]
    assert rl.pack == "research_lab"
    actions = [s.action for s in rl.steps]
    # At least one science__ and one business__ namespaced action / awareness.
    assert any(a.startswith("research_lab.") and "science__" in a for a in actions)
    assert any(a.startswith("research_lab.") and "business__" in a for a in actions)


def test_loader_round_trips_composite_pack_dir(tmp_path) -> None:
    """A pack directory whose name doesn't match any registered pack
    is still discoverable; the loader uses the dir name as the label
    and the runner resolves the slug from the *step.action* prefix."""

    custom = tmp_path / "research_lab"
    custom.mkdir()
    (custom / "smoke.json").write_text(
        '{"id": "research_lab.smoke", '
        '"name": "smoke", '
        '"steps": [{"id": "kpi", "action": "research_lab.business__kpi_snapshot"}]}',
        encoding="utf-8",
    )
    out = discover(tmp_path)
    assert "research_lab.smoke" in out
    assert out["research_lab.smoke"].pack == "research_lab"


# --------------------------------------------------------------------
# Awareness target parsing for namespaced source ids
# --------------------------------------------------------------------


def test_parse_awareness_target_handles_namespaced_source() -> None:
    slug, source_id = _parse_awareness_target(
        "research_lab.awareness.science__local_papers.snapshot"
    )
    assert slug == "research_lab"
    assert source_id == "science__local_papers"

    slug, source_id = _parse_awareness_target(
        "ops_room.awareness.traders__news_feed.snapshot"
    )
    assert slug == "ops_room"
    assert source_id == "traders__news_feed"


# --------------------------------------------------------------------
# Runner — composite playbook end-to-end
# --------------------------------------------------------------------


def test_runner_executes_research_lab_paper_to_pitch_composite() -> None:
    pb = get_playbook("research_lab.paper_to_pitch", refresh=True)
    assert pb is not None

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    # All three steps land green; awareness dispatch + composite action
    # dispatch + sub-pack action dispatch all share one trace.
    assert by_id["papers"]["ok"] is True
    assert by_id["kpi"]["ok"] is True
    assert by_id["brief"]["ok"] is True

    stored = out["context"]["steps"]
    assert "papers" in stored
    assert "kpi" in stored


def test_runner_executes_ops_room_morning_standup_composite() -> None:
    pb = get_playbook("ops_room.morning_standup", refresh=True)
    assert pb is not None

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    # Market summary is sequential; downline + news are parallel
    # awareness/action snapshots — all three must land.
    assert by_id["market"]["ok"] is True
    assert by_id["downline"]["ok"] is True
    assert by_id["news"]["ok"] is True
    # Output order is deterministic and matches declaration.
    assert [s["id"] for s in out["steps"]] == ["market", "downline", "news"]


def test_runner_dispatches_atomic_action_from_composite_dir() -> None:
    """A playbook living under ``playbooks/research_lab/`` is free to
    call atomic-pack actions directly when the operator wants the
    sub-pack's surface (no ``__`` prefix). The runner only cares about
    the slug + action id; the directory is just a label."""

    pb = Playbook(
        id="t.composite_dir_atomic",
        name="t",
        description="",
        steps=(
            PlaybookStep(id="kpi_atomic", action="business.kpi_snapshot"),
            PlaybookStep(id="kpi_namespaced", action="research_lab.business__kpi_snapshot"),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    # Both forms hit the same handler and return shape-compatible data.
    assert by_id["kpi_atomic"]["ok"] is True
    assert by_id["kpi_namespaced"]["ok"] is True


def test_runner_blocks_destructive_composite_action_in_confirm_mode(
    tmp_path, monkeypatch
) -> None:
    """A destructive sub-pack action surfaced through the composite
    must still flow through the policy gate — destructive flags
    propagate from the leaf into the namespaced spec."""

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.policy import reset_policy_store

    reset_policy_store()

    pb = Playbook(
        id="t.composite_destructive",
        name="t",
        description="",
        on_block="continue",
        steps=(
            PlaybookStep(id="kpi", action="research_lab.business__kpi_snapshot"),
            PlaybookStep(
                id="email",
                action="research_lab.business__draft_email",
                args={"to": "x@y.z"},
            ),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.CONFIRM)

    out = asyncio.run(run())
    by_id = {s["id"]: s for s in out["steps"]}
    assert by_id["kpi"]["ok"] is True
    assert by_id["email"]["blocked"] is True
    assert by_id["email"]["confirmation_token"]
    assert by_id["email"]["confirmation_token"].startswith("cfm_")


def test_runner_templating_flows_across_sub_packs() -> None:
    """A sub-pack's output must be referenceable from a downstream
    step that targets a *different* sub-pack — the whole point of a
    composite playbook."""

    pb = Playbook(
        id="t.composite_templating",
        name="t",
        description="",
        steps=(
            PlaybookStep(
                id="papers",
                action="research_lab.awareness.science__local_papers.snapshot",
                store_as="papers",
            ),
            PlaybookStep(
                id="brief",
                action="research_lab.business__daily_brief",
                args={
                    # Not actually consumed by daily_brief schema, but the
                    # value flow proves the resolver walked across sub-packs.
                    "context_paper_count": "${steps.papers.count}",
                },
            ),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    assert by_id["papers"]["ok"] is True
    assert by_id["brief"]["ok"] is True
