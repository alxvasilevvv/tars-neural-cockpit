"""HTTP surface for AI Clone v0.1 + v0.2 sync (Wave 73 + Wave 151).

Endpoints:

- ``GET  /api/clone/profile`` — current style snapshot.
- ``POST /api/clone/draft``   — draft what the operator would say.
  Body: ``{context: str, k?: int}``.
- ``POST /api/clone/record``  — explicitly seed a message into the
  style store (the chat write path also calls this implicitly via
  ``record_message`` once Wave 73 lands the orchestrator hook —
  this endpoint stays available for backfill / SDK clients).
- ``POST /api/clone/export``  — Wave 151. Build a portable envelope
  of the current style state so the operator can rehydrate on a
  fresh machine. Body is empty; returns the envelope JSON.
- ``POST /api/clone/import``  — Wave 151. Accept an envelope and
  rehydrate the local store. Body: ``{envelope: {...}}``.

The clone profile is honest about its version (``0.1`` heuristic,
``0.2`` sync transport) and falls back gracefully when no LLM key
is configured.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.core.clone import draft as clone_draft, profile as clone_profile, record_message
from backend.core.clone.sync import (
    StyleEnvelope,
    export_profile,
    import_profile,
)
from backend.core.meeet import get_client as get_meeet_client, new_trace_id, trace_scope


router = APIRouter(prefix="/api/clone", tags=["clone"])


@router.get("/profile")
async def clone_profile_endpoint() -> dict[str, Any]:
    style = await clone_profile()
    return {"ok": True, **style.to_dict()}


@router.post("/draft")
async def clone_draft_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    context = str(body.get("context") or "").strip()
    if not context:
        raise HTTPException(status_code=400, detail="context_required")
    if len(context) > 4000:
        raise HTTPException(status_code=400, detail="context_too_long")
    try:
        k = int(body.get("k") or 5)
    except (TypeError, ValueError):
        k = 5

    trace_id = new_trace_id()
    meeet = get_meeet_client()
    with trace_scope(trace_id):
        await meeet.emit("clone.draft.requested", {"context_len": len(context), "k": k})
        out = await clone_draft(context=context, k=k)
        await meeet.emit(
            "clone.draft.completed",
            {
                "ok": out.get("ok"),
                "examples_used": out.get("examples_used"),
                "fallback": out.get("fallback", False),
            },
        )
    out["trace_id"] = trace_id
    return out


@router.post("/record")
async def clone_record_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text_required")
    if len(text) > 8000:
        raise HTTPException(status_code=400, detail="text_too_long")
    written = await record_message(text)
    return {"ok": True, "recorded": written}


# ─── Wave 151 — sync surface ────────────────────────────────────────────


@router.post("/export")
async def clone_export_endpoint() -> dict[str, Any]:
    """Build a :class:`StyleEnvelope` from the current store.

    The caller signs / hashes the envelope before transmitting; we
    return raw JSON here.
    """

    env = await export_profile()
    return {"ok": True, "envelope": env.to_dict()}


@router.post("/import")
async def clone_import_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Rehydrate the local store from an envelope.

    Body shape: ``{envelope: <envelope-dict>}`` or the envelope
    directly. Returns ``{ok, imported, skipped, schema_version,
    contract_version}``.
    """

    body = payload or {}
    raw = body.get("envelope") if isinstance(body.get("envelope"), dict) else body
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=400, detail="envelope_required")
    try:
        env = StyleEnvelope.from_dict(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"envelope_invalid: {exc}")
    result = await import_profile(env)
    return result
