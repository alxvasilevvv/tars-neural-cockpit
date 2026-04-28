"""Trace context for end-to-end logging.

Every TARS request gets one ``trace_id`` carried through context vars. The
domain router calls :func:`start_trace` at request entry; child coroutines
read :func:`current_trace`. Cross-process consumers (meeet.world ingest)
receive the same id through the event payload.
"""

from __future__ import annotations

import contextvars
import secrets
import time
from contextlib import contextmanager
from typing import Iterator

_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tars.trace_id", default=None
)


def new_trace_id() -> str:
    """Return a fresh trace id.

    Format: ``trc_<unix_ms>_<urlsafe_token>``. Sortable on prefix, unique
    by token. Matches what the meeet contract expects.
    """

    return f"trc_{int(time.time() * 1000)}_{secrets.token_urlsafe(8)}"


def start_trace(parent: str | None = None) -> str:
    """Set the trace context. Returns the active trace id.

    If ``parent`` is provided, it becomes the active trace (cross-service
    propagation). Otherwise a fresh id is generated.
    """

    trace_id = parent or new_trace_id()
    _trace.set(trace_id)
    return trace_id


def current_trace() -> str | None:
    return _trace.get()


@contextmanager
def trace_scope(parent: str | None = None) -> Iterator[str]:
    """Context manager: start a trace, restore previous on exit."""

    token = _trace.set(parent or new_trace_id())
    try:
        yield _trace.get()  # type: ignore[misc]
    finally:
        _trace.reset(token)
