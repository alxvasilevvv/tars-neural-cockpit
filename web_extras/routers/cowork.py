"""HTTP surface for the Cowork subsystem (Wave 149).

Wires the W129 backend module (`backend/core/cowork/`) into FastAPI
endpoints. Mirrors the routes specified in `docs/contracts/COWORK.md`
v1.0 and the paste-ready scaffolding at
`docs/handoff/COWORK_WIRING_FOR_CURSOR.md`.

Why this lives here (not at brother's core-bridge):
  - Lets the local TARS backend (`make backend-tars-up`) serve
    /api/cowork/* directly, so operator can demo Cowork end-to-end
    without depending on the core-bridge edge function.
  - Brother can copy this file verbatim into core-bridge with the
    same import paths — the contracts match.
  - W129 frontend was deleted with the SPA cleanup (e5f1911); future
    Tauri-side Cowork UI will call these same routes via 127.0.0.1.

Endpoints (10 total, all return JSON unless noted):

  POST  /api/cowork/sessions                    create session
  GET   /api/cowork/sessions                    list (filter by owner/workspace)
  GET   /api/cowork/sessions/:slug              fetch by slug or id
  POST  /api/cowork/sessions/:id/members        add member, returns token
  GET   /api/cowork/sessions/:id/members        list members (no tokens leaked)
  POST  /api/cowork/sessions/:id/heartbeat      presence ping (member_token)
  POST  /api/cowork/sessions/:id/cursor         cursor publish (member_token)
  POST  /api/cowork/sessions/:id/handoff        open handoff link
  POST  /api/cowork/handoff/:token/accept       consume handoff
  GET   /api/cowork/sessions/:id/stream         SSE pub/sub stream
  POST  /api/cowork/sessions/:id/end            end session (idempotent)

Contract version: 1.0 (see `docs/contracts/COWORK.md`).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.cowork import (
    HandoffError,
    MemberRole,
    accept_handoff,
    create_handoff,
    get_store,
    get_tracker,
    publish,
    subscribe,
)


router = APIRouter(prefix="/api/cowork", tags=["cowork"])


# ---------- pydantic bodies -------------------------------------------------


class CreateSessionBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    owner_user_id: str = Field(..., min_length=1, max_length=200)
    workspace_id: str | None = None
    metadata: dict[str, Any] | None = None


class AddMemberBody(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    user_id: str | None = None
    email: str | None = None
    role: str = "editor"


class HeartbeatBody(BaseModel):
    member_token: str
    typing: bool = False
    focus_path: str | None = None


class CursorBody(BaseModel):
    member_token: str
    path: str = Field(..., min_length=1, max_length=400)
    line: int = 0
    col: int = 0
    selection: dict[str, Any] | None = None


class HandoffBody(BaseModel):
    from_user_id: str
    to_email: str | None = None
    ttl_seconds: int | None = None


class AcceptHandoffBody(BaseModel):
    accepted_by_user_id: str


# ---------- serialisers -----------------------------------------------------


def _session_to_dict(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "slug": s.slug,
        "owner_user_id": s.owner_user_id,
        "status": s.status.value,
        "created_at": s.created_at,
        "ended_at": s.ended_at,
        "workspace_id": s.workspace_id,
        "metadata": s.metadata,
    }


def _member_to_dict(m: Any) -> dict[str, Any]:
    """Token-less member view — DO NOT include `token` in list responses.

    Token only goes back on create (in :func:`add_member` below).
    """
    return {
        "id": m.id,
        "session_id": m.session_id,
        "display_name": m.display_name,
        "user_id": m.user_id,
        "email": m.email,
        "role": m.role.value,
        "color": m.color,
        "joined_at": m.joined_at,
        "last_seen_at": m.last_seen_at,
    }


def _cursor_to_dict(c: Any) -> dict[str, Any]:
    return {
        "id": c.id,
        "session_id": c.session_id,
        "member_id": c.member_id,
        "path": c.path,
        "line": c.line,
        "col": c.col,
        "selection": c.selection,
        "updated_at": c.updated_at,
    }


async def _resolve_member(token: str) -> Any:
    store = await get_store()
    m = await store.get_member_by_token(token)
    if m is None:
        raise HTTPException(status_code=401, detail="invalid_member_token")
    return m


# ---------- sessions --------------------------------------------------------


@router.post("/sessions")
async def create_session(body: CreateSessionBody) -> dict[str, Any]:
    store = await get_store()
    s = await store.create_session(
        name=body.name,
        owner_user_id=body.owner_user_id,
        workspace_id=body.workspace_id,
        metadata=body.metadata or {},
    )
    return _session_to_dict(s)


@router.get("/sessions")
async def list_sessions(
    owner_user_id: str | None = None,
    workspace_id: str | None = None,
    active_only: bool = False,
) -> dict[str, Any]:
    store = await get_store()
    sessions = await store.list_sessions(
        owner_user_id=owner_user_id,
        workspace_id=workspace_id,
        active_only=active_only,
    )
    return {"sessions": [_session_to_dict(s) for s in sessions]}


@router.get("/sessions/{slug_or_id}")
async def get_session(slug_or_id: str) -> dict[str, Any]:
    store = await get_store()
    # Try slug first (URL-friendly), fall back to id.
    s = await store.get_session_by_slug(slug_or_id)
    if s is None:
        s = await store.get_session(slug_or_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return _session_to_dict(s)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str) -> dict[str, Any]:
    store = await get_store()
    ok = await store.end_session(session_id)
    return {"ok": ok}


# ---------- members ---------------------------------------------------------


@router.post("/sessions/{session_id}/members")
async def add_member(session_id: str, body: AddMemberBody) -> dict[str, Any]:
    store = await get_store()
    s = await store.get_session(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    m = await store.add_member(
        session_id=session_id,
        display_name=body.display_name,
        user_id=body.user_id,
        email=body.email,
        role=body.role,
    )
    # First and only place the token is exposed.
    out = _member_to_dict(m)
    out["token"] = m.token
    return out


@router.get("/sessions/{session_id}/members")
async def list_members(session_id: str) -> dict[str, Any]:
    store = await get_store()
    members = await store.list_members(session_id=session_id)
    return {"members": [_member_to_dict(m) for m in members]}


# ---------- presence + cursor ----------------------------------------------


@router.post("/sessions/{session_id}/heartbeat")
async def heartbeat(session_id: str, body: HeartbeatBody) -> dict[str, Any]:
    m = await _resolve_member(body.member_token)
    if m.session_id != session_id:
        raise HTTPException(status_code=403, detail="member_session_mismatch")
    tracker = await get_tracker()
    tracker.heartbeat(
        session_id, m.id, typing=body.typing, focus_path=body.focus_path
    )
    store = await get_store()
    await store.touch_member(m.id)
    return {"ok": True, "member_id": m.id}


@router.post("/sessions/{session_id}/cursor")
async def publish_cursor(session_id: str, body: CursorBody) -> dict[str, Any]:
    m = await _resolve_member(body.member_token)
    if m.session_id != session_id:
        raise HTTPException(status_code=403, detail="member_session_mismatch")
    if m.role == MemberRole.VIEWER:
        raise HTTPException(status_code=403, detail="viewers_cannot_publish_cursors")
    store = await get_store()
    c = await store.upsert_cursor(
        session_id=session_id,
        member_id=m.id,
        path=body.path,
        line=body.line,
        col=body.col,
        selection=body.selection,
    )
    # Fan-out cursor move so other live subscribers see it.
    await publish(
        session_id,
        {
            "type": "cursor",
            "data": {
                "member_id": m.id,
                "member_name": m.display_name,
                "path": c.path,
                "line": c.line,
                "col": c.col,
                "label": f"moved to line {c.line}",
            },
        },
    )
    return _cursor_to_dict(c)


# ---------- handoff ---------------------------------------------------------


@router.post("/sessions/{session_id}/handoff")
async def open_handoff(session_id: str, body: HandoffBody) -> dict[str, Any]:
    try:
        h = await create_handoff(
            session_id=session_id,
            from_user_id=body.from_user_id,
            to_email=body.to_email,
            ttl_seconds=body.ttl_seconds,
        )
    except HandoffError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "handoff_id": h.id,
        "token": h.token,
        "expires_at": h.expires_at,
    }


@router.post("/handoff/{token}/accept")
async def consume_handoff(token: str, body: AcceptHandoffBody) -> dict[str, Any]:
    try:
        h = await accept_handoff(
            token=token,
            accepted_by_user_id=body.accepted_by_user_id,
        )
    except HandoffError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "handoff_id": h.id,
        "session_id": h.session_id,
        "accepted_at": h.accepted_at,
        "accepted_by_user_id": h.accepted_by_user_id,
    }


# ---------- SSE stream ------------------------------------------------------


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: str, request: Request
) -> StreamingResponse:
    """SSE stream of live events for a session.

    Emits frames in the contract envelope (`{id, type, occurred_at, data}`)
    plus a synthetic `heartbeat` every 15 s if nothing real happens
    (keeps the connection alive through proxies that kill idle streams).
    """

    async def event_source():
        # Initial retry advisory so EventSource clients reconnect at
        # the cadence we expect.
        yield "retry: 15000\n\n"
        async for event in subscribe(session_id):
            if await request.is_disconnected():
                return
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",  # disable nginx buffering if proxied
            "connection": "keep-alive",
        },
    )
