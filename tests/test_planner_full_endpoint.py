"""Tests for ``GET /api/planner/{plan_id}/full``.

The aggregate endpoint is the cockpit's one-shot fetch for the
plan-detail drawer. It bundles:

- the plan envelope (same shape as ``GET /{plan_id}``),
- reconstructed runs (same shape as ``GET /{plan_id}/runs``),
- a ``usage_lifetime`` block summing every run's per-run rollup.

Pinned here:

- 404 for unknown ``plan_id``.
- Empty plan (no runs yet) → empty runs list + zero-valued
  lifetime block + ``runs_aggregated=0``.
- Multiple completed runs → lifetime block sums calls / tokens
  / latency / cost across runs.
- ``cost_usd`` is ``None`` when no run had a priced model
  (so the cockpit renders "n/a", not "$0.00").
- Mixed priced + unpriced runs → lifetime sums *only* the
  priced runs' costs and reports ``has_priced_models=True``.
- ``in_flight`` count surfaces correctly when a run is open.
- ``limit`` query param caps the per-kind fetch but still
  produces a valid (potentially partial) envelope.
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


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _seed_plan(client: TestClient) -> str:
    resp = client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["plan"]["id"]


async def _emit(kind: str, payload: dict[str, Any]) -> None:
    from backend.core.meeet import get_client

    await get_client().emit(kind, payload)


def test_full_endpoint_returns_404_for_unknown_plan(app_client):
    resp = app_client.get("/api/planner/pln_unknown/full")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_found"


def test_full_endpoint_with_no_runs_returns_zero_usage(app_client):
    plan_id = _seed_plan(app_client)
    resp = app_client.get(f"/api/planner/{plan_id}/full")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["plan_id"] == plan_id
    assert body["plan"]["id"] == plan_id
    assert body["runs"]["count"] == 0
    assert body["runs"]["in_flight"] == 0
    assert body["runs"]["items"] == []
    usage = body["usage_lifetime"]
    assert usage["calls"] == 0
    assert usage["tokens_in"] == 0
    assert usage["tokens_out"] == 0
    assert usage["cost_usd"] is None
    assert usage["latency_ms_total"] == 0.0
    assert usage["has_priced_models"] is False
    assert usage["runs_aggregated"] == 0


def test_full_endpoint_aggregates_two_priced_runs(app_client):
    import asyncio

    plan_id = _seed_plan(app_client)

    async def seed():
        # Run 1.
        await _emit(
            "plan.run.started", {"plan_id": plan_id, "mode": "autopilot"}
        )
        await _emit(
            "plan.completed",
            {
                "plan_id": plan_id,
                "ok": True,
                "usage": {
                    "calls": 2,
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "cost_usd": 0.0123,
                    "latency_ms_total": 12.0,
                    "has_priced_models": True,
                },
            },
        )
        # Run 2.
        await _emit(
            "plan.run.started", {"plan_id": plan_id, "mode": "confirm"}
        )
        await _emit(
            "plan.completed",
            {
                "plan_id": plan_id,
                "ok": True,
                "usage": {
                    "calls": 1,
                    "tokens_in": 25,
                    "tokens_out": 75,
                    "cost_usd": 0.0042,
                    "latency_ms_total": 8.5,
                    "has_priced_models": True,
                },
            },
        )

    asyncio.run(seed())

    body = app_client.get(f"/api/planner/{plan_id}/full").json()
    assert body["runs"]["count"] == 2
    assert body["runs"]["in_flight"] == 0

    usage = body["usage_lifetime"]
    assert usage["calls"] == 3
    assert usage["tokens_in"] == 125
    assert usage["tokens_out"] == 125
    # Floating-point sums are predictable for these specific
    # values; allow a tiny epsilon just in case.
    assert usage["cost_usd"] == pytest.approx(0.0165, rel=1e-9)
    assert usage["latency_ms_total"] == pytest.approx(20.5, rel=1e-9)
    assert usage["has_priced_models"] is True
    assert usage["runs_aggregated"] == 2


def test_full_endpoint_unpriced_runs_keep_cost_null(app_client):
    """A run that explicitly reports ``has_priced_models=false``
    must NOT contribute to the lifetime cost — the cockpit needs
    to distinguish "no priced model" from "$0.00 priced model"
    so the n/a label stays meaningful.
    """

    import asyncio

    plan_id = _seed_plan(app_client)

    async def seed():
        await _emit("plan.run.started", {"plan_id": plan_id})
        await _emit(
            "plan.completed",
            {
                "plan_id": plan_id,
                "ok": True,
                "usage": {
                    "calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": None,
                    "latency_ms_total": 0.0,
                    "has_priced_models": False,
                },
            },
        )

    asyncio.run(seed())

    body = app_client.get(f"/api/planner/{plan_id}/full").json()
    usage = body["usage_lifetime"]
    assert usage["cost_usd"] is None
    assert usage["has_priced_models"] is False
    assert usage["runs_aggregated"] == 1


def test_full_endpoint_mixed_priced_and_unpriced_runs(app_client):
    """Mixed bag: one priced run, one unpriced. Lifetime cost
    must equal *only* the priced run's cost and
    ``has_priced_models`` must flip to True.
    """

    import asyncio

    plan_id = _seed_plan(app_client)

    async def seed():
        # Unpriced run.
        await _emit("plan.run.started", {"plan_id": plan_id})
        await _emit(
            "plan.completed",
            {
                "plan_id": plan_id,
                "ok": True,
                "usage": {
                    "calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": None,
                    "latency_ms_total": 0.0,
                    "has_priced_models": False,
                },
            },
        )
        # Priced run.
        await _emit("plan.run.started", {"plan_id": plan_id})
        await _emit(
            "plan.completed",
            {
                "plan_id": plan_id,
                "ok": True,
                "usage": {
                    "calls": 5,
                    "tokens_in": 200,
                    "tokens_out": 100,
                    "cost_usd": 0.0500,
                    "latency_ms_total": 30.0,
                    "has_priced_models": True,
                },
            },
        )

    asyncio.run(seed())

    body = app_client.get(f"/api/planner/{plan_id}/full").json()
    usage = body["usage_lifetime"]
    assert usage["cost_usd"] == pytest.approx(0.05, rel=1e-9)
    assert usage["has_priced_models"] is True
    assert usage["calls"] == 5
    assert usage["tokens_in"] == 200
    assert usage["tokens_out"] == 100
    assert usage["runs_aggregated"] == 2


def test_full_endpoint_in_flight_run_surfaces_correctly(app_client):
    import asyncio

    plan_id = _seed_plan(app_client)

    async def seed():
        # Completed.
        await _emit("plan.run.started", {"plan_id": plan_id})
        await _emit("plan.completed", {"plan_id": plan_id, "ok": True})
        # Still running.
        await _emit("plan.run.started", {"plan_id": plan_id})

    asyncio.run(seed())

    body = app_client.get(f"/api/planner/{plan_id}/full").json()
    assert body["runs"]["count"] == 2
    assert body["runs"]["in_flight"] == 1
    statuses = [r["status"] for r in body["runs"]["items"]]
    assert "running" in statuses
    assert "completed" in statuses


def test_full_endpoint_envelope_shape_keys(app_client):
    """Pin the top-level envelope keys so the cockpit's parser
    has a stable contract.
    """

    plan_id = _seed_plan(app_client)
    body = app_client.get(f"/api/planner/{plan_id}/full").json()

    assert set(body.keys()) == {
        "ok",
        "plan_id",
        "plan",
        "runs",
        "usage_lifetime",
    }
    assert set(body["runs"].keys()) == {"count", "in_flight", "items"}
    assert set(body["usage_lifetime"].keys()) == {
        "calls",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "latency_ms_total",
        "has_priced_models",
        "runs_aggregated",
    }
