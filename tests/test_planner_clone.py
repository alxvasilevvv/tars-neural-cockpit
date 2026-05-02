"""Tests for ``Plan.clone(...)`` (PR #108).

Covers:

- :meth:`PlannerStore.clone` returns a fresh :class:`Plan` with a
  new id, ``status="proposed"``, fresh timestamps, deep-copied
  steps; the original plan is untouched.
- ``thread_id`` and ``goal_override`` overrides bind to the new
  clone only.
- Cloning an unknown plan returns ``None``.
- HTTP ``POST /api/planner/{plan_id}/clone`` happy path returns
  the new plan + ``source_plan_id``; emits ``planner.cloned``
  with the parent → child link; supports body ``thread_id`` and
  ``goal_override``; 404s on unknown plans.
- CLI ``clone`` subcommand happy path + ``--thread-id`` /
  ``--goal`` overrides + 404 envelope.
- Timeline allow-list + summariser pick up the new
  ``planner.cloned`` event.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)

    from backend.core.meeet import reset_client, reset_store
    from backend.core.planner import reset_planner_store, reset_run_registry
    from backend.core.planner import store as planner_store_mod

    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)
    yield
    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    from backend.core.planner.cli import main

    buf = StringIO()
    with patch("sys.stdout", new=buf):
        code = main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else {})


def _seed_plan(goal: str = "traders.morning_check") -> dict[str, Any]:
    code, body = _run_cli(["synthesize", goal])
    assert code == 0, body
    return body["plan"]


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# PlannerStore.clone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_clone_returns_fresh_proposed_plan_with_new_id():
    from backend.core.planner import (
        Plan,
        PlanStatus,
        PlanStep,
        get_planner_store,
    )

    store = get_planner_store()
    original = await store.insert(
        Plan(
            id="",
            goal="g",
            steps=(PlanStep(id="s1", action="x.y"),),
            status=PlanStatus.APPROVED,
            rationale="why",
            model="heuristic-v1",
            pack_slug="pack",
            playbook_id="pb",
            thread_id="thr_a",
            trace_id="trc_old",
        )
    )
    # Move original to terminal so we can prove the clone is independent.
    await store.set_status(original.id, PlanStatus.COMPLETED)

    cloned = await store.clone(original.id)
    assert cloned is not None
    assert cloned.id != original.id
    assert cloned.id.startswith("pln_")
    assert cloned.status == PlanStatus.PROPOSED
    assert cloned.goal == "g"
    assert cloned.rationale == "why"
    assert cloned.model == "heuristic-v1"
    assert cloned.pack_slug == "pack"
    assert cloned.playbook_id == "pb"
    assert cloned.thread_id == "thr_a"
    # trace_id of the clone is left to the caller (HTTP / CLI sets it).
    assert cloned.trace_id is None
    assert cloned.created_at >= original.created_at
    # Steps are deep-copied (different tuple identity, equal payload).
    assert cloned.steps is not original.steps
    assert cloned.steps[0].to_dict() == original.steps[0].to_dict()

    # Original is unchanged.
    refreshed = await store.get(original.id)
    assert refreshed.status == PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_store_clone_thread_id_override():
    from backend.core.planner import (
        Plan,
        PlanStatus,
        PlanStep,
        get_planner_store,
    )

    store = get_planner_store()
    original = await store.insert(
        Plan(
            id="",
            goal="g",
            steps=(PlanStep(id="s1", action="x.y"),),
            thread_id="thr_old",
        )
    )
    cloned = await store.clone(original.id, thread_id="thr_new")
    assert cloned is not None
    assert cloned.thread_id == "thr_new"


@pytest.mark.asyncio
async def test_store_clone_goal_override_is_stripped():
    from backend.core.planner import (
        Plan,
        PlanStep,
        get_planner_store,
    )

    store = get_planner_store()
    original = await store.insert(
        Plan(id="", goal="old goal", steps=(PlanStep(id="s1", action="x.y"),))
    )
    cloned = await store.clone(original.id, goal_override="  brand new goal  ")
    assert cloned is not None
    assert cloned.goal == "brand new goal"


@pytest.mark.asyncio
async def test_store_clone_unknown_plan_returns_none():
    from backend.core.planner import get_planner_store

    cloned = await get_planner_store().clone("pln_nope")
    assert cloned is None


# ---------------------------------------------------------------------------
# HTTP — POST /api/planner/{plan_id}/clone
# ---------------------------------------------------------------------------


def test_http_clone_returns_fresh_plan_and_emits_event(app_client):
    import asyncio

    plan = _seed_plan()

    resp = app_client.post(f"/api/planner/{plan['id']}/clone")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["source_plan_id"] == plan["id"]
    cloned = body["plan"]
    assert cloned["id"] != plan["id"]
    assert cloned["status"] == "proposed"
    assert cloned["step_count"] == plan["step_count"]
    # trace_id was assigned by the route's trace_scope.
    assert cloned["trace_id"] is not None

    # planner.cloned event landed.
    from backend.core.meeet import get_store

    rows = asyncio.run(
        get_store().list_events(kind="planner.cloned", limit=10)
    )
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["plan_id"] == cloned["id"]
    assert payload["source_plan_id"] == plan["id"]
    assert payload["source_status"] == "proposed"
    assert payload["thread_id_rebind"] is False
    assert payload["goal_overridden"] is False


def test_http_clone_supports_thread_id_rebind(app_client):
    import asyncio

    plan = _seed_plan()
    resp = app_client.post(
        f"/api/planner/{plan['id']}/clone",
        json={"thread_id": "thr_clone_target"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"]["thread_id"] == "thr_clone_target"

    from backend.core.meeet import get_store

    rows = asyncio.run(
        get_store().list_events(kind="planner.cloned", limit=10)
    )
    assert rows[0].payload["thread_id_rebind"] is True


def test_http_clone_supports_goal_override(app_client):
    import asyncio

    plan = _seed_plan()
    resp = app_client.post(
        f"/api/planner/{plan['id']}/clone",
        json={"goal_override": "rerun for second window"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"]["goal"] == "rerun for second window"

    from backend.core.meeet import get_store

    rows = asyncio.run(
        get_store().list_events(kind="planner.cloned", limit=10)
    )
    assert rows[0].payload["goal_overridden"] is True


def test_http_clone_404_for_unknown_plan(app_client):
    resp = app_client.post("/api/planner/pln_unknown/clone")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_found"


# ---------------------------------------------------------------------------
# CLI — clone subcommand
# ---------------------------------------------------------------------------


def test_cli_clone_happy_path():
    plan = _seed_plan()
    code, body = _run_cli(["clone", plan["id"]])
    assert code == 0
    assert body["plan"]["status"] == "proposed"
    assert body["plan"]["id"] != plan["id"]
    assert body["source_plan_id"] == plan["id"]


def test_cli_clone_with_thread_id_and_goal_overrides():
    plan = _seed_plan()
    code, body = _run_cli(
        [
            "clone",
            plan["id"],
            "--thread-id",
            "thr_branched",
            "--goal",
            "new objective",
        ]
    )
    assert code == 0
    assert body["plan"]["thread_id"] == "thr_branched"
    assert body["plan"]["goal"] == "new objective"


def test_cli_clone_unknown_plan_returns_envelope():
    code, body = _run_cli(["clone", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_found"


# ---------------------------------------------------------------------------
# Timeline allow-list + summariser
# ---------------------------------------------------------------------------


def test_timeline_summarises_planner_cloned_event():
    from backend.core.search.timeline import (
        _RELEVANT_EVENT_KINDS,
        _summarise_event,
    )

    assert "planner.cloned" in _RELEVANT_EVENT_KINDS

    summary = _summarise_event(
        "planner.cloned",
        {
            "plan_id": "pln_new",
            "source_plan_id": "pln_old",
            "step_count": 3,
            "thread_id_rebind": True,
            "goal_overridden": False,
        },
    )
    assert "plan=pln_new" in summary
    assert "from=pln_old" in summary
    assert "steps=3" in summary
    assert "thread-rebind" in summary
    assert "goal-override" not in summary


def test_timeline_summary_omits_flags_when_unset():
    from backend.core.search.timeline import _summarise_event

    summary = _summarise_event(
        "planner.cloned",
        {
            "plan_id": "pln_new",
            "source_plan_id": "pln_old",
            "step_count": 1,
            "thread_id_rebind": False,
            "goal_overridden": False,
        },
    )
    assert "thread-rebind" not in summary
    assert "goal-override" not in summary
