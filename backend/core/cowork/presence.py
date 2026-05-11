"""Heartbeat-based presence tracker for cowork sessions (Wave 129).

A member is *present* when their last heartbeat was less than
``PRESENCE_TTL_S`` seconds ago. The tracker keeps state in process —
single-tenant TARS doesn't need a distributed store. v9.3 multi-tenant
will swap to Redis-backed presence without changing the public surface.

The tracker is intentionally tiny: it doesn't care about Member rows,
it just records ``(session_id, member_id) → last_seen_at`` and answers
``who_is_present(session_id)``. The store is the source of truth for
*membership*; presence is the source of truth for *liveness*.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


# How long after a heartbeat a member is still considered "present".
# Frontend pings every 10 s; 25 s gives us 2 missed beats of slack
# before the dot goes grey.
PRESENCE_TTL_S: float = 25.0


@dataclass
class PresenceState:
    """One member's presence record."""

    member_id: str
    last_seen_at: float
    typing: bool = False
    focus_path: str | None = None  # which shared file/buffer they're on

    def is_present(self, now: float | None = None) -> bool:
        ref = now if now is not None else time.time()
        return (ref - self.last_seen_at) < PRESENCE_TTL_S


class PresenceTracker:
    """In-process presence for cowork sessions.

    Concurrent reads + writes are safe — the inner dict ops are atomic
    enough for our use (presence is best-effort UX hint, not a primary
    record). We don't hold any lock across awaits.
    """

    def __init__(self) -> None:
        # session_id -> {member_id -> PresenceState}
        self._state: dict[str, dict[str, PresenceState]] = {}

    def heartbeat(
        self,
        session_id: str,
        member_id: str,
        *,
        typing: bool = False,
        focus_path: str | None = None,
    ) -> PresenceState:
        """Record a heartbeat. Returns the updated state."""

        if not session_id or not member_id:
            # Defensive: never let bad input crash the hot path.
            return PresenceState(
                member_id=member_id or "",
                last_seen_at=time.time(),
                typing=typing,
                focus_path=focus_path,
            )
        bucket = self._state.setdefault(session_id, {})
        state = bucket.get(member_id)
        if state is None:
            state = PresenceState(
                member_id=member_id,
                last_seen_at=time.time(),
                typing=typing,
                focus_path=focus_path,
            )
            bucket[member_id] = state
        else:
            state.last_seen_at = time.time()
            state.typing = typing
            state.focus_path = focus_path
        return state

    def who_is_present(self, session_id: str) -> list[PresenceState]:
        """Return live members. Stale records are filtered, not deleted —
        a follow-up :meth:`gc` pass cleans them up."""

        bucket = self._state.get(session_id)
        if not bucket:
            return []
        now = time.time()
        return [s for s in bucket.values() if s.is_present(now)]

    def member_state(
        self, session_id: str, member_id: str
    ) -> PresenceState | None:
        bucket = self._state.get(session_id)
        if not bucket:
            return None
        return bucket.get(member_id)

    def leave(self, session_id: str, member_id: str) -> None:
        """Explicit leave — drop the record immediately rather than
        waiting for TTL expiry."""

        bucket = self._state.get(session_id)
        if not bucket:
            return
        bucket.pop(member_id, None)
        if not bucket:
            self._state.pop(session_id, None)

    def gc(self) -> int:
        """Drop stale records across all sessions. Returns count dropped.

        Cheap enough to call from a periodic task or piggy-back on the
        SSE heartbeat tick.
        """

        now = time.time()
        dropped = 0
        for sid in list(self._state.keys()):
            bucket = self._state[sid]
            for mid in list(bucket.keys()):
                if not bucket[mid].is_present(now):
                    del bucket[mid]
                    dropped += 1
            if not bucket:
                del self._state[sid]
        return dropped

    def snapshot(self) -> dict[str, list[PresenceState]]:
        """Test helper: full state dump."""

        out: dict[str, list[PresenceState]] = {}
        for sid, bucket in self._state.items():
            out[sid] = list(bucket.values())
        return out


# ---------- Module singleton -------------------------------------------------


_tracker_singleton: PresenceTracker | None = None
_tracker_lock = asyncio.Lock()


async def get_tracker() -> PresenceTracker:
    global _tracker_singleton
    if _tracker_singleton is not None:
        return _tracker_singleton
    async with _tracker_lock:
        if _tracker_singleton is None:
            _tracker_singleton = PresenceTracker()
        return _tracker_singleton


def reset_tracker() -> None:
    """Test helper: drop the cached singleton."""

    global _tracker_singleton
    _tracker_singleton = None
