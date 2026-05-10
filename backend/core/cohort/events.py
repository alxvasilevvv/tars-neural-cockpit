"""Event sourcing helpers for the cohort module (Wave 94).

Bridges the webhook event envelope (``{id, type, occurred_at, data}``)
with attendee-action tracking, plus a couple of pure-functional
helpers for stat aggregation.

Public surface:

- :func:`record_from_webhook_event` — match a webhook envelope to an
  attendee (by ``email`` or ``attendee_token`` in ``data``) and append
  an :class:`AttendeeAction`.
- :func:`infer_phase_advance` — heuristic to detect when a recent
  action history implies the attendee should move to the next phase.
- :func:`compute_active_now` — count of attendees with an action in
  the last N seconds (independent of the rolled counter on the row).
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from .models import (
    PHASES,
    AttendeeAction,
    next_phase,
    normalize_phase,
)


# Webhook event types we know how to translate. Anything outside this
# set falls through to a generic action with ``type=event["type"]``.
EVENT_TYPE_TO_ACTION: dict[str, str] = {
    "playbook.started": "playbook_start",
    "playbook.finished": "playbook_finish",
    "playbook.completed": "playbook_finish",
    "playbook.failed": "error",
    "playbook.error": "error",
    "hil.requested": "hil_gate",
    "hil.approved": "playbook_finish",
    "cohort.broadcast.ack": "broadcast_ack",
    "cohort.attendee.joined": "join",
    "cohort.phase.advanced": "phase_advance",
}


def _extract_attendee_key(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pull (email, attendee_token) out of an event data dict.

    Both fields are optional; the caller picks whichever the store
    can resolve. Email is normalised to lowercase here so the store
    indexed lookup matches.
    """

    email = data.get("email") or data.get("attendee_email")
    token = data.get("attendee_token") or data.get("token")
    email_norm = str(email).strip().lower() if email else None
    token_norm = str(token).strip() if token else None
    return email_norm or None, token_norm or None


async def record_from_webhook_event(
    cohort_id: str,
    event: dict[str, Any],
    *,
    store=None,
) -> dict[str, Any]:
    """Translate a webhook envelope into an :class:`AttendeeAction`.

    Resolves the attendee from ``data.email`` first, then
    ``data.attendee_token``. Returns ``{ok, matched, attendee_id?,
    action_id?, reason?}``. The ``cohort_id`` argument is used to
    constrain the email lookup so we don't accidentally write into a
    different cohort that happens to share an email.
    """

    if store is None:
        from .store import get_store

        store = get_store()
    if not store.enabled:
        return {"ok": True, "matched": False, "reason": "disabled"}

    if not isinstance(event, dict):
        return {"ok": False, "matched": False, "reason": "event_not_dict"}

    event_type = str(event.get("type") or "").strip()
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    occurred_at_raw = event.get("occurred_at")
    try:
        occurred_at = float(occurred_at_raw) if occurred_at_raw is not None else None
    except (TypeError, ValueError):
        occurred_at = None

    email, token = _extract_attendee_key(data)
    attendee = None
    if token:
        attendee = await store.get_attendee_by_token(token)
        # Make sure the attendee actually belongs to this cohort.
        if attendee is not None and attendee.cohort_id != cohort_id:
            attendee = None
    if attendee is None and email:
        cand = await store.find_attendee_by_email(email)
        if cand is not None and cand.cohort_id == cohort_id:
            attendee = cand
    if attendee is None:
        return {
            "ok": True,
            "matched": False,
            "reason": "no_attendee",
            "event_type": event_type,
        }

    action_type = EVENT_TYPE_TO_ACTION.get(event_type, event_type or "event")
    payload = dict(data)
    payload.setdefault("source_event_id", event.get("id"))
    payload.setdefault("source_event_type", event_type)

    action = await store.record_action(
        attendee_id=attendee.id,
        action_type=action_type,
        payload=payload,
        occurred_at=occurred_at,
    )
    return {
        "ok": True,
        "matched": True,
        "attendee_id": attendee.id,
        "action_id": action.id,
        "action_type": action_type,
        "cohort_id": cohort_id,
    }


# ---------- phase advance heuristic -----------------------------------------


# Action types that, when seen, imply the attendee has reached at least
# the corresponding phase. Order matters: the highest-rank match wins.
_PHASE_SIGNAL: tuple[tuple[str, str], ...] = (
    # action_type, implies_phase_at_least
    ("join", "intake"),
    ("playbook_start", "design"),
    ("hil_gate", "test"),
    ("playbook_finish", "test"),
    ("phase_advance", "deploy"),
)


def _phase_rank(phase: str) -> int:
    try:
        return PHASES.index(normalize_phase(phase))
    except ValueError:
        return 0


def infer_phase_advance(
    current_phase: str,
    recent_actions: Iterable[AttendeeAction | dict[str, Any]],
) -> str | None:
    """Suggest a next phase based on recent action history.

    Returns the phase the attendee should advance to (one step at a
    time; we never skip phases) or ``None`` if no advance is implied.

    The heuristic is intentionally simple and conservative:
    - We look at the highest-ranked phase implied by any recent action.
    - If it strictly exceeds the attendee's current phase, we advance
      by exactly one step toward it.
    - We never advance past ``deploy`` automatically; ``done`` requires
      an explicit phase_advance event.
    """

    cur_rank = _phase_rank(current_phase)
    implied_rank = cur_rank

    for raw in recent_actions:
        if isinstance(raw, AttendeeAction):
            action_type = raw.type
            payload = raw.payload
        elif isinstance(raw, dict):
            action_type = str(raw.get("type") or "")
            payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        else:
            continue

        # Explicit phase_advance with a target wins outright.
        if action_type == "phase_advance":
            target = payload.get("to") or payload.get("phase")
            if target:
                t_rank = _phase_rank(target)
                if t_rank > implied_rank:
                    implied_rank = t_rank

        for sig_action, sig_phase in _PHASE_SIGNAL:
            if action_type == sig_action:
                r = _phase_rank(sig_phase)
                if r > implied_rank:
                    implied_rank = r

    if implied_rank <= cur_rank:
        return None

    # Step exactly one phase forward, capped at deploy unless an
    # explicit phase_advance pushed us past it.
    suggestion = next_phase(PHASES[cur_rank])
    if suggestion is None:
        return None
    # If a stronger signal was seen, still return the one-step move
    # — phase advance should be a deliberate progression so the FE can
    # show a transition rather than a jump.
    return suggestion


# ---------- active-now compute ----------------------------------------------


async def compute_active_now(
    cohort_id: str,
    *,
    window_s: int = 300,
    store=None,
) -> int:
    """Count attendees with at least one action in the last `window_s`.

    Reads the most recent action per attendee from the actions table,
    so it stays accurate even if the rolled counters on the attendee
    row drift (e.g., manual DB edits).
    """

    if store is None:
        from .store import get_store

        store = get_store()
    if not store.enabled:
        return 0
    attendees = await store.list_attendees(cohort_id)
    if not attendees:
        return 0
    now = time.time()
    count = 0
    for att in attendees:
        recent = await store.attendee_timeline(att.id, limit=1)
        last_at = recent[0].occurred_at if recent else att.last_activity_at
        if (now - last_at) <= window_s:
            count += 1
    return count
