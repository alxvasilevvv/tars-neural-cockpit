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
- ``GET /updates/{target}/{current_version}.json`` — live Tauri
  updater channel manifest, generated from the same in-memory
  ``DownloadManifest`` as ``/api/product/downloads`` so the two
  surfaces never drift.
- ``GET /updates/{target}/latest.json`` — alias for the latest
  release of ``target`` (helpful for marketing site links).

- ``GET /install.sh`` — **302** to the raw GitHub install script
  (marketing / ``resolution_monitor`` **B-001** parity when
  ``meeet.world`` is stale).

- ``GET /dl/{artifact}`` — **302** to GitHub Release installers for
  the canonical **v9.1.0** marketing filenames (same mapping as
  ``meeet-solana-state`` ``public/_redirects``). The previous
  v8.4.0 filenames stay registered for backwards-compat with any
  blog post / shared link from the audit-1 era.

All endpoints are read-only, side-effect-free, and emit a permissive
``Cache-Control`` so a CDN can serve them with a one-minute TTL.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from starlette.responses import RedirectResponse

from backend.core.product import DEFAULT_MANIFEST, load_manifest
from backend.core.product.manifest import VALID_OS
from backend.core.product.updater import (
    build_channel_from_release,
    known_targets,
    target_to_os_arch,
)


router = APIRouter(prefix="/api/product", tags=["product"])

# Tauri's updater plugin polls a hard-coded URL pattern that lives
# *outside* the ``/api/product`` prefix (operators want to expose
# ``https://meeet.world/updates/<target>/<v>.json``). We mount this
# second router at the app level so the path stays stable.
updates_router = APIRouter(prefix="/updates", tags=["product", "updater"])

# Legacy marketing URLs on ``tars.meeet.world`` — parity with ``meeet.world``
# ``_redirects`` when Vercel production is stale (**B-001**).
legacy_redirect_router = APIRouter(tags=["product", "legacy-b001"])

LEGACY_INSTALL_SH_RAW = (
    "https://raw.githubusercontent.com/"
    "alxvasilevvv/tars-neural-cockpit/main/scripts/install-tars.sh"
)

# Canonical filenames exposed on the marketing site (hyphens in dmg/exe names).
LEGACY_DL_TO_RELEASE_URL: dict[str, str] = {
    "TARS-9.1.0-arm64.dmg": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v9.1.0/TARS_9.1.0_aarch64.dmg"
    ),
    "TARS-9.1.0-x64.dmg": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v9.1.0/TARS_9.1.0_x64.dmg"
    ),
    "TARS-9.1.0-setup.exe": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v9.1.0/TARS_9.1.0_x64-setup.exe"
    ),
    "TARS-9.1.0.AppImage": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v9.1.0/TARS_9.1.0_amd64.AppImage"
    ),
    # Backwards-compat for v8.4.0 marketing URLs (kept registered
    # so any pre-audit blog post / shared link still resolves).
    "TARS-8.4.0-arm64.dmg": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg"
    ),
    "TARS-8.4.0-setup.exe": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v8.4.0/TARS_8.4.0_x64-setup.exe"
    ),
    "TARS-8.4.0.AppImage": (
        "https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "releases/download/v8.4.0/TARS_8.4.0_amd64.AppImage"
    ),
}


@legacy_redirect_router.get("/install.sh", include_in_schema=False)
async def legacy_install_sh() -> RedirectResponse:
    return RedirectResponse(url=LEGACY_INSTALL_SH_RAW, status_code=302)


@legacy_redirect_router.get("/dl/{artifact}", include_in_schema=False)
async def legacy_dl_artifact(artifact: str) -> RedirectResponse:
    dest = LEGACY_DL_TO_RELEASE_URL.get(artifact)
    if dest is None:
        raise HTTPException(status_code=404, detail="unknown_legacy_dl")
    return RedirectResponse(url=dest, status_code=302)


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


@router.get("/updater/targets")
async def get_known_targets(response: Response) -> dict[str, Any]:
    """Discovery helper: list every Tauri target the live channel
    serves. Useful for monitors / marketing site to render
    "available platforms" without hard-coding the matrix.
    """

    response.headers["Cache-Control"] = "public, max-age=300"
    return {"ok": True, "targets": list(known_targets())}


# ---------------------------------------------------------------------
# Tauri updater channel JSON (live)
# ---------------------------------------------------------------------


def _resolve_channel_payload(
    target: str, version_path: str
) -> tuple[dict[str, Any], str] | None:
    """Look up the channel manifest for ``target`` from the live
    ``DownloadManifest``.

    Returns ``(payload, version)`` where ``version`` is the latest
    available version for the target's OS, or ``None`` when the
    target is unknown / no release is available.

    ``version_path`` is the URL segment the operator's installed app
    sent (without the ``.json`` suffix). The function does not
    compare versions — Tauri does that on the client side based on
    the ``version`` field in the returned JSON.
    """

    os_arch = target_to_os_arch(target)
    if os_arch is None:
        return None
    os_id, _arch = os_arch

    manifest = load_manifest()
    entry = manifest.latest(os_id=os_id)
    if entry is None:
        return None

    channel = build_channel_from_release(entry, target=target)
    if not channel.platforms:
        return None
    return channel.to_dict(), entry.version


@updates_router.get("/{target}/{version_path}.json")
async def get_updater_channel(
    response: Response,
    target: str,
    version_path: str,
) -> dict[str, Any]:
    """Live updater channel JSON for one ``target``.

    Tauri's plugin polls this URL with the *current* installed
    version embedded in the path; we always respond with the
    latest manifest and let the client's semver comparison decide
    whether to upgrade. The endpoint never 304s — Tauri caches via
    its own ETag / If-Modified-Since machinery.
    """

    if target not in set(known_targets()):
        raise HTTPException(status_code=404, detail="unknown_target")

    payload = _resolve_channel_payload(target, version_path)
    if payload is None:
        raise HTTPException(
            status_code=404, detail="no_release_for_target"
        )
    body, _latest_version = payload
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["X-Tars-Updater-Target"] = target
    return body
