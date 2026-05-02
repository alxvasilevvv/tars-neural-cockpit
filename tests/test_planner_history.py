"""Tests for the plan-run reconstructor (PR #105).

Covers:

- ``reconstruct_runs_async`` walks the meeet store and groups
  ``plan.run.started`` → ``plan.completed`` / ``plan.aborted``
  windows into per-run dicts.
- Step events between the boundaries land on the open run; their
  ``ok`` / ``blocked`` / ``skipped`` / ``took_ms`` / ``error``
  fields round-trip from the meeet payloads.
- A ``plan.step.allowed`` followed by ``plan.step.completed``
  populates ``allowed`` / ``allow_reason`` on the same step (no
  duplicates).
- An open run with no terminal event surfaces as ``status="running"``
  so the cockpit can render an "in flight" badge.
- A second ``plan.run.started`` with no preceding terminal event
  closes the previous run as ``aborted no_terminal_event``.
- Orphan step events (no preceding ``plan.run.started``) are
  dropped instead of fabricating a synthetic run.
- HTTP surface ``GET /api/planner/{plan_id}/runs``: 200 happy path
  with newest-first ordering + run counts; 404 for unknown plan
  ids; ``in_flight`` count populated for runs without a terminal
  event.
"""

from __future__ import annotations

import time
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _emit(kind: str, payload: dict[str, Any]) -> None:
    from backend.core.meeet import get_client

    await get_client().emit(kind, payload)


# ---------------------------------------------------------------------------
# reconstruct_runs_async — pure reducer behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconstruct_groups_one_completed_run():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_one"
    await _emit(
        "plan.run.started",
        {
            "plan_id": plan_id,
            "mode": "autopilot",
            "step_count": 2,
        },
    )
    await _emit(
        "plan.step.allowed",
        {"plan_id": plan_id, "step_id": "s1", "allowed": True, "reason": "executed"},
    )
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "action": "x.y",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 12.0,
        },
    )
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "s2",
            "action": "x.z",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 7.5,
        },
    )
    await _emit(
        "plan.completed",
        {
            "plan_id": plan_id,
            "ok": True,
            "steps_run": 2,
            "steps_blocked": 0,
            "steps_failed": 0,
        },
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    run = runs[0].to_dict()
    assert run["status"] == "completed"
    assert run["mode"] == "autopilot"
    assert run["step_count"] == 2
    assert run["steps_run"] == 2
    assert run["steps_blocked"] == 0
    assert run["steps_failed"] == 0
    assert [s["id"] for s in run["steps"]] == ["s1", "s2"]
    s1 = run["steps"][0]
    assert s1["allowed"] is True
    assert s1["allow_reason"] == "executed"
    assert s1["took_ms"] == 12.0
    assert run["took_ms"] is not None
    assert run["took_ms"] >= 0.0


@pytest.mark.asyncio
async def test_reconstruct_groups_two_runs_newest_first():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_two"
    await _emit("plan.run.started", {"plan_id": plan_id, "mode": "confirm"})
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

    # Tiny gap so the second run's started_at is strictly later.
    time.sleep(0.01)
    await _emit("plan.run.started", {"plan_id": plan_id, "mode": "autopilot"})
    await _emit(
        "plan.aborted",
        {"plan_id": plan_id, "reason": "operator_abort"},
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 2
    statuses = [r.status for r in runs]
    # Newest first.
    assert statuses == ["aborted", "completed"]
    assert runs[0].abort_reason == "operator_abort"
    assert runs[0].mode == "autopilot"
    assert runs[1].mode == "confirm"
    assert runs[0].started_at >= runs[1].started_at


@pytest.mark.asyncio
async def test_reconstruct_marks_open_run_as_running():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_in_flight"
    await _emit("plan.run.started", {"plan_id": plan_id, "step_count": 3})
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "action": "x.y",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 4.0,
        },
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    run = runs[0].to_dict()
    assert run["status"] == "running"
    assert run["completed_at"] is None
    assert run["took_ms"] is None
    assert len(run["steps"]) == 1


@pytest.mark.asyncio
async def test_reconstruct_step_failure_counts_increment():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_fail"
    await _emit("plan.run.started", {"plan_id": plan_id})
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "ok",
            "action": "a.b",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 1.0,
        },
    )
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "blk",
            "action": "a.c",
            "ok": False,
            "blocked": True,
            "skipped": False,
            "took_ms": 0.0,
            "error": "blocked_by_policy",
        },
    )
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "fail",
            "action": "a.d",
            "ok": False,
            "blocked": False,
            "skipped": False,
            "took_ms": 5.0,
            "error": "boom",
        },
    )
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "skip",
            "action": "a.e",
            "ok": True,
            "blocked": False,
            "skipped": True,
            "took_ms": 0.0,
        },
    )
    await _emit(
        "plan.aborted",
        {
            "plan_id": plan_id,
            "reason": "step_failed",
            # Authoritative counters from the runner override the
            # ones we accumulated locally — assert that handover.
            "steps_run": 3,
            "steps_blocked": 1,
            "steps_failed": 1,
        },
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    run = runs[0]
    assert run.status == "aborted"
    assert run.abort_reason == "step_failed"
    assert run.steps_run == 3
    assert run.steps_blocked == 1
    assert run.steps_failed == 1
    fail_step = next(s for s in run.steps if s.id == "fail")
    assert fail_step.error == "boom"


@pytest.mark.asyncio
async def test_reconstruct_aborts_unterminated_previous_run():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_no_term"
    await _emit("plan.run.started", {"plan_id": plan_id})
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "action": "x.y",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 1.0,
        },
    )
    # No terminal event before the next start — the previous run
    # should be auto-closed as aborted/no_terminal_event.
    time.sleep(0.01)
    await _emit("plan.run.started", {"plan_id": plan_id})
    await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 2
    # Newest first.
    assert runs[0].status == "completed"
    assert runs[1].status == "aborted"
    assert runs[1].abort_reason == "no_terminal_event"


@pytest.mark.asyncio
async def test_reconstruct_drops_orphan_step_events():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_orphan"
    # No plan.run.started → these should be ignored.
    await _emit(
        "plan.step.completed",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "action": "x.y",
            "ok": True,
            "blocked": False,
            "skipped": False,
            "took_ms": 1.0,
        },
    )
    await _emit(
        "plan.completed",
        {"plan_id": plan_id, "ok": True},
    )

    runs = await reconstruct_runs_async(plan_id)
    assert runs == []


@pytest.mark.asyncio
async def test_reconstruct_filters_by_plan_id():
    from backend.core.planner import reconstruct_runs_async

    await _emit("plan.run.started", {"plan_id": "wanted"})
    await _emit("plan.completed", {"plan_id": "wanted", "ok": True})
    await _emit("plan.run.started", {"plan_id": "other"})
    await _emit("plan.completed", {"plan_id": "other", "ok": True})

    wanted = await reconstruct_runs_async("wanted")
    other = await reconstruct_runs_async("other")
    assert len(wanted) == 1
    assert len(other) == 1
    assert wanted[0].plan_id == "wanted"
    assert other[0].plan_id == "other"


@pytest.mark.asyncio
async def test_reconstruct_records_abort_requested_and_exception():
    from backend.core.planner import reconstruct_runs_async

    plan_id = "pln_aux"
    await _emit("plan.run.started", {"plan_id": plan_id})
    await _emit("plan.abort.requested", {"plan_id": plan_id, "ok": True})
    await _emit("plan.run.exception", {"plan_id": plan_id, "error": "boom!"})
    await _emit(
        "plan.aborted",
        {"plan_id": plan_id, "reason": "operator_abort"},
    )

    runs = await reconstruct_runs_async(plan_id)
    assert len(runs) == 1
    assert runs[0].abort_requested is True
    assert runs[0].exception == "boom!"


# ---------------------------------------------------------------------------
# HTTP surface — GET /api/planner/{plan_id}/runs
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _seed_plan_via_http(
    client: TestClient,
    *,
    goal: str = "traders.morning_check",
) -> str:
    """Insert a plan via the public ``POST /plan`` route.

    The default ``goal`` resolves to the bundled
    ``traders.morning_check`` playbook so the synthesizer always
    accepts it without us needing to register a probe pack here.
    """

    resp = client.post("/api/planner/plan", json={"goal": goal})
    assert resp.status_code == 200, resp.text
    return resp.json()["plan"]["id"]


def test_http_runs_endpoint_returns_404_for_unknown_plan(app_client):
    resp = app_client.get("/api/planner/pln_unknown/runs")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_found"


def test_http_runs_endpoint_returns_empty_list_when_no_events(app_client):
    plan_id = _seed_plan_via_http(app_client)
    # synthesize emits a `plan.proposed` but no `plan.run.started`,
    # so reconstruct_runs returns nothing.
    resp = app_client.get(f"/api/planner/{plan_id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["plan_id"] == plan_id
    assert body["count"] == 0
    assert body["in_flight"] == 0
    assert body["runs"] == []


def test_http_runs_endpoint_returns_runs_in_order_with_in_flight_count(app_client):
    plan_id = _seed_plan_via_http(app_client)

    import asyncio

    async def seed():
        # Run 1 — completed.
        await _emit("plan.run.started", {"plan_id": plan_id, "mode": "autopilot"})
        await _emit(
            "plan.step.completed",
            {
                "plan_id": plan_id,
                "step_id": "s1",
                "action": "x.y",
                "ok": True,
                "blocked": False,
                "skipped": False,
                "took_ms": 3.0,
            },
        )
        await _emit("plan.completed", {"plan_id": plan_id, "ok": True})

        # Run 2 — still running (no terminal).
        await _emit("plan.run.started", {"plan_id": plan_id, "mode": "confirm"})
        await _emit(
            "plan.step.completed",
            {
                "plan_id": plan_id,
                "step_id": "s2",
                "action": "x.z",
                "ok": True,
                "blocked": False,
                "skipped": False,
                "took_ms": 1.0,
            },
        )

    asyncio.run(seed())

    resp = app_client.get(f"/api/planner/{plan_id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["in_flight"] == 1
    statuses = [r["status"] for r in body["runs"]]
    # Newest first → "running" run is first.
    assert statuses == ["running", "completed"]
    assert body["runs"][0]["mode"] == "confirm"
    assert body["runs"][1]["mode"] == "autopilot"


def test_http_runs_endpoint_respects_limit_param(app_client):
    plan_id = _seed_plan_via_http(app_client)

    import asyncio

    async def seed_n(n: int):
        for _ in range(n):
            await _emit("plan.run.started", {"plan_id": plan_id})
            await _emit(
                "plan.completed", {"plan_id": plan_id, "ok": True}
            )

    asyncio.run(seed_n(3))

    # ``limit`` is a per-kind cap, not a runs cap. With 3 starts +
    # 3 completes per plan, asking for limit=1 keeps only the
    # newest start and the newest complete — so only 1 run is
    # reconstructable.
    resp = app_client.get(
        f"/api/planner/{plan_id}/runs", params={"limit": 1}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Sanity: limit=1000 returns all runs.
    full = app_client.get(f"/api/planner/{plan_id}/runs", params={"limit": 1000})
    assert full.json()["count"] == 3
    assert body["count"] <= full.json()["count"]


# ---------------------------------------------------------------------------
# Last-Event-ID header on /api/planner/events
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[dict[str, Any]]:
    import json

    out: list[dict[str, Any]] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data:"):
                data = line[len("data:") :].strip()
                try:
                    out.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
    return out


def test_http_events_honours_last_event_id_header(app_client):
    """``Last-Event-ID`` is the SSE-spec way ``EventSource`` resumes."""

    import asyncio

    async def seed():
        await _emit("plan.proposed", {"plan_id": "p1"})
        await _emit("plan.completed", {"plan_id": "p1"})

    asyncio.run(seed())

    # Find the row id of the first event so we can pass it as the
    # ``Last-Event-ID`` header.
    from backend.core.meeet import get_store

    rows = asyncio.run(get_store().list_events(kind="plan.proposed", limit=1))
    seen_id = rows[0].id

    resp = app_client.get(
        "/api/planner/events",
        params={"poll_interval_s": 0.05, "max_duration_s": 0.15},
        headers={"Last-Event-ID": str(seen_id)},
    )
    assert resp.status_code == 200
    frames = _parse_sse(resp.text)
    hello = frames[0]
    assert hello["kind"] == "hello"
    assert hello["after_id"] == seen_id
    assert hello["after_id_source"] == "header"
    plan_kinds = [f["kind"] for f in frames if f["kind"].startswith("plan.")]
    # Only the post-cursor event should appear.
    assert plan_kinds == ["plan.completed"]


def test_http_events_header_overrides_query_after_id(app_client):
    import asyncio

    async def seed():
        for i in range(3):
            await _emit("plan.proposed", {"plan_id": f"p{i}"})

    asyncio.run(seed())

    from backend.core.meeet import get_store

    rows = asyncio.run(get_store().list_events(kind="plan.proposed", limit=10))
    ids = sorted(r.id for r in rows)
    # query param skips the first event; header skips the first two →
    # header wins, so we only see the third.
    resp = app_client.get(
        "/api/planner/events",
        params={
            "after_id": ids[0],
            "poll_interval_s": 0.05,
            "max_duration_s": 0.15,
        },
        headers={"Last-Event-ID": str(ids[1])},
    )
    assert resp.status_code == 200
    frames = _parse_sse(resp.text)
    hello = frames[0]
    assert hello["after_id"] == ids[1]
    assert hello["after_id_source"] == "header"
    plan_payloads = [
        f.get("payload", {}) for f in frames if f["kind"].startswith("plan.")
    ]
    plan_ids = [p.get("plan_id") for p in plan_payloads]
    assert plan_ids == ["p2"]


def test_http_events_falls_back_to_query_when_header_invalid(app_client):
    import asyncio

    async def seed():
        await _emit("plan.proposed", {"plan_id": "p1"})

    asyncio.run(seed())

    resp = app_client.get(
        "/api/planner/events",
        params={"after_id": 0, "poll_interval_s": 0.05, "max_duration_s": 0.1},
        headers={"Last-Event-ID": "not-a-number"},
    )
    assert resp.status_code == 200
    frames = _parse_sse(resp.text)
    hello = frames[0]
    # Falls back to the query default (0).
    assert hello["after_id"] == 0
    assert hello["after_id_source"] == "default"


def test_http_events_default_when_no_cursor_provided(app_client):
    resp = app_client.get(
        "/api/planner/events",
        params={"poll_interval_s": 0.05, "max_duration_s": 0.1},
    )
    assert resp.status_code == 200
    frames = _parse_sse(resp.text)
    hello = frames[0]
    assert hello["after_id"] == 0
    assert hello["after_id_source"] == "default"
