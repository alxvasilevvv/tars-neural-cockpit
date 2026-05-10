"""HTTP surface for the marketplace module (Wave 106).

Endpoints (operator-facing; loopback-only by deployment policy):

- ``GET    /api/marketplace/listings``                browse + filter
- ``GET    /api/marketplace/listings/{id}``           single listing
- ``POST   /api/marketplace/listings/{id}/install``   HIL-gated
- ``GET    /api/marketplace/installed``               local library
- ``POST   /api/marketplace/installed/{id}/uninstall`` HIL-gated
- ``POST   /api/marketplace/listings/{id}/rate``      local-only rating
- ``GET    /api/marketplace/listings/{id}/ratings``   aggregate
- ``POST   /api/marketplace/registry/refresh``        force re-fetch
- ``POST   /api/marketplace/listings/{id}/preview``   preview payload

Install + uninstall route through ``policy_gate.require_confirm``
so the HIL gate (Wave 76) kicks in when
``TARS_REQUIRE_OPERATOR_CONFIRM=1``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from backend.core.marketplace import (
    LISTING_KINDS,
)
from backend.core.marketplace.installer import (
    install as install_listing,
    is_installed,
    list_installed,
    uninstall as uninstall_listing,
)
from backend.core.marketplace.ratings import (
    get_aggregate,
    list_for_listing,
    submit_rating,
)
from backend.core.marketplace.registry import (
    fetch_registry,
    get_listing,
    list_listings,
)
from backend.core.marketplace.seed import seed_count

from web_extras import policy_gate


router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


# ---------- listings -------------------------------------------------------


@router.get("/listings")
async def get_listings(
    category: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    min_rating: float | None = Query(default=None, ge=0.0, le=5.0),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    if kind and kind not in LISTING_KINDS:
        raise HTTPException(status_code=400, detail=f"bad_kind:{kind}")
    items = await list_listings(
        category=category,
        kind=kind,
        q=q,
        min_rating=min_rating,
        force_refresh=force_refresh,
    )
    payload = await fetch_registry()
    # Decorate with installed flag + live local rating aggregate so
    # the FE doesn't need to do a fanout.
    listings_out: list[dict[str, Any]] = []
    for it in items:
        d = it.to_dict()
        d["installed"] = await is_installed(it.id)
        local_agg = await get_aggregate(it.id)
        if local_agg.get("count"):
            d["ratings"] = {
                "count": local_agg["count"],
                "avg": local_agg["avg"],
            }
        listings_out.append(d)
    return {
        "ok": True,
        "source": payload.get("source"),
        "fetched_at": payload.get("fetched_at"),
        "count": len(listings_out),
        "listings": listings_out,
    }


@router.get("/listings/{listing_id}")
async def get_one_listing(listing_id: str) -> dict[str, Any]:
    listing = await get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing_not_found")
    out = listing.to_dict()
    out["installed"] = await is_installed(listing.id)
    local_agg = await get_aggregate(listing.id)
    if local_agg.get("count"):
        out["ratings"] = {
            "count": local_agg["count"],
            "avg": local_agg["avg"],
        }
    return {"ok": True, "listing": out}


# ---------- install / uninstall (HIL-gated) -------------------------------


@router.post("/listings/{listing_id}/install")
async def post_install(
    listing_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    listing = await get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing_not_found")
    target = (payload.get("target") or "personal").strip().lower()
    if target not in {"personal", "workspace"}:
        raise HTTPException(status_code=400, detail="bad_target")

    await policy_gate.require_confirm(
        request,
        wallet_id="marketplace",
        action="marketplace.install",
        params={"listing_id": listing_id, "target": target},
    )

    result = await install_listing(listing, target=target)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "install_failed")
    return result


@router.get("/installed")
async def get_installed(
    kind: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    items = await list_installed(kind=kind, category=category)
    return {
        "ok": True,
        "count": len(items),
        "installed": [i.to_dict() for i in items],
    }


@router.post("/installed/{listing_id}/uninstall")
async def post_uninstall(
    listing_id: str,
    request: Request,
) -> dict[str, Any]:
    await policy_gate.require_confirm(
        request,
        wallet_id="marketplace",
        action="marketplace.uninstall",
        params={"listing_id": listing_id},
    )
    result = await uninstall_listing(listing_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error") or "uninstall_failed",
        )
    return result


# ---------- ratings -------------------------------------------------------


@router.post("/listings/{listing_id}/rate")
async def post_rate(
    listing_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    score_raw = payload.get("score")
    try:
        score = int(score_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="score_required")
    if score < 1 or score > 5:
        raise HTTPException(status_code=400, detail="score_out_of_range")
    comment = str(payload.get("comment") or "")
    rater_email = str(payload.get("rater_email") or "")
    result = await submit_rating(
        listing_id, score, comment=comment, rater_email=rater_email
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "rate_failed",
        )
    return result


@router.get("/listings/{listing_id}/ratings")
async def get_ratings(
    listing_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    aggregate = await get_aggregate(listing_id)
    items = await list_for_listing(listing_id, limit=limit)
    return {
        "ok": True,
        "aggregate": aggregate,
        "ratings": [r.to_dict() for r in items],
    }


# ---------- registry refresh + preview ------------------------------------


@router.post("/registry/refresh")
async def post_refresh() -> dict[str, Any]:
    payload = await fetch_registry(force_refresh=True)
    return {
        "ok": True,
        "source": payload.get("source"),
        "fetched_at": payload.get("fetched_at"),
        "count": len(payload.get("listings") or []),
        "seed_count": seed_count(),
    }


@router.post("/listings/{listing_id}/preview")
async def post_preview(listing_id: str) -> dict[str, Any]:
    listing = await get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing_not_found")
    # v0 preview is the listing's structured payload + a tiny
    # render of "what you'd get". The skill loader plug-in lands
    # in v9.3 alongside payouts.
    payload = listing.install_payload
    sample_inputs: dict[str, Any] = {}
    sample_outputs: dict[str, Any] = {}
    if isinstance(payload, dict):
        if payload.get("recipe"):
            sample_inputs = {"steps": payload["recipe"].get("steps", [])}
        if payload.get("source_dir"):
            sample_inputs = {"source_dir": payload.get("source_dir")}
        if payload.get("module"):
            sample_inputs = {"module": payload.get("module")}
    sample_outputs = {
        "kind": listing.kind,
        "name": listing.name,
        "category": listing.category,
        "tags": listing.tags,
    }
    return {
        "ok": True,
        "listing_id": listing.id,
        "preview": {
            "description": listing.description,
            "inputs": sample_inputs,
            "outputs": sample_outputs,
            "preview_url": listing.preview_url or None,
        },
    }


__all__ = ["router"]
