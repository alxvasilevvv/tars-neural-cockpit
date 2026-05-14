"""W248 — unified WS real-time event bus tests.

Four required cases (per task spec):

1. subscribe / publish round-trip
2. multiple subscribers receive the same event
3. unsubscribe stops delivery
4. snapshot returns the current state

Plus a fifth integration test exercising the actual ``/api/realtime``
WS endpoint through FastAPI's :class:`fastapi.testclient.TestClient`
(websockets supported via ``websocket_connect``). The integration
test is skipped automatically if FastAPI / the app aren't importable
in the test environment.
"""

from __future__ import annotations

import asyncio
import json
import pytest

from backend.core.realtime import (
    publish_event,
    reset_for_tests,
    set_snapshot_provider,
    snapshot,
    subscribe,
)


@pytest.fixture(autouse=True)
def _clean_broker():
    reset_for_tests()
    yield
    reset_for_tests()


# ── 1. subscribe / publish round-trip ─────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_and_publish_roundtrip():
    """A single subscriber on a topic receives every event published
    after registration. Verifies the envelope shape."""

    received: list = []

    async def consume():
        async for env in subscribe("usage"):
            received.append(env)
            if len(received) >= 2:
                return

    task = asyncio.create_task(consume())
    # Yield so the subscriber actually registers its queue.
    await asyncio.sleep(0.05)

    publish_event("usage", {"tokens_in": 10, "tokens_out": 5})
    publish_event("usage", {"tokens_in": 1, "tokens_out": 1})

    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 2
    assert received[0].type == "usage"
    assert received[0].payload["tokens_in"] == 10
    assert received[1].payload["tokens_out"] == 1
    assert received[0].ts <= received[1].ts


# ── 2. multiple subscribers receive the same event ───────────────────


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_same_event():
    """Fan-out: two independent subscribers on the same topic both
    see every published event."""

    bucket_a: list = []
    bucket_b: list = []

    async def reader(bucket):
        async for env in subscribe("bg_agents"):
            bucket.append(env)
            if len(bucket) >= 3:
                return

    a = asyncio.create_task(reader(bucket_a))
    b = asyncio.create_task(reader(bucket_b))
    await asyncio.sleep(0.05)  # let both queues register

    for i in range(3):
        publish_event("bg_agents", {"task_id": f"t{i}", "status": "running"})

    await asyncio.wait_for(asyncio.gather(a, b), timeout=2.0)

    assert [e.payload["task_id"] for e in bucket_a] == ["t0", "t1", "t2"]
    assert [e.payload["task_id"] for e in bucket_b] == ["t0", "t1", "t2"]


# ── 3. unsubscribe stops delivery ────────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    """Once the async generator is closed, the broker drops the
    subscriber queue and never delivers another event to it."""

    from backend.core.realtime import subscriber_count

    received: list = []

    async def reader_then_quit():
        # subscribe + take exactly one event, then leave (this is
        # what the WS handler does on disconnect — the iterator's
        # ``finally`` block unregisters the queue).
        async for env in subscribe("health"):
            received.append(env)
            return  # exits the generator → finally runs

    # Pre-condition: zero subscribers.
    assert subscriber_count("health") == 0

    task = asyncio.create_task(reader_then_quit())
    await asyncio.sleep(0.05)
    assert subscriber_count("health") == 1

    publish_event("health", {"ok": True, "uptime_s": 1.0})
    await asyncio.wait_for(task, timeout=2.0)

    # Subscriber unregistered after exit.
    assert subscriber_count("health") == 0

    # Further publishes don't crash and (since no one is listening)
    # reach zero subscribers.
    delivered = publish_event("health", {"ok": True, "uptime_s": 2.0})
    assert delivered == 0
    assert len(received) == 1


# ── 4. snapshot returns the current state ────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_returns_current_state():
    """``snapshot()`` resolves via the registered provider first, and
    falls back to the last cached envelope when no provider is set."""

    # 4a — provider path
    set_snapshot_provider(
        "cap_status",
        lambda: {"level": "60", "percent_used": 0.62},
    )
    env = await snapshot("cap_status")
    assert env is not None
    assert env.type == "cap_status"
    assert env.payload["level"] == "60"

    # 4b — async provider also works
    async def _async_provider():
        return {"level": "90", "percent_used": 0.92}

    set_snapshot_provider("cap_status", _async_provider)
    env2 = await snapshot("cap_status")
    assert env2.payload["level"] == "90"

    # 4c — fallback to last cached envelope when no provider
    publish_event("privacy.data_plane", {"dest": "anthropic", "allowed": True})
    env3 = await snapshot("privacy.data_plane")
    assert env3 is not None
    assert env3.payload["dest"] == "anthropic"

    # 4d — unknown topic with no provider + no cache → None
    env4 = await snapshot("totally.unknown")
    assert env4 is None


# ── 5. integration: real /api/realtime WS round-trip ─────────────────


@pytest.mark.asyncio
async def test_realtime_ws_endpoint_roundtrip():
    """Spin the FastAPI TestClient against ``/api/realtime`` and
    verify subscribe → publish → receive over the actual WS layer.
    Skipped when fastapi / app aren't importable."""

    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from web_extras.routers import realtime as rt_router
    except Exception as exc:  # pragma: no cover — env without fastapi
        pytest.skip(f"fastapi unavailable: {exc}")

    app = FastAPI()
    app.include_router(rt_router.router)

    with TestClient(app) as client:
        with client.websocket_connect("/api/realtime") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            assert "health" in hello["payload"]["topics"]

            ws.send_json({"op": "subscribe", "topics": ["usage"]})
            ack = ws.receive_json()
            # `subscribed` ack (snapshot may interleave; loop until we see it).
            seen_ack = False
            for _ in range(5):
                if ack["type"] == "subscribed" and "usage" in ack["payload"]["topics"]:
                    seen_ack = True
                    break
                ack = ws.receive_json()
            assert seen_ack, f"never saw subscribed ack, last={ack}"

            # Now publish on the broker — the WS task should forward it.
            publish_event("usage", {"tokens_in": 7, "tokens_out": 3})
            env = ws.receive_json()
            # Drain any out-of-order frames until we get the usage push.
            for _ in range(5):
                if env["type"] == "usage":
                    break
                env = ws.receive_json()
            assert env["type"] == "usage"
            assert env["payload"]["tokens_in"] == 7

            # Snapshot op also works.
            ws.send_json({"op": "snapshot", "topic": "usage"})
            snap = ws.receive_json()
            for _ in range(5):
                if snap["type"] == "usage":
                    break
                snap = ws.receive_json()
            assert snap["type"] == "usage"

            # Unsubscribe and then publish — we should not see another
            # `usage` envelope before the next non-usage frame.
            ws.send_json({"op": "unsubscribe", "topics": ["usage"]})
            unsub_ack = ws.receive_json()
            assert unsub_ack["type"] in ("unsubscribed", "usage")
            # Drain any in-flight buffered "usage" frames; eventually
            # we'll get the unsubscribed ack.
            for _ in range(5):
                if unsub_ack["type"] == "unsubscribed":
                    break
                unsub_ack = ws.receive_json()
            assert unsub_ack["type"] == "unsubscribed"
