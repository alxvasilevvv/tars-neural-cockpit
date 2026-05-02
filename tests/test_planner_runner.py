"""Tests for the planner runner (PR #102 — L6.2).

Covers:

- ``PlanRunRegistry`` primitives (register / abort / is_running).
- ``PlanRunner.run`` happy path: status transitions ``approved →
  running → completed``, ``plan.run.started`` /
  ``plan.step.requested`` / ``plan.step.allowed`` /
  ``plan.step.completed`` / ``plan.completed`` events emitted in
  order, with ``thread_id`` auto-injection from the persisted plan.
- ``PlanRunner.run`` refuses to enter a non-approved plan
  (``plan_not_runnable``), an unknown plan (``plan_not_found``),
  or a plan that is already running (``plan_already_running``).
- Cooperative abort: setting the abort event between groups stops
  subsequent steps and flips status to ``aborted`` with reason
  ``operator_abort``.
- Step failure with ``on_error="stop"`` aborts the run; with
  ``on_error="continue"`` the run carries on.
- Policy gate blocking (destructive action in ``confirm`` mode)
  marks the run aborted with reason ``blocked_by_policy`` and
  emits ``plan.step.allowed{allowed=false}``.
- HTTP surface: ``POST /api/planner/{id}/run`` happy path (200,
  events emitted, status persisted), ``404`` for unknown plan,
  ``409`` for plans not in ``approved`` state, plus
  ``POST /api/planner/{id}/abort`` happy path + ``404`` when the
  plan isn't running.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.domains.base import (
    ActionSpec,
    DomainManifest,
    DomainPack,
)
from backend.core.domains.registry import _REGISTRY as _DOMAIN_REGISTRY
from backend.core.domains.registry import register as _register_pack
from backend.core.planner import (
    Plan,
    PlanRunError,
    PlanRunRegistry,
    PlanRunner,
    PlanStatus,
    PlanStep,
    get_planner_store,
    get_run_registry,
    reset_planner_store,
    reset_run_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    """Per-test isolated SQLite stores + meeet client."""

    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.delenv("PLANNER_STORE", raising=False)

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


# ---------------------------------------------------------------------------
# Probe domain pack — supplies the actions the runner dispatches
# ---------------------------------------------------------------------------


_PROBE_MANIFEST = DomainManifest(
    slug="run_probe",
    name="Run Probe",
    short="Test pack used to drive PlanRunner.",
    description="Test-only — registered fresh per test.",
    color="#67E8F9",
    capabilities=("test",),
    audience="agents",
)


def _register_probe_pack(actions: tuple[ActionSpec, ...]) -> None:
    class _ProbePack(DomainPack):
        manifest = _PROBE_MANIFEST

        def actions(self):
            return actions

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    _register_pack(_ProbePack())


@pytest.fixture()
def remove_probe_pack():
    yield
    _DOMAIN_REGISTRY.pop("run_probe", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _aevents(kind: str | None = None) -> list[dict[str, Any]]:
    """Read meeet events from inside an async test (no asyncio.run)."""

    from backend.core.meeet import get_client

    rows = await get_client().store.list_events(kind=kind, limit=500)
    return [{"kind": r.kind, "payload": r.payload} for r in rows]


def _events(kind: str | None = None) -> list[dict[str, Any]]:
    """Read meeet events from inside a sync test."""

    from backend.core.meeet import get_client

    rows = asyncio.run(
        get_client().store.list_events(kind=kind, limit=500)
    )
    return [{"kind": r.kind, "payload": r.payload} for r in rows]


async def _seed_plan(
    *,
    steps: tuple[PlanStep, ...],
    status: PlanStatus = PlanStatus.APPROVED,
    thread_id: str | None = "thr_runner_001",
) -> Plan:
    plan = Plan(
        id="",
        goal="run probe",
        steps=steps,
        status=PlanStatus.PROPOSED,
        rationale="seed",
        model="heuristic-v1",
        pack_slug="run_probe",
        thread_id=thread_id,
    )
    saved = await get_planner_store().insert(plan)
    if status != PlanStatus.PROPOSED:
        await get_planner_store().set_status(saved.id, status)
    return await get_planner_store().get(saved.id)


# ---------------------------------------------------------------------------
# PlanRunRegistry
# ---------------------------------------------------------------------------


def test_run_registry_register_and_abort_lifecycle() -> None:
    reg = PlanRunRegistry()
    assert reg.is_running("pln_a") is False
    ev = reg.register("pln_a")
    assert reg.is_running("pln_a") is True
    assert ev.is_set() is False
    flipped = reg.abort("pln_a")
    assert flipped is True
    assert ev.is_set() is True


def test_run_registry_abort_unknown_returns_false() -> None:
    reg = PlanRunRegistry()
    assert reg.abort("pln_does_not_exist") is False


def test_run_registry_unregister_removes_event() -> None:
    reg = PlanRunRegistry()
    reg.register("pln_a")
    reg.unregister("pln_a")
    assert reg.is_running("pln_a") is False
    assert reg.abort("pln_a") is False


def test_run_registry_in_flight_returns_keys() -> None:
    reg = PlanRunRegistry()
    reg.register("pln_a")
    reg.register("pln_b")
    assert set(reg.in_flight()) == {"pln_a", "pln_b"}


# ---------------------------------------------------------------------------
# PlanRunner — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_happy_path_completes_and_emits_events(
    remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    calls: list[dict[str, Any]] = []

    async def echo(args):
        calls.append(dict(args))
        return {"ok": True, "echoed": dict(args)}

    spec = ActionSpec(
        id="echo",
        name="Echo",
        description="Test echo action.",
        handler=echo,
        schema={"type": "object", "properties": {}},
        destructive=False,
    )
    _register_probe_pack((spec,))

    plan = await _seed_plan(
        steps=(PlanStep(id="step-1", action="run_probe.echo"),),
    )

    result = await PlanRunner().run(plan.id)
    assert result["ok"] is True
    assert result["status"] == PlanStatus.COMPLETED.value
    assert len(calls) == 1

    refreshed = await get_planner_store().get(plan.id)
    assert refreshed.status == PlanStatus.COMPLETED
    assert refreshed.error is None

    # Events: every plan.* family, in the right order, all stamped
    # with the persisted thread_id thanks to thread_id_scope.
    # ``list_events`` returns newest-first, so reverse for the
    # emission sequence.
    plan_events = list(reversed(await _aevents()))
    kinds_in_order = [
        e["kind"] for e in plan_events if e["kind"].startswith("plan.")
    ]
    assert kinds_in_order == [
        "plan.run.started",
        "plan.step.requested",
        "plan.step.allowed",
        "plan.step.completed",
        "plan.completed",
    ]
    for ev in plan_events:
        if ev["kind"].startswith("plan."):
            assert ev["payload"].get("thread_id") == "thr_runner_001"
            assert ev["payload"].get("plan_id") == plan.id


@pytest.mark.asyncio
async def test_run_passes_args_to_handler(remove_probe_pack, monkeypatch):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    seen: dict[str, Any] = {}

    async def capture(args):
        seen.update(args)
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="capture",
                name="capture",
                description="d",
                handler=capture,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(
                id="step-1",
                action="run_probe.capture",
                args={"hello": "world", "n": 3},
            ),
        ),
    )

    await PlanRunner().run(plan.id)
    assert seen == {"hello": "world", "n": 3}


# ---------------------------------------------------------------------------
# PlanRunner — entry guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_unknown_plan_id_raises_plan_not_found():
    with pytest.raises(PlanRunError) as exc:
        await PlanRunner().run("pln_does_not_exist")
    assert exc.value.reason == "plan_not_found"


@pytest.mark.asyncio
async def test_run_proposed_plan_raises_plan_not_runnable(remove_probe_pack):
    _register_probe_pack(())
    plan = await _seed_plan(
        steps=(PlanStep(id="s", action="run_probe.noop"),),
        status=PlanStatus.PROPOSED,
    )
    with pytest.raises(PlanRunError) as exc:
        await PlanRunner().run(plan.id)
    assert exc.value.reason == "plan_not_runnable"


@pytest.mark.asyncio
async def test_run_completed_plan_raises_plan_not_runnable(remove_probe_pack):
    _register_probe_pack(())
    plan = await _seed_plan(
        steps=(PlanStep(id="s", action="run_probe.noop"),),
        status=PlanStatus.COMPLETED,
    )
    with pytest.raises(PlanRunError) as exc:
        await PlanRunner().run(plan.id)
    assert exc.value.reason == "plan_not_runnable"


@pytest.mark.asyncio
async def test_run_already_running_raises(remove_probe_pack):
    _register_probe_pack(())
    plan = await _seed_plan(
        steps=(PlanStep(id="s", action="run_probe.noop"),),
        status=PlanStatus.APPROVED,
    )
    # Pretend it's already in flight.
    get_run_registry().register(plan.id)
    try:
        with pytest.raises(PlanRunError) as exc:
            await PlanRunner().run(plan.id)
        assert exc.value.reason == "plan_already_running"
    finally:
        get_run_registry().unregister(plan.id)


# ---------------------------------------------------------------------------
# Step failure semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step_failure_stop_marks_plan_aborted(
    remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    async def boom(args):
        raise RuntimeError("intentional failure")

    async def ok(args):
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="boom",
                name="boom",
                description="d",
                handler=boom,
                schema={"type": "object"},
                destructive=False,
            ),
            ActionSpec(
                id="ok",
                name="ok",
                description="d",
                handler=ok,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(id="boom", action="run_probe.boom", on_error="stop"),
            PlanStep(id="ok", action="run_probe.ok"),
        ),
    )

    result = await PlanRunner().run(plan.id)
    assert result["ok"] is False
    assert result["status"] == PlanStatus.ABORTED.value

    refreshed = await get_planner_store().get(plan.id)
    assert refreshed.status == PlanStatus.ABORTED
    assert refreshed.error == "step_failed"

    aborted_events = await _aevents("plan.aborted")
    assert aborted_events
    payload = aborted_events[0]["payload"]
    assert payload["reason"] == "step_failed"
    assert payload["steps_failed"] == 1


@pytest.mark.asyncio
async def test_step_failure_continue_runs_subsequent_steps(
    remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    invoked: list[str] = []

    async def boom(args):
        invoked.append("boom")
        raise RuntimeError("ignored")

    async def good(args):
        invoked.append("good")
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="boom",
                name="boom",
                description="d",
                handler=boom,
                schema={"type": "object"},
                destructive=False,
            ),
            ActionSpec(
                id="good",
                name="good",
                description="d",
                handler=good,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(id="boom", action="run_probe.boom", on_error="continue"),
            PlanStep(id="good", action="run_probe.good"),
        ),
    )

    result = await PlanRunner().run(plan.id)
    # The plan completed all groups, but ok=False because at least
    # one step errored.
    assert result["status"] == PlanStatus.COMPLETED.value
    assert invoked == ["boom", "good"]


# ---------------------------------------------------------------------------
# Policy gate blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_destructive_step_in_confirm_mode_blocks_and_aborts(
    remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    async def destructive(args):
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="destructive",
                name="destructive",
                description="d",
                handler=destructive,
                schema={"type": "object"},
                destructive=True,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(PlanStep(id="d", action="run_probe.destructive"),),
    )

    result = await PlanRunner().run(plan.id)
    assert result["ok"] is False
    assert result["status"] == PlanStatus.ABORTED.value

    refreshed = await get_planner_store().get(plan.id)
    assert refreshed.status == PlanStatus.ABORTED
    assert refreshed.error == "blocked_by_policy"

    allowed_events = await _aevents("plan.step.allowed")
    assert allowed_events
    assert allowed_events[0]["payload"]["allowed"] is False
    assert allowed_events[0]["payload"]["reason"] == "blocked_by_policy"


# ---------------------------------------------------------------------------
# Cooperative abort via the registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_abort_set_before_run_skips_all_steps(
    remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    invoked: list[str] = []

    async def good(args):
        invoked.append("ran")
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="good",
                name="good",
                description="d",
                handler=good,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(id="a", action="run_probe.good"),
            PlanStep(id="b", action="run_probe.good"),
        ),
    )

    runner = PlanRunner()

    # Patch the registry so we can pre-flip the abort event before
    # the runner enters its group loop.
    real_registry = get_run_registry()

    class _PreAbortRegistry(PlanRunRegistry):
        def register(self, plan_id):
            ev = super().register(plan_id)
            ev.set()  # already aborted before any group runs
            return ev

    runner.registry = _PreAbortRegistry()

    result = await runner.run(plan.id)
    assert result["status"] == PlanStatus.ABORTED.value
    assert invoked == []

    refreshed = await get_planner_store().get(plan.id)
    assert refreshed.status == PlanStatus.ABORTED
    assert refreshed.error == "operator_abort"


@pytest.mark.asyncio
async def test_abort_set_between_groups_stops_remainder(
    remove_probe_pack, monkeypatch
):
    """Abort fired during a step is observed at the next group
    boundary, so the second step never runs."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    invoked: list[str] = []

    async def first(args):
        invoked.append("first")
        # Fire abort while the first step is mid-flight.
        get_run_registry().abort(_PLAN_ID["id"])
        return {"ok": True}

    async def second(args):
        invoked.append("second")
        return {"ok": True}

    _register_probe_pack(
        (
            ActionSpec(
                id="first",
                name="first",
                description="d",
                handler=first,
                schema={"type": "object"},
                destructive=False,
            ),
            ActionSpec(
                id="second",
                name="second",
                description="d",
                handler=second,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_plan(
        steps=(
            PlanStep(id="a", action="run_probe.first"),
            PlanStep(id="b", action="run_probe.second"),
        ),
    )
    _PLAN_ID["id"] = plan.id

    result = await PlanRunner().run(plan.id)
    assert result["status"] == PlanStatus.ABORTED.value
    assert invoked == ["first"]

    refreshed = await get_planner_store().get(plan.id)
    assert refreshed.status == PlanStatus.ABORTED
    assert refreshed.error == "operator_abort"


# Module-level holder so the in-handler closure can read the active plan id
# without breaking the dataclass-frozen handler signature.
_PLAN_ID: dict[str, str] = {"id": ""}


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_http_run_404_for_unknown_plan(app_client):
    resp = app_client.post("/api/planner/pln_does_not_exist/run", json={})
    assert resp.status_code == 404
    # The router 404s on the pre-flight ``store.get`` so ``detail`` is
    # a plain string here (the ``PlanRunError`` envelope is reserved
    # for runner-level errors).
    assert resp.json()["detail"] == "plan_not_found"


def test_http_run_409_when_plan_not_approved(app_client):
    created = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
    )
    plan_id = created.json()["plan"]["id"]
    # Still 'proposed' — must 409.
    resp = app_client.post(f"/api/planner/{plan_id}/run", json={})
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason"] == "plan_not_runnable"


def test_http_run_happy_path_emits_plan_completed(
    app_client, remove_probe_pack, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    async def good(args):
        return {"ok": True, "echo": dict(args)}

    _register_probe_pack(
        (
            ActionSpec(
                id="good",
                name="good",
                description="d",
                handler=good,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    # Seed the plan via the store so we don't depend on the
    # synthesizer matching "run_probe" (the synthesizer only knows
    # registered packs at HTTP-call time, but registering above is
    # enough for the in-process runner to dispatch).
    plan = asyncio.run(
        _seed_plan(
            steps=(PlanStep(id="step-1", action="run_probe.good"),),
        )
    )

    resp = app_client.post(
        f"/api/planner/{plan.id}/run",
        json={},
        headers={"x-tars-policy-mode": "autopilot"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["run"]["status"] == PlanStatus.COMPLETED.value

    completed = _events("plan.completed")
    assert completed
    assert completed[0]["payload"]["plan_id"] == plan.id


def test_http_abort_404_when_plan_not_running(app_client):
    resp = app_client.post("/api/planner/pln_does_not_exist/abort")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_running"


def test_http_abort_flips_event_for_in_flight_plan(app_client):
    # Pretend a plan is already in flight by registering it directly.
    plan_id = "pln_inflight_001"
    get_run_registry().register(plan_id)
    try:
        resp = app_client.post(f"/api/planner/{plan_id}/abort")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["plan_id"] == plan_id
    finally:
        get_run_registry().unregister(plan_id)

    abort_events = _events("plan.abort.requested")
    assert abort_events
    assert abort_events[0]["payload"]["plan_id"] == plan_id


def test_http_create_plan_emits_plan_proposed(app_client):
    resp = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
        headers={"x-tars-thread-id": "thr_proposed_001"},
    )
    assert resp.status_code == 200, resp.text
    plan_id = resp.json()["plan"]["id"]

    proposed = _events("plan.proposed")
    assert proposed
    assert proposed[0]["payload"]["plan_id"] == plan_id
    # thread_id auto-injected via the meeet client (PR #100).
    assert proposed[0]["payload"].get("thread_id") == "thr_proposed_001"
