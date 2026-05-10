"""HTTP surface for the Workspaces module (Wave 110 — additive MVP).

Endpoints are NEW — no existing route is changed. Single-tenant code
in v9.1.0 still runs against the per-store databases; these endpoints
just register / list / invite, ready for v9.3 to flip the switch.

Endpoints:

- ``GET    /api/workspaces``                              list workspaces
- ``POST   /api/workspaces``                              create (HIL-gated)
- ``GET    /api/workspaces/permissions``                  RBAC matrix
- ``GET    /api/workspaces/{id}``                         single
- ``PATCH  /api/workspaces/{id}``                         update name/plan/settings
- ``POST   /api/workspaces/{id}/archive``                 soft-delete (HIL-gated)
- ``GET    /api/workspaces/{id}/members``                 list members
- ``POST   /api/workspaces/{id}/invites``                 mint pending invite
- ``GET    /api/workspaces/{id}/invites``                 list pending invites
- ``DELETE /api/workspaces/{id}/members/{user_id}``       revoke member
- ``PATCH  /api/workspaces/{id}/members/{user_id}``       change role
- ``POST   /api/workspaces/invites/{token}/accept``       accept invite

The accept endpoint takes the token as the auth itself — no other
credentials are required. Mirrors the cohort-attendee join pattern
shipped in W94.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from backend.core.workspaces import (
    CONTRACT_VERSION,
    extract_workspace_id,
)
from backend.core.workspaces.roles import matrix_to_dict
from backend.core.workspaces.store import PERSONAL_ID, get_store

from web_extras import policy_gate


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ---------- helpers --------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="workspaces_store_disabled")


def _workspace_to_dict(w) -> dict[str, Any]:
    return w.to_dict()


def _membership_to_dict(m) -> dict[str, Any]:
    return m.to_dict()


def _invite_to_dict(inv, *, include_token: bool = False) -> dict[str, Any]:
    return inv.to_dict(include_token=include_token)


# ---------- list / create / permissions -----------------------------------


@router.get("")
async def list_workspaces(request: Request) -> dict[str, Any]:
    """Return every workspace the requester can see.

    v9.1.0 single-tenant: returns every workspace in the store; the
    "personal" row is always present. v9.3 will scope this to the
    JWT subject.
    """

    _ensure_enabled()
    # Record the requested workspace context (no enforcement yet).
    extract_workspace_id(request)
    store = get_store()
    items = await store.list_workspaces(user_id=None)
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "count": len(items),
        "workspaces": [_workspace_to_dict(w) for w in items],
        "personal_id": PERSONAL_ID,
    }


@router.get("/permissions")
async def get_permissions() -> dict[str, Any]:
    """Return the RBAC role -> permission matrix for FE consumption."""

    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "matrix": matrix_to_dict(),
    }


@router.post("")
async def create_workspace(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Create a new workspace. HIL-gated under ``workspace.create``."""

    _ensure_enabled()
    slug = (payload.get("slug") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    owner_user_id = (payload.get("owner_user_id") or "").strip() or "local"
    plan = (payload.get("plan") or "free").strip().lower()
    settings = payload.get("settings") or {}
    if not slug:
        raise HTTPException(status_code=422, detail="slug_required")
    if not name:
        raise HTTPException(status_code=422, detail="name_required")

    await policy_gate.require_confirm(
        request,
        wallet_id="workspaces",
        action="workspace.create",
        params={"slug": slug, "owner_user_id": owner_user_id},
    )

    try:
        ws = await get_store().create_workspace(
            slug=slug,
            name=name,
            owner_user_id=owner_user_id,
            plan=plan,
            settings=settings if isinstance(settings, dict) else {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "workspace": _workspace_to_dict(ws)}


# ---------- single + update + archive --------------------------------------


@router.get("/{workspace_id}")
async def get_one(workspace_id: str) -> dict[str, Any]:
    _ensure_enabled()
    ws = await get_store().get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    return {"ok": True, "workspace": _workspace_to_dict(ws)}


@router.patch("/{workspace_id}")
async def patch_workspace(
    workspace_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    _ensure_enabled()
    name = payload.get("name")
    plan = payload.get("plan")
    settings = payload.get("settings")
    try:
        ws = await get_store().update_workspace(
            workspace_id,
            name=name if isinstance(name, str) else None,
            plan=plan if isinstance(plan, str) else None,
            settings=settings if isinstance(settings, dict) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    return {"ok": True, "workspace": _workspace_to_dict(ws)}


@router.post("/{workspace_id}/archive")
async def archive_workspace(
    workspace_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Archive (soft-delete) a workspace. HIL-gated."""

    _ensure_enabled()
    await policy_gate.require_confirm(
        request,
        wallet_id="workspaces",
        action="workspace.archive",
        params={"workspace_id": workspace_id},
    )
    try:
        ok = await get_store().archive_workspace(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    return {"ok": True}


# ---------- members --------------------------------------------------------


@router.get("/{workspace_id}/members")
async def list_members(workspace_id: str) -> dict[str, Any]:
    _ensure_enabled()
    items = await get_store().list_members(workspace_id)
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "count": len(items),
        "members": [_membership_to_dict(m) for m in items],
    }


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: str, user_id: str) -> dict[str, Any]:
    _ensure_enabled()
    try:
        ok = await get_store().revoke_member(workspace_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="member_not_found")
    return {"ok": True}


@router.patch("/{workspace_id}/members/{user_id}")
async def change_role(
    workspace_id: str,
    user_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    _ensure_enabled()
    new_role = (payload.get("role") or "").strip().lower()
    if not new_role:
        raise HTTPException(status_code=422, detail="role_required")
    try:
        m = await get_store().update_member_role(
            workspace_id, user_id, new_role
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if m is None:
        raise HTTPException(status_code=404, detail="member_not_found")
    return {"ok": True, "member": _membership_to_dict(m)}


# ---------- invites --------------------------------------------------------


@router.post("/{workspace_id}/invites")
async def create_invite(
    workspace_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    _ensure_enabled()
    email = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or "").strip().lower()
    invited_by = (payload.get("invited_by") or "").strip() or "local"
    expires_in_days = int(payload.get("expires_in_days") or 7)
    if not email:
        raise HTTPException(status_code=422, detail="email_required")
    if not role:
        raise HTTPException(status_code=422, detail="role_required")
    try:
        inv = await get_store().create_invite(
            workspace_id=workspace_id,
            email=email,
            role=role,
            invited_by=invited_by,
            expires_in_days=expires_in_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "ok": True,
        "invite": _invite_to_dict(inv, include_token=True),
    }


@router.get("/{workspace_id}/invites")
async def list_pending_invites(workspace_id: str) -> dict[str, Any]:
    _ensure_enabled()
    items = await get_store().list_pending_invites(workspace_id)
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "count": len(items),
        # Tokens stay server-side after creation — list endpoint is
        # safe to surface to anyone with access to the workspace UI.
        "invites": [_invite_to_dict(inv) for inv in items],
    }


@router.post("/invites/{token}/accept")
async def accept_invite(
    token: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Accept an invite. Token is the auth — no other creds required."""

    _ensure_enabled()
    user_id = (payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id_required")
    try:
        m = await get_store().accept_invite(token, user_id)
    except ValueError as exc:
        # Don't leak whether the token was missing vs expired in the
        # status code — same 410 for both.
        msg = str(exc)
        if "expired" in msg or "not found" in msg or "not pending" in msg:
            raise HTTPException(status_code=410, detail=msg) from exc
        raise HTTPException(status_code=422, detail=msg) from exc
    return {"ok": True, "membership": _membership_to_dict(m)}


__all__ = ["router"]
