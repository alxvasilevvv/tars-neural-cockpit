"""HTTP surface — operator roles (Phase M / P7).

Endpoints:

  GET    /api/roles                  → list defaults + custom roles
  GET    /api/roles/active           → currently selected role (or null)
  POST   /api/roles/{slug}/activate  → switch active role
  POST   /api/roles                  → mint a custom role (synthesise overlay)
  DELETE /api/roles/{slug}           → remove a custom role
  GET    /api/roles/{slug}/overlay   → just the synthesised system-prompt fragment
                                       (so the cockpit can preview / edit it)

Mutating endpoints emit ``role.{created,activated,deleted}`` events
into the meeet store.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header
from pydantic import BaseModel, Field

from backend.core.meeet import get_client, trace_scope
from backend.core.roles import (
    create_custom_role,
    delete_custom_role,
    get_active_role,
    get_role,
    list_roles,
    set_active_role,
)
from web_extras.errors import TARSAPIError


router = APIRouter(prefix="/api/roles", tags=["roles"])


class CustomRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    backing_packs: list[str] = Field(default_factory=list)
    samples: list[str] | None = Field(default=None, max_length=8)
    color: str = Field(default="#22D3EE")
    icon: str = Field(default="Sparkles")


@router.get("")
async def get_roles() -> dict[str, Any]:
    roles = [r.to_dict() for r in list_roles()]
    return {"ok": True, "count": len(roles), "roles": roles}


@router.get("/active")
async def get_active() -> dict[str, Any]:
    active = get_active_role()
    return {
        "ok": True,
        "role": active.to_dict() if active else None,
    }


@router.post("/{slug}/activate")
async def activate(
    slug: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        role = set_active_role(slug)
    except KeyError as exc:
        raise TARSAPIError(
            status_code=404,
            error_code="role_not_found",
            message=f"unknown role: {slug!r}",
            hint="GET /api/roles to see what's available",
        ) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "role.activated",
            {"slug": role.slug, "name": role.name, "custom": role.custom},
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "role": role.to_dict(),
        }


@router.post("")
async def create_role(
    body: CustomRoleRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        role = create_custom_role(
            name=body.name,
            description=body.description,
            backing_packs=body.backing_packs,
            samples=body.samples,
            color=body.color,
            icon=body.icon,
        )
    except ValueError as exc:
        raise TARSAPIError(
            status_code=400,
            error_code="role_invalid",
            message=str(exc),
        ) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "role.created",
            {
                "slug": role.slug,
                "name": role.name,
                "backing_packs": list(role.backing_packs),
            },
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "role": role.to_dict(),
        }


@router.delete("/{slug}")
async def remove_role(
    slug: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        ok = delete_custom_role(slug)
    except ValueError as exc:
        raise TARSAPIError(
            status_code=400,
            error_code="role_invalid",
            message=str(exc),
            hint="built-in roles cannot be removed",
        ) from exc
    if not ok:
        raise TARSAPIError(
            status_code=404,
            error_code="role_not_found",
            message=f"unknown custom role: {slug!r}",
        )

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit("role.deleted", {"slug": slug})
        return {"ok": True, "trace_id": trace_id, "slug": slug}


@router.get("/{slug}/overlay")
async def get_overlay(slug: str) -> dict[str, Any]:
    role = get_role(slug)
    if role is None:
        raise TARSAPIError(
            status_code=404,
            error_code="role_not_found",
            message=f"unknown role: {slug!r}",
        )
    return {
        "ok": True,
        "slug": role.slug,
        "name": role.name,
        "overlay": role.overlay,
        "backing_packs": list(role.backing_packs),
    }
