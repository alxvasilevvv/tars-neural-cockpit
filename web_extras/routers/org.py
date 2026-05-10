"""HTTP surface for the org onboarding wizard (Wave 99).

Persists Step 1 (org info) and Step 3 (team invites) of the
``/onboard/org`` wizard. Steps 2 / 4 / 5 either reuse existing
endpoints (connectors / playbooks / scheduler) or live entirely in
localStorage on the FE — the org metadata column carries forward a
small JSON blob with their summary state so the cockpit can render a
"Setup: 4 of 5 steps complete" badge without re-querying every
subsystem.

Endpoints:

- ``GET    /api/org/info``       — current org or 404.
- ``POST   /api/org/info``       — create or patch the single org row.
- ``DELETE /api/org/info``       — wipe (used by "Restart wizard").
- ``POST   /api/org/info/meta``  — patch metadata only (used by
  Steps 2 / 4 / 5 to record their summary).
- ``POST   /api/org/invites``    — body ``[{email, role}]``.
- ``GET    /api/org/invites``    — list with status.
- ``DELETE /api/org/invites/{id}`` — remove one invite.

The store is best-effort optional: when ``TARS_ORG_STORE=disabled``
every endpoint returns 503 ``org_store_disabled`` so the wizard can
fall back to localStorage-only mode.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.core.org import (
    INVITE_ROLES,
    ORG_TYPES,
    Invite,
    Org,
    get_store,
)


router = APIRouter(prefix="/api/org", tags=["org"])


# ---------- helpers ---------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="org_store_disabled")


def _org_to_dict(o: Org) -> dict[str, Any]:
    return {
        "id": o.id,
        "name": o.name,
        "type": o.type,
        "size": o.size,
        "timezone": o.timezone,
        "primary_use_case": o.primary_use_case,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "metadata": dict(o.metadata),
    }


def _invite_to_dict(i: Invite) -> dict[str, Any]:
    return {
        "id": i.id,
        "org_id": i.org_id,
        "email": i.email,
        "role": i.role,
        "invited_at": i.invited_at,
        "status": i.status,
    }


# ---------- org info -------------------------------------------------------


@router.get("/info")
async def get_org_info() -> dict[str, Any]:
    _ensure_enabled()
    org = await get_store().get_org()
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    return {
        "ok": True,
        "org": _org_to_dict(org),
        "org_types": list(ORG_TYPES),
        "invite_roles": list(INVITE_ROLES),
    }


@router.post("/info")
async def upsert_org_info(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata_must_be_object")
    try:
        org = await get_store().upsert_org(
            name=name,
            type=str(payload.get("type") or payload.get("org_type") or "other"),
            size=str(payload.get("size") or ""),
            timezone=str(payload.get("timezone") or "UTC"),
            primary_use_case=str(payload.get("primary_use_case") or ""),
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "org": _org_to_dict(org)}


@router.delete("/info")
async def delete_org_info() -> dict[str, Any]:
    _ensure_enabled()
    deleted = await get_store().delete_org()
    return {"ok": True, "deleted": bool(deleted)}


@router.post("/info/meta")
async def patch_org_meta(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body_must_be_object")
    org = await get_store().patch_metadata(payload)
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    return {"ok": True, "org": _org_to_dict(org)}


# ---------- invites --------------------------------------------------------


@router.post("/invites")
async def add_invites(payload: Any = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    org = await get_store().get_org()
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    # Accept either a bare list ``[{email, role}]`` or
    # ``{invites: [...], note?}`` for forward compat.
    items: list[dict[str, Any]]
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        raw = payload.get("invites") or []
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="invites_must_be_list")
        items = [x for x in raw if isinstance(x, dict)]
    else:
        raise HTTPException(status_code=400, detail="invalid_payload")
    saved = await get_store().add_invites(org_id=org.id, items=items)
    return {
        "ok": True,
        "count": len(saved),
        "invites": [_invite_to_dict(i) for i in saved],
        "note": (
            "Multi-tenant workspaces ship in v9.3 — invites are recorded "
            "as roadmap intent until then."
        ),
    }


@router.get("/invites")
async def list_invites() -> dict[str, Any]:
    _ensure_enabled()
    org = await get_store().get_org()
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    invites = await get_store().list_invites(org.id)
    return {
        "ok": True,
        "count": len(invites),
        "invites": [_invite_to_dict(i) for i in invites],
    }


@router.delete("/invites/{invite_id}")
async def delete_invite(invite_id: str) -> dict[str, Any]:
    _ensure_enabled()
    deleted = await get_store().delete_invite(invite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="invite_not_found")
    return {"ok": True, "deleted": invite_id}
