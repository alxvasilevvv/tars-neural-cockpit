"""HTTP surface over the meeet durable store.

Endpoints:

- ``GET /api/meeet/stats`` — quick summary (total / unpushed / first_ts / last_ts).
- ``GET /api/meeet/events`` — list events newest-first with filters
  ``limit, since, trace_id, kind, kind_prefix, session_id, only_unpushed``.
- ``POST /api/meeet/replay`` — flush unpushed events to ingest now.
- ``GET /api/meeet/health`` — bridge health (ingest url set?, api key set?,
  contract version, store stats, last replay attempt).
- ``GET /api/meeet/traces`` — list rolled-up trace summaries
  (event_count, kinds, route, cost, contradictions, duration_ms).
- ``GET /api/meeet/traces/{trace_id}`` — single rollup row.
- ``POST /api/meeet/traces/refresh`` — rebuild the rollup from
  the events table on demand.

Every event TARS emits flows through the SQLite WAL store, so this is
the operator's local "black box": survives offline, replays on
reconnect.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.meeet import (
    get_client,
    get_store,
    get_trace_summary_store,
)

router = APIRouter(prefix="/api/meeet", tags=["meeet"])


@router.get("/stats")
async def stats() -> dict[str, Any]:
    return await get_store().stats()


@router.get("/events")
async def list_events(
    limit: int = Query(default=100, ge=1, le=1000),
    since: Optional[float] = Query(default=None),
    trace_id: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    kind_prefix: Optional[str] = Query(
        default=None,
        description=(
            "Filter to events whose kind starts with this prefix "
            "(e.g. 'pair.' for the pairing audit lane)."
        ),
        max_length=64,
    ),
    session_id: Optional[str] = Query(default=None),
    only_unpushed: bool = Query(default=False),
) -> dict[str, Any]:
    events = await get_store().list_events(
        limit=limit,
        since=since,
        trace_id=trace_id,
        kind=kind,
        kind_prefix=kind_prefix,
        session_id=session_id,
        only_unpushed=only_unpushed,
    )
    return {
        "ok": True,
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "ts": e.ts,
                "trace_id": e.trace_id,
                "session_id": e.session_id,
                "route": e.route,
                "kind": e.kind,
                "source": e.source,
                "contract_version": e.contract_version,
                "payload": e.payload,
                "pushed": e.pushed,
                "pushed_at": e.pushed_at,
                "last_error": e.last_error,
            }
            for e in events
        ],
    }


@router.post("/replay")
async def replay(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    return await get_client().replay_unpushed(limit=limit)


@router.get("/health")
async def health() -> dict[str, Any]:
    return await get_client().health()


@router.get("/traces")
async def list_traces(
    limit: int = Query(default=50, ge=1, le=500),
    since: Optional[float] = Query(default=None),
    primary_route: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    summaries = await get_trace_summary_store().list_summaries(
        limit=limit,
        since=since,
        primary_route=primary_route,
        session_id=session_id,
    )
    return {
        "ok": True,
        "count": len(summaries),
        "traces": [s.to_dict() for s in summaries],
    }


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    summary = await get_trace_summary_store().get(trace_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="trace_not_found")
    return {"ok": True, "trace": summary.to_dict()}


@router.post("/traces/refresh")
async def refresh_traces(
    since: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    return await get_trace_summary_store().rebuild(since=since)
