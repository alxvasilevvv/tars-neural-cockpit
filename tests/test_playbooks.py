"""Tests for the playbook loader + runner (Phase E)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.playbooks import (
    Playbook,
    PlaybookStep,
    discover,
    get_playbook,
    list_playbooks,
    reset_loader_cache,
    run_playbook,
)
from backend.core.playbooks.runner import (
    _resolve_args,
    _resolve_template,
)
from backend.core.policy import PolicyMode


def test_template_returns_native_when_full_match() -> None:
    ctx = {"steps": {"x": {"value": 42}}}
    assert _resolve_template("${steps.x.value}", ctx) == 42
    assert _resolve_template("count=${steps.x.value}", ctx) == "count=42"


def test_resolve_args_walks_dicts_and_lists() -> None:
    ctx = {
        "steps": {"a": {"items": [1, 2, 3]}, "b": "hello"},
        "context": {"u": "alien"},
    }
    args = {
        "first": "${steps.a.items.0}",
        "join": "user=${context.u} second=${steps.a.items.1}",
        "static": 7,
        "nested": {"x": "${steps.b}"},
    }
    out = _resolve_args(args, ctx)
    assert out["first"] == 1
    assert out["join"] == "user=alien second=2"
    assert out["static"] == 7
    assert out["nested"]["x"] == "hello"


def test_loader_discovers_repo_playbooks() -> None:
    reset_loader_cache()
    items = {pb.id: pb for pb in list_playbooks()}
    assert "traders.morning_check" in items
    assert "business.morning_brief" in items
    assert "mlm.retention_round" in items
    assert "mlm.recruitment_round" in items
    pb = items["business.morning_brief"]
    assert any(s.action.startswith("business.") for s in pb.steps)


def test_loader_rejects_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "x" / "bad.json"
    bad.parent.mkdir(parents=True)
    bad.write_text(json.dumps({"id": "x.bad"}))  # no steps
    with pytest.raises(ValueError, match="no steps"):
        discover(tmp_path)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    payload = {
        "id": "shared.id",
        "name": "x",
        "steps": [{"id": "s", "action": "business.kpi_snapshot"}],
    }
    (a / "x.json").write_text(json.dumps(payload))
    (b / "y.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicate"):
        discover(tmp_path)


def test_runner_executes_read_only_playbook() -> None:
    pb = get_playbook("business.morning_brief", refresh=True)
    assert pb is not None

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    assert by_id["kpi"]["ok"] is True
    assert by_id["brief"]["ok"] is True
    assert by_id["calendar"]["ok"] is True
    # Stored values flowed into the context.
    stored = out["context"]["steps"]
    assert "kpi" in stored
    assert "brief" in stored
    assert isinstance(stored["calendar"], dict)


def test_runner_blocks_destructive_step_in_confirm_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.policy import reset_policy_store
    reset_policy_store()

    pb = get_playbook("mlm.retention_round", refresh=True)
    assert pb is not None

    async def run():
        return await run_playbook(pb, mode=PolicyMode.CONFIRM)

    out = asyncio.run(run())
    by_id = {s["id"]: s for s in out["steps"]}
    # Read-only steps run.
    assert by_id["snapshot"]["ok"] is True
    assert by_id["alert"]["ok"] is True
    # Destructive step staged with a token.
    assert by_id["outreach"]["blocked"] is True
    assert by_id["outreach"]["confirmation_token"]
    assert by_id["outreach"]["confirmation_token"].startswith("cfm_")


def test_runner_when_clause_skips_step() -> None:
    pb = Playbook(
        id="t.when",
        name="t",
        description="",
        steps=(
            PlaybookStep(
                id="kpi",
                action="business.kpi_snapshot",
                store_as="kpi",
            ),
            PlaybookStep(
                id="never",
                action="business.kpi_snapshot",
                when="false",
            ),
            PlaybookStep(
                id="always",
                action="business.kpi_snapshot",
                when="${steps.kpi.ok}",
            ),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    by_id = {s["id"]: s for s in out["steps"]}
    assert by_id["kpi"]["ok"] is True and not by_id["kpi"]["skipped"]
    assert by_id["never"]["skipped"] is True
    assert by_id["always"]["ok"] is True and not by_id["always"]["skipped"]


def test_runner_handles_unknown_action() -> None:
    pb = Playbook(
        id="t.bad",
        name="t",
        description="",
        steps=(
            PlaybookStep(id="bad", action="business.does_not_exist"),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is False
    assert out["steps"][0]["error"] == "action_not_found"


def test_runner_groups_parallel_steps() -> None:
    from backend.core.playbooks.runner import _group_steps

    steps = (
        PlaybookStep(id="a", action="x.y"),
        PlaybookStep(id="b", action="x.y", parallel=True),
        PlaybookStep(id="c", action="x.y", parallel=True),
        PlaybookStep(id="d", action="x.y"),
        PlaybookStep(id="e", action="x.y", parallel=True),
    )
    groups = _group_steps(steps)
    assert [[s.id for s in g] for g in groups] == [
        ["a", "b", "c"],
        ["d", "e"],
    ]


def test_runner_first_step_parallel_starts_own_group() -> None:
    from backend.core.playbooks.runner import _group_steps

    steps = (
        PlaybookStep(id="a", action="x.y", parallel=True),
        PlaybookStep(id="b", action="x.y", parallel=True),
    )
    # First step has no previous to attach to → starts its own group;
    # second step then joins it.
    groups = _group_steps(steps)
    assert [[s.id for s in g] for g in groups] == [["a", "b"]]


def test_runner_executes_parallel_group_concurrently() -> None:
    """Two parallel awareness snapshots should both succeed and the
    overall wall-clock should be roughly the slower of the two."""

    pb = Playbook(
        id="t.par",
        name="parallel",
        description="",
        steps=(
            PlaybookStep(
                id="kpi",
                action="business.kpi_snapshot",
                store_as="kpi",
            ),
            PlaybookStep(
                id="cal",
                action="business.awareness.gcalendar.snapshot",
                store_as="cal",
                parallel=True,
            ),
            PlaybookStep(
                id="hub",
                action="business.awareness.hubspot.snapshot",
                store_as="hub",
                parallel=True,
            ),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.AUTOPILOT)

    out = asyncio.run(run())
    assert out["ok"] is True
    by_id = {s["id"]: s for s in out["steps"]}
    # Output order matches declaration regardless of completion order.
    assert [s["id"] for s in out["steps"]] == ["kpi", "cal", "hub"]
    assert by_id["cal"]["ok"] is True
    assert by_id["hub"]["ok"] is True
    assert "cal" in out["context"]["steps"]
    assert "hub" in out["context"]["steps"]


def test_runner_parallel_group_blocks_dont_break_siblings(tmp_path, monkeypatch) -> None:
    """A blocked destructive step inside a parallel batch must not stop
    the read-only sibling. Both step results land; the playbook
    short-circuits afterwards if on_block=stop."""

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.policy import reset_policy_store
    reset_policy_store()

    pb = Playbook(
        id="t.par.block",
        name="parallel-block",
        description="",
        on_block="continue",
        steps=(
            PlaybookStep(id="kpi", action="business.kpi_snapshot"),
            PlaybookStep(
                id="email",
                action="business.draft_email",
                args={"to": "x@y.z"},
                parallel=True,
            ),
            PlaybookStep(
                id="cal",
                action="business.awareness.gcalendar.snapshot",
                parallel=True,
            ),
        ),
    )

    async def run():
        return await run_playbook(pb, mode=PolicyMode.CONFIRM)

    out = asyncio.run(run())
    by_id = {s["id"]: s for s in out["steps"]}
    assert by_id["kpi"]["ok"] is True
    # email is destructive → blocked with token
    assert by_id["email"]["blocked"] is True
    assert by_id["email"]["confirmation_token"]
    # cal sibling still ran
    assert by_id["cal"]["ok"] is True and by_id["cal"]["blocked"] is False


def test_loader_round_trips_parallel_flag() -> None:
    from backend.core.playbooks import get_playbook, reset_loader_cache

    reset_loader_cache()
    pb = get_playbook("traders.morning_check")
    assert pb is not None
    by_id = {s.id: s for s in pb.steps}
    assert by_id["news"].parallel is True
    assert by_id["portfolio"].parallel is True
    assert by_id["market"].parallel is False
