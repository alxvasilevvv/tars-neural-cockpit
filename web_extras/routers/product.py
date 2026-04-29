"""Public product surface — download manifest endpoints.

These endpoints power the marketing site's download buttons and the
``meeet.world`` SSR shell. The wire shape is pinned by
:mod:`backend.core.product.manifest`'s ``CONTRACT_VERSION`` —
consumers should pin the major.

Endpoints:

- ``GET /api/product/downloads`` — full manifest.
- ``GET /api/product/downloads/latest`` — latest release (optional
  ``os`` / ``channel`` filters).
- ``GET /api/product/version`` — minimal version probe used by Tauri
  updater fallbacks and lightweight monitors.

All endpoints are read-only, side-effect-free, and emit a permissive
``Cache-Control`` so a CDN can serve them with a one-minute TTL.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Response

from backend.core.product import DEFAULT_MANIFEST, load_manifest
from backend.core.product.manifest import VALID_OS


router = APIRouter(prefix="/api/product", tags=["product"])


@router.get("/downloads")
async def get_downloads(response: Response) -> dict[str, Any]:
    manifest = load_manifest()
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["X-Tars-Contract"] = manifest.contract_version
    return {"ok": True, **manifest.to_dict()}


@router.get("/downloads/latest")
async def get_latest_release(
    response: Response,
    os: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    manifest = load_manifest()
    target_os = (os or "").strip().lower() or None
    if target_os and target_os not in VALID_OS:
        raise HTTPException(status_code=400, detail="invalid_os")
    target_channel = (channel or "").strip().lower() or None
    entry = manifest.latest(os_id=target_os, channel=target_channel)
    if entry is None:
        raise HTTPException(status_code=404, detail="no_release_for_filters")
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["X-Tars-Contract"] = manifest.contract_version
    return {
        "ok": True,
        "product": manifest.product,
        "contract_version": manifest.contract_version,
        "release": entry.to_dict(),
    }


@router.get("/version")
async def get_version(response: Response) -> dict[str, Any]:
    manifest = load_manifest()
    latest = manifest.latest()
    response.headers["Cache-Control"] = "public, max-age=30"
    return {
        "ok": True,
        "product": manifest.product,
        "contract_version": manifest.contract_version,
        "channel": manifest.channel,
        "version": latest.version if latest else None,
    }
