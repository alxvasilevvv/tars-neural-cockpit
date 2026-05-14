"""W244 -- Privacy mode + data plane HTTP surface.

Endpoints:

- ``GET  /api/privacy/config``        -- current PrivacyConfig + recent flows
- ``POST /api/privacy/config``        -- partial update (any subset of fields)
- ``GET  /api/privacy/data_plane``    -- snapshot of recent_flows +
                                         allowed / blocked destinations
- ``GET  /api/privacy/data_plane/stream`` -- SSE live feed for the cockpit
                                             "data plane" indicator

Everything stays in-process: no auth, no DB. The persisted config lives
in ``~/.tars/privacy.json`` (resolved by ``backend.core.privacy``). The
ring buffer is RAM only.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.core.privacy import (
    PrivacyConfig,
    load_privacy,
    recent_flows,
    save_privacy,
    snapshot,
)


router = APIRouter(prefix="/api/privacy", tags=["privacy"])


# -- /config -----------------------------------------------------------


@router.get("/config")
async def get_config(
    flows_limit: int = Query(default=50, ge=1, le=1000),
) -> dict[str, Any]:
    cfg = load_privacy()
    return {
        "ok": True,
        "config": cfg.to_dict(),
        "recent_flows": recent_flows(limit=flows_limit),
    }


@router.post("/config")
async def update_config(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Partial update of the PrivacyConfig.

    Two paths:

    1) ``{"mode": "privacy"}`` -- swap to a canonical preset. The four
       bool toggles get reset to the preset's defaults; pass extra
       fields to override individual ones in the same call.
    2) ``{"block_cloud_llm": true}`` -- tweak a single field while
       keeping the existing mode + other toggles.
    """
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "error": "invalid_body"},
        )

    cur = load_privacy()
    base = cur

    mode = payload.get("mode")
    if isinstance(mode, str):
        m = mode.strip().lower()
        if m not in ("normal", "privacy", "strict"):
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "error": "invalid_mode",
                    "allowed": ["normal", "privacy", "strict"],
                },
            )
        base = PrivacyConfig.preset_for(m)  # type: ignore[arg-type]

    # Now layer any explicit bool overrides on top of the preset.
    def _b(key: str, current: bool) -> bool:
        v = payload.get(key)
        if isinstance(v, bool):
            return v
        return current

    new_cfg = PrivacyConfig(
        mode=base.mode,
        block_cloud_llm=_b("block_cloud_llm", base.block_cloud_llm),
        block_meeet_telemetry=_b("block_meeet_telemetry", base.block_meeet_telemetry),
        block_outbound_connectors=_b(
            "block_outbound_connectors", base.block_outbound_connectors
        ),
        local_only_models=_b("local_only_models", base.local_only_models),
    )
    save_privacy(new_cfg)
    return {"ok": True, "config": new_cfg.to_dict()}


# -- /data_plane -------------------------------------------------------


@router.get("/data_plane")
async def get_data_plane(
    limit: int = Query(default=50, ge=1, le=1000),
) -> dict[str, Any]:
    return snapshot(limit=limit)


@router.get("/data_plane/stream")
async def stream_data_plane(
    interval_s: float = Query(default=1.5, ge=0.25, le=10.0),
    limit: int = Query(default=20, ge=1, le=200),
) -> StreamingResponse:
    """Server-Sent Events feed of recent flows.

    Polling shape -- emits a snapshot every ``interval_s`` seconds.
    The cockpit indicator subscribes once and updates from each frame
    rather than re-issuing ``GET /data_plane`` on a timer.
    """

    async def _gen():
        # First frame immediately so the indicator paints on connect.
        yield f"data: {json.dumps(snapshot(limit=limit))}\n\n"
        while True:
            try:
                await asyncio.sleep(interval_s)
                yield f"data: {json.dumps(snapshot(limit=limit))}\n\n"
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
        },
    )
