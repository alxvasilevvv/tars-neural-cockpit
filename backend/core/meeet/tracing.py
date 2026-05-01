"""Trace + session + route context for end-to-end logging.

Every TARS request gets one ``trace_id`` carried through context vars.
On top of that we now plumb two more dimensions:

- ``session_id`` — long-lived correlation handle the cockpit assigns when
  an operator starts working ("morning standup", "trade review"). Multiple
  trace ids can roll up to the same session, so the meeet event log
  reconstructs operator narratives.
- ``route`` — where the request was actually serviced: ``edge`` (purely
  local, deterministic), ``cloud`` (LLM voice or upstream API hit),
  ``fallback`` (cloud failed, edge took over). Tagged on every emitted
  event so meeet can render a routing map.

Cross-process consumers (meeet.world ingest) receive the same trio
through the event payload (see ``MeeetClient.emit``).
"""

from __future__ import annotations

import contextvars
import secrets
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Literal, Mapping, Sequence

Route = Literal["edge", "cloud", "fallback", "mixed"]

_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tars.trace_id", default=None
)
_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tars.session_id", default=None
)
_route: contextvars.ContextVar[Route | None] = contextvars.ContextVar(
    "tars.route", default=None
)


def new_trace_id() -> str:
    """Return a fresh trace id (``trc_<unix_ms>_<urlsafe_token>``)."""

    return f"trc_{int(time.time() * 1000)}_{secrets.token_urlsafe(8)}"


def new_session_id() -> str:
    """Return a fresh session id (``ses_<urlsafe_token>``)."""

    return f"ses_{secrets.token_urlsafe(8)}"


def start_trace(parent: str | None = None) -> str:
    trace_id = parent or new_trace_id()
    _trace.set(trace_id)
    return trace_id


def current_trace() -> str | None:
    return _trace.get()


def current_session() -> str | None:
    return _session.get()


def current_route() -> Route | None:
    return _route.get()


def set_route(route: Route | None) -> None:
    """Set the route hint for the active scope.

    Idempotent contract:
    - ``edge``  → first concrete claim sticks; later ``edge`` no-op.
    - ``cloud`` → upgrades from ``edge`` (cloud crossed the boundary).
    - ``fallback`` → upgrades from anything (failure path took over).
    - ``mixed`` → set explicitly when both edge and cloud landed.
    """

    if route is None:
        _route.set(None)
        return
    cur = _route.get()
    rank = {"edge": 0, "cloud": 1, "mixed": 2, "fallback": 3}
    if cur is None or rank.get(route, 0) >= rank.get(cur, -1):
        _route.set(route)


@contextmanager
def trace_scope(
    parent: str | None = None,
    *,
    session: str | None = None,
    route: Route | None = None,
) -> Iterator[str]:
    """Open a fresh trace scope, optionally nested under a session/route.

    All three context vars are pushed and popped together so nested
    scopes never leak. Pass ``session`` to override the active session
    (e.g. SSE handshake creates a session, every action under it inherits).
    """

    trace_token = _trace.set(parent or new_trace_id())
    session_token = _session.set(session) if session is not None else None
    route_token = _route.set(route) if route is not None else None
    try:
        yield _trace.get()  # type: ignore[misc]
    finally:
        _trace.reset(trace_token)
        if session_token is not None:
            _session.reset(session_token)
        if route_token is not None:
            _route.reset(route_token)


@contextmanager
def session_scope(session_id: str | None = None) -> Iterator[str]:
    """Open a session scope. Generates an id when one isn't provided.

    Synchronous and silent — does not emit boundary events. Use
    :func:`async_session_scope` when you want narrative reconstruction
    via ``session.opened`` / ``session.closed`` events.
    """

    sid = session_id or new_session_id()
    token = _session.set(sid)
    try:
        yield sid
    finally:
        _session.reset(token)


def _iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(
        timespec="milliseconds"
    )


async def _safe_emit_session_event(
    kind: str, payload: Mapping[str, Any]
) -> None:
    """Best-effort emit; swallow any failure so boundary calls never crash callers.

    Uses a deferred import to avoid the ``meeet.client`` ↔ ``meeet.tracing``
    import cycle.
    """

    try:
        from .client import get_client

        await get_client().emit(kind, dict(payload))
    except Exception:
        return


@asynccontextmanager
async def async_session_scope(
    session_id: str | None = None,
    *,
    topic: str | None = None,
    participants: Sequence[str] | None = None,
    emit_boundary: bool = True,
) -> AsyncIterator[str]:
    """Async session scope that emits ``session.opened`` / ``session.closed``.

    Both events carry ``session_id``, ``topic``, ``participants`` and the
    paired ``started_at`` ISO timestamp; ``session.closed`` additionally
    carries ``ended_at`` and ``duration_ms``. The events are routed
    through :class:`MeeetClient` so they hit the durable SQLite buffer and
    (when configured) the meeet.world ingest. Pass ``emit_boundary=False``
    to inherit the silent semantics of :func:`session_scope`.
    """

    sid = session_id or new_session_id()
    parts = list(participants or ())
    started_at = time.time()
    started_iso = _iso_utc(started_at)
    token = _session.set(sid)
    if emit_boundary:
        await _safe_emit_session_event(
            "session.opened",
            {
                "session_id": sid,
                "topic": topic,
                "participants": parts,
                "started_at": started_iso,
            },
        )
    try:
        yield sid
    finally:
        if emit_boundary:
            ended_at = time.time()
            await _safe_emit_session_event(
                "session.closed",
                {
                    "session_id": sid,
                    "topic": topic,
                    "participants": parts,
                    "started_at": started_iso,
                    "ended_at": _iso_utc(ended_at),
                    "duration_ms": int((ended_at - started_at) * 1000),
                },
            )
        _session.reset(token)
