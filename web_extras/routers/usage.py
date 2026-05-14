"""HTTP surface over the cost ledger + consumption console (W235).

Legacy endpoints (Wave K — kept for back-compat with cockpit panels):

- ``GET /api/usage`` — tokens & USD rollup from the meeet event-store.
- ``GET /api/usage/lines`` — raw ``usage.tokens`` data points.
- ``GET /api/usage/prices`` — current price table.

W235 endpoints (consumption console):

- ``GET /api/usage/console`` — today / month / balance / recent_events.
- ``GET /api/usage/stream`` — SSE feed of every new UsageEvent.
- ``GET /api/usage/events`` — paginated history (``since``, ``limit``).
- ``POST /api/usage/retry_failed`` — drain ``usage_retry_queue`` to meeet.
- ``GET /api/usage/healthz`` — metering subsystem health.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.core.usage import default_price_table, get_ledger
from backend.core.metering import (
    aggregate_month,
    aggregate_today,
    current_balance_local,
    get_recent_events,
    healthz as metering_healthz,
    resolve_tier,
    retry_failed_sync,
    subscribe,
    unsubscribe,
)
from backend.core.metering.recorder import get_events_since

router = APIRouter(prefix="/api/usage", tags=["usage"])


# ── legacy (Wave K) ───────────────────────────────────────────────────

@router.get("")
async def rollup(
    limit: int = Query(default=1000, ge=1, le=5000),
    since: Optional[float] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    out = await get_ledger().rollup(
        limit=limit, since=since, session_id=session_id
    )
    return {"ok": True, "rollup": out.to_dict()}


@router.get("/lines")
async def lines(
    limit: int = Query(default=200, ge=1, le=1000),
    since: Optional[float] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    trace_id: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    items = await get_ledger().list_lines(
        limit=limit, since=since, session_id=session_id, trace_id=trace_id
    )
    return {
        "ok": True,
        "count": len(items),
        "lines": [
            {
                "ts": ln.ts,
                "trace_id": ln.trace_id,
                "session_id": ln.session_id,
                "route": ln.route,
                "model": ln.model,
                "tokens_in": ln.tokens_in,
                "tokens_out": ln.tokens_out,
                "latency_ms": ln.latency_ms,
                "cost_usd": ln.cost_usd,
                "kind": ln.kind,
            }
            for ln in items
        ],
    }


@router.get("/prices")
async def prices() -> dict[str, Any]:
    table = default_price_table()
    return {
        "ok": True,
        "prices": {
            model: {
                "input_per_mtok": entry.input_per_mtok,
                "output_per_mtok": entry.output_per_mtok,
            }
            for model, entry in table.entries.items()
        },
    }


# ── W235 consumption console ──────────────────────────────────────────

@router.get("/console")
async def usage_console(recent_limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """One-shot payload feeding the 4 cockpit panels."""

    return {
        "ok": True,
        "today": aggregate_today(),
        "month": aggregate_month(),
        "balance": current_balance_local(),
        "tier": resolve_tier(),
        "recent_events": get_recent_events(recent_limit),
    }


@router.get("/stream")
async def usage_stream() -> StreamingResponse:
    """SSE feed: one ``data: {json}\\n\\n`` per new UsageEvent.

    Tauri WebView (WebKit2 / WebView2) supports the standard
    ``EventSource`` API, so the cockpit can consume this directly.
    """

    q = subscribe()

    async def _gen() -> AsyncIterator[bytes]:
        # initial hello so the client knows we're connected
        yield b": tars-usage-stream-connected\n\n"
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # SSE keep-alive comment — proxies will drop idle conns.
                    yield b": keepalive\n\n"
                    continue
                payload = json.dumps(ev.to_dict(), separators=(",", ":"))
                yield f"event: usage\ndata: {payload}\n\n".encode("utf-8")
        finally:
            unsubscribe(q)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/events")
async def usage_events(
    since: Optional[str] = Query(default=None, description="ISO-8601 UTC"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    rows = get_events_since(since, limit)
    return {"ok": True, "count": len(rows), "events": rows}


@router.post("/retry_failed")
async def usage_retry_failed() -> dict[str, Any]:
    result = await retry_failed_sync()
    return result


@router.get("/healthz")
async def usage_healthz() -> dict[str, Any]:
    return metering_healthz()
