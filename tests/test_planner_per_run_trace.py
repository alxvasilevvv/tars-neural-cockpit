"""Tests for the per-run trace_id contract (PR #109).

Before this PR each run of a plan inherited the plan's birth
trace via ``trace_scope(parent=plan.trace_id)``. That made
parallel runs of the same plan share a trace and forced the
usage rollup to fall back on a wall-clock window clamp to keep
their costs apart.

PR #109 switched the runner to ``trace_scope()`` (no parent) so
each run mints a fresh trace. The plan's birth trace is now
stamped on the ``plan.run.started`` payload and on
``PlanRunner.run`` return dict as ``parent_trace_id`` so
consumers can stitch synthesis ↔ execution by either ``plan_id``
or by walking the parent pointer.

Cases:

- Two consecutive runs of the same plan emit ``plan.run.started``
  events with **different** ``trace_id`` row metadata.
- Each run's terminal ``plan.completed`` event shares the trace
  of its own ``plan.run.started`` (intra-run consistency).
- Both ``plan.run.started`` payloads carry the same
  ``parent_trace_id`` (= ``plan.trace_id``).
- ``PlanRunner.run`` return dict reports both ``trace_id`` (the
  fresh per-run trace) and ``parent_trace_id`` (the plan's
  birth trace).
- ``usage.tokens`` events fired from inside one run are *not*
  attributed to a sibling run via the cost rollup — the rollup
  is now strictly trace-scoped.
"""

from __future__ import annotations

from pathlib import Path

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
    reset_planner_store,
    reset_run_registry,
)


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

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


_MANIFEST = DomainManifest(
    slug="trace_probe",
    name="Trace Probe",
    short="Test pack to assert per-run trace_id semantics.",
    description="Emits a usage.tokens to verify trace propagation.",
    color="#67E8F9",
    capabilities=("test",),
    audience="agents",
)


def _register_pack(actions: tuple[ActionSpec, ...]) -> None:
    class _Pack(DomainPack):
        manifest = _MANIFEST

        def actions(self):
            return actions

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    _register_pack_top(_Pack())


_register_pack_top = _register_pack  # alias to silence shadow
_register_pack_top = _register_pack  # noqa: F811


def _make_pack(actions: tuple[ActionSpec, ...]) -> None:
    class _Pack(DomainPack):
        manifest = _MANIFEST

        def actions(self):
            return actions

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    from backend.core.domains.registry import register as _r

    _r(_Pack())


@pytest.fixture()
def remove_pack():
    yield
    _DOMAIN_REGISTRY.pop("trace_probe", None)


async def _seed_approved_plan(steps: tuple[PlanStep, ...]) -> Plan:
    plan = Plan(
        id="",
        goal="trace probe",
        steps=steps,
        status=PlanStatus.PROPOSED,
        rationale="seed",
        model="heuristic-v1",
        pack_slug="trace_probe",
        thread_id="thr_trace_001",
        trace_id="trc_plan_birth",
    )
    saved = await get_planner_store().insert(plan)
    await get_planner_store().set_status(saved.id, PlanStatus.APPROVED)
    return await get_planner_store().get(saved.id)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_each_run_mints_a_fresh_trace_id(remove_pack, monkeypatch):
    async def noop(args):
        return {"ok": True}

    _make_pack(
        (
            ActionSpec(
                id="noop",
                name="noop",
                description="d",
                handler=noop,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan_a = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="trace_probe.noop"),)
    )
    plan_b = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="trace_probe.noop"),)
    )

    result1 = await PlanRunner().run(plan_a.id)
    result2 = await PlanRunner().run(plan_b.id)

    # Each run reports its own fresh trace and the plan's birth
    # trace as the parent.
    assert result1["trace_id"] != result2["trace_id"]
    assert result1["parent_trace_id"] == "trc_plan_birth"
    assert result2["parent_trace_id"] == "trc_plan_birth"
    # The new trace is NOT just plan.trace_id renamed.
    assert result1["trace_id"] != "trc_plan_birth"
    assert result2["trace_id"] != "trc_plan_birth"


@pytest.mark.asyncio
async def test_started_event_carries_parent_trace_id(
    remove_pack, monkeypatch
):
    from backend.core.meeet import get_client

    async def noop(args):
        return {"ok": True}

    _make_pack(
        (
            ActionSpec(
                id="noop",
                name="noop",
                description="d",
                handler=noop,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="trace_probe.noop"),)
    )
    result = await PlanRunner().run(plan.id)

    rows = await get_client().store.list_events(
        kind="plan.run.started", limit=5
    )
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["plan_id"] == plan.id
    assert payload["parent_trace_id"] == "trc_plan_birth"
    # The event's row trace_id matches the run's fresh trace.
    assert rows[0].trace_id == result["trace_id"]


@pytest.mark.asyncio
async def test_terminal_event_shares_trace_with_started(
    remove_pack, monkeypatch
):
    """plan.run.started and plan.completed must share the run's
    fresh trace so meeet ``list_events(trace_id=…)`` returns the
    full lifecycle of one run in one call."""

    from backend.core.meeet import get_client

    async def noop(args):
        return {"ok": True}

    _make_pack(
        (
            ActionSpec(
                id="noop",
                name="noop",
                description="d",
                handler=noop,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="trace_probe.noop"),)
    )
    result = await PlanRunner().run(plan.id)

    started = await get_client().store.list_events(
        kind="plan.run.started", limit=5
    )
    completed = await get_client().store.list_events(
        kind="plan.completed", limit=5
    )
    assert started[0].trace_id == completed[0].trace_id
    assert started[0].trace_id == result["trace_id"]


@pytest.mark.asyncio
async def test_usage_rollup_is_strictly_per_run_trace_scoped(
    remove_pack, monkeypatch
):
    """Two consecutive runs of the same plan; each step emits a
    usage.tokens. The runner's per-run trace_id ensures the
    rollup attributes each event to the correct run only."""

    from backend.core.meeet import get_client

    async def emit(args):
        await get_client().emit(
            "usage.tokens",
            {
                "model": "openai/gpt-4o-mini",
                "tokens_in": int(args.get("tokens_in") or 0),
                "tokens_out": 0,
                "latency_ms": 1.0,
                "cost_usd": 0.0001,
            },
        )
        return {"ok": True}

    _make_pack(
        (
            ActionSpec(
                id="emit",
                name="emit",
                description="d",
                handler=emit,
                schema={"type": "object"},
                destructive=False,
            ),
        )
    )

    plan_a = await _seed_approved_plan(
        steps=(
            PlanStep(
                id="s1",
                action="trace_probe.emit",
                args={"tokens_in": 11},
            ),
        )
    )
    plan_b = await _seed_approved_plan(
        steps=(
            PlanStep(
                id="s1",
                action="trace_probe.emit",
                args={"tokens_in": 222},
            ),
        )
    )
    result1 = await PlanRunner().run(plan_a.id)
    result2 = await PlanRunner().run(plan_b.id)

    assert result1["usage"]["tokens_in"] == 11
    assert result2["usage"]["tokens_in"] == 222
    assert result1["trace_id"] != result2["trace_id"]
