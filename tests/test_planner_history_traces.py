"""Tests for per-run trace surfacing on ``PlanRun.to_dict()``.

The runner mints a fresh ``trace_id`` for each invocation and
propagates the plan's birth trace as ``parent_trace_id`` on the
``plan.run.started`` event payload (see PR #109). This module
verifies that the reconstructor in
:mod:`backend.core.planner.history` exposes both fields on
``PlanRun.to_dict()`` and on the HTTP ``GET /{plan_id}/runs``
response so the cockpit can:

- deep-link from a single run back to the synthesis trace, and
- group sibling runs of the same plan under a collapsible
  "all runs of plan X" node by ``parent_trace_id``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.delenv("TARS_POLICY_MODE", raising=False)

    from backend.core.meeet import reset_client, reset_store
    from backend.core.planner import reset_planner_store, reset_run_registry

    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()
    yield
    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()


async def _emit(kind: str, payload: dict[str, Any]) -> None:
    from backend.core.meeet import get_client

    await get_client().emit(kind, payload)


async def _emit_in_fresh_trace(kind: str, payload: dict[str, Any]) -> str:
    """Emit ``kind`` inside its own trace_scope and return the
    trace id that ended up stamped on the event.

    Any ambient ``current_trace()`` from a prior test or fixture
    is shadowed for the duration of the scope, so callers can
    assert on the trace deterministically regardless of run order.
    """

    from backend.core.meeet import get_client
    from backend.core.meeet.tracing import trace_scope

    with trace_scope() as trace_id:
        await get_client().emit(kind, payload)
    return trace_id


@pytest.mark.asyncio
async def test_plan_run_dict_exposes_trace_and_parent_trace():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_trace_surface"
    minted_trace = await _emit_in_fresh_trace(
        "plan.run.started",
        {
            "plan_id": plan_id,
            "mode": "autopilot",
            "step_count": 1,
            "parent_trace_id": "trc_plan_birth",
        },
    )
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    run = runs[0].to_dict()

    assert "trace_id" in run
    assert "parent_trace_id" in run
    assert run["parent_trace_id"] == "trc_plan_birth"
    # ``trace_id`` is the per-event trace stamped on the
    # ``plan.run.started`` row by the meeet client; it must equal
    # the trace we explicitly minted above and must NOT equal the
    # plan's birth trace.
    assert run["trace_id"] == minted_trace
    assert run["trace_id"] != run["parent_trace_id"]


@pytest.mark.asyncio
async def test_plan_run_dict_parent_trace_is_none_for_legacy_event():
    """A ``plan.run.started`` without ``parent_trace_id`` (legacy
    rows produced before PR #109 landed) must not crash the
    reconstructor — it just surfaces ``parent_trace_id=None``.
    """

    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_legacy_trace"
    minted_trace = await _emit_in_fresh_trace(
        "plan.run.started",
        {
            "plan_id": plan_id,
            "mode": "autopilot",
            "step_count": 1,
            # No `parent_trace_id` key — mirrors a legacy event.
        },
    )
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    run = runs[0].to_dict()
    assert run["parent_trace_id"] is None
    assert run["trace_id"] == minted_trace


@pytest.mark.asyncio
async def test_two_runs_of_same_plan_share_parent_trace():
    """Sibling runs of the same plan share ``parent_trace_id`` and
    have distinct per-run ``trace_id``s — exactly what the cockpit
    needs to group "all runs of plan X" under one node.
    """

    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_siblings"
    parent = "trc_plan_birth_v2"

    # Each run is emitted in its own trace_scope so the test does
    # not depend on what any earlier test or fixture left in the
    # ``current_trace()`` ContextVar.
    trace_a = await _emit_in_fresh_trace(
        "plan.run.started",
        {"plan_id": plan_id, "mode": "autopilot", "parent_trace_id": parent},
    )
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})
    trace_b = await _emit_in_fresh_trace(
        "plan.run.started",
        {"plan_id": plan_id, "mode": "confirm", "parent_trace_id": parent},
    )
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

    assert trace_a != trace_b

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 2
    # Both runs report the same parent trace.
    parents = {r.parent_trace_id for r in runs}
    assert parents == {parent}
    # And each run has its own per-event trace, matching exactly
    # the trace ids we minted via trace_scope above.
    traces = {r.trace_id for r in runs}
    assert traces == {trace_a, trace_b}
    assert parent not in traces


def _seed_plan_via_http(client: TestClient) -> str:
    resp = client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["plan"]["id"]


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_http_runs_endpoint_surfaces_parent_trace(app_client):
    """The ``GET /api/planner/{plan_id}/runs`` JSON envelope carries
    ``trace_id`` + ``parent_trace_id`` per run so the cockpit can
    deep-link without an extra round-trip.
    """

    import asyncio

    plan_id = _seed_plan_via_http(app_client)

    async def seed() -> str:
        trace = await _emit_in_fresh_trace(
            "plan.run.started",
            {
                "plan_id": plan_id,
                "mode": "autopilot",
                "parent_trace_id": "trc_synthesis",
            },
        )
        await _emit("plan.completed", {"plan_id": plan_id, "ok": True})
        return trace

    minted_trace = asyncio.run(seed())

    resp = app_client.get(f"/api/planner/{plan_id}/runs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    run = body["runs"][0]
    assert run["parent_trace_id"] == "trc_synthesis"
    assert run["trace_id"] == minted_trace
    assert run["trace_id"] != run["parent_trace_id"]
