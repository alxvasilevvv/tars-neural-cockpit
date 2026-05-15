"""W274 — Persistent conversation memory HTTP surface.

Endpoints:

  GET    /api/conversations               — recent turns (?session_id, ?limit)
  GET    /api/conversations/search        — semantic / FTS search (?q, ?limit)
  GET    /api/conversations/sessions      — list sessions with summaries
  DELETE /api/conversations/session/{id}  — drop a session + all its turns
  POST   /api/conversations/turn          — append one turn (used by chat)

The router is read/write; the chat orchestrator appends turns via
``add_exchange`` directly when it has the call site, but the HTTP
endpoint stays available for cockpit-local logging and tests.

Privacy mode (W244): when ``PRIVACY_MODE=strict`` the body of each
turn is replaced with ``"(redacted)"`` in responses.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.memory.conversation import (
    ConversationTurn,
    get_conversation_memory,
)

logger = logging.getLogger("tars.conversations")

router = APIRouter(prefix="/api/conversations", tags=["conversations", "memory"])


def _privacy_strict() -> bool:
    return (os.getenv("PRIVACY_MODE") or "").strip().lower() == "strict"


def _redact(d: dict[str, Any]) -> dict[str, Any]:
    if not _privacy_strict():
        return d
    d = dict(d)
    d["text"] = "(redacted)"
    return d


@router.get("")
async def recent(
    session_id: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(10, ge=1, le=200),
) -> dict[str, Any]:
    mem = get_conversation_memory()
    turns = mem.recent(session_id, limit=limit)
    return {
        "ok": True,
        "session_id": session_id,
        "count": len(turns),
        "turns": [_redact(t.to_dict()) for t in turns],
    }


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    mem = get_conversation_memory()
    turns = mem.search(q, limit=limit)
    return {
        "ok": True,
        "query": q,
        "count": len(turns),
        "results": [_redact(t.to_dict()) for t in turns],
    }


@router.get("/sessions")
async def sessions(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    mem = get_conversation_memory()
    rows = mem.list_sessions(limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "sessions": rows,
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    if not session_id:
        raise HTTPException(status_code=400, detail={"error": "missing_session_id"})
    mem = get_conversation_memory()
    n = mem.delete_session(session_id)
    return {"ok": True, "session_id": session_id, "deleted": n}


class TurnIn(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., min_length=1, max_length=16)
    text: str = Field(..., min_length=1, max_length=10000)
    audio_url: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


@router.post("/turn")
async def add_turn(turn: TurnIn) -> dict[str, Any]:
    mem = get_conversation_memory()
    rec = ConversationTurn(
        id="",
        session_id=turn.session_id,
        role=turn.role,
        text=turn.text,
        audio_url=turn.audio_url,
        tokens_in=turn.tokens_in,
        tokens_out=turn.tokens_out,
    )
    saved = mem.add_turn(rec)
    return {"ok": True, "turn": _redact(saved.to_dict())}


class ExchangeIn(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_text: str = Field(..., min_length=1, max_length=10000)
    tars_text: str = Field(..., min_length=1, max_length=10000)
    audio_url: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


@router.post("/exchange")
async def add_exchange(ex: ExchangeIn) -> dict[str, Any]:
    """Convenience: append user + TARS in one shot (atomic-ish)."""
    mem = get_conversation_memory()
    u, t = mem.add_exchange(
        session_id=ex.session_id,
        user_text=ex.user_text,
        tars_text=ex.tars_text,
        audio_url=ex.audio_url,
        tokens_in=ex.tokens_in,
        tokens_out=ex.tokens_out,
    )
    return {
        "ok": True,
        "user_turn": _redact(u.to_dict()),
        "tars_turn": _redact(t.to_dict()),
    }


@router.get("/context")
async def context(
    session_id: str = Query(..., min_length=1, max_length=120),
    q: str = Query("", max_length=500),
    recent_limit: int = Query(10, ge=1, le=50),
    search_limit: int = Query(5, ge=0, le=20),
) -> dict[str, Any]:
    """Bundle a session's recent + related turns for the LLM prompt."""
    mem = get_conversation_memory()
    blob = mem.context_for(
        session_id=session_id,
        query=q,
        recent_limit=recent_limit,
        search_limit=search_limit,
    )
    if _privacy_strict():
        blob["recent"] = [_redact(t) for t in blob.get("recent", [])]
        blob["related"] = [_redact(t) for t in blob.get("related", [])]
    return {"ok": True, **blob}
