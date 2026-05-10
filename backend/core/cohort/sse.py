"""In-process SSE pub/sub for cohort live events (Wave 94).

Each cohort gets a fan-out registry of ``asyncio.Queue`` subscribers.
``publish(cohort_id, event)`` non-blockingly enqueues the event into
every live subscriber. ``subscribe(cohort_id)`` is an async generator
that yields events as they arrive, with a 15 s heartbeat sentinel to
keep the SSE connection from being killed by intermediate proxies.

This is single-process only — fine for local single-tenant TARS. v9.3
multi-tenant will swap to a Redis pub/sub backend without changing
the public surface.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator


# Heartbeat cadence (seconds). Matches the `retry: 15000` advisory the
# router emits so reconnects line up with the heartbeat.
HEARTBEAT_INTERVAL_S = 15.0

# Bound on per-subscriber queue depth. If a subscriber falls this far
# behind we drop the oldest event rather than back-pressure the
# publisher (the dashboard is best-effort, not transactional).
_MAX_QUEUE_DEPTH = 256


# Map of cohort_id -> set of asyncio.Queue subscribers.
_subscribers: dict[str, set[asyncio.Queue]] = {}
# Lock guarding _subscribers structural changes (add/remove). We don't
# hold it across await points to keep the publish hot path latency-free.
_lock = asyncio.Lock()


def _heartbeat_event() -> dict[str, Any]:
    return {
        "id": f"hb_{int(time.time() * 1000)}",
        "type": "heartbeat",
        "occurred_at": time.time(),
        "data": {},
    }


async def publish(cohort_id: str, event: dict[str, Any]) -> int:
    """Fan an event out to every live subscriber on this cohort.

    Returns the number of subscribers the event was dispatched to.
    Never raises; a bad event shape just gets enqueued as-is and is
    the consumer's problem to deal with.
    """

    if not cohort_id:
        return 0
    subs = _subscribers.get(cohort_id)
    if not subs:
        return 0
    delivered = 0
    # Snapshot the set so we don't mutate during iteration. The cost
    # is one shallow copy of refs.
    for q in list(subs):
        try:
            if q.qsize() >= _MAX_QUEUE_DEPTH:
                # Drop the oldest to make room.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)
            delivered += 1
        except Exception:
            # Malformed queue / closed loop — silently skip.
            continue
    return delivered


async def _register(cohort_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_DEPTH)
    async with _lock:
        bucket = _subscribers.setdefault(cohort_id, set())
        bucket.add(q)
    return q


async def _unregister(cohort_id: str, q: asyncio.Queue) -> None:
    async with _lock:
        bucket = _subscribers.get(cohort_id)
        if bucket is None:
            return
        bucket.discard(q)
        if not bucket:
            _subscribers.pop(cohort_id, None)


async def subscribe(
    cohort_id: str,
    *,
    heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
) -> AsyncIterator[dict[str, Any]]:
    """Async generator yielding live events for one cohort.

    Yields a synthetic ``heartbeat`` event every
    ``heartbeat_interval_s`` seconds when the queue is idle, so SSE
    consumers (and intermediate proxies / load balancers) keep the
    connection open.
    """

    q = await _register(cohort_id)
    try:
        # Initial sentinel — confirms the stream is live before any
        # real events flow. Helpful for FE skeleton → ready transition.
        yield {
            "id": f"open_{int(time.time() * 1000)}",
            "type": "stream.open",
            "occurred_at": time.time(),
            "data": {"cohort_id": cohort_id},
        }
        while True:
            try:
                event = await asyncio.wait_for(
                    q.get(), timeout=heartbeat_interval_s
                )
                yield event
            except asyncio.TimeoutError:
                yield _heartbeat_event()
    finally:
        await _unregister(cohort_id, q)


def subscriber_count(cohort_id: str) -> int:
    """Return the current subscriber count for a cohort.

    Cheap accessor used by tests + the optional SSE health endpoint.
    """

    bucket = _subscribers.get(cohort_id)
    return len(bucket) if bucket else 0


def reset_subscribers() -> None:
    """Clear every subscriber bucket — for tests only."""

    _subscribers.clear()
