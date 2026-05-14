"""W245 — HTTP surface for the codebase indexer.

Endpoints
---------

- ``POST /api/codebase/index``            body ``{root, force?}``    kick off (async) index
- ``GET  /api/codebase/index/{trace_id}`` progress for a kicked-off run
- ``GET  /api/codebase/status``           live counters / size / last-indexed
- ``POST /api/codebase/search``           body ``{query, limit, root?}`` cosine hits
- ``POST /api/codebase/watch``            body ``{root, enable}``     start/stop watcher

All five are policy-mode-agnostic — there's no spend, no LLM, no
receipt. The indexer reads source files; if the operator wants to
fence specific roots off they can drop a ``.gitignore``-style
denylist in the future (out of scope for v0).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.core import codebase


router = APIRouter(prefix="/api/codebase", tags=["codebase"])


# ---------------------------------------------------------------------------
# Index — kick off + poll
# ---------------------------------------------------------------------------


@router.post("/index")
async def kick_off_index(body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Start an async index of ``root`` and return a poll-able trace_id.

    We run ``index_path`` in a background thread; the caller polls
    ``GET /index/{trace_id}`` for progress.
    """

    root = (body or {}).get("root")
    if not root or not isinstance(root, str):
        raise HTTPException(status_code=400, detail="missing required field 'root'")
    force = bool((body or {}).get("force", False))
    trace_id = uuid.uuid4().hex[:12]

    # Pre-create the progress slot so a fast poll right after kick-off
    # always sees a valid entry, never a 404.
    codebase._progress[trace_id] = codebase.IndexProgress(  # noqa: SLF001
        trace_id=trace_id,
        root=root,
    )

    async def _run() -> None:
        await asyncio.to_thread(
            codebase.index_path,
            root,
            force,
            trace_id=trace_id,
        )

    asyncio.create_task(_run())
    return {"ok": True, "trace_id": trace_id, "root": root, "force": force}


@router.get("/index/{trace_id}")
async def get_index_progress(trace_id: str) -> dict[str, Any]:
    """Return the in-flight or finished progress for one index run."""

    p = codebase.get_progress(trace_id)
    if not p:
        raise HTTPException(status_code=404, detail="unknown trace_id")
    return {"ok": True, "progress": p}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Live counters for the cockpit's Settings panel."""

    return {"ok": True, "status": codebase.status()}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@router.post("/search")
async def search_chunks(body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Cosine-similarity search over the indexed chunks."""

    query = (body or {}).get("query", "")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="missing required field 'query'")
    limit_raw = (body or {}).get("limit", 10)
    try:
        limit = max(1, min(int(limit_raw), 50))
    except (TypeError, ValueError):
        limit = 10
    root = (body or {}).get("root")
    if root is not None and not isinstance(root, str):
        raise HTTPException(status_code=400, detail="'root' must be a string")

    hits = await asyncio.to_thread(codebase.search, query, limit, root)
    return {
        "ok": True,
        "query": query,
        "limit": limit,
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }


# ---------------------------------------------------------------------------
# Watch
# ---------------------------------------------------------------------------


@router.post("/watch")
async def toggle_watch(body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Start or stop the mtime watcher for ``root``."""

    root = (body or {}).get("root")
    if not root or not isinstance(root, str):
        raise HTTPException(status_code=400, detail="missing required field 'root'")
    enable = bool((body or {}).get("enable", True))
    out = codebase.watch_for_changes(root, enable=enable)
    return out


__all__ = ["router"]
