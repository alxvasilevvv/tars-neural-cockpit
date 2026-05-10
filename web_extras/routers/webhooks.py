"""HTTP surface for the webhooks subsystem (Wave 90).

Outgoing endpoints (operator-facing, manage destinations):

- ``GET    /api/webhooks/outgoing``                              list
- ``POST   /api/webhooks/outgoing``                              create
- ``PATCH  /api/webhooks/outgoing/{id}``                         update
  (active / url / name / event_filter)
- ``DELETE /api/webhooks/outgoing/{id}``                         soft-delete
  (set ``active=False``; deliveries already in flight stop on next
  loop tick)
- ``POST   /api/webhooks/outgoing/{id}/test``                    fire a
  synthetic ``webhook.test`` event immediately
- ``GET    /api/webhooks/outgoing/{id}/deliveries``              last N
  delivery rows (default 50, max 500)
- ``POST   /api/webhooks/outgoing/{id}/deliveries/{delivery_id}/replay``
  re-attempt a single delivery, regardless of status

Incoming endpoints (operator-facing for create/list, public for inbox):

- ``GET    /api/webhooks/incoming``                              list
- ``POST   /api/webhooks/incoming``                              create
  — response carries the plaintext token ONLY in this response;
  subsequent listings expose the token too because the cockpit is a
  local single-tenant tool, but third-party deployments should
  treat the create response as the authoritative time-to-copy
- ``DELETE /api/webhooks/incoming/{id}``                         revoke
  (soft-delete — ``active=False``)
- ``POST   /api/webhooks/inbox/{token}``                         public
  inbox entry point — token in path, optional ``X-Signature`` HMAC
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request

from backend.core.webhooks import (
    DeliveryStatus,
    get_store,
    new_token,
)
from backend.core.webhooks.dispatcher import dispatch, fire_delivery
from backend.core.webhooks.inbox import handle_inbox

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ---------- helpers ---------------------------------------------------------


def _outgoing_to_dict(w) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "url": w.url,
        "event_filter": list(w.event_filter),
        "active": w.active,
        "created_at": w.created_at,
        # secret is BLOB — surface only its byte length so the cockpit can
        # show "32 bytes" without leaking the value back to the UI.
        "secret_bytes": len(w.secret),
    }


def _incoming_to_dict(w, *, include_token: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": w.id,
        "name": w.name,
        "trigger_playbook_id": w.trigger_playbook_id,
        "allowed_event_schemas": list(w.allowed_event_schemas),
        "active": w.active,
        "created_at": w.created_at,
    }
    if include_token:
        out["token"] = w.token
    return out


def _delivery_to_dict(d) -> dict[str, Any]:
    return {
        "id": d.id,
        "webhook_id": d.webhook_id,
        "event_id": d.event_id,
        "event_type": d.event_type,
        "status": d.status.value if hasattr(d.status, "value") else str(d.status),
        "attempts": d.attempts,
        "last_attempt_at": d.last_attempt_at,
        "next_attempt_at": d.next_attempt_at,
        "last_error": d.last_error,
        "last_status_code": d.last_status_code,
        "signature_used": d.signature_used,
        "created_at": d.created_at,
    }


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="webhooks_store_disabled")


# ---------- outgoing CRUD --------------------------------------------------


@router.get("/outgoing")
async def list_outgoing(
    include_inactive: bool = Query(default=True),
) -> dict[str, Any]:
    _ensure_enabled()
    items = await get_store().list_outgoing(include_inactive=include_inactive)
    return {
        "ok": True,
        "count": len(items),
        "items": [_outgoing_to_dict(w) for w in items],
    }


@router.post("/outgoing")
async def create_outgoing(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    _ensure_enabled()
    name = str(payload.get("name") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    if not url:
        raise HTTPException(status_code=400, detail="url_required")

    secret_raw = payload.get("secret")
    if isinstance(secret_raw, str) and secret_raw:
        secret = secret_raw.encode("utf-8")
    elif isinstance(secret_raw, (bytes, bytearray)):
        secret = bytes(secret_raw)
    else:
        # Auto-mint a 32-byte URL-safe secret so operators don't have to
        # generate one by hand.
        secret = new_token(32).encode("utf-8")

    event_filter = payload.get("event_filter") or []
    if not isinstance(event_filter, list):
        raise HTTPException(status_code=400, detail="event_filter_must_be_list")

    active = bool(payload.get("active", True))

    try:
        rec = await get_store().create_outgoing(
            name=name,
            url=url,
            secret=secret,
            event_filter=[str(p) for p in event_filter],
            active=active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out = _outgoing_to_dict(rec)
    # Surface the plaintext secret ONCE on create so the operator can copy
    # it into the receiving system. Subsequent fetches do not expose it.
    out["secret"] = rec.secret.decode("utf-8", errors="replace")
    return {"ok": True, "webhook": out}


@router.patch("/outgoing/{webhook_id}")
async def patch_outgoing(
    webhook_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    _ensure_enabled()
    try:
        rec = await get_store().patch_outgoing(webhook_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    return {"ok": True, "webhook": _outgoing_to_dict(rec)}


@router.delete("/outgoing/{webhook_id}")
async def delete_outgoing(webhook_id: str) -> dict[str, Any]:
    _ensure_enabled()
    rec = await get_store().deactivate_outgoing(webhook_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    return {"ok": True, "webhook": _outgoing_to_dict(rec)}


@router.post("/outgoing/{webhook_id}/test")
async def test_outgoing(webhook_id: str) -> dict[str, Any]:
    _ensure_enabled()
    rec = await get_store().get_outgoing(webhook_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    if not rec.active:
        raise HTTPException(status_code=409, detail="webhook_inactive")
    # Force-route to this webhook only by emitting an event whose name
    # the webhook will match — but we want the test endpoint to fire even
    # when the webhook's filter is narrow. Easiest: temporarily widen
    # the filter? No — instead fire a synthetic event with the webhook's
    # primary filter (or a generic ``webhook.test`` if none).
    chosen_event = "webhook.test"
    if rec.event_filter:
        first = rec.event_filter[0]
        # Strip the trailing ``*`` from glob patterns so we land somewhere
        # the filter will match.
        chosen_event = first.replace("*", "ping").replace("?", "p").strip(".") or "webhook.test"
    payload = {
        "test": True,
        "webhook_id": webhook_id,
        "note": "Synthetic test fired from /api/webhooks/outgoing/{id}/test",
    }
    out = await dispatch(chosen_event, payload, store=get_store(), fire_immediately=True)
    return {"ok": True, "event_type": chosen_event, "summary": out}


@router.get("/outgoing/{webhook_id}/deliveries")
async def list_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    _ensure_enabled()
    rec = await get_store().get_outgoing(webhook_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    deliveries = await get_store().list_deliveries_for_webhook(
        webhook_id, limit=limit
    )
    return {
        "ok": True,
        "webhook_id": webhook_id,
        "count": len(deliveries),
        "deliveries": [_delivery_to_dict(d) for d in deliveries],
    }


@router.post("/outgoing/{webhook_id}/deliveries/{delivery_id}/replay")
async def replay_delivery(webhook_id: str, delivery_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    rec = await store.get_outgoing(webhook_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    delivery = await store.get_delivery(delivery_id)
    if delivery is None or delivery.webhook_id != webhook_id:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    # Reset to PENDING so fire_delivery's state machine can re-evaluate.
    refreshed = await store.patch_delivery(
        delivery_id,
        {
            "status": DeliveryStatus.PENDING,
            "next_attempt_at": None,
            "last_error": None,
        },
    )
    target = refreshed or delivery
    updated = await fire_delivery(target, webhook=rec, store=store)
    return {"ok": True, "delivery": _delivery_to_dict(updated)}


# ---------- incoming CRUD --------------------------------------------------


@router.get("/incoming")
async def list_incoming(
    include_inactive: bool = Query(default=True),
) -> dict[str, Any]:
    _ensure_enabled()
    items = await get_store().list_incoming(include_inactive=include_inactive)
    return {
        "ok": True,
        "count": len(items),
        # NOTE: tokens are surfaced because the cockpit is local
        # single-tenant; remote deployments should drop this field.
        "items": [_incoming_to_dict(w, include_token=True) for w in items],
    }


@router.post("/incoming")
async def create_incoming(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Create an incoming webhook.

    The plaintext ``token`` is returned in the response only ONCE. In
    the local single-tenant cockpit we still expose it on
    ``GET /api/webhooks/incoming`` for convenience, but multi-tenant
    deployments should hash on disk and treat this response as the
    authoritative copy-to-clipboard moment (see WEBHOOKS.md).
    """

    _ensure_enabled()
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    trigger = payload.get("trigger_playbook_id")
    if trigger is not None and not isinstance(trigger, str):
        raise HTTPException(status_code=400, detail="trigger_playbook_id_must_be_string")
    schemas = payload.get("allowed_event_schemas") or []
    if not isinstance(schemas, list):
        raise HTTPException(status_code=400, detail="allowed_event_schemas_must_be_list")
    schemas = [s for s in schemas if isinstance(s, dict)]
    active = bool(payload.get("active", True))

    rec = await get_store().create_incoming(
        name=name,
        trigger_playbook_id=trigger,
        allowed_event_schemas=schemas,
        active=active,
    )
    return {"ok": True, "webhook": _incoming_to_dict(rec, include_token=True)}


@router.delete("/incoming/{webhook_id}")
async def delete_incoming(webhook_id: str) -> dict[str, Any]:
    _ensure_enabled()
    rec = await get_store().deactivate_incoming(webhook_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    return {"ok": True, "webhook": _incoming_to_dict(rec, include_token=False)}


@router.post("/inbox/{token}")
async def inbox(
    token: str,
    request: Request,
    x_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    """Public inbox entry point.

    Auth = token in path. Optional HMAC verification when an inbound
    secret is configured (see :mod:`backend.core.webhooks.inbox`).
    """

    _ensure_enabled()
    body_bytes = await request.body()
    import os as _os

    inbound_secret_raw = _os.getenv("TARS_WEBHOOKS_INBOUND_SECRET")
    inbound_secret = inbound_secret_raw.encode("utf-8") if inbound_secret_raw else None

    out = await handle_inbox(
        token=token,
        body_bytes=body_bytes,
        signature_header=x_signature,
        store=get_store(),
        inbound_secret=inbound_secret,
    )
    status = int(out.pop("status", 200))
    if status >= 400:
        raise HTTPException(status_code=status, detail=out.get("reason") or "inbox_error")
    return out
