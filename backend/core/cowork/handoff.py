"""TARS Handoff — session ownership transfer (Wave 129).

Closes the W122 audit gap on task #100: a one-time token that lets
the owner of an active cowork session hand it off to another user
(typically by sending them a link). The recipient ``accept``\\s the
handoff, the store atomically swaps owner_user_id, and a
``handoff.accepted`` event is broadcast to every subscriber so the
UI updates in real time on everyone's screen.

Properties:

- *Single-use*: ``accept`` flips ``accepted_at`` atomically with a
  conditional UPDATE. A second accept on the same token loses the
  race and raises :class:`HandoffError`.
- *Short TTL*: default 15 min (see :data:`models.DEFAULT_HANDOFF_TTL_S`).
  Expired tokens accept silently fails.
- *Revocable*: the original owner can revoke a pending handoff.
- *Audited*: every state change is durable in ``handoffs`` table; the
  W104 compliance bundler picks them up automatically.
"""

from __future__ import annotations

import time
from typing import Any

from .models import Handoff, new_handoff_id, new_token
from .store import get_store
from .stream import publish


class HandoffError(Exception):
    """Raised when a handoff state transition can't proceed."""


async def create_handoff(
    *,
    session_id: str,
    from_user_id: str,
    to_email: str | None = None,
    ttl_seconds: int | None = None,
) -> Handoff:
    """Open a pending handoff for ``session_id``.

    The returned handoff carries a fresh :data:`Handoff.token`; the
    sender shares it with the recipient via whatever channel they
    like (link, email, Slack DM). The recipient calls
    :func:`accept_handoff` with the same token.

    Raises :class:`HandoffError` if:
      - the session doesn't exist
      - the session is not LIVE (no point handing off an ended session)
      - ``from_user_id`` isn't the current owner.
    """

    store = await get_store()
    session = await store.get_session(session_id)
    if session is None:
        raise HandoffError(f"session {session_id!r} not found")
    if not session.is_active:
        raise HandoffError(
            f"session {session_id!r} is not live (status={session.status.value})"
        )
    if session.owner_user_id != from_user_id:
        raise HandoffError(
            "only the current owner can initiate a handoff"
        )

    handoff = Handoff(
        id=new_handoff_id(),
        session_id=session_id,
        from_user_id=from_user_id,
        to_email=(to_email or None) and to_email.strip().lower() or None,
        token=new_token(),
    )
    if ttl_seconds is not None and ttl_seconds > 0:
        handoff.expires_at = time.time() + int(ttl_seconds)

    await store.insert_handoff(handoff)
    await publish(
        session_id,
        {
            "type": "handoff.created",
            "data": {
                "handoff_id": handoff.id,
                "to_email": handoff.to_email,
                "expires_at": handoff.expires_at,
            },
        },
    )
    return handoff


async def get_handoff(token: str) -> Handoff | None:
    """Look up a handoff by token. Returns ``None`` if not found."""

    if not token:
        return None
    store = await get_store()
    return await store.get_handoff_by_token(token)


async def accept_handoff(
    *,
    token: str,
    accepted_by_user_id: str,
) -> Handoff:
    """Accept a pending handoff. Transfers ownership atomically.

    Raises :class:`HandoffError` for invalid token / already accepted /
    expired / revoked. Re-fetches the handoff after the atomic UPDATE
    so the returned record reflects the new state.
    """

    if not token:
        raise HandoffError("token is required")
    if not accepted_by_user_id:
        raise HandoffError("accepted_by_user_id is required")

    store = await get_store()
    handoff = await store.get_handoff_by_token(token)
    if handoff is None:
        raise HandoffError("unknown handoff token")
    if handoff.accepted_at is not None:
        raise HandoffError("handoff already accepted")
    if handoff.revoked_at is not None:
        raise HandoffError("handoff was revoked")
    if handoff.is_expired:
        raise HandoffError("handoff has expired")

    # Atomic accept — only one winner under concurrent calls.
    ok = await store.mark_handoff_accepted(handoff.id, accepted_by_user_id)
    if not ok:
        # Re-fetch to give a precise error.
        h2 = await store.get_handoff_by_token(token)
        if h2 and h2.accepted_at is not None:
            raise HandoffError("handoff already accepted")
        raise HandoffError("handoff could not be accepted (expired or revoked)")

    transferred = await store.transfer_ownership(
        handoff.session_id, accepted_by_user_id
    )
    if not transferred:
        # This is unreachable in practice — we just confirmed the session
        # existed at create time and no one deletes session rows in cowork.
        # But surface a precise error if it ever happens.
        raise HandoffError("ownership transfer failed unexpectedly")

    updated = await store.get_handoff_by_token(token)
    assert updated is not None  # we just wrote it

    await publish(
        handoff.session_id,
        {
            "type": "handoff.accepted",
            "data": {
                "handoff_id": handoff.id,
                "accepted_by_user_id": accepted_by_user_id,
                "from_user_id": handoff.from_user_id,
            },
        },
    )
    return updated


async def revoke_handoff(
    *,
    handoff_id: str,
    requested_by_user_id: str,
) -> bool:
    """Revoke a pending handoff. Returns ``True`` if state changed."""

    if not handoff_id:
        return False
    store = await get_store()
    # Quick guard: only the originator can revoke.
    # (We don't have a direct fetch-by-id helper; round-trip through
    # a list-by-session would be heavier than a tiny dedicated lookup
    # — but the store interface is intentionally compact and a token
    # lookup is the only public read. So accept the cost of a get-all
    # filter for now; this is a low-rate operation.)
    sessions = await store.list_sessions()
    handoff: Handoff | None = None
    for session in sessions:
        # Cheap: pull handoffs only when we need them. For now we use
        # the token-keyed lookup if the caller passed one; otherwise
        # fall back to ID lookup via a token-less store read.
        # (This is a v9.3 perf optimisation candidate — for v9.1 the
        # call rate is trivial.)
        _ = session  # noqa: unused — explicit no-op for the loop body
        break
    # Pull the row via the SQL store directly. The simplest approach
    # is to bypass token uniqueness and use the id column via a small
    # additional store method — added inline below.
    handoff = await _get_handoff_by_id(handoff_id)
    if handoff is None:
        return False
    if handoff.from_user_id != requested_by_user_id:
        raise HandoffError("only the originator can revoke a handoff")
    if not handoff.is_pending:
        return False

    ok = await store.revoke_handoff(handoff_id)
    if ok:
        await publish(
            handoff.session_id,
            {
                "type": "handoff.revoked",
                "data": {"handoff_id": handoff_id},
            },
        )
    return ok


async def _get_handoff_by_id(handoff_id: str) -> Handoff | None:
    """Local helper: fetch a handoff by its ID.

    Implemented here rather than on the store so the public store
    surface stays focused on the token-keyed flow that 99% of callers
    use; revoke is a rare path.
    """

    import asyncio as _aio  # local import to dodge a circular issue at boot

    store = await get_store()
    # Reach into the store's connection pattern. This is the only
    # place that touches SQLite outside store.py; kept tight.
    def _read() -> Handoff | None:
        conn = store._connect()  # noqa: SLF001 — intentional, see docstring
        try:
            row = conn.execute(
                "SELECT * FROM handoffs WHERE id=?", (handoff_id,)
            ).fetchone()
            if row is None:
                return None
            from .store import _row_to_handoff  # local import to avoid cycle
            return _row_to_handoff(row)
        finally:
            conn.close()

    return await _aio.to_thread(_read)
