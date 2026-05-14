"""W248 — unified in-process WebSocket event bus.

Public surface:

- :func:`publish_event` -- non-blocking fanout from any module
- :func:`subscribe`     -- async generator of envelopes for one topic
- :func:`snapshot`      -- one-shot read of the last cached envelope
- :func:`set_snapshot_provider` -- register a callable that produces a
  fresh state object for a topic on demand (so ``{op:"snapshot"}`` over
  the WS works for callers that haven't yet seen a push)
- :func:`subscriber_count` / :func:`reset_for_tests`

The pattern mirrors :mod:`backend.core.cowork.stream` so brother's
core-bridge can lift the same shape later. Single-process / single-
tenant for v9.2; a v10.x multi-tenant deploy will swap the broker for
Redis pub/sub without changing the public surface.
"""

from __future__ import annotations

from .broker import (  # noqa: F401
    EventEnvelope,
    publish_event,
    subscribe,
    snapshot,
    set_snapshot_provider,
    subscriber_count,
    reset_for_tests,
)

__all__ = [
    "EventEnvelope",
    "publish_event",
    "subscribe",
    "snapshot",
    "set_snapshot_provider",
    "subscriber_count",
    "reset_for_tests",
]
