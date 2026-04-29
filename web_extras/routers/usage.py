"""HTTP surface over the cost ledger.

Endpoints:

- ``GET /api/usage`` — tokens & USD rollup grouped by model, route,
  session. Supports optional ``since`` (unix seconds), ``session_id``,
  and ``limit`` (max events scanned, default 1000).
- ``GET /api/usage/lines`` — raw ``usage.tokens`` data points (for the
  cockpit ledger panel).
- ``GET /api/usage/prices`` — current price table — purely informational
  so the UI can show "n/a" for unpriced models.

The ledger is backed by the existing meeet event store; nothing extra
to provision.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query

from backend.core.usage import default_price_table, get_ledger

router = APIRouter(prefix="/api/usage", tags=["usage"])


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
