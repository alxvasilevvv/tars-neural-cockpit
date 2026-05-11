"""In-process SSE/WebSocket pub/sub for cowork events (Wave 129).

Pattern lifted from :mod:`backend.core.cohort.sse` so brother's
core-bridge has one mental model for both surfaces. Each session
gets a fan-out registry of ``asyncio.Queue`` subscribers; ``publish``
non-blockingly enqueues an event onto every subscriber; ``subscribe``
is an async generator that yields events with a 15 s heartbeat
sentinel.

Event shape — a thin envelope, type-discriminated:

    {
      "id": "<server-assigned>",
      "type": "agent.frame" | "presence" | "cursor" | "chat"
              | "handoff.created" | "handoff.accepted" | "session.ended"
              | "heartbeat",
      "occurred_at": <unix-seconds-float>,
      "data": { … type-specific payload … }
    }

Single-process for single-tenant TARS. v9.3 multi-tenant will swap
to Redis pub/sub backend without changing the public surface.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncIterator


HEARTBEAT_INTERVAL_S = 15.0

# Bound on per-subscriber queue depth. If a subscriber falls this far
# behind we drop the oldest event rather than back-pressure the
# publisher (cowork events are advisory UX, not transactional).
_MAX_QUEUE_DEPTH = 256


# Map of session_id -> set of asyncio.Queue subscribers.
_subscribers: dict[str, set[asyncio.Queue]] = {}
_lock = asyncio.Lock()


def _new_event_id() -> str:
    return f"ev_{uuid.uuid4().hex[:18]}"


def _heartbeat_event() -> dict[str, Any]:
    return {
        "id": f"hb_{int(time.time() * 1000)}",
        "type": "heartbeat",
        "occurred_at": time.time(),
        "data": {},
    }


async def publish(session_id: str, event: dict[str, Any]) -> int:
    """Fan an event out to every live subscriber on this session.

    Returns the number of subscribers the event was dispatched to.
    Never raises; a bad event shape gets passed through and is the
    consumer's problem.
    """

    if not session_id:
        return 0

    # Normalise envelope: add id + occurred_at if the caller didn't.
    if "id" not in event:
        event["id"] = _new_event_id()
    if "occurred_at" not in event:
        event["occurred_at"] = time.time()

    subs = _subscribers.get(session_id)
    if not subs:
        return 0
    delivered = 0
    for q in list(subs):
        try:
            if q.qsize() >= _MAX_QUEUE_DEPTH:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)
            delivered += 1
        except Exception:
            continue
    return delivered


async def _register(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_DEPTH)
    async with _lock:
        _subscribers.setdefault(session_id, set()).add(q)
    return q


async def _unregister(session_id: str, q: asyncio.Queue) -> None:
    async with _lock:
        bucket = _subscribers.get(session_id)
        if bucket:
            bucket.discard(q)
            if not bucket:
                _subscribers.pop(session_id, None)


async def subscribe(
    session_id: str,
    *,
    heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
) -> AsyncIterator[dict[str, Any]]:
    """Async generator yielding events for a session.

    Emits a synthetic ``heartbeat`` event every ``heartbeat_interval_s``
    seconds when no real events arrive. The router consuming this
    generator should serialise to SSE ``data: <json>\\n\\n`` frames.

    Usage::

        async for event in subscribe("cw_..."):
            yield f"data: {json.dumps(event)}\\n\\n"
    """

    if not session_id:
        return
    q = await _register(session_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    q.get(), timeout=heartbeat_interval_s
                )
                yield event
            except asyncio.TimeoutError:
                yield _heartbeat_event()
    finally:
        await _unregister(session_id, q)


def subscriber_count(session_id: str | None = None) -> int:
    """Total subscribers, or the count for one session."""

    if session_id is None:
        return sum(len(s) for s in _subscribers.values())
    return len(_subscribers.get(session_id, set()))


def reset_subscribers() -> None:
    """Test helper: drop all subscriber state. Don't call in prod."""

    _subscribers.clear()
