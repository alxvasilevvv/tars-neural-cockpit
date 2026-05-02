"""HTTP surface over the council orchestrator.

Single endpoint for now: ``POST /api/council/deliberate``. Body:

    {
        "prompt": "...",
        "context": {"topic": "market", "avg_change_24h": -1.5, ...},
        "mode": "dual_vote"
    }

Returns a :class:`Deliberation` payload with all voice proposals,
the chosen stance, agreement score, contradictions, and recommended
actions. Backed by the same trace_id so a council deliberation can be
linked to the action that triggered it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from backend.core.council import get_council
from backend.core.meeet import trace_scope

router = APIRouter(prefix="/api/council", tags=["council"])


@router.post("/deliberate")
async def deliberate(
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "")
    context = payload.get("context") or {}
    mode = str(payload.get("mode") or "dual_vote")

    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context_must_be_object")

    try:
        with trace_scope(parent=x_meeet_trace_id):
            out = await get_council().deliberate(
                prompt,
                context,
                mode=mode,
                thread_id=x_tars_thread_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return out.to_dict()
