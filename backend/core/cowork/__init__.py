"""TARS cowork subsystem (Wave 129).

Multi-user real-time collaboration over agent sessions and shared
workspace files. Closes the gap that the W122 audit flagged: tasks
#99 (Shared Agent Sessions) and #100 (TARS Handoff) were historically
marked complete but had no live backend code. This module ships them.

Conceptually equivalent to the "Cowork mode" in Anthropic's desktop
app — several humans + an agent share a session: live presence,
shared cursors over workspace files, fan-out of agent run events,
and a one-click handoff that transfers ownership of an active session
to another user.

Architecture mirrors the W94 cohort module:

- :mod:`.models`   — dataclasses (`Session`, `Member`, `Cursor`,
  `Handoff`) plus ID + token helpers.
- :mod:`.store`    — SQLite-backed CRUD at ``~/.tars/cowork.sqlite``
  (override via ``TARS_COWORK_DB_PATH``). WAL + ``asyncio.to_thread``
  discipline, same as the rest of the W90+ stack.
- :mod:`.presence` — heartbeat-based liveness tracking with a 25 s
  TTL window. Pure in-process; v9.3 multi-tenant will swap to Redis
  without changing the public surface.
- :mod:`.stream`   — in-process pub/sub via ``asyncio.Queue`` with
  15 s heartbeat sentinel, fan-out of agent run frames + cursor +
  presence + handoff events.
- :mod:`.handoff`  — token-gated session ownership transfer with
  TTL + single-use semantics.

Disable the whole module with ``TARS_COWORK_STORE=disabled``. Hot-path
helpers swallow exceptions so a misbehaving store never breaks the
caller (the orchestrator stays decoupled from cowork plumbing).

Contract version: 1.0 (see ``docs/contracts/COWORK.md``).
"""

from __future__ import annotations

import logging
from typing import Any

from .handoff import (
    HandoffError,
    accept_handoff,
    create_handoff,
    get_handoff,
)
from .models import (
    CONTRACT_VERSION,
    Cursor,
    Handoff,
    Member,
    MemberRole,
    Session,
    SessionStatus,
    new_cursor_id,
    new_handoff_id,
    new_member_id,
    new_session_id,
    new_token,
)
from .presence import (
    PresenceState,
    PresenceTracker,
    get_tracker,
    reset_tracker,
)
from .store import CoworkStore, get_store, reset_store
from .stream import (
    HEARTBEAT_INTERVAL_S,
    publish,
    subscribe,
    subscriber_count,
)

logger = logging.getLogger(__name__)


__all__ = [
    "CONTRACT_VERSION",
    "CoworkStore",
    "Cursor",
    "HEARTBEAT_INTERVAL_S",
    "Handoff",
    "HandoffError",
    "Member",
    "MemberRole",
    "PresenceState",
    "PresenceTracker",
    "Session",
    "SessionStatus",
    "accept_handoff",
    "create_handoff",
    "emit_agent_frame",
    "get_handoff",
    "get_store",
    "get_tracker",
    "new_cursor_id",
    "new_handoff_id",
    "new_member_id",
    "new_session_id",
    "new_token",
    "publish",
    "reset_store",
    "reset_tracker",
    "subscribe",
    "subscriber_count",
]


async def emit_agent_frame(
    session_id: str,
    frame_type: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """Best-effort: publish one agent-run frame onto a cowork session.

    Called from the orchestrator hot path. Swallows every exception so
    that a Cowork outage cannot block agent execution. Returns the
    number of subscribers the frame was delivered to, or 0 on failure.
    """

    try:
        return await publish(
            session_id,
            {
                "type": "agent.frame",
                "frame_type": frame_type,
                "data": payload or {},
            },
        )
    except Exception:  # noqa: BLE001 — intentionally permissive
        logger.debug("emit_agent_frame swallowed exception", exc_info=True)
        return 0
