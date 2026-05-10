"""MCP bridge HTTP surface — Wave M6 (cockpit panel).

Read-only operator endpoints that surface the state of the
M5 MCP bridge:

- ``GET /api/mcp/bridge/status``  — registered bridged packs,
  cache freshness, and (when M6 pool is wired) live session
  pool stats.
- ``GET /api/mcp/bridge/servers`` — configured remote MCP
  servers from ``$TARS_HOME/mcp/servers.json``.
- ``POST /api/mcp/bridge/refresh`` — re-discover all (or one)
  servers, refresh the on-disk tool cache, register the new
  ``BridgedPack`` instances. Optional ``only`` field
  restricts to a subset.

Never raises a 5xx for missing optional deps. The whole MCP
bridge module is opt-in (operator must populate
``servers.json``); when nothing is configured the endpoints
return ``{ok: true, available: false}`` so the cockpit can
render a friendly empty state.

Pool stats are surfaced when the M6 SessionPool is available
via ``backend.core.mcp_bridge.get_default_pool``. Cockpit
should treat the ``pool`` field as optional and degrade
gracefully when it's missing — the bridge works without
pooling, that's just a perf optimisation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


log = logging.getLogger("tars.mcp.bridge")

router = APIRouter(prefix="/api/mcp/bridge", tags=["mcp-bridge"])


# ---------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Snapshot of the bridge state. Cockpit polls this at
    30s intervals to render the panel."""

    try:
        from backend.core.mcp_bridge import (
            ToolCache,
            unregister_bridges as _u,  # noqa: F401 — used in refresh
        )
        from backend.core.mcp_bridge.bootstrap import _default_cache_root
        from backend.mcp.client.registry import get_client_registry
    except ImportError as exc:
        return {
            "ok": True,
            "available": False,
            "reason": f"mcp_bridge_unavailable: {exc}",
            "as_of": int(time.time()),
        }

    try:
        registry = get_client_registry()
    except Exception as exc:  # noqa: BLE001 — degrade
        return {
            "ok": True,
            "available": False,
            "reason": f"client_registry_failed: {exc}",
            "as_of": int(time.time()),
        }

    servers = registry.list()

    # Cache snapshot
    cache_rows: list[dict[str, Any]] = []
    try:
        cache = ToolCache(_default_cache_root())
        for name in cache.list_servers():
            entry = cache.read(name)
            if entry is None:
                cache_rows.append({"server": name, "status": "unreadable"})
                continue
            cache_rows.append(
                {
                    "server": name,
                    "discovered_at": entry.discovered_at,
                    "age_seconds": round(entry.age_seconds(), 1),
                    "fresh": entry.is_fresh(),
                    "tool_count": len(entry.tools),
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp.bridge.cache.snapshot_failed: %s", exc)

    # Registered packs (`mcp-*` slugs)
    registered: list[dict[str, Any]] = []
    try:
        from backend.core.domains.registry import all_packs

        for pack in all_packs():
            slug = pack.manifest.slug
            if not slug.startswith("mcp-"):
                continue
            registered.append(
                {
                    "slug": slug,
                    "name": pack.manifest.name,
                    "tool_count": len(pack.actions()),
                    "pooled": getattr(pack, "pooled", False),
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp.bridge.registry.snapshot_failed: %s", exc)

    # Optional pool stats (Wave M6)
    pool_payload: dict[str, Any] | None = None
    try:
        from backend.core.mcp_bridge import get_default_pool

        pool = get_default_pool()
        pool_payload = pool.stats()
    except ImportError:
        pool_payload = None
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp.bridge.pool.stats_failed: %s", exc)
        pool_payload = {"error": str(exc)}

    return {
        "ok": True,
        "available": True,
        "as_of": int(time.time()),
        "servers": [s.to_dict() for s in servers],
        "registered": registered,
        "cache": cache_rows,
        "pool": pool_payload,
    }


# ---------------------------------------------------------------------
# Server config (read-only)
# ---------------------------------------------------------------------


@router.get("/servers")
async def list_servers() -> dict[str, Any]:
    try:
        from backend.mcp.client.registry import get_client_registry
    except ImportError as exc:
        return {"ok": True, "available": False, "reason": str(exc)}
    try:
        rows = [s.to_dict() for s in get_client_registry().list()]
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "available": False, "reason": str(exc)}
    return {"ok": True, "available": True, "servers": rows, "count": len(rows)}


# ---------------------------------------------------------------------
# Refresh — re-bootstrap with optional `only` filter
# ---------------------------------------------------------------------


class RefreshRequest(BaseModel):
    only: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of server names to refresh. If "
            "omitted, refreshes every configured server."
        ),
    )
    discovery_timeout: float = Field(
        default=10.0,
        gt=0,
        le=60.0,
        description="Per-server discovery timeout in seconds.",
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest | None = None) -> dict[str, Any]:
    """Force a re-discovery + cache refresh + re-registration of
    every (or selected) bridged pack.

    Wraps ``aboot_mcp_bridges(refresh=True, ...)`` — the async
    variant so it's safe inside the running event loop. Pool is
    threaded in when the M6 module is available."""

    try:
        from backend.core.mcp_bridge import aboot_mcp_bridges
    except ImportError as exc:
        raise HTTPException(503, f"mcp_bridge_unavailable: {exc}") from exc

    # Optional pool wire-up (M6)
    pool = None
    try:
        from backend.core.mcp_bridge import get_default_pool

        pool = get_default_pool()
    except ImportError:
        pool = None

    payload = req or RefreshRequest()
    try:
        result = await aboot_mcp_bridges(
            refresh=True,
            only=payload.only,
            discovery_timeout=payload.discovery_timeout,
            pool=pool,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("mcp.bridge.refresh.uncaught")
        raise HTTPException(500, f"refresh_failed: {exc}") from exc

    return {
        "ok": not result.failed,
        "result": result.to_dict(),
        "as_of": int(time.time()),
    }


# ---------------------------------------------------------------------
# Lifecycle helpers — used by web_extras/app.py to wire the pool
# into the FastAPI lifespan (best-effort; degrades if M6 missing).
# ---------------------------------------------------------------------


async def shutdown_pool_if_active() -> int:
    """Close every pooled MCP session at host shutdown.

    Returns the number of sessions closed; 0 if M6 isn't
    available or the pool was empty. Safe to call
    unconditionally from the FastAPI lifespan teardown.
    """

    try:
        from backend.core.mcp_bridge import get_default_pool
    except ImportError:
        return 0
    try:
        pool = get_default_pool()
    except Exception:  # noqa: BLE001
        return 0
    try:
        return await pool.close_all()
    except Exception as exc:  # noqa: BLE001
        log.warning("mcp.bridge.pool.shutdown_failed: %s", exc)
        return 0
