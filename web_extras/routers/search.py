"""HTTP surface for the unified search + observability layer (Phase L8).

Endpoints:

- ``POST /api/search`` — unified hybrid search across chunks +
  messages + traces; ``scope`` lets the caller restrict to one source.
- ``POST /api/search/chunks`` — cross-thread (or single-thread) chunk
  search; same FTS5 + vector engine the in-thread retrieval uses.
- ``POST /api/search/messages`` — keyword search over chat messages.
- ``POST /api/search/traces`` — free-text search over the meeet event
  durable buffer.
- ``GET  /api/chat/threads/{id}/timeline`` — structured per-thread
  timeline (mounted under the existing chat router below).

Headers honoured (consistent with the rest of the cockpit):
``x-tars-session-id``, ``x-meeet-trace-id``.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.search import (
    SearchScope,
    get_thread_timeline,
    search,
    search_chunks,
    search_messages,
    search_traces,
)


router = APIRouter(prefix="/api/search", tags=["search"])


def _parse_scope(value: Any) -> SearchScope:
    raw = str(value or "").strip().lower() or "all"
    if raw not in ("all", "chunks", "messages", "traces"):
        raise HTTPException(status_code=400, detail="invalid_scope")
    return raw  # type: ignore[return-value]


def _query(payload: dict[str, Any] | None, *, key: str = "query") -> str:
    body = payload or {}
    raw = body.get(key) or body.get("q") or ""
    text = str(raw).strip()
    if not text:
        raise HTTPException(status_code=400, detail="query_required")
    return text


@router.post("")
@router.post("/")
async def unified_search(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    text = _query(payload)
    body = payload or {}
    scope = _parse_scope(body.get("scope"))
    top_k = max(1, min(int(body.get("top_k") or 12), 50))
    res = await search(text, scope=scope, top_k=top_k)
    return {"ok": True, **res.to_dict()}


@router.post("/chunks")
async def chunks_search(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    text = _query(payload)
    body = payload or {}
    top_k = max(1, min(int(body.get("top_k") or 12), 50))
    thread_id = body.get("thread_id")
    hits = await search_chunks(
        text,
        top_k=top_k,
        thread_id=str(thread_id) if thread_id else None,
    )
    return {
        "ok": True,
        "query": text,
        "scope": "chunks",
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.post("/messages")
async def messages_search(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    text = _query(payload)
    body = payload or {}
    top_k = max(1, min(int(body.get("top_k") or 12), 50))
    thread_id = body.get("thread_id")
    role = body.get("role")
    hits = await search_messages(
        text,
        top_k=top_k,
        thread_id=str(thread_id) if thread_id else None,
        role=str(role) if role else None,
    )
    return {
        "ok": True,
        "query": text,
        "scope": "messages",
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


@router.post("/traces")
async def traces_search(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    text = _query(payload)
    body = payload or {}
    top_k = max(1, min(int(body.get("top_k") or 12), 50))
    kind = body.get("kind")
    trace_id = body.get("trace_id")
    hits = await search_traces(
        text,
        top_k=top_k,
        kind=str(kind) if kind else None,
        trace_id=str(trace_id) if trace_id else None,
    )
    return {
        "ok": True,
        "query": text,
        "scope": "traces",
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


# ----------------------------------------------------------------------
# Timeline (mounted via the chat router prefix below to keep URLs
# operator-friendly: /api/chat/threads/{id}/timeline)
# ----------------------------------------------------------------------


timeline_router = APIRouter(prefix="/api/chat", tags=["chat"])


@timeline_router.get("/threads/{thread_id}/timeline")
async def thread_timeline(
    thread_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    entries = await get_thread_timeline(
        thread_id, limit_per_source=limit
    )
    return {
        "ok": True,
        "thread_id": thread_id,
        "count": len(entries),
        "entries": [e.to_dict() for e in entries],
    }
