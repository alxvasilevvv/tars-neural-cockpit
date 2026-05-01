"""HTTP surface over the policy gate confirmation queue.

Endpoints:

- ``GET  /api/policy/pending``         — list pending confirmations.
- ``GET  /api/policy/recent``          — last N (any status).
- ``POST /api/policy/confirm/{token}`` — execute the staged action.
- ``POST /api/policy/cancel/{token}``  — drop the staged action.
- ``POST /api/policy/expire``          — expire stale tokens (admin / cron).
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from backend.core.domains.registry import get_pack
from backend.core.meeet import get_client, trace_scope
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
    }


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
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "policy.confirm",
            {
                "slug": confirmation.slug,
                "action": confirmation.action_id,
                "token": token,
            },
        )
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
    await get_client().emit(
        "policy.cancelled",
        {
            "slug": confirmation.slug,
            "action": confirmation.action_id,
            "token": token,
        },
    )
    return {"ok": True, "confirmation": _to_dict(resolved) if resolved else None}


@router.post("/expire")
async def expire_stale() -> dict[str, Any]:
    expired = await get_policy_store().expire_stale()
    client = get_client()
    for c in expired:
        await client.emit(
            "policy.expired",
            {
                "token": c.token,
                "slug": c.slug,
                "action": c.action_id,
                "expired_at": c.resolved_at,
                "trace_id": c.trace_id,
            },
        )
    return {
        "ok": True,
        "expired": len(expired),
        "tokens": [c.token for c in expired],
    }
