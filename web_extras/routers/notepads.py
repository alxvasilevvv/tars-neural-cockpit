"""W243 — HTTP surface for the Notepad templates module.

Endpoints
---------

- ``GET    /api/notepads``              -> list / search (``pack=&q=&limit=``)
- ``POST   /api/notepads``              -> create new notepad
- ``GET    /api/notepads/seed``         -> seed 5 defaults if DB empty
- ``GET    /api/notepads/{id}``         -> full notepad
- ``PUT    /api/notepads/{id}``         -> update title/body/tags/pack
- ``DELETE /api/notepads/{id}``         -> remove
- ``POST   /api/notepads/{id}/use``     -> increment usage_count, return body

The router never raises out of band — store-level failures map to
HTTP 4xx/5xx envelopes the unified error handler understands.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.notepads import (
    extract_variables,
    fill_variables,
    get_notepad_store,
)


router = APIRouter(prefix="/api/notepads", tags=["notepads"])


# ---------------------------------------------------------------------
# List / search
# ---------------------------------------------------------------------


@router.get("")
async def list_notepads(
    pack: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Return notepads, filtered by ``pack`` and/or ``q``.

    ``pack`` semantics:
    - omitted / ``None`` — return notepads across all packs
    - ``""``               — return only the no-pack global notepads
    - ``"<slug>"``         — return only that pack's notepads
    """

    store = get_notepad_store()
    rows = store.list(pack=pack, q=q, limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "fts": bool(store.fts_enabled),
        "items": [n.to_dict() for n in rows],
    }


# ---------------------------------------------------------------------
# Seed defaults
# ---------------------------------------------------------------------


@router.get("/seed")
async def seed_defaults() -> dict[str, Any]:
    """Seed 5 default notepads. Idempotent — no-ops if any rows exist."""

    store = get_notepad_store()
    seeded = store.seed_defaults()
    return {
        "ok": True,
        "seeded": [n.to_dict() for n in seeded],
        "skipped": not bool(seeded),
        "count": store.count(),
    }


# ---------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------


@router.post("")
async def create_notepad(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    title = str(body.get("title") or "").strip()
    note_body = str(body.get("body") or "")
    if not title:
        raise HTTPException(status_code=400, detail="title_required")
    if not note_body:
        raise HTTPException(status_code=400, detail="body_required")
    raw_tags = body.get("tags") or []
    if not isinstance(raw_tags, list):
        raise HTTPException(status_code=400, detail="tags_must_be_list")
    tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    pack = body.get("pack")
    if pack is not None and not isinstance(pack, str):
        raise HTTPException(status_code=400, detail="pack_must_be_string")
    owner = str(body.get("owner") or "local").strip() or "local"

    store = get_notepad_store()
    pad = store.create(
        title=title,
        body=note_body,
        tags=tags,
        pack=pack,
        owner=owner,
    )
    return {"ok": True, "notepad": pad.to_dict()}


# ---------------------------------------------------------------------
# Get / Update / Delete
# ---------------------------------------------------------------------


@router.get("/{pad_id}")
async def get_notepad(pad_id: str) -> dict[str, Any]:
    pad = get_notepad_store().get(pad_id)
    if not pad:
        raise HTTPException(status_code=404, detail="notepad_not_found")
    return {"ok": True, "notepad": pad.to_dict()}


@router.put("/{pad_id}")
async def update_notepad(
    pad_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    title = body.get("title")
    note_body = body.get("body")
    tags = body.get("tags")
    pack_value: Any = ...
    if "pack" in body:
        pack_value = body.get("pack")
        if pack_value is not None and not isinstance(pack_value, str):
            raise HTTPException(status_code=400, detail="pack_must_be_string")
    if title is not None and not isinstance(title, str):
        raise HTTPException(status_code=400, detail="title_must_be_string")
    if note_body is not None and not isinstance(note_body, str):
        raise HTTPException(status_code=400, detail="body_must_be_string")
    if tags is not None and not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags_must_be_list")
    norm_tags = (
        [str(t).strip() for t in tags if str(t).strip()]
        if isinstance(tags, list)
        else None
    )

    store = get_notepad_store()
    updated = store.update(
        pad_id,
        title=title,
        body=note_body,
        tags=norm_tags,
        pack=pack_value,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="notepad_not_found")
    return {"ok": True, "notepad": updated.to_dict()}


@router.delete("/{pad_id}")
async def delete_notepad(pad_id: str) -> dict[str, Any]:
    ok = get_notepad_store().delete(pad_id)
    if not ok:
        raise HTTPException(status_code=404, detail="notepad_not_found")
    return {"ok": True, "removed": pad_id}


# ---------------------------------------------------------------------
# Use — bump usage_count and return body (with optional variable fill)
# ---------------------------------------------------------------------


@router.post("/{pad_id}/use")
async def use_notepad(
    pad_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Increment ``usage_count`` and return the body, optionally filled
    with ``{name}`` variables from the request body's ``variables``
    map. Unknown placeholders are left as-is.
    """

    body = payload or {}
    raw_vars = body.get("variables") or {}
    if not isinstance(raw_vars, dict):
        raise HTTPException(status_code=400, detail="variables_must_be_object")
    values: dict[str, str] = {
        str(k): str(v) for k, v in raw_vars.items() if str(k).strip()
    }

    store = get_notepad_store()
    pad = store.mark_used(pad_id)
    if pad is None:
        raise HTTPException(status_code=404, detail="notepad_not_found")
    rendered = fill_variables(pad.body, values) if values else pad.body
    return {
        "ok": True,
        "id": pad.id,
        "title": pad.title,
        "body": rendered,
        "raw_body": pad.body,
        "variables": extract_variables(pad.body),
        "usage_count": pad.usage_count,
    }
