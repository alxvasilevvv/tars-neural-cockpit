"""Tests for the planner SSE event stream + the meeet store
``after_id`` cursor that powers it.

Covers:

- ``MeeetStore.list_events(after_id=N)`` returns only rows with
  ``id > N``; combines cleanly with ``kind`` filters.
- ``_planner_sse_producer`` emits a ``hello`` frame, then the
  expected ``plan.*`` frames in id-ascending order, and a ``bye``
  frame on ``max_duration_reached``.
- ``plan_id`` / ``thread_id`` query filters drop non-matching
  events but still advance the cursor so they don't get re-read
  forever.
- The HTTP endpoint mounts at ``GET /api/planner/events`` and the
  ``/{plan_id}`` route does NOT swallow the path (the SSE route is
  declared first).
"""

from __future__ import annotations

import asyncio
import json
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
# MeeetStore.list_events(after_id=…)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_after_id_returns_only_newer_rows():
    from backend.core.meeet import get_client, get_store

    client = get_client()
    await client.emit("plan.proposed", {"plan_id": "p1"})
    await client.emit("plan.proposed", {"plan_id": "p2"})
    await client.emit("plan.proposed", {"plan_id": "p3"})

    store = get_store()
    all_rows = await store.list_events(kind="plan.proposed", limit=50)
    assert len(all_rows) == 3
    # Newest-first inside list_events; sort by id to be explicit.
    ids = sorted(r.id for r in all_rows)

    after_first = await store.list_events(
        kind="plan.proposed", after_id=ids[0], limit=50
    )
    assert {r.id for r in after_first} == {ids[1], ids[2]}

    after_last = await store.list_events(
        kind="plan.proposed", after_id=ids[2], limit=50
    )
    assert after_last == []


@pytest.mark.asyncio
async def test_list_events_after_id_combines_with_kind_prefix():
    from backend.core.meeet import get_client, get_store

    client = get_client()
    await client.emit("plan.run.started", {"plan_id": "p1"})
    await client.emit("plan.completed", {"plan_id": "p1"})
    await client.emit("policy.allowed", {"slug": "x"})  # different prefix
    await client.emit("plan.aborted", {"plan_id": "p1"})

    store = get_store()
    plan_only = await store.list_events(
        kind_prefix="plan.", after_id=0, limit=50
    )
    kinds = {ev.kind for ev in plan_only}
    assert "plan.run.started" in kinds
    assert "plan.completed" in kinds
    assert "plan.aborted" in kinds
    assert "policy.allowed" not in kinds


# ---------------------------------------------------------------------------
# _planner_sse_producer — the async generator
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[dict[str, Any]]:
    """Tiny SSE parser: returns one dict per ``data:`` frame."""

    out: list[dict[str, Any]] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Each chunk has optional ``id: N`` line + a ``data: …`` line.
        for line in chunk.splitlines():
            if line.startswith("data:"):
                data = line[len("data:"):].strip()
                try:
                    out.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
    return out


@pytest.mark.asyncio
async def test_sse_producer_emits_hello_then_events_then_bye():
    from backend.core.meeet import get_client
    from web_extras.routers.planner import _planner_sse_producer

    client = get_client()
    await client.emit("plan.proposed", {"plan_id": "p1", "goal": "g"})
    await client.emit("plan.run.started", {"plan_id": "p1"})

    chunks: list[str] = []

    async def consume():
        async for chunk in _planner_sse_producer(
            plan_id=None,
            thread_id=None,
            after_id=0,
            poll_interval_s=0.05,
            max_duration_s=0.25,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(consume(), timeout=2.0)

    frames = _parse_sse("\n\n".join(chunks))
    assert frames[0]["kind"] == "hello"
    plan_kinds = [f["kind"] for f in frames if f["kind"].startswith("plan.")]
    assert plan_kinds == ["plan.proposed", "plan.run.started"]
    assert frames[-1]["kind"] == "bye"
    assert frames[-1]["reason"] == "max_duration_reached"


@pytest.mark.asyncio
async def test_sse_producer_after_id_skips_already_seen_events():
    from backend.core.meeet import get_client, get_store
    from web_extras.routers.planner import _planner_sse_producer

    client = get_client()
    await client.emit("plan.proposed", {"plan_id": "p1"})
    seen_id = (await get_store().list_events(kind="plan.proposed", limit=1))[0].id
    await client.emit("plan.completed", {"plan_id": "p1"})

    chunks: list[str] = []

    async def consume():
        async for chunk in _planner_sse_producer(
            plan_id=None,
            thread_id=None,
            after_id=seen_id,
            poll_interval_s=0.05,
            max_duration_s=0.2,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(consume(), timeout=2.0)

    frames = _parse_sse("\n\n".join(chunks))
    plan_kinds = [f["kind"] for f in frames if f["kind"].startswith("plan.")]
    # Only the post-cursor event should appear.
    assert plan_kinds == ["plan.completed"]


@pytest.mark.asyncio
async def test_sse_producer_filters_by_plan_id():
    from backend.core.meeet import get_client
    from web_extras.routers.planner import _planner_sse_producer

    client = get_client()
    await client.emit("plan.proposed", {"plan_id": "wanted"})
    await client.emit("plan.proposed", {"plan_id": "other"})
    await client.emit("plan.completed", {"plan_id": "wanted"})

    chunks: list[str] = []

    async def consume():
        async for chunk in _planner_sse_producer(
            plan_id="wanted",
            thread_id=None,
            after_id=0,
            poll_interval_s=0.05,
            max_duration_s=0.2,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(consume(), timeout=2.0)

    frames = _parse_sse("\n\n".join(chunks))
    plan_payloads = [
        f.get("payload", {}) for f in frames if f["kind"].startswith("plan.")
    ]
    plan_ids = {p.get("plan_id") for p in plan_payloads}
    assert plan_ids == {"wanted"}


@pytest.mark.asyncio
async def test_sse_producer_filters_by_thread_id():
    from backend.core.meeet import get_client
    from web_extras.routers.planner import _planner_sse_producer

    client = get_client()
    await client.emit("plan.proposed", {"plan_id": "p1", "thread_id": "thr_a"})
    await client.emit("plan.proposed", {"plan_id": "p2", "thread_id": "thr_b"})

    chunks: list[str] = []

    async def consume():
        async for chunk in _planner_sse_producer(
            plan_id=None,
            thread_id="thr_a",
            after_id=0,
            poll_interval_s=0.05,
            max_duration_s=0.2,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(consume(), timeout=2.0)

    frames = _parse_sse("\n\n".join(chunks))
    payloads = [
        f.get("payload", {}) for f in frames if f["kind"].startswith("plan.")
    ]
    thread_ids = {p.get("thread_id") for p in payloads}
    assert thread_ids == {"thr_a"}


@pytest.mark.asyncio
async def test_sse_producer_hello_carries_filter_metadata():
    from web_extras.routers.planner import _planner_sse_producer

    chunks: list[str] = []

    async def consume():
        async for chunk in _planner_sse_producer(
            plan_id="pln_hi",
            thread_id="thr_x",
            after_id=42,
            poll_interval_s=0.05,
            max_duration_s=0.1,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(consume(), timeout=2.0)

    frames = _parse_sse("\n\n".join(chunks))
    assert frames[0]["kind"] == "hello"
    assert frames[0]["after_id"] == 42
    assert frames[0]["filter"]["plan_id"] == "pln_hi"
    assert frames[0]["filter"]["thread_id"] == "thr_x"


# ---------------------------------------------------------------------------
# HTTP endpoint mounting
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_http_events_endpoint_mounts_at_correct_path(app_client):
    """The SSE route must be matched before ``/{plan_id}`` (which
    otherwise would parse ``events`` as a plan id and 404)."""

    # Use a tiny max_duration so the test client can finish the
    # request quickly. TestClient's stream is synchronous so we
    # just read the full body.
    resp = app_client.get(
        "/api/planner/events",
        params={
            "poll_interval_s": 0.05,
            "max_duration_s": 0.15,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    frames = _parse_sse(body)
    assert frames[0]["kind"] == "hello"
    assert frames[-1]["kind"] == "bye"


def test_http_events_endpoint_does_not_collide_with_get_plan_route(app_client):
    """Sanity: after introducing /events, GET /api/planner/{plan_id}
    still 404s for an unknown id (would 200-stream if /events
    captured everything)."""

    resp = app_client.get("/api/planner/pln_does_not_exist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_found"
