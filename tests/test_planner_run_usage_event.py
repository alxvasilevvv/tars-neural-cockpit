"""Tests for the dedicated ``plan.run.usage`` event.

The runner now emits a standalone ``plan.run.usage`` event right
before the terminal ``plan.completed`` / ``plan.aborted`` event.
This lets billing dashboards do a cheap
``SELECT * FROM events WHERE kind='plan.run.usage'`` query
without parsing the heavier terminal payload, and gives the
cockpit a single canonical "cost record" per run.

Contract pinned here:

- One ``plan.run.usage`` per run, regardless of terminal status.
- Carries ``plan_id``, ``status`` (matches the upcoming
  terminal status, ``"completed"`` or ``"aborted"``),
  ``parent_trace_id`` (plan's birth trace), and the same
  ``usage`` block (calls / tokens / cost / latency) that travels
  on the terminal event.
- The ``usage`` block on ``plan.run.usage`` is identical to the
  one on the terminal event (same source, copied verbatim).
- The event inherits the per-run ``trace_id`` from the
  enclosing ``trace_scope`` so it groups with the rest of the
  run by trace.
- Wired into the planner SSE allow-list and the timeline
  summariser so cockpit consumers pick it up.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.base import ActionSpec, DomainManifest, DomainPack
from backend.core.domains.registry import _REGISTRY, register
from backend.core.planner import Plan, PlanStatus, PlanStep


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

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
def remove_probe_pack():
    yield
    _REGISTRY.pop("usage_probe", None)


_PROBE_MANIFEST = DomainManifest(
    slug="usage_probe",
    name="Usage Probe",
    short="Test pack to assert plan.run.usage event semantics.",
    description="No-op + boom actions for usage event tests.",
    color="#67E8F9",
    capabilities=("test",),
    audience="agents",
)


def _register_probe_pack(actions: tuple[ActionSpec, ...]) -> None:
    class _Pack(DomainPack):
        manifest = _PROBE_MANIFEST

        def actions(self):  # type: ignore[override]
            return actions

        def awareness(self):  # type: ignore[override]
            return ()

        def system_prompt(self) -> str:  # type: ignore[override]
            return ""

    register(_Pack())


async def _seed_approved_plan(
    *, steps: tuple[PlanStep, ...], thread_id: str = "thr_usage_event"
) -> Plan:
    from backend.core.planner import get_planner_store
    

    plan = Plan(
        id="",
        goal="probe",
        steps=steps,
        status=PlanStatus.PROPOSED,
        rationale="probe",
        model="heuristic-v1",
        pack_slug="usage_probe",
        playbook_id=None,
        thread_id=thread_id,
        trace_id="trc_plan_birth",
    )
    saved = await get_planner_store().insert(plan)
    await get_planner_store().set_status(saved.id, PlanStatus.APPROVED)
    return await get_planner_store().get(saved.id)


async def _events(kind: str | None = None) -> list[dict[str, Any]]:
    from backend.core.meeet import get_store

    rows = await get_store().list_events(limit=200, kind=kind)
    return [
        {"kind": r.kind, "payload": r.payload, "trace_id": r.trace_id}
        for r in rows
    ]


@pytest.mark.asyncio
async def test_runner_emits_plan_run_usage_on_completion(remove_probe_pack):
    from backend.core.planner.runner import PlanRunner

    async def noop(_args):
        return {"ok": True}

    _register_probe_pack(
        (ActionSpec(id="noop", name="noop", description="", handler=noop),)
    )

    plan = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="usage_probe.noop"),)
    )
    result = await PlanRunner().run(plan.id)
    assert result["status"] == "completed"

    rows = await _events(kind="plan.run.usage")
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["plan_id"] == plan.id
    assert payload["status"] == "completed"
    assert payload["parent_trace_id"] == "trc_plan_birth"
    assert "usage" in payload
    usage = payload["usage"]
    # Schema check — the rollup keys downstream consumers depend on.
    for key in (
        "calls",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "latency_ms_total",
        "has_priced_models",
    ):
        assert key in usage, f"usage block missing key {key!r}"


@pytest.mark.asyncio
async def test_runner_emits_plan_run_usage_on_abort(remove_probe_pack):
    from backend.core.planner.runner import PlanRunner

    async def boom(_args):
        raise RuntimeError("boom")

    _register_probe_pack(
        (ActionSpec(id="boom", name="boom", description="", handler=boom),)
    )

    plan = await _seed_approved_plan(
        steps=(
            PlanStep(
                id="s1",
                action="usage_probe.boom",
                on_error="stop",
            ),
        )
    )
    result = await PlanRunner().run(plan.id)
    assert result["status"] == "aborted"

    rows = await _events(kind="plan.run.usage")
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["status"] == "aborted"
    assert payload["plan_id"] == plan.id
    assert payload["parent_trace_id"] == "trc_plan_birth"
    assert "usage" in payload


@pytest.mark.asyncio
async def test_plan_run_usage_block_matches_terminal_event(remove_probe_pack):
    """The usage block on ``plan.run.usage`` is the exact same
    object the terminal event ships, so consumers that read either
    one see identical numbers.
    """

    from backend.core.planner.runner import PlanRunner

    async def noop(_args):
        return {"ok": True}

    _register_probe_pack(
        (ActionSpec(id="noop", name="noop", description="", handler=noop),)
    )

    plan = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="usage_probe.noop"),)
    )
    await PlanRunner().run(plan.id)

    usage_rows = await _events(kind="plan.run.usage")
    completed_rows = await _events(kind="plan.completed")
    assert len(usage_rows) == 1 and len(completed_rows) == 1
    assert usage_rows[0]["payload"]["usage"] == completed_rows[0]["payload"]["usage"]


@pytest.mark.asyncio
async def test_plan_run_usage_inherits_run_trace(remove_probe_pack):
    """The dedicated rollup event lives on the run's trace, NOT
    the plan's birth trace, so trace-scoped queries still work.
    """

    from backend.core.planner.runner import PlanRunner

    async def noop(_args):
        return {"ok": True}

    _register_probe_pack(
        (ActionSpec(id="noop", name="noop", description="", handler=noop),)
    )

    plan = await _seed_approved_plan(
        steps=(PlanStep(id="s1", action="usage_probe.noop"),)
    )
    result = await PlanRunner().run(plan.id)
    run_trace = result["trace_id"]

    usage_rows = await _events(kind="plan.run.usage")
    started_rows = await _events(kind="plan.run.started")
    assert usage_rows[0]["trace_id"] == run_trace
    assert started_rows[0]["trace_id"] == run_trace
    assert run_trace != "trc_plan_birth"


def test_planner_sse_allowlist_includes_plan_run_usage():
    from web_extras.routers.planner import _PLAN_EVENT_KINDS

    assert "plan.run.usage" in _PLAN_EVENT_KINDS


def test_timeline_relevant_kinds_include_plan_run_usage():
    from backend.core.search.timeline import _RELEVANT_EVENT_KINDS

    assert "plan.run.usage" in _RELEVANT_EVENT_KINDS


def test_timeline_summarises_plan_run_usage_with_priced_model():
    from backend.core.search.timeline import _summarise_event

    summary = _summarise_event(
        "plan.run.usage",
        {
            "plan_id": "pln_x",
            "status": "completed",
            "usage": {
                "calls": 3,
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_usd": 0.0123,
                "latency_ms_total": 12.0,
                "has_priced_models": True,
            },
        },
    )
    assert "plan=pln_x" in summary
    assert "status=completed" in summary
    assert "calls=3" in summary
    assert "tokens=100+200" in summary
    assert "cost=$0.0123" in summary


def test_timeline_summarises_plan_run_usage_unpriced_as_na():
    from backend.core.search.timeline import _summarise_event

    summary = _summarise_event(
        "plan.run.usage",
        {
            "plan_id": "pln_y",
            "status": "aborted",
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
    assert "cost=n/a" in summary
    assert "status=aborted" in summary
