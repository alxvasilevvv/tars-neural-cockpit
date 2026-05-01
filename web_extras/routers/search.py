"""HTTP surface for the unified search + observability layer (Phase L8).

Endpoints:

- ``POST /api/search`` — unified hybrid search across chunks +
  messages + traces; ``scope`` lets the caller restrict to one source.
- ``POST /api/search/chunks`` — cross-thread (or single-thread) chunk
  search; same FTS5 + vector engine the in-thread retrieval uses.
- ``POST /api/search/messages`` — hybrid (BM25 + vector) search over
  chat messages. Falls back to keyword-only when no embedder is
  reachable or no message has an embedding yet.
- ``POST /api/search/embed-messages`` — embed pending messages so
  vector fusion has something to blend; returns counts. Equivalent
  to ``POST /api/meeet/traces/refresh`` for the trace materialised
  view (operator-triggered; the periodic loop is opt-in via
  ``TARS_MESSAGE_EMBED_INTERVAL_S``).
- ``POST /api/search/traces`` — free-text search over the meeet event
  durable buffer.
- ``GET    /api/search/saved`` — list operator-saved search presets
  (pinned first, then by last update).
- ``POST   /api/search/saved`` — create a saved search.
- ``GET    /api/search/saved/{id}`` — fetch one preset.
- ``PATCH  /api/search/saved/{id}`` — partial update of a preset.
- ``DELETE /api/search/saved/{id}`` — remove a preset.
- ``POST   /api/search/saved/{id}/run`` — execute the preset and
  stamp ``last_run_at``.
- ``GET  /api/chat/threads/{id}/timeline`` — structured per-thread
  timeline (mounted under the existing chat router below).

Headers honoured (consistent with the rest of the cockpit):
``x-tars-session-id``, ``x-meeet-trace-id``.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.chat import SavedSearch
from backend.core.chat.embeddings import embed_pending_messages
from backend.core.chat.store import get_chat_store
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


@router.post("/embed-messages")
async def embed_messages_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Embed pending chat messages for hybrid search.

    Body:
    - ``limit`` (int, default 200, max 1000) — pending rows scanned.
    - ``batch_size`` (int, default 32, max 256) — embedder batch size.

    Returns the same stats shape as
    :func:`backend.core.chat.embeddings.embed_pending_messages`.
    """

    body = payload or {}
    limit = max(1, min(int(body.get("limit") or 200), 1000))
    batch_size = max(1, min(int(body.get("batch_size") or 32), 256))
    chat = get_chat_store()
    pending = await chat.count_messages_pending_embedding()
    out = await embed_pending_messages(
        chat=chat, limit=limit, batch_size=batch_size
    )
    out.setdefault("pending_at_start", pending)
    return out


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
# Saved searches — operator presets for the cockpit ⌘K palette.
# Persisted in ~/.tars/chat.sqlite (table ``saved_searches``).
# ----------------------------------------------------------------------


def _saved_payload(saved: SavedSearch | None) -> dict[str, Any]:
    return saved.to_dict() if saved else {}


@router.get("/saved")
async def list_saved_searches(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    chat = get_chat_store()
    rows = await chat.list_saved_searches(limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "items": [r.to_dict() for r in rows],
    }


@router.post("/saved")
async def create_saved_search(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    label = str(body.get("label") or "").strip()
    query = str(body.get("query") or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label_required")
    if not query:
        raise HTTPException(status_code=400, detail="query_required")
    scope = _parse_scope(body.get("scope") or "all")
    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        raise HTTPException(status_code=400, detail="filters_must_be_object")
    pinned = bool(body.get("pinned") or False)
    saved = SavedSearch.fresh(
        label=label,
        query=query,
        scope=scope,
        filters=filters,
        pinned=pinned,
    )
    chat = get_chat_store()
    await chat.insert_saved_search(saved)
    return {"ok": True, "item": saved.to_dict()}


@router.get("/saved/{search_id}")
async def get_saved_search(search_id: str) -> dict[str, Any]:
    chat = get_chat_store()
    saved = await chat.get_saved_search(search_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "item": saved.to_dict()}


@router.patch("/saved/{search_id}")
async def update_saved_search(
    search_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    label = body.get("label")
    if label is not None and not str(label).strip():
        raise HTTPException(status_code=400, detail="label_blank")
    query = body.get("query")
    if query is not None and not str(query).strip():
        raise HTTPException(status_code=400, detail="query_blank")
    scope = body.get("scope")
    if scope is not None:
        scope = _parse_scope(scope)
    filters = body.get("filters")
    if filters is not None and not isinstance(filters, dict):
        raise HTTPException(status_code=400, detail="filters_must_be_object")
    pinned = body.get("pinned")
    if pinned is not None:
        pinned = bool(pinned)
    chat = get_chat_store()
    saved = await chat.update_saved_search(
        search_id,
        label=str(label) if label is not None else None,
        query=str(query) if query is not None else None,
        scope=scope,
        filters=filters,
        pinned=pinned,
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "item": saved.to_dict()}


@router.delete("/saved/{search_id}")
async def delete_saved_search(search_id: str) -> dict[str, Any]:
    chat = get_chat_store()
    deleted = await chat.delete_saved_search(search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "deleted": search_id}


@router.post("/saved/{search_id}/run")
async def run_saved_search(
    search_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Execute a saved search and stamp ``last_run_at``.

    Body:
    - ``top_k`` (int, default 12, max 50) — overrides the default;
      saved-search filters are honoured for ``thread_id`` / ``role`` /
      ``kind`` / ``trace_id`` depending on the scope.
    """

    body = payload or {}
    top_k = max(1, min(int(body.get("top_k") or 12), 50))
    chat = get_chat_store()
    saved = await chat.get_saved_search(search_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="not_found")

    filters = dict(saved.filters or {})
    if saved.scope == "all":
        res = await search(saved.query, scope="all", top_k=top_k)
        hits = [h.to_dict() for h in res.hits]
    elif saved.scope == "chunks":
        thread_id = filters.get("thread_id")
        hit_objs = await search_chunks(
            saved.query,
            top_k=top_k,
            thread_id=str(thread_id) if thread_id else None,
        )
        hits = [h.to_dict() for h in hit_objs]
    elif saved.scope == "messages":
        thread_id = filters.get("thread_id")
        role = filters.get("role")
        hit_objs = await search_messages(
            saved.query,
            top_k=top_k,
            thread_id=str(thread_id) if thread_id else None,
            role=str(role) if role else None,
        )
        hits = [h.to_dict() for h in hit_objs]
    elif saved.scope == "traces":
        kind = filters.get("kind")
        trace_id = filters.get("trace_id")
        hit_objs = await search_traces(
            saved.query,
            top_k=top_k,
            kind=str(kind) if kind else None,
            trace_id=str(trace_id) if trace_id else None,
        )
        hits = [h.to_dict() for h in hit_objs]
    else:  # pragma: no cover — _parse_scope already gates this
        hits = []

    refreshed = await chat.stamp_saved_search_run(search_id)
    return {
        "ok": True,
        "item": _saved_payload(refreshed) or saved.to_dict(),
        "query": saved.query,
        "scope": saved.scope,
        "count": len(hits),
        "hits": hits,
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
