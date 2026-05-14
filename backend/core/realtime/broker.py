"""In-process pub/sub broker for the W248 unified WS event bus.

One :class:`asyncio.Queue` per (topic, subscriber). ``publish_event``
is non-blocking: a slow consumer just drops its oldest queued event
once the per-subscriber buffer fills. Cockpit dashboards are advisory
UX — never back-pressure the producer for them.

Envelope shape (every push, every snapshot):

    {
        "type":    "<topic>",
        "ts":      <unix-seconds-float>,
        "payload": { ... }
    }

The broker also caches the **last** envelope per topic so that:

1. A late subscriber gets immediate context on first connect.
2. ``{op: "snapshot", topic: "..."}`` returns something useful even
   when no fresh push has happened.

Topics are free-form strings; the router exposes a curated list to
clients. Backend modules import :func:`publish_event` and call it
inline — no plumbing needed.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, Union


# Bound on per-subscriber queue depth. Big enough that a normal
# subscriber never drops anything; small enough that a stalled client
# can't pin memory.
_MAX_QUEUE_DEPTH = 512


@dataclass
class EventEnvelope:
    """Server-pushed payload wrapper."""

    type: str
    ts: float
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "ts": self.ts, "payload": self.payload}


# ── module-level state ────────────────────────────────────────────────

#: topic -> set of asyncio queues (one per subscriber).
_subscribers: dict[str, set[asyncio.Queue[EventEnvelope]]] = {}

#: topic -> last envelope ever published. Used for cache-on-connect
#: and for the ``snapshot`` op when no provider is registered.
_last: dict[str, EventEnvelope] = {}

#: topic -> callable returning either a payload dict or an awaitable
#: producing one. When the router handles ``{op:"snapshot"}`` it asks
#: the provider for fresh state before falling back to ``_last``.
SnapshotProvider = Callable[[], Union[dict[str, Any], Awaitable[dict[str, Any]]]]
_snapshot_providers: dict[str, SnapshotProvider] = {}

_lock = asyncio.Lock()


# ── public API ────────────────────────────────────────────────────────


def publish_event(topic: str, payload: dict[str, Any]) -> int:
    """Fan an event out to every live subscriber on ``topic``.

    Returns the number of subscribers reached. Never raises — telemetry
    failures must not break the calling hot path. Safe to call from
    sync code (no event loop required); if called outside an event
    loop the broker still updates the last-envelope cache so a future
    snapshot returns the value.
    """

    if not topic:
        return 0
    env = EventEnvelope(type=topic, ts=time.time(), payload=payload or {})
    _last[topic] = env

    subs = _subscribers.get(topic)
    if not subs:
        return 0
    delivered = 0
    for q in list(subs):
        try:
            if q.qsize() >= _MAX_QUEUE_DEPTH:
                # Drop oldest so the queue never blocks.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(env)
            delivered += 1
        except Exception:
            # Slow / closed consumer — skip; the WS handler will
            # unregister it shortly.
            continue
    return delivered


def set_snapshot_provider(topic: str, provider: SnapshotProvider) -> None:
    """Register a callable that produces fresh state for ``topic``."""

    if not topic or not callable(provider):
        return
    _snapshot_providers[topic] = provider


async def snapshot(topic: str) -> Optional[EventEnvelope]:
    """Resolve the current state for ``topic``.

    Order of resolution:
        1. registered snapshot provider (async or sync)
        2. last published envelope cached in ``_last``
        3. ``None`` (no data yet)
    """

    if not topic:
        return None
    provider = _snapshot_providers.get(topic)
    if provider is not None:
        try:
            result = provider()
            if asyncio.iscoroutine(result):
                payload = await result
            else:
                payload = result
            if isinstance(payload, dict):
                env = EventEnvelope(type=topic, ts=time.time(), payload=payload)
                _last[topic] = env
                return env
        except Exception:
            # Fall through to the cache.
            pass
    return _last.get(topic)


async def _register(topic: str) -> asyncio.Queue[EventEnvelope]:
    q: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=_MAX_QUEUE_DEPTH)
    async with _lock:
        _subscribers.setdefault(topic, set()).add(q)
    return q


async def _unregister(topic: str, q: asyncio.Queue[EventEnvelope]) -> None:
    async with _lock:
        bucket = _subscribers.get(topic)
        if bucket:
            bucket.discard(q)
            if not bucket:
                _subscribers.pop(topic, None)


async def subscribe(topic: str) -> AsyncIterator[EventEnvelope]:
    """Async generator yielding every envelope published to ``topic``.

    The consumer is responsible for the heartbeat cadence — this iter
    blocks indefinitely on each ``queue.get()``. The router wraps
    multiple :func:`subscribe` calls (one per requested topic) inside
    its own ``asyncio.wait`` to multiplex onto a single WS connection.
    """

    if not topic:
        return
    q = await _register(topic)
    try:
        while True:
            env = await q.get()
            yield env
    finally:
        await _unregister(topic, q)


def subscriber_count(topic: Optional[str] = None) -> int:
    """Total live subscribers, or the count for one topic."""

    if topic is None:
        return sum(len(s) for s in _subscribers.values())
    return len(_subscribers.get(topic, set()))


def reset_for_tests() -> None:
    """Test helper — drop every queue + cache. Don't call in prod."""

    _subscribers.clear()
    _last.clear()
    _snapshot_providers.clear()
