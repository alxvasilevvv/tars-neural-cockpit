"""HTTP surface over the meeet durable store.

Endpoints:

- ``GET /api/meeet/stats`` — quick summary (total / unpushed / first_ts / last_ts).
- ``GET /api/meeet/events`` — list events newest-first with filters
  ``limit, since, trace_id, kind, only_unpushed``.
- ``POST /api/meeet/replay`` — flush unpushed events to ingest now.
- ``GET /api/meeet/health`` — bridge health (ingest url set?, api key set?,
  contract version, store stats, last replay attempt).

Every event TARS emits flows through the SQLite WAL store, so this is
the operator's local "black box": survives offline, replays on
reconnect.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query

from backend.core.meeet import get_client, get_store

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
    only_unpushed: bool = Query(default=False),
) -> dict[str, Any]:
    events = await get_store().list_events(
        limit=limit,
        since=since,
        trace_id=trace_id,
        kind=kind,
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
