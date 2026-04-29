"""HTTP surface for Phase L5 device pairing — shape-only / mock crypto.

Endpoints (pinned by ``docs/contracts/L5_PAIRING_DRAFT.md``):

- ``POST /api/pairing/begin``           → mint accept token + fingerprint.
- ``POST /api/pairing/accept/{token}``  → operator-confirmed link.
- ``POST /api/pairing/reject/{token}``  → operator-declined.
- ``GET  /api/pairing/status``          → poll a pending pair_id.
- ``POST /api/pairing/revoke``          → drop a paired device.
- ``GET  /api/pairing/devices``        → list paired devices.
- ``GET  /api/pairing/identity``       → host identity / vault fingerprints.

Every state transition emits a ``pair.<state>`` event into the meeet
event store so replay on a paired device gives the same audit trail
that already exists for tool calls and policy actions.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.meeet import get_client, trace_scope
from backend.core.pairing import PairingNotFound, get_pairing_store


router = APIRouter(prefix="/api/pairing", tags=["pairing"])


VALID_KINDS = {"desktop_macos", "desktop_windows", "mobile_ios", "mobile_android"}


# --- request / response models ---------------------------------------


class BeginRequest(BaseModel):
    client_epk: str = Field(..., min_length=8, max_length=512)
    kind: str = Field(..., description="Device kind, see pairing contract.")
    pair_id: Optional[str] = Field(default=None, description="Optional caller-provided id.")


class RevokeRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)


# --- helpers ---------------------------------------------------------


def _record_to_dict(rec: Any) -> dict[str, Any]:
    payload = rec.to_dict()
    return payload


# --- endpoints -------------------------------------------------------


@router.post("/begin")
async def begin(
    body: BeginRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    if body.kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail="invalid_kind")

    store = get_pairing_store()
    try:
        rec = await store.begin(
            client_epk=body.client_epk,
            client_kind=body.kind,  # type: ignore[arg-type]
            pair_id=body.pair_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_client_epk: {exc}") from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "pair.attempted",
            {
                "pair_id": rec.pair_id,
                "kind": rec.client_kind,
                "host_id": rec.host_id,
                "host_fingerprint": rec.host_fingerprint,
                "expires_at": rec.expires_at,
            },
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "pair_id": rec.pair_id,
            "accept_token": rec.accept_token,
            "host_id": rec.host_id,
            "host_fingerprint": rec.host_fingerprint,
            "host_public_key": rec.host_public_key,
            "expires_at": rec.expires_at,
        }


@router.post("/accept/{token}")
async def accept(
    token: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_pairing_store()
    try:
        rec = await store.accept(token=token)
    except PairingNotFound as exc:
        raise HTTPException(status_code=404, detail="pair_not_found") from exc

    if rec.state == "expired":
        raise HTTPException(status_code=410, detail="pair_expired")
    if rec.state == "rejected":
        raise HTTPException(status_code=409, detail="pair_rejected")

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        if rec.state == "linked":
            await client.emit(
                "pair.linked",
                {
                    "pair_id": rec.pair_id,
                    "device_id": rec.device_id,
                    "kind": rec.client_kind,
                },
            )
        return {
            "ok": True,
            "trace_id": trace_id,
            **_record_to_dict(rec),
        }


@router.post("/reject/{token}")
async def reject(
    token: str,
    reason: str = Query(default="operator_declined"),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_pairing_store()
    try:
        rec = await store.reject(token=token, reason=reason)
    except PairingNotFound as exc:
        raise HTTPException(status_code=404, detail="pair_not_found") from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "pair.rejected",
            {
                "pair_id": rec.pair_id,
                "reason": rec.rejected_reason,
            },
        )
        return {"ok": True, "trace_id": trace_id, **_record_to_dict(rec)}


@router.get("/status")
async def status(pair_id: str = Query(...)) -> dict[str, Any]:
    store = get_pairing_store()
    try:
        rec = await store.status(pair_id=pair_id)
    except PairingNotFound as exc:
        raise HTTPException(status_code=404, detail="pair_not_found") from exc
    return {"ok": True, **_record_to_dict(rec)}


@router.post("/revoke")
async def revoke(
    body: RevokeRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_pairing_store()
    removed = await store.revoke(device_id=body.device_id)
    if not removed:
        raise HTTPException(status_code=404, detail="device_not_found")

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "pair.revoked",
            {"device_id": body.device_id, "at": time.time()},
        )
        return {"ok": True, "trace_id": trace_id, "device_id": body.device_id}


@router.get("/devices")
async def devices() -> dict[str, Any]:
    store = get_pairing_store()
    items = await store.list_devices()
    return {
        "ok": True,
        "count": len(items),
        "devices": [d.to_dict() for d in items],
    }


@router.get("/identity")
async def identity() -> dict[str, Any]:
    """Report the host's long-term identity status.

    Used by the cockpit's first-launch flow to decide whether to
    show the recovery-seed prompt (``identity_was_freshly_minted``
    is true the very first time) and to surface the current
    fingerprint to the operator.
    """

    store = get_pairing_store()
    return {
        "ok": True,
        "host_id": store.host_id,
        "host_public_key": store.host_public_key_b64,
        "host_fingerprint": store.fingerprint(host_id=store.host_id, pair_id=store.host_id),
        "vault": {
            "configured": store.vault is not None,
            "loaded_from_disk": store.identity_was_loaded,
            "freshly_minted": store.identity_was_freshly_minted,
        },
        "recovery_fingerprint": store.recovery_fingerprint,
    }
