"""HTTP surface for the bundles module (Wave 107).

Endpoints (operator-facing; loopback-only by deployment policy):

- ``GET    /api/bundles``                    list builtins + recommended
- ``GET    /api/bundles/{id}``               single bundle full payload
- ``POST   /api/bundles/{id}/preview``       dry-run InstallReport
- ``POST   /api/bundles/{id}/install``       HIL-gated install
- ``GET    /api/bundles/installed``          list installs (optional org_id)
- ``POST   /api/bundles/{id}/uninstall``     HIL-gated cleanup

Install + uninstall route through ``policy_gate.require_confirm`` so
the HIL gate (Wave 76) kicks in when ``TARS_REQUIRE_OPERATOR_CONFIRM=1``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from backend.core.bundles import (
    CONTRACT_VERSION,
    bundle_by_id,
    bundle_for_org_type,
    list_bundles,
)
from backend.core.bundles.installer import (
    install_bundle,
    list_installed,
    uninstall_bundle,
)
from backend.core.bundles.previewer import preview_bundle

from web_extras import policy_gate


router = APIRouter(prefix="/api/bundles", tags=["bundles"])


# ---------- list / single -------------------------------------------------


@router.get("")
async def get_bundles(
    org_type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return every built-in bundle.

    When ``org_type`` is supplied, the response also carries a
    ``recommended`` payload so the FE can highlight one card.
    """

    bundles = [b.to_dict() for b in list_bundles()]
    payload: dict[str, Any] = {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "count": len(bundles),
        "bundles": bundles,
    }
    if org_type:
        rec = bundle_for_org_type(org_type)
        payload["recommended"] = {
            "org_type": org_type,
            "bundle_id": rec.id,
            "slug": rec.slug,
            "name": rec.name,
        }
    return payload


@router.get("/installed")
async def get_installed(
    org_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return all bundle installs (optionally filtered by org_id).

    Defined before ``/{bundle_id}`` so the literal route wins the
    FastAPI matcher.
    """

    items = await list_installed(org_id=org_id)
    return {
        "ok": True,
        "count": len(items),
        "installed": items,
    }


@router.get("/{bundle_id}")
async def get_one_bundle(bundle_id: str) -> dict[str, Any]:
    bundle = bundle_by_id(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    return {
        "ok": True,
        "bundle": bundle.to_dict(),
        "counts": bundle.counts(),
    }


# ---------- preview / install / uninstall ---------------------------------


@router.post("/{bundle_id}/preview")
async def post_preview(
    bundle_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    org_id = (payload.get("org_id") or "").strip() or None
    out = preview_bundle(bundle_id, org_id=org_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error") or "preview_failed")
    return out


@router.post("/{bundle_id}/install")
async def post_install(
    bundle_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    bundle = bundle_by_id(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    org_id = (payload.get("org_id") or "").strip() or "default"
    run_first_now = bool(payload.get("run_first_now") or False)

    await policy_gate.require_confirm(
        request,
        wallet_id="bundles",
        action="bundles.install",
        params={"bundle_id": bundle_id, "org_id": org_id},
    )

    report = await install_bundle(
        bundle_id, org_id, run_first_now=run_first_now
    )
    return {
        "ok": True,
        "report": report.to_dict(),
    }


@router.post("/{bundle_id}/uninstall")
async def post_uninstall(
    bundle_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    org_id = (payload.get("org_id") or "").strip() or "default"
    await policy_gate.require_confirm(
        request,
        wallet_id="bundles",
        action="bundles.uninstall",
        params={"bundle_id": bundle_id, "org_id": org_id},
    )
    report = await uninstall_bundle(bundle_id, org_id)
    if "not_installed" in report.warnings:
        raise HTTPException(status_code=404, detail="not_installed")
    return {
        "ok": True,
        "report": report.to_dict(),
    }


__all__ = ["router"]
