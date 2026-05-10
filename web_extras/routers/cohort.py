"""HTTP surface for the cohort tracking subsystem (Wave 94).

Operator (facilitator) endpoints — manage cohorts + see live activity:

- ``GET    /api/cohort``                                      list cohorts
- ``POST   /api/cohort``                                      create cohort
- ``GET    /api/cohort/{id}``                                 cohort detail + status
- ``DELETE /api/cohort/{id}``                                 delete (cascade)
- ``POST   /api/cohort/{id}/end``                             mark cohort ended

- ``POST   /api/cohort/{id}/attendees``                       add attendee (returns token)
- ``GET    /api/cohort/{id}/attendees?filter=...``            list attendees
- ``GET    /api/cohort/{id}/attendees/{aid}/timeline``        recent actions
- ``POST   /api/cohort/{id}/attendees/{aid}/flag``            flag (body: {reason})
- ``DELETE /api/cohort/{id}/attendees/{aid}/flag``            unflag

- ``POST   /api/cohort/{id}/broadcast``                       fan-out + timeline rows
- ``GET    /api/cohort/{id}/stream``                          SSE live events

Attendee-facing endpoints — public, token-protected:

- ``POST   /api/cohort/join/{token}``                         self-join (no-op if
  the attendee already exists; returns the attendee record so the FE
  can stash ``attendee_id`` for subsequent action posts)
- ``POST   /api/cohort/attendee/{aid}/action``                manual action record
  (FE fires this when an attendee finishes a playbook from inside the
  embedded workshop UI)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.core.cohort import (
    PHASES,
    compute_active_now,
    get_store,
    publish,
    subscribe,
)


router = APIRouter(prefix="/api/cohort", tags=["cohort"])


# ---------- helpers ---------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="cohort_store_disabled")


def _cohort_to_dict(c) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "started_at": c.started_at,
        "ended_at": c.ended_at,
        "facilitator_user_id": c.facilitator_user_id,
        "max_attendees": c.max_attendees,
        "metadata": dict(c.metadata),
        "is_active": c.is_active,
    }


def _attendee_to_dict(a, *, include_token: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": a.id,
        "cohort_id": a.cohort_id,
        "display_name": a.display_name,
        "email": a.email,
        "joined_at": a.joined_at,
        "current_phase": a.current_phase,
        "last_activity_at": a.last_activity_at,
        "playbook_runs": a.playbook_runs,
        "errors": a.errors,
        "flagged": a.flagged,
        "flag_reason": a.flag_reason,
    }
    if include_token:
        out["token"] = a.token
    return out


def _action_to_dict(act) -> dict[str, Any]:
    return {
        "id": act.id,
        "attendee_id": act.attendee_id,
        "type": act.type,
        "occurred_at": act.occurred_at,
        "payload": dict(act.payload),
    }


# ---------- cohort CRUD ----------------------------------------------------


@router.get("")
async def list_cohorts(
    facilitator_user_id: str | None = Query(default=None),
    include_ended: bool = Query(default=True),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    cohorts = await store.list_cohorts(
        facilitator_user_id=facilitator_user_id,
        include_ended=include_ended,
    )
    return {
        "ok": True,
        "count": len(cohorts),
        "cohorts": [_cohort_to_dict(c) for c in cohorts],
    }


@router.post("")
async def create_cohort(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    name = str(payload.get("name") or "").strip()
    slug = str(payload.get("slug") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    if not slug:
        # Auto-derive slug from name; lowercase + hyphenate.
        slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower())
        slug = "-".join(p for p in slug.split("-") if p) or "cohort"
    max_attendees = payload.get("max_attendees")
    facilitator_user_id = payload.get("facilitator_user_id")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata_must_be_object")
    store = get_store()
    try:
        cohort = await store.create_cohort(
            name=name,
            slug=slug,
            facilitator_user_id=facilitator_user_id,
            max_attendees=int(max_attendees) if max_attendees else None,
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "cohort": _cohort_to_dict(cohort)}


@router.get("/{cohort_id}")
async def get_cohort(cohort_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    status = await store.get_cohort_status(cohort_id)
    if not status.get("ok"):
        raise HTTPException(status_code=404, detail="cohort_not_found")
    # Light-touch: also report the live SSE active-now (independent of
    # the cached counter, in case the row drifted).
    try:
        live = await compute_active_now(cohort_id, store=store)
    except Exception:
        live = status.get("active_now", 0)
    status["active_now_live"] = live
    return status


@router.delete("/{cohort_id}")
async def delete_cohort(cohort_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    deleted = await store.delete_cohort(cohort_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="cohort_not_found")
    return {"ok": True, "deleted": cohort_id}


@router.post("/{cohort_id}/end")
async def end_cohort(cohort_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    cohort = await store.end_cohort(cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="cohort_not_found")
    return {"ok": True, "cohort": _cohort_to_dict(cohort)}


# ---------- attendee CRUD --------------------------------------------------


@router.post("/{cohort_id}/attendees")
async def add_attendee(
    cohort_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    _ensure_enabled()
    display_name = str(payload.get("display_name") or payload.get("name") or "").strip()
    email = payload.get("email")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name_required")
    store = get_store()
    try:
        attendee = await store.add_attendee(
            cohort_id=cohort_id,
            display_name=display_name,
            email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Best-effort live notify.
    try:
        await publish(
            cohort_id,
            {
                "id": attendee.id,
                "type": "cohort.attendee.added",
                "occurred_at": attendee.joined_at,
                "data": {
                    "attendee_id": attendee.id,
                    "display_name": attendee.display_name,
                    "email": attendee.email,
                },
            },
        )
    except Exception:
        pass
    # Token IS surfaced here — it's the "copy this URL to your
    # attendee" moment, so the cockpit can render it once.
    return {"ok": True, "attendee": _attendee_to_dict(attendee, include_token=True)}


@router.get("/{cohort_id}/attendees")
async def list_attendees(
    cohort_id: str,
    filter: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    cohort = await store.get_cohort(cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="cohort_not_found")
    attendees = await store.list_attendees(cohort_id, filter=filter)
    return {
        "ok": True,
        "count": len(attendees),
        "filter": filter or "all",
        "attendees": [_attendee_to_dict(a) for a in attendees],
    }


@router.get("/{cohort_id}/attendees/{attendee_id}/timeline")
async def attendee_timeline(
    cohort_id: str,
    attendee_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    attendee = await store.get_attendee(attendee_id)
    if attendee is None or attendee.cohort_id != cohort_id:
        raise HTTPException(status_code=404, detail="attendee_not_found")
    actions = await store.attendee_timeline(attendee_id, limit=limit)
    return {
        "ok": True,
        "attendee": _attendee_to_dict(attendee),
        "count": len(actions),
        "actions": [_action_to_dict(a) for a in actions],
    }


@router.post("/{cohort_id}/attendees/{attendee_id}/flag")
async def flag_attendee(
    cohort_id: str,
    attendee_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    attendee = await store.get_attendee(attendee_id)
    if attendee is None or attendee.cohort_id != cohort_id:
        raise HTTPException(status_code=404, detail="attendee_not_found")
    reason = payload.get("reason") if isinstance(payload, dict) else None
    updated = await store.flag_attendee(attendee_id, reason=reason)
    try:
        await publish(
            cohort_id,
            {
                "id": attendee_id,
                "type": "cohort.attendee.flagged",
                "occurred_at": (updated.last_activity_at if updated else 0.0),
                "data": {"attendee_id": attendee_id, "reason": reason},
            },
        )
    except Exception:
        pass
    return {"ok": True, "attendee": _attendee_to_dict(updated) if updated else None}


@router.delete("/{cohort_id}/attendees/{attendee_id}/flag")
async def unflag_attendee(cohort_id: str, attendee_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    attendee = await store.get_attendee(attendee_id)
    if attendee is None or attendee.cohort_id != cohort_id:
        raise HTTPException(status_code=404, detail="attendee_not_found")
    updated = await store.unflag_attendee(attendee_id)
    return {"ok": True, "attendee": _attendee_to_dict(updated) if updated else None}


# ---------- broadcast + SSE ------------------------------------------------


@router.post("/{cohort_id}/broadcast")
async def broadcast_message(
    cohort_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    _ensure_enabled()
    message = str(payload.get("message") or "").strip()
    sender = payload.get("sender_user_id")
    if not message:
        raise HTTPException(status_code=400, detail="message_required")
    store = get_store()
    cohort = await store.get_cohort(cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="cohort_not_found")
    result = await store.broadcast_message(
        cohort_id, message=message, sender_user_id=sender
    )
    # Live fan-out (independent of timeline rows so subscribers see the
    # broadcast even if they don't poll the per-attendee timeline).
    try:
        await publish(
            cohort_id,
            {
                "id": f"bcast_{int(cohort.started_at * 1000)}",
                "type": "cohort.broadcast",
                "occurred_at": cohort.started_at,
                "data": {
                    "message": message,
                    "sender_user_id": sender,
                    "fanout_count": result.get("count", 0),
                },
            },
        )
    except Exception:
        pass
    return {"ok": True, **result}


def _sse_format(event: dict[str, Any]) -> str:
    """Encode one event as an SSE frame."""

    return (
        f"id: {event.get('id', '')}\n"
        f"event: {event.get('type', 'message')}\n"
        f"data: {json.dumps(event, default=str)}\n\n"
    )


@router.get("/{cohort_id}/stream")
async def stream_cohort(cohort_id: str, request: Request) -> StreamingResponse:
    _ensure_enabled()
    store = get_store()
    cohort = await store.get_cohort(cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="cohort_not_found")

    async def _gen() -> AsyncIterator[bytes]:
        # Advisory retry hint to the EventSource — match the heartbeat
        # cadence so reconnects happen on a known cycle.
        yield b"retry: 15000\n\n"
        try:
            async for event in subscribe(cohort_id):
                if await request.is_disconnected():
                    break
                yield _sse_format(event).encode("utf-8")
        except asyncio.CancelledError:
            return

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",  # disable nginx buffering for live SSE
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        _gen(), media_type="text/event-stream", headers=headers
    )


# ---------- attendee-facing public endpoints --------------------------------


@router.post("/join/{token}")
async def attendee_join(token: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    attendee = await store.get_attendee_by_token(token)
    if attendee is None:
        raise HTTPException(status_code=404, detail="invalid_token")
    # Idempotent: just refresh the join action so the dashboard gets
    # a "rejoined" signal but we don't double-create the attendee row.
    try:
        await store.record_action(
            attendee_id=attendee.id,
            action_type="join",
            payload={"via": "self_join_token"},
        )
        await publish(
            attendee.cohort_id,
            {
                "id": attendee.id,
                "type": "cohort.attendee.joined",
                "occurred_at": attendee.joined_at,
                "data": {
                    "attendee_id": attendee.id,
                    "display_name": attendee.display_name,
                },
            },
        )
    except Exception:
        pass
    return {"ok": True, "attendee": _attendee_to_dict(attendee)}


@router.post("/attendee/{attendee_id}/action")
async def record_attendee_action(
    attendee_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    attendee = await store.get_attendee(attendee_id)
    if attendee is None:
        raise HTTPException(status_code=404, detail="attendee_not_found")
    action_type = str(payload.get("type") or payload.get("action_type") or "").strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type_required")
    extra = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    try:
        action = await store.record_action(
            attendee_id=attendee_id,
            action_type=action_type,
            payload=extra,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        await publish(
            attendee.cohort_id,
            {
                "id": action.id,
                "type": action_type,
                "occurred_at": action.occurred_at,
                "data": {
                    "attendee_id": attendee.id,
                    "display_name": attendee.display_name,
                    **extra,
                },
            },
        )
    except Exception:
        pass
    return {"ok": True, "action": _action_to_dict(action)}
