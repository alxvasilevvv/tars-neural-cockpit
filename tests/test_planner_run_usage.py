"""Tests for the per-run usage rollup (PR #106).

Covers:

- ``_compute_run_usage`` filters ``usage.tokens`` events by
  ``trace_id`` and clamps the wall-clock window to
  ``started_at..finished_at`` so a parallel run on the same plan
  doesn't bleed in.
- Returned dict shape: ``calls`` / ``tokens_in`` / ``tokens_out``
  / ``cost_usd`` / ``latency_ms_total`` / ``has_priced_models``.
- ``cost_usd`` is ``None`` (not ``0.0``) when no priced model
  fired so the cockpit can render "n/a".
- ``PlanRunner.run`` stamps the rollup on the terminal event
  payload (``plan.completed`` / ``plan.aborted``) AND on the
  return value.
- The HTTP ``GET /api/planner/{plan_id}/runs`` reflector picks up
  the rollup via the reconstructor.
- ``trace_id=None`` short-circuits to a zero rollup.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.base import (
    ActionSpec,
    DomainManifest,
    DomainPack,
)
from backend.core.domains.registry import _REGISTRY as _DOMAIN_REGISTRY
from backend.core.domains.registry import register as _register_pack
from backend.core.planner import (
    Plan,
    PlanRunner,
    PlanStatus,
    PlanStep,
    get_planner_store,
    reconstruct_runs_async,
    reset_planner_store,
    reset_run_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)

    from backend.core.meeet import reset_client, reset_store
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


_USAGE_MANIFEST = DomainManifest(
    slug="usage_probe",
    name="Usage Probe",
    short="Used to drive the per-run usage rollup tests.",
    description="Test pack — emits a usage.tokens event from inside a step.",
    color="#67E8F9",
    capabilities=("test",),
    audience="agents",
)


def _register_usage_pack(actions: tuple[ActionSpec, ...]) -> None:
    class _UsagePack(DomainPack):
        manifest = _USAGE_MANIFEST

        def actions(self):
            return actions

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    _register_pack(_UsagePack())


@pytest.fixture()
def remove_usage_pack():
    yield
    _DOMAIN_REGISTRY.pop("usage_probe", None)


async def _seed_plan(steps: tuple[PlanStep, ...]) -> Plan:
    plan = Plan(
        id="",
        goal="usage probe",
        steps=steps,
        status=PlanStatus.PROPOSED,
        rationale="seed",
        model="heuristic-v1",
        pack_slug="usage_probe",
        thread_id="thr_usage_001",
    )
    saved = await get_planner_store().insert(plan)
    await get_planner_store().set_status(saved.id, PlanStatus.APPROVED)
    return await get_planner_store().get(saved.id)


# ---------------------------------------------------------------------------
# _compute_run_usage — pure helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_run_usage_returns_zero_when_trace_id_none():
    from backend.core.planner.runner import _compute_run_usage

    out = await _compute_run_usage(
        trace_id=None, started_at=0.0, finished_at=0.0
    )
    assert out["calls"] == 0
    assert out["tokens_in"] == 0
    assert out["tokens_out"] == 0
    assert out["cost_usd"] is None
    assert out["has_priced_models"] is False


@pytest.mark.asyncio
async def test_compute_run_usage_sums_matching_events():
    from backend.core.meeet import get_client, trace_scope
    from backend.core.planner.runner import _compute_run_usage

    import time as _time

    started = _time.time()
    with trace_scope() as tid:
        await get_client().emit(
            "usage.tokens",
            {
                "model": "anthropic/claude-3-5-sonnet-20241022",
                "tokens_in": 100,
                "tokens_out": 200,
                "latency_ms": 50.0,
                "cost_usd": 0.0033,
            },
        )
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 500,
                "tokens_out": 1000,
                "latency_ms": 75.0,
                "cost_usd": 0.0125,
            },
        )

    finished = _time.time() + 0.5
    out = await _compute_run_usage(
        trace_id=tid, started_at=started, finished_at=finished
    )
    assert out["calls"] == 2
    assert out["tokens_in"] == 600
    assert out["tokens_out"] == 1200
    assert out["latency_ms_total"] == 125.0
    assert out["has_priced_models"] is True
    assert out["cost_usd"] == pytest.approx(0.0158, rel=1e-3)


@pytest.mark.asyncio
async def test_compute_run_usage_returns_none_cost_for_unpriced_models():
    from backend.core.meeet import get_client, trace_scope
    from backend.core.planner.runner import _compute_run_usage

    import time as _time

    started = _time.time()
    with trace_scope() as tid:
        # cost_usd absent — emitter couldn't price the model.
        await get_client().emit(
            "usage.tokens",
            {
                "model": "open-source/llama-7b",
                "tokens_in": 1000,
                "tokens_out": 500,
                "latency_ms": 100.0,
            },
        )

    out = await _compute_run_usage(
        trace_id=tid,
        started_at=started,
        finished_at=_time.time() + 0.5,
    )
    assert out["calls"] == 1
    assert out["tokens_in"] == 1000
    assert out["tokens_out"] == 500
    assert out["cost_usd"] is None
    assert out["has_priced_models"] is False


@pytest.mark.asyncio
async def test_compute_run_usage_filters_by_trace_id():
    from backend.core.meeet import get_client, trace_scope
    from backend.core.planner.runner import _compute_run_usage

    import time as _time

    started = _time.time()
    # Emit one event under a DIFFERENT trace — it must be skipped.
    with trace_scope() as other_tid:
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 99999,
                "tokens_out": 99999,
                "cost_usd": 99.99,
            },
        )

    with trace_scope() as wanted_tid:
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_usd": 0.0001,
            },
        )

    finished = _time.time() + 0.5
    out = await _compute_run_usage(
        trace_id=wanted_tid, started_at=started, finished_at=finished
    )
    assert out["calls"] == 1
    assert out["tokens_in"] == 10
    assert out["tokens_out"] == 20
    assert other_tid != wanted_tid


@pytest.mark.asyncio
async def test_compute_run_usage_clamps_to_time_window():
    from backend.core.meeet import get_client, trace_scope
    from backend.core.planner.runner import _compute_run_usage

    import time as _time

    with trace_scope() as tid:
        # Event from "before" the window.
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 1000,
                "tokens_out": 1000,
                "cost_usd": 0.05,
            },
        )
        # Open the window strictly after the first event.
        await asyncio.sleep(0.05)
        window_start = _time.time()
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 5,
                "tokens_out": 5,
                "cost_usd": 0.0001,
            },
        )

    out = await _compute_run_usage(
        trace_id=tid,
        started_at=window_start,
        finished_at=_time.time() + 0.5,
    )
    assert out["calls"] == 1
    assert out["tokens_in"] == 5


# ---------------------------------------------------------------------------
# PlanRunner stamps usage on the terminal event + return value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_stamps_usage_on_completed_event(
    remove_usage_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from backend.core.meeet import get_client

    async def emit_tokens(args):
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o-mini",
                "tokens_in": 200,
                "tokens_out": 50,
                "latency_ms": 12.0,
                "cost_usd": 0.000060,
            },
        )
        return {"ok": True}

    _register_usage_pack(
        (
            ActionSpec(
                id="emit",
                name="emit",
                description="emit a usage.tokens",
                handler=emit_tokens,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(PlanStep(id="s1", action="usage_probe.emit"),)
    )
    result = await PlanRunner().run(plan.id)

    assert result["ok"] is True
    assert result["status"] == PlanStatus.COMPLETED.value
    usage = result["usage"]
    assert usage["calls"] == 1
    assert usage["tokens_in"] == 200
    assert usage["tokens_out"] == 50
    assert usage["has_priced_models"] is True
    assert usage["cost_usd"] == pytest.approx(0.000060, rel=1e-3)

    # Same numbers should land on the plan.completed event itself.
    rows = await get_client().store.list_events(
        kind="plan.completed", limit=10
    )
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["usage"]["calls"] == 1
    assert payload["usage"]["tokens_in"] == 200


@pytest.mark.asyncio
async def test_runner_stamps_usage_on_aborted_event(remove_usage_pack, monkeypatch):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from backend.core.meeet import get_client

    async def fail(args):
        # Emit usage *before* raising so the rollup still sees it.
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o-mini",
                "tokens_in": 10,
                "tokens_out": 5,
                "latency_ms": 5.0,
                "cost_usd": 0.00001,
            },
        )
        raise RuntimeError("boom")

    _register_usage_pack(
        (
            ActionSpec(
                id="fail",
                name="fail",
                description="fails after emitting usage",
                handler=fail,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(id="s1", action="usage_probe.fail", on_error="stop"),
        )
    )
    result = await PlanRunner().run(plan.id)

    assert result["ok"] is False
    assert result["status"] == PlanStatus.ABORTED.value
    usage = result["usage"]
    assert usage["calls"] == 1
    assert usage["tokens_in"] == 10
    assert usage["has_priced_models"] is True

    rows = await get_client().store.list_events(
        kind="plan.aborted", limit=10
    )
    assert len(rows) == 1
    assert rows[0].payload["usage"]["tokens_in"] == 10


@pytest.mark.asyncio
async def test_runner_zero_usage_when_no_tokens_event(
    remove_usage_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    async def silent(args):
        return {"ok": True}

    _register_usage_pack(
        (
            ActionSpec(
                id="silent",
                name="silent",
                description="no usage events",
                handler=silent,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(PlanStep(id="s1", action="usage_probe.silent"),)
    )
    result = await PlanRunner().run(plan.id)
    usage = result["usage"]
    assert usage["calls"] == 0
    assert usage["tokens_in"] == 0
    assert usage["tokens_out"] == 0
    assert usage["cost_usd"] is None
    assert usage["has_priced_models"] is False


# ---------------------------------------------------------------------------
# Reconstructor surfaces usage on PlanRun + /runs HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconstructor_surfaces_usage_block(
    remove_usage_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from backend.core.meeet import get_client

    async def emit_tokens(args):
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o",
                "tokens_in": 500,
                "tokens_out": 100,
                "latency_ms": 30.0,
                "cost_usd": 0.0021,
            },
        )
        return {"ok": True}

    _register_usage_pack(
        (
            ActionSpec(
                id="emit",
                name="emit",
                description="emit usage",
                handler=emit_tokens,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(PlanStep(id="s1", action="usage_probe.emit"),)
    )
    await PlanRunner().run(plan.id)

    runs = await reconstruct_runs_async(plan.id)
    assert len(runs) == 1
    run_dict = runs[0].to_dict()
    usage = run_dict["usage"]
    assert usage["calls"] == 1
    assert usage["tokens_in"] == 500
    assert usage["tokens_out"] == 100
    assert usage["has_priced_models"] is True
    assert usage["cost_usd"] == pytest.approx(0.0021, rel=1e-3)
    assert usage["latency_ms_total"] == 30.0


@pytest.mark.asyncio
async def test_reconstructor_handles_missing_usage_block_gracefully():
    """Older terminal events written before this PR landed lacked
    the ``usage`` key. The reconstructor must default to a zero
    rollup with ``cost_usd=None`` rather than crashing."""

    from backend.core.meeet import get_client

    plan_id = "pln_legacy"
    await get_client().emit(
        "plan.run.started", {"plan_id": plan_id, "mode": "autopilot"}
    )
    await get_client().emit(
        "plan.completed",
        {"plan_id": plan_id, "ok": True, "steps_run": 1},
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    usage = runs[0].to_dict()["usage"]
    assert usage["calls"] == 0
    assert usage["cost_usd"] is None
    assert usage["has_priced_models"] is False


def test_http_runs_endpoint_includes_usage_block(monkeypatch):
    """End-to-end: POST a plan, run it, GET /runs — usage block on
    the returned run should match what the runner stamped."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.core.meeet import get_client
    from web_extras.routers.planner import router

    async def emit_tokens(args):
        await get_client().emit(
            "usage.tokens",
            {
                "model": "anthropic/claude-3-5-haiku",
                "tokens_in": 1000,
                "tokens_out": 500,
                "latency_ms": 80.0,
                "cost_usd": 0.0028,
            },
        )
        return {"ok": True}

    _register_usage_pack(
        (
            ActionSpec(
                id="emit",
                name="emit",
                description="emit usage",
                handler=emit_tokens,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )
    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Synthesize via the public plan endpoint.
        resp = client.post(
            "/api/planner/plan",
            json={"goal": "usage_probe.emit", "pinned_pack": "usage_probe"},
        )
        assert resp.status_code == 200, resp.text
        plan_id = resp.json()["plan"]["id"]

        # Approve so the runner will accept it.
        approve = client.post(
            f"/api/planner/{plan_id}/status", json={"status": "approved"}
        )
        assert approve.status_code == 200, approve.text

        # Run.
        run = client.post(f"/api/planner/{plan_id}/run")
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["ok"] is True
        run_usage = body["run"]["usage"]
        assert run_usage["tokens_in"] == 1000

        # And the reconstructor reflects it.
        runs = client.get(f"/api/planner/{plan_id}/runs")
        assert runs.status_code == 200
        runs_body = runs.json()
        assert runs_body["count"] == 1
        usage = runs_body["runs"][0]["usage"]
        assert usage["calls"] == 1
        assert usage["tokens_in"] == 1000
        assert usage["tokens_out"] == 500
        assert usage["has_priced_models"] is True
        assert usage["cost_usd"] == pytest.approx(0.0028, rel=1e-3)
    finally:
        _DOMAIN_REGISTRY.pop("usage_probe", None)
