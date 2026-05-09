"""HTTP surface for per-pack memory partitions.

Endpoints under ``/api/packs/{slug}/memory`` give every domain pack a
namespaced key-value store. The ``slug`` is *not* validated against
the pack registry on purpose — operators can stash facts under
arbitrary tags (a "draft" namespace, a "shared" namespace, etc.) and
the registry membership is a separate concern.

- ``GET    /api/packs/{slug}/memory``                 — list entries
- ``POST   /api/packs/{slug}/memory``                 — upsert
- ``GET    /api/packs/{slug}/memory/{key}``           — fetch one
- ``DELETE /api/packs/{slug}/memory/{key}``           — delete
- ``POST   /api/packs/{slug}/memory/_purge_expired``  — TTL sweep
- ``GET    /api/packs/{slug}/memory/_stats``          — pack stats
- ``GET    /api/memory/stats``                        — global stats
- ``POST   /api/memory/reflect``                      — Wave 73 weekly reflection

TTL semantics: pass ``ttl_seconds`` (relative window) or
``ttl_until`` (absolute POSIX) on upsert. The list/get endpoints
return only live entries by default; pass ``include_expired=true``
to inspect everything still on disk.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from backend.core.memory import MemoryEntry, get_memory_store
from backend.core.memory.reflection import run_reflection
from backend.core.meeet import get_client as get_meeet_client, new_trace_id, trace_scope


router = APIRouter(prefix="/api", tags=["memory"])


@router.post("/memory/reflect")
async def memory_reflect_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Wave 73 Feature 3 — manually trigger the weekly reflection.

    Body (all optional):
      ``{days: int = 7, force: bool = false}``

    Force=true overwrites any existing row for the current ISO week.
    """

    body = payload or {}
    try:
        days = int(body.get("days") or 7)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="days_must_be_int")
    days = max(1, min(days, 30))
    force = bool(body.get("force"))

    trace_id = new_trace_id()
    meeet = get_meeet_client()
    with trace_scope(trace_id):
        await meeet.emit("memory.reflect.requested", {"days": days, "force": force})
        out = await run_reflection(days=days, force=force)
        await meeet.emit(
            "memory.reflect.completed",
            {
                "ok": out.get("ok"),
                "key": out.get("key"),
                "skipped": out.get("skipped", False),
                "message_count": out.get("message_count"),
                "provider": out.get("provider"),
            },
        )
    out["trace_id"] = trace_id
    return out


def _entry_dict(entry: MemoryEntry | None) -> dict[str, Any] | None:
    return entry.to_dict() if entry else None


def _resolve_ttl(body: dict[str, Any]) -> float | None:
    if "ttl_until" in body and body["ttl_until"] is not None:
        try:
            ts = float(body["ttl_until"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="ttl_until_must_be_number"
            )
        return ts
    if "ttl_seconds" in body and body["ttl_seconds"] is not None:
        try:
            secs = float(body["ttl_seconds"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="ttl_seconds_must_be_number"
            )
        if secs <= 0:
            return None
        return time.time() + secs
    return None


@router.get("/packs/{slug}/memory")
async def list_memory(
    slug: str,
    kind: str | None = Query(default=None),
    key_prefix: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    include_expired: bool = Query(default=False),
) -> dict[str, Any]:
    store = get_memory_store()
    if not store.enabled:
        return {"ok": False, "reason": "memory_store_disabled"}
    entries = await store.list(
        pack_slug=slug,
        kind=kind,
        key_prefix=key_prefix,
        limit=limit,
        include_expired=include_expired,
    )
    return {
        "ok": True,
        "pack_slug": slug,
        "count": len(entries),
        "entries": [e.to_dict() for e in entries],
    }


@router.post("/packs/{slug}/memory")
async def upsert_memory(
    slug: str,
    payload: dict[str, Any] = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    body = payload or {}
    key = body.get("key")
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(status_code=400, detail="key_required")
    if "value" not in body:
        raise HTTPException(status_code=400, detail="value_required")
    kind = body.get("kind") or "fact"
    if not isinstance(kind, str):
        raise HTTPException(status_code=400, detail="kind_must_be_string")
    source = body.get("source")
    if source is not None and not isinstance(source, str):
        raise HTTPException(
            status_code=400, detail="source_must_be_string_or_null"
        )
    metadata = body.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata_must_be_object")

    ttl_until = _resolve_ttl(body)

    store = get_memory_store()
    if not store.enabled:
        raise HTTPException(
            status_code=503, detail="memory_store_disabled"
        )

    # 2026-05-04 audit-3: pack memory writes are operator-meaningful
    # (every saved fact eventually feeds prompt context). Trace
    # them so the meeet trail captures provenance.
    parent_trace = (x_meeet_trace_id or "").strip() or None
    trace_id = parent_trace or new_trace_id()
    meeet = get_meeet_client()
    base_payload = {
        "pack_slug": slug,
        "key": key,
        "kind": kind,
        "source": source,
        "ttl_until": ttl_until,
        "has_metadata": bool(metadata),
    }

    with trace_scope(trace_id):
        await meeet.emit("memory.upsert.requested", base_payload)
        try:
            entry = await store.upsert(
                pack_slug=slug,
                key=key,
                value=body["value"],
                kind=kind,
                ttl_until=ttl_until,
                source=source,
                metadata=metadata,
            )
        except Exception as exc:
            await meeet.emit(
                "memory.upsert.failed",
                {**base_payload, "error": str(exc)[:200]},
            )
            raise

        await meeet.emit(
            "memory.upsert.completed",
            {**base_payload, "entry_id": getattr(entry, "id", None)},
        )

    return {"ok": True, "entry": _entry_dict(entry), "trace_id": trace_id}


@router.get("/packs/{slug}/memory/_stats")
async def pack_memory_stats(slug: str) -> dict[str, Any]:
    return await get_memory_store().stats(pack_slug=slug)


@router.post("/packs/{slug}/memory/_purge_expired")
async def purge_pack_expired(slug: str) -> dict[str, Any]:
    return await get_memory_store().purge_expired(pack_slug=slug)


@router.get("/packs/{slug}/memory/{key:path}")
async def get_memory_entry(
    slug: str,
    key: str,
    include_expired: bool = Query(default=False),
) -> dict[str, Any]:
    store = get_memory_store()
    if not store.enabled:
        raise HTTPException(
            status_code=503, detail="memory_store_disabled"
        )
    entry = await store.get(
        pack_slug=slug, key=key, include_expired=include_expired,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "entry": entry.to_dict()}


@router.delete("/packs/{slug}/memory/{key:path}")
async def delete_memory_entry(
    slug: str,
    key: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_memory_store()
    parent_trace = (x_meeet_trace_id or "").strip() or None
    trace_id = parent_trace or new_trace_id()
    meeet = get_meeet_client()
    base_payload = {"pack_slug": slug, "key": key}

    with trace_scope(trace_id):
        await meeet.emit("memory.delete.requested", base_payload)
        deleted = await store.delete(pack_slug=slug, key=key)
        if not deleted:
            await meeet.emit(
                "memory.delete.failed",
                {**base_payload, "error": "not_found"},
            )
            raise HTTPException(status_code=404, detail="not_found")
        await meeet.emit("memory.delete.completed", base_payload)

    return {"ok": True, "pack_slug": slug, "key": key, "trace_id": trace_id}


@router.get("/memory/stats")
async def global_memory_stats() -> dict[str, Any]:
    return await get_memory_store().stats()


@router.post("/memory/_purge_expired")
async def global_purge_expired() -> dict[str, Any]:
    return await get_memory_store().purge_expired()
