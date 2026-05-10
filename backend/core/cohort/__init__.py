"""TARS cohort tracking subsystem (Wave 94).

Real-time facilitator dashboard backend for `/workshop/cohort`. Replaces
the Wave 89 mock SSE with durable attendee tracking + in-process pub/sub.

Persists to ``~/.tars/cohort.sqlite`` (override via
``TARS_COHORT_DB_PATH``). Disable with ``TARS_COHORT_STORE=disabled``.

Public surface:

- :mod:`.models`  — dataclasses (`Cohort`, `Attendee`, `AttendeeAction`).
- :mod:`.store`   — SQLite-backed CRUD + status aggregation + timeline.
- :mod:`.events`  — webhook event → AttendeeAction translation +
  phase inference + active-now compute.
- :mod:`.sse`     — in-process pub/sub via asyncio.Queue; subscribe
  yields events with 15 s heartbeat.

Hot-path helpers (best-effort, never raise):

- :func:`is_member`               — fast email→attendee lookup.
- :func:`record_action_if_member` — record an action only when the
  attendee is in some cohort. Wrap in try/except at the call site.

Contract version: 1.0 (see ``docs/contracts/COHORT.md``).
"""

from __future__ import annotations

import logging
from typing import Any

from .events import (
    compute_active_now,
    infer_phase_advance,
    record_from_webhook_event,
)
from .models import (
    CONTRACT_VERSION,
    PHASES,
    Attendee,
    AttendeeAction,
    Cohort,
    new_action_id,
    new_attendee_id,
    new_cohort_id,
    new_token,
)
from .sse import publish, subscribe
from .store import CohortStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "PHASES",
    "Attendee",
    "AttendeeAction",
    "Cohort",
    "CohortStore",
    "compute_active_now",
    "get_store",
    "infer_phase_advance",
    "is_member",
    "new_action_id",
    "new_attendee_id",
    "new_cohort_id",
    "new_token",
    "publish",
    "record_action_if_member",
    "record_from_webhook_event",
    "reset_store",
    "subscribe",
]


_log = logging.getLogger("tars.cohort")


async def is_member(email: str) -> bool:
    """Return True if `email` is registered as an attendee anywhere.

    Best-effort: never raises; returns False when the store is
    disabled or any lookup error fires.
    """

    if not email:
        return False
    try:
        store = get_store()
        if not store.enabled:
            return False
        return await store.find_attendee_by_email(email) is not None
    except Exception as exc:  # pragma: no cover - never break callers
        _log.debug("cohort.is_member swallowed: %s: %s", type(exc).__name__, exc)
        return False


async def record_action_if_member(
    email: str | None,
    action_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record an action against the attendee with this email if any.

    Returns ``{ok, attendee_id?, cohort_id?}``. Swallows every
    exception so the calling hot path never breaks.
    """

    if not email:
        return {"ok": True, "matched": False}
    try:
        store = get_store()
        if not store.enabled:
            return {"ok": True, "matched": False, "reason": "disabled"}
        att = await store.find_attendee_by_email(email)
        if att is None:
            return {"ok": True, "matched": False}
        action = await store.record_action(
            attendee_id=att.id,
            action_type=action_type,
            payload=dict(payload or {}),
        )
        # Best-effort SSE fan-out so dashboards see the event live.
        try:
            await publish(
                att.cohort_id,
                {
                    "id": action.id,
                    "type": action_type,
                    "occurred_at": action.occurred_at,
                    "data": {
                        "attendee_id": att.id,
                        "email": att.email,
                        "display_name": att.display_name,
                        **(payload or {}),
                    },
                },
            )
        except Exception:
            pass
        return {
            "ok": True,
            "matched": True,
            "attendee_id": att.id,
            "cohort_id": att.cohort_id,
        }
    except Exception as exc:  # pragma: no cover - never break callers
        _log.debug(
            "cohort.record_action_if_member swallowed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return {"ok": False, "matched": False, "error": str(exc)}
