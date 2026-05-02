"""Tests for the planner synthesis + persistence layer.

Pre-PR: nothing existed. This module pins:

- ``Plan`` / ``PlanStep`` / ``PlanStatus`` dataclass round-trip.
- ``PlannerStore`` CRUD + status transitions + terminal lock.
- ``synthesize_plan(...)`` deterministic resolution priority
  (playbook → action → pack-fallback → no_match).
- HTTP surface: ``POST /api/planner/plan`` (success + every error
  reason), ``GET /api/planner/{id}``, ``GET /api/planner`` (incl.
  filters), ``GET /api/planner/_stats``,
  ``POST /api/planner/{id}/status`` (operator transitions),
  ``DELETE /api/planner/{id}`` + matching meeet event emissions.
- ``thread_id`` linkage end-to-end (header → store row → emitted
  events) so plan rows surface in the per-thread audit lane.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.planner import (
    Plan,
    PlannerError,
    PlannerStore,
    PlannerSynthesisRequest,
    PlanStatus,
    PlanStep,
    synthesize_plan,
)


@pytest.fixture(autouse=True)
def isolated_planner_db(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.delenv("PLANNER_STORE", raising=False)
    from backend.core.meeet import reset_client, reset_store
    from backend.core.planner import store as planner_store_mod

    reset_store()
    reset_client()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)
    yield
    reset_store()
    reset_client()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------------
# Fixtures: synthetic playbooks + actions to keep tests deterministic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeStep:
    id: str
    action: str
    args: dict
    store_as: str | None = None
    when: str | None = None
    on_error: str = "stop"
    parallel: bool = False


@dataclass(frozen=True)
class _FakePlaybook:
    id: str
    name: str
    description: str
    steps: tuple
    pack: str | None = None
    tags: tuple = ()
    on_block: str = "stop"


_PB_MORNING = _FakePlaybook(
    id="traders.morning_check",
    name="Traders morning check",
    description="Three-step morning routine.",
    steps=(
        _FakeStep(
            id="market",
            action="traders.summarize_market",
            args={"basket": ["BTC", "ETH"]},
            store_as="market",
        ),
        _FakeStep(
            id="news",
            action="traders.awareness.news_feed.snapshot",
            args={},
            store_as="news",
        ),
    ),
    pack="traders",
    tags=("morning", "routine"),
)


_AVAILABLE_ACTIONS = (
    # (slug, action_id, destructive, is_snapshot)
    ("traders", "summarize_market", False, True),
    ("traders", "place_alert", True, False),
    ("traders", "list_alerts", False, True),
    ("business", "kpi_snapshot", False, True),
    ("business", "log_deal", True, False),
)


# ---------------------------------------------------------------------------
# Plan / PlanStep / PlanStatus
# ---------------------------------------------------------------------------


def test_plan_status_terminal_set() -> None:
    terminal = PlanStatus.terminal()
    assert PlanStatus.COMPLETED in terminal
    assert PlanStatus.ABORTED in terminal
    assert PlanStatus.REJECTED in terminal
    assert PlanStatus.PROPOSED not in terminal
    assert PlanStatus.APPROVED not in terminal
    assert PlanStatus.RUNNING not in terminal


def test_plan_status_is_terminal() -> None:
    assert PlanStatus.COMPLETED.is_terminal()
    assert not PlanStatus.PROPOSED.is_terminal()


def test_plan_step_round_trip() -> None:
    s = PlanStep(
        id="step-1",
        action="traders.place_alert",
        args={"ticker": "BTC", "price": 100.0},
        store_as="alert",
        when="market.bias != 'risk_off'",
        on_error="continue",
        parallel=True,
        rationale="Why",
        destructive=True,
    )
    raw = s.to_dict()
    s2 = PlanStep.from_dict(raw)
    assert s2 == s


def test_plan_round_trip_preserves_estimated_cost() -> None:
    p = Plan(
        id="pln_x",
        goal="Test",
        steps=(
            PlanStep(
                id="step-1", action="traders.summarize_market"
            ),
        ),
        estimated_cost_usd=0.0042,
    )
    raw = p.to_dict()
    assert raw["estimated_cost_usd"] == pytest.approx(0.0042)
    assert raw["step_count"] == 1
    assert raw["destructive_step_count"] == 0


def test_plan_to_dict_counts_destructive_steps() -> None:
    p = Plan(
        id="pln_x",
        goal="Test",
        steps=(
            PlanStep(id="a", action="a.b", destructive=False),
            PlanStep(id="b", action="c.d", destructive=True),
            PlanStep(id="c", action="e.f", destructive=True),
        ),
    )
    assert p.to_dict()["destructive_step_count"] == 2


# ---------------------------------------------------------------------------
# Synthesizer
# ---------------------------------------------------------------------------


def test_synthesize_raises_on_empty_goal() -> None:
    with pytest.raises(PlannerError) as exc:
        synthesize_plan(PlannerSynthesisRequest(goal=""))
    assert exc.value.reason == "empty_goal"


def test_synthesize_raises_on_no_match() -> None:
    with pytest.raises(PlannerError) as exc:
        synthesize_plan(
            PlannerSynthesisRequest(
                goal="Pet the dog",
                available_playbooks=(_PB_MORNING,),
                available_actions=_AVAILABLE_ACTIONS,
            )
        )
    assert exc.value.reason == "no_match"


def test_synthesize_matches_playbook_by_id() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="Run traders.morning_check please",
            available_playbooks=(_PB_MORNING,),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.playbook_id == "traders.morning_check"
    assert plan.pack_slug == "traders"
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "traders.summarize_market"


def test_synthesize_matches_playbook_by_name() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="run traders morning check now",
            available_playbooks=(_PB_MORNING,),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.playbook_id == "traders.morning_check"


def test_synthesize_matches_playbook_by_tag() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="kick off the morning routine",
            available_playbooks=(_PB_MORNING,),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.playbook_id == "traders.morning_check"


def test_synthesize_matches_action_directly() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="please run business.kpi_snapshot",
            available_playbooks=(_PB_MORNING,),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "business.kpi_snapshot"
    assert plan.steps[0].destructive is False
    assert plan.pack_slug == "business"


def test_synthesize_marks_destructive_action_step() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="run traders.place_alert",
            available_playbooks=(),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.steps[0].destructive is True


def test_synthesize_pack_fallback_picks_snapshot_action() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="give me a quick traders summary",
            available_playbooks=(),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.pack_slug == "traders"
    assert plan.steps[0].destructive is False
    assert plan.steps[0].action.startswith("traders.")


def test_synthesize_raises_ambiguous_packs_when_two_pack_names_appear() -> None:
    with pytest.raises(PlannerError) as exc:
        synthesize_plan(
            PlannerSynthesisRequest(
                goal="cover traders and business today",
                available_playbooks=(),
                available_actions=_AVAILABLE_ACTIONS,
            )
        )
    assert exc.value.reason == "ambiguous_packs"


def test_synthesize_pinned_pack_disambiguates() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="cover traders and business today",
            pinned_pack="traders",
            available_playbooks=(),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.pack_slug == "traders"


def test_synthesize_pinned_pack_with_unknown_pack_raises() -> None:
    with pytest.raises(PlannerError) as exc:
        synthesize_plan(
            PlannerSynthesisRequest(
                goal="run x",
                pinned_pack="nonexistent",
                available_playbooks=(_PB_MORNING,),
                available_actions=_AVAILABLE_ACTIONS,
            )
        )
    # No playbook / action / snapshot under the pinned pack → falls
    # through to the unknown_pack branch.
    assert exc.value.reason in {"unknown_pack", "no_match"}


def test_synthesize_carries_thread_id_and_trace_id_through() -> None:
    plan = synthesize_plan(
        PlannerSynthesisRequest(
            goal="run traders.summarize_market",
            thread_id="thr_x",
            trace_id="trc_y",
            available_playbooks=(),
            available_actions=_AVAILABLE_ACTIONS,
        )
    )
    assert plan.thread_id == "thr_x"
    assert plan.trace_id == "trc_y"


# ---------------------------------------------------------------------------
# PlannerStore CRUD + status transitions
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> PlannerStore:
    return PlannerStore(str(tmp_path / "planner.sqlite"))


def _make_plan() -> Plan:
    return Plan(
        id="",
        goal="goal",
        steps=(
            PlanStep(id="s1", action="traders.summarize_market"),
        ),
        rationale="why",
        thread_id="thr_a",
    )


@pytest.mark.asyncio
async def test_store_insert_assigns_pln_id_and_timestamps(tmp_path):
    store = _store(tmp_path)
    saved = await store.insert(_make_plan())
    assert saved.id.startswith("pln_")
    assert saved.created_at > 0
    assert saved.updated_at > 0


@pytest.mark.asyncio
async def test_store_get_round_trips_steps(tmp_path):
    store = _store(tmp_path)
    saved = await store.insert(_make_plan())
    fetched = await store.get(saved.id)
    assert fetched is not None
    assert len(fetched.steps) == 1
    assert fetched.steps[0].action == "traders.summarize_market"


@pytest.mark.asyncio
async def test_store_get_unknown_id_returns_none(tmp_path):
    store = _store(tmp_path)
    assert await store.get("pln_does_not_exist") is None


@pytest.mark.asyncio
async def test_store_set_status_updates(tmp_path):
    store = _store(tmp_path)
    saved = await store.insert(_make_plan())
    updated = await store.set_status(saved.id, PlanStatus.APPROVED)
    assert updated is not None
    assert updated.status == PlanStatus.APPROVED


@pytest.mark.asyncio
async def test_store_terminal_status_is_immutable(tmp_path):
    store = _store(tmp_path)
    saved = await store.insert(_make_plan())
    completed = await store.set_status(saved.id, PlanStatus.COMPLETED)
    assert completed.status == PlanStatus.COMPLETED
    # Try to flip it back — must stay terminal.
    out = await store.set_status(saved.id, PlanStatus.APPROVED)
    assert out.status == PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_store_list_filters_by_status(tmp_path):
    store = _store(tmp_path)
    a = await store.insert(_make_plan())
    b = await store.insert(_make_plan())
    await store.set_status(b.id, PlanStatus.APPROVED)

    proposed = await store.list(status=PlanStatus.PROPOSED)
    approved = await store.list(status=PlanStatus.APPROVED)
    assert {p.id for p in proposed} == {a.id}
    assert {p.id for p in approved} == {b.id}


@pytest.mark.asyncio
async def test_store_list_filters_by_thread_id(tmp_path):
    store = _store(tmp_path)
    a = await store.insert(_make_plan())  # thread_id="thr_a"
    other_plan = Plan(
        id="",
        goal="other",
        steps=(PlanStep(id="s1", action="traders.summarize_market"),),
        thread_id="thr_b",
    )
    await store.insert(other_plan)

    just_a = await store.list(thread_id="thr_a")
    assert {p.id for p in just_a} == {a.id}


@pytest.mark.asyncio
async def test_store_delete_removes_row(tmp_path):
    store = _store(tmp_path)
    saved = await store.insert(_make_plan())
    assert await store.delete(saved.id) is True
    assert await store.get(saved.id) is None


@pytest.mark.asyncio
async def test_store_stats_counts_by_status(tmp_path):
    store = _store(tmp_path)
    a = await store.insert(_make_plan())
    b = await store.insert(_make_plan())
    await store.set_status(b.id, PlanStatus.APPROVED)

    out = await store.stats()
    assert out["total"] == 2
    assert out["by_status"]["proposed"] == 1
    assert out["by_status"]["approved"] == 1


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_http_create_plan_happy_path(app_client):
    resp = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
        headers={"x-tars-thread-id": "thr_http_001"},
    )
    assert resp.status_code == 200, resp.text
    plan = resp.json()["plan"]
    assert plan["id"].startswith("pln_")
    assert plan["status"] == "proposed"
    assert plan["thread_id"] == "thr_http_001"
    assert plan["step_count"] >= 1


def test_http_create_plan_400_on_empty_goal(app_client):
    resp = app_client.post("/api/planner/plan", json={"goal": "   "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "goal_required"


def test_http_create_plan_400_on_no_match(app_client):
    resp = app_client.post("/api/planner/plan", json={"goal": "pet the dog"})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["reason"] == "no_match"


def test_http_get_plan_returns_404_for_unknown(app_client):
    resp = app_client.get("/api/planner/pln_nope")
    assert resp.status_code == 404


def test_http_get_plan_returns_persisted_plan(app_client):
    created = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
    )
    plan_id = created.json()["plan"]["id"]
    resp = app_client.get(f"/api/planner/{plan_id}")
    assert resp.status_code == 200
    assert resp.json()["plan"]["id"] == plan_id


def test_http_list_plans_filters_by_status(app_client):
    a = app_client.post(
        "/api/planner/plan", json={"goal": "run traders.summarize_market"}
    ).json()["plan"]
    # Set a → approved
    app_client.post(f"/api/planner/{a['id']}/status", json={"status": "approved"})
    app_client.post(
        "/api/planner/plan", json={"goal": "run business.kpi_snapshot"}
    )
    proposed = app_client.get("/api/planner?status=proposed").json()
    approved = app_client.get("/api/planner?status=approved").json()
    assert proposed["count"] == 1
    assert approved["count"] == 1


def test_http_list_plans_unknown_status_returns_400(app_client):
    resp = app_client.get("/api/planner?status=bogus")
    assert resp.status_code == 400


def test_http_status_endpoint_emits_meeet_event(app_client):
    from backend.core.meeet import get_client

    plan = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
        headers={"x-tars-thread-id": "thr_http_002"},
    ).json()["plan"]
    resp = app_client.post(
        f"/api/planner/{plan['id']}/status", json={"status": "approved"}
    )
    assert resp.status_code == 200
    events = asyncio.run(
        get_client().store.list_events(kind="planner.approved", limit=10)
    )
    assert events
    payload = events[0].payload
    assert payload["plan_id"] == plan["id"]
    # thread_id auto-injected by the meeet client (see PR #100).
    assert payload.get("thread_id") == "thr_http_002"


def test_http_status_endpoint_409_on_terminal(app_client):
    plan = app_client.post(
        "/api/planner/plan", json={"goal": "run traders.summarize_market"}
    ).json()["plan"]
    app_client.post(f"/api/planner/{plan['id']}/status", json={"status": "rejected"})
    second = app_client.post(
        f"/api/planner/{plan['id']}/status", json={"status": "approved"}
    )
    assert second.status_code == 409


def test_http_status_endpoint_400_on_invalid_status(app_client):
    plan = app_client.post(
        "/api/planner/plan", json={"goal": "run traders.summarize_market"}
    ).json()["plan"]
    resp = app_client.post(
        f"/api/planner/{plan['id']}/status", json={"status": "running"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["reason"] == "invalid_status"


def test_http_delete_plan(app_client):
    plan = app_client.post(
        "/api/planner/plan", json={"goal": "run traders.summarize_market"}
    ).json()["plan"]
    resp = app_client.delete(f"/api/planner/{plan['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    after = app_client.get(f"/api/planner/{plan['id']}")
    assert after.status_code == 404


def test_http_delete_plan_404_for_unknown(app_client):
    resp = app_client.delete("/api/planner/pln_nope")
    assert resp.status_code == 404


def test_http_stats_endpoint(app_client):
    app_client.post(
        "/api/planner/plan", json={"goal": "run traders.summarize_market"}
    )
    resp = app_client.get("/api/planner/_stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert "by_status" in body


def test_http_synthesis_failed_emits_event(app_client):
    from backend.core.meeet import get_client

    resp = app_client.post(
        "/api/planner/plan", json={"goal": "pet the dog"}
    )
    assert resp.status_code == 400
    events = asyncio.run(
        get_client().store.list_events(kind="planner.synthesis.failed", limit=10)
    )
    assert events
    assert events[0].payload["reason"] == "no_match"


def test_http_synthesis_completed_emits_event(app_client):
    from backend.core.meeet import get_client

    plan = app_client.post(
        "/api/planner/plan",
        json={"goal": "run traders.summarize_market"},
    ).json()["plan"]
    events = asyncio.run(
        get_client().store.list_events(
            kind="planner.synthesis.completed", limit=10
        )
    )
    assert events
    assert events[0].payload["plan_id"] == plan["id"]
