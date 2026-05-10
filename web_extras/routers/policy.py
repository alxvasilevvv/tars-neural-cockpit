"""HTTP surface over the policy gate confirmation queue.

Endpoints:

- ``GET  /api/policy/pending``                — list pending confirmations.
- ``GET  /api/policy/recent``                 — last N (any status).
- ``POST /api/policy/confirm/{token}``        — execute the staged action.
- ``POST /api/policy/cancel/{token}``         — drop the staged action.
- ``POST /api/policy/expire``                 — expire stale tokens (admin / cron).

Wave 101 — unified /inbox HIL queue endpoints (alias surface that
projects ``confirmations`` rows under a more discoverable shape):

- ``GET  /api/policy/queue``                  — list with status / type / since filters.
- ``GET  /api/policy/queue/{id}``             — single row + full payload.
- ``POST /api/policy/deny/{id}``              — deny w/ required reason.
- ``POST /api/policy/queue/bulk-approve``     — bulk confirm w/ safety check.
- ``GET  /api/policy/queue/stream``           — SSE poll-fallback for new pending.
- ``POST /api/policy/auto-approve-threshold`` — Settings toggle for $X cap.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.core.domains.registry import get_pack
from backend.core.meeet import get_client, thread_id_scope, trace_scope
from backend.core.policy import get_policy_store

router = APIRouter(prefix="/api/policy", tags=["policy"])


def _to_dict(c) -> dict[str, Any]:
    return {
        "token": c.token,
        "created_at": c.created_at,
        "slug": c.slug,
        "action_id": c.action_id,
        "args": c.args,
        "status": c.status,
        "resolved_at": c.resolved_at,
        "result": c.result,
        "expires_at": c.expires_at,
        "requested_by": c.requested_by,
        "trace_id": c.trace_id,
        "thread_id": c.thread_id,
    }


def _attach_thread_id(payload: dict[str, Any], confirmation) -> dict[str, Any]:
    """Surface the originating thread on the policy event payload.

    The cockpit's per-thread timeline filters meeet events by
    ``payload.thread_id``; without this hop ``policy.confirm`` /
    ``policy.cancelled`` would never appear in the conversation
    feed even though the originating action was triggered from a
    chat thread.
    """

    tid = getattr(confirmation, "thread_id", None)
    if tid:
        payload["thread_id"] = tid
    return payload


@router.get("/pending")
async def pending(limit: int = Query(default=50, ge=1, le=1000)) -> dict[str, Any]:
    items = await get_policy_store().list_pending(limit=limit)
    return {"ok": True, "count": len(items), "pending": [_to_dict(i) for i in items]}


@router.get("/recent")
async def recent(limit: int = Query(default=50, ge=1, le=1000)) -> dict[str, Any]:
    items = await get_policy_store().list_recent(limit=limit)
    return {"ok": True, "count": len(items), "recent": [_to_dict(i) for i in items]}


@router.post("/confirm/{token}")
async def confirm(
    token: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_policy_store()
    confirmation = await store.get(token)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="confirmation_not_found")
    if confirmation.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"confirmation_already_{confirmation.status}",
        )
    if confirmation.expires_at and confirmation.expires_at < time.time():
        await store.resolve(token, status="expired")
        raise HTTPException(status_code=410, detail="confirmation_expired")

    pack = get_pack(confirmation.slug)
    if pack is None:
        await store.resolve(token, status="failed", result={"error": "domain_not_found"})
        raise HTTPException(status_code=404, detail="domain_not_found")
    spec = pack.find_action(confirmation.action_id)
    if spec is None:
        await store.resolve(
            token, status="failed", result={"error": "action_not_found"}
        )
        raise HTTPException(status_code=404, detail="action_not_found")

    client = get_client()
    with thread_id_scope(confirmation.thread_id), trace_scope(parent=x_meeet_trace_id) as trace_id:
        _hil_payload = _attach_thread_id(
            {
                "slug": confirmation.slug,
                "action": confirmation.action_id,
                "token": token,
            },
            confirmation,
        )
        await client.emit("policy.confirm", _hil_payload)
        # Wave 90 — outbound webhook fan-out for HIL approval. Wrapped
        # so a webhook store error never breaks the confirm flow.
        try:
            from backend.core.webhooks import emit as _wh_emit

            await _wh_emit("hil.approved", _hil_payload)
        except Exception:
            pass
        # Wave 95 — unified receipt ledger.
        try:
            from backend.core.receipts import record as _rcpt_record

            await _rcpt_record(
                type="hil.approved",
                actor="operator",
                resource=confirmation.slug,
                payload=dict(_hil_payload),
            )
        except Exception:
            pass
        try:
            result = await spec.handler(confirmation.args)
        except Exception as exc:
            await store.resolve(
                token, status="failed", result={"error": str(exc)}
            )
            await client.emit(
                "domain.action.failed",
                {
                    "slug": confirmation.slug,
                    "action": confirmation.action_id,
                    "error": str(exc),
                    "via": "confirm",
                },
            )
            raise HTTPException(status_code=500, detail=f"action_failed: {exc}") from exc

        resolved = await store.resolve(token, status="confirmed", result=result)
        await client.emit(
            "domain.action.completed",
            {
                "slug": confirmation.slug,
                "action": confirmation.action_id,
                "via": "confirm",
                "result_kind": type(result).__name__,
            },
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "confirmation": _to_dict(resolved) if resolved else None,
            "result": result,
        }


@router.post("/cancel/{token}")
async def cancel(token: str) -> dict[str, Any]:
    store = get_policy_store()
    confirmation = await store.get(token)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="confirmation_not_found")
    if confirmation.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"confirmation_already_{confirmation.status}",
        )
    resolved = await store.resolve(token, status="cancelled")
    _denied_payload = _attach_thread_id(
        {
            "slug": confirmation.slug,
            "action": confirmation.action_id,
            "token": token,
        },
        confirmation,
    )
    await get_client().emit("policy.cancelled", _denied_payload)
    # Wave 90 — outbound webhook fan-out for HIL denial.
    try:
        from backend.core.webhooks import emit as _wh_emit

        await _wh_emit("hil.denied", _denied_payload)
    except Exception:
        pass
    # Wave 95 — unified receipt ledger.
    try:
        from backend.core.receipts import record as _rcpt_record

        await _rcpt_record(
            type="hil.denied",
            actor="operator",
            resource=confirmation.slug,
            payload=dict(_denied_payload),
        )
    except Exception:
        pass
    return {"ok": True, "confirmation": _to_dict(resolved) if resolved else None}


@router.post("/expire")
async def expire_stale() -> dict[str, Any]:
    expired = await get_policy_store().expire_stale()
    client = get_client()
    for c in expired:
        await client.emit(
            "policy.expired",
            _attach_thread_id(
                {
                    "token": c.token,
                    "slug": c.slug,
                    "action": c.action_id,
                    "expired_at": c.resolved_at,
                    "trace_id": c.trace_id,
                },
                c,
            ),
        )
    return {
        "ok": True,
        "expired": len(expired),
        "tokens": [c.token for c in expired],
    }


# ---------------------------------------------------------------------------
# Wave 101 — /inbox HIL queue surface
#
# The frontend /inbox page uses a single normalised shape (`id`, `time`,
# `action`, `resource`, `dollar_impact`, `category`, `reason`) so the
# table renders without per-row branching. We project the raw
# ``PendingConfirmation`` rows under that shape here.
# ---------------------------------------------------------------------------


# Action category mapping. Used by /inbox to drive the colour chips
# (wallet=indigo, outreach=violet, code=cyan, live trading=red).
_CATEGORY_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("wallet.", "wallet"),
    ("outreach.", "outreach"),
    ("code.", "code"),
    ("github.", "code"),
    ("algotrade.live", "live_trading"),
    ("algotrade.promote", "live_trading"),
    ("algotrade.", "code"),
)


def _category_for(slug: str, action_id: str) -> str:
    """Map (slug, action_id) → high-level category for the /inbox chip strip."""

    fq = f"{slug}.{action_id}"
    for prefix, cat in _CATEGORY_BY_PREFIX:
        if fq.startswith(prefix) or action_id.startswith(prefix):
            return cat
    if slug in {"wallet", "wallets"}:
        return "wallet"
    if slug in {"outreach", "email", "gmail"}:
        return "outreach"
    if slug in {"algotrade", "trading"}:
        return "live_trading" if "live" in action_id or "promote" in action_id else "code"
    return "other"


def _dollar_impact(args: dict[str, Any]) -> float | None:
    """Best-effort $-impact extraction from common arg keys.

    Looks at ``amount_usd``, ``cap_usd``, ``budget_usd``, ``usd``, then
    falls back to ``amount`` (assumed USD). Returns ``None`` if no
    numeric field is present so the FE renders an em-dash.
    """

    for key in ("amount_usd", "cap_usd", "budget_usd", "usd"):
        v = args.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    v = args.get("amount")
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _to_inbox(c) -> dict[str, Any]:
    """Project a PendingConfirmation under the /inbox table shape."""

    args = c.args or {}
    return {
        "id": c.token,
        "token": c.token,
        "time": c.created_at,
        "slug": c.slug,
        "action": f"{c.slug}.{c.action_id}",
        "action_id": c.action_id,
        "resource": (
            args.get("resource")
            or args.get("recipient")
            or args.get("address")
            or args.get("strategy")
            or args.get("subject")
            or "—"
        ),
        "dollar_impact": _dollar_impact(args),
        "category": _category_for(c.slug, c.action_id),
        "reason": args.get("reason") or args.get("description"),
        "status": c.status,
        "expires_at": c.expires_at,
        "requested_by": c.requested_by,
        "thread_id": c.thread_id,
        "trace_id": c.trace_id,
        "args": args,
    }


# Bulk-approve safety: refuse to auto-confirm any single staged action
# whose extracted $-impact exceeds this cap. Operators can still confirm
# them one-at-a-time via the normal Approve button.
BULK_APPROVE_DOLLAR_CEILING = 10_000.0


def _within_time_window(created_at: float, since: str | None) -> bool:
    """Match the FE time-filter dropdown values."""

    if not since:
        return True
    now = time.time()
    if since == "hour":
        return now - created_at <= 3600
    if since == "day":
        return now - created_at <= 86400
    if since == "week":
        return now - created_at <= 7 * 86400
    return True


@router.get("/queue")
async def queue(
    status: str = Query(default="pending"),
    type: str | None = Query(default=None, description="Category filter (wallet/outreach/code/live_trading/other)"),
    since: str | None = Query(default=None, description="Time window: hour/day/week"),
    limit: int = Query(default=200, ge=1, le=1000),
    count_only: bool = Query(default=False),
) -> dict[str, Any]:
    """Unified /inbox queue listing.

    The frontend nav badge calls this with ``count_only=true`` every
    30s so the badge stays cheap; the page itself calls without that
    flag and renders the full row list.
    """

    store = get_policy_store()
    if status == "all":
        rows = await store.list_recent(limit=limit)
    else:
        rows = await store.list_pending(limit=limit) if status == "pending" else [
            r for r in await store.list_recent(limit=limit) if r.status == status
        ]
    items = [_to_inbox(r) for r in rows if _within_time_window(r.created_at, since)]
    if type:
        items = [it for it in items if it["category"] == type]
    if count_only:
        return {"ok": True, "count": len(items)}
    return {"ok": True, "count": len(items), "items": items}


@router.get("/queue/{token}")
async def queue_detail(token: str) -> dict[str, Any]:
    """Single staged confirmation, projected under the /inbox row shape."""

    confirmation = await get_policy_store().get(token)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="confirmation_not_found")
    return {"ok": True, "item": _to_inbox(confirmation)}


@router.post("/deny/{token}")
async def deny(token: str, body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Deny a staged confirmation. Reason is REQUIRED.

    Frontend's <ApprovalReasonModal /> enforces the same constraint;
    the backend re-checks so a hand-rolled curl can't bypass the audit
    trail. Stored as ``cancelled`` (the existing terminal state) with
    the reason persisted on the resolution result.
    """

    reason = (body or {}).get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise HTTPException(status_code=422, detail="reason_required")

    store = get_policy_store()
    confirmation = await store.get(token)
    if confirmation is None:
        raise HTTPException(status_code=404, detail="confirmation_not_found")
    if confirmation.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"confirmation_already_{confirmation.status}",
        )
    resolved = await store.resolve(
        token,
        status="cancelled",
        result={"reason": reason.strip(), "via": "deny"},
    )
    payload = _attach_thread_id(
        {
            "slug": confirmation.slug,
            "action": confirmation.action_id,
            "token": token,
            "reason": reason.strip(),
        },
        confirmation,
    )
    await get_client().emit("policy.cancelled", payload)
    try:
        from backend.core.webhooks import emit as _wh_emit

        await _wh_emit("hil.denied", payload)
    except Exception:
        pass
    try:
        from backend.core.receipts import record as _rcpt_record

        await _rcpt_record(
            type="hil.denied",
            actor="operator",
            resource=confirmation.slug,
            payload=dict(payload),
        )
    except Exception:
        pass
    return {"ok": True, "confirmation": _to_dict(resolved) if resolved else None}


@router.post("/queue/bulk-approve")
async def bulk_approve(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Bulk-approve a set of staged confirmations.

    Safety check: any single staged action with a detected $-impact >
    ``BULK_APPROVE_DOLLAR_CEILING`` is rejected. Operators must confirm
    those one-at-a-time via the standard Approve button so the audit
    trail records a per-token decision.
    """

    ids_raw = (body or {}).get("ids") or []
    if not isinstance(ids_raw, list) or not ids_raw:
        raise HTTPException(status_code=422, detail="ids_required")
    bulk_reason = (body or {}).get("reason")

    store = get_policy_store()
    rejected: list[dict[str, Any]] = []
    approved: list[str] = []
    failed: list[dict[str, str]] = []

    for tok in ids_raw:
        if not isinstance(tok, str):
            continue
        confirmation = await store.get(tok)
        if confirmation is None:
            failed.append({"token": tok, "error": "not_found"})
            continue
        if confirmation.status != "pending":
            failed.append({"token": tok, "error": f"already_{confirmation.status}"})
            continue
        impact = _dollar_impact(confirmation.args or {})
        if impact is not None and impact > BULK_APPROVE_DOLLAR_CEILING:
            rejected.append(
                {
                    "token": tok,
                    "dollar_impact": impact,
                    "reason": "exceeds_bulk_ceiling",
                    "ceiling": BULK_APPROVE_DOLLAR_CEILING,
                }
            )
            continue
        # Resolve immediately as confirmed; don't fire the action handler
        # here. Bulk approve is a metadata-only acknowledgement so the
        # operator doesn't accidentally trigger 50 wallet sigs in one
        # click. The actual handler still runs via /confirm/{token} when
        # the operator opens the row individually — the gated action
        # remains queued in its origin module's outbox.
        resolved = await store.resolve(
            tok,
            status="confirmed",
            result={
                "via": "bulk_approve",
                "reason": bulk_reason if isinstance(bulk_reason, str) else None,
            },
        )
        if resolved is None:
            failed.append({"token": tok, "error": "resolve_lost_race"})
            continue
        approved.append(tok)
        payload = _attach_thread_id(
            {
                "slug": confirmation.slug,
                "action": confirmation.action_id,
                "token": tok,
                "via": "bulk_approve",
            },
            confirmation,
        )
        await get_client().emit("policy.confirm", payload)
        try:
            from backend.core.webhooks import emit as _wh_emit

            await _wh_emit("hil.approved", payload)
        except Exception:
            pass
        try:
            from backend.core.receipts import record as _rcpt_record

            await _rcpt_record(
                type="hil.approved",
                actor="operator",
                resource=confirmation.slug,
                payload=dict(payload),
            )
        except Exception:
            pass
    return {
        "ok": True,
        "approved": approved,
        "approved_count": len(approved),
        "rejected": rejected,
        "rejected_count": len(rejected),
        "failed": failed,
    }


@router.get("/queue/stream")
async def queue_stream(poll_interval_s: float = Query(default=5.0, ge=1.0, le=60.0)) -> StreamingResponse:
    """SSE stream that re-emits the current pending count every N seconds.

    The frontend opens this as a fallback for the auto-refresh poll;
    if the connection drops the page falls back to a setInterval(5000)
    GET on /api/policy/queue. We keep the SSE body small (just a
    count + ts) so a long-open connection costs nothing.
    """

    async def gen():
        # Emit a hello so the client knows the channel opened.
        yield f"event: hello\ndata: {json.dumps({'ts': time.time()})}\n\n"
        while True:
            try:
                items = await get_policy_store().list_pending(limit=1000)
                payload = {"count": len(items), "ts": time.time()}
                yield f"event: pending\ndata: {json.dumps(payload)}\n\n"
            except Exception as exc:  # pragma: no cover - defensive
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            await asyncio.sleep(poll_interval_s)

    return StreamingResponse(gen(), media_type="text/event-stream")


# Auto-approve threshold (Settings toggle).  Stored on the policy gate
# module via env var so a restart preserves the value the operator set
# in the UI. Setting to 0 (default) disables auto-approve entirely.
_AUTO_APPROVE_ENV = "TARS_HIL_AUTO_APPROVE_USD"


@router.get("/auto-approve-threshold")
async def get_auto_approve_threshold() -> dict[str, Any]:
    raw = os.environ.get(_AUTO_APPROVE_ENV, "0")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        val = 0.0
    return {"ok": True, "threshold_usd": val}


@router.post("/auto-approve-threshold")
async def set_auto_approve_threshold(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    raw = (body or {}).get("threshold_usd")
    if not isinstance(raw, (int, float)) or raw < 0:
        raise HTTPException(status_code=422, detail="threshold_usd_required_non_negative")
    os.environ[_AUTO_APPROVE_ENV] = str(float(raw))
    return {"ok": True, "threshold_usd": float(raw)}
