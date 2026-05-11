# TARS v9.1.1 — Cowork core-bridge wiring handoff for Cursor

> Paste-ready prompt for the Cursor session running on Andrey Syrchin's Mac
> (same setup as `APPLE_SIGNING_FOR_CURSOR.md`).
>
> Expected duration: ~25-40 minutes wall-clock for a competent FastAPI dev.
> Ownership: Cursor writes the routes, Andrey reviews + commits + deploys
> to the core-bridge Supabase Edge Function (or whatever runtime hosts the
> bridge — same place that handles `/api/cohort/*` and `/api/webhooks/*`).
>
> If you're doing Apple cert first (`APPLE_SIGNING_FOR_CURSOR.md`), finish
> that, ship v9.1.0, THEN come back to this doc for v9.1.1.

---

## Context for Cursor

- Repo: https://github.com/alxvasilevvv/tars-neural-cockpit
- Backend module already shipped: `backend/core/cowork/` (Wave 129)
- Frontend page already shipped: `experiments/neural-showcase-v3/src/pages/Cowork.tsx`
- Contract: `docs/contracts/COWORK.md` (read this first — has full event
  envelope + endpoint table + storage schema)
- Brother handoff context: `docs/BROTHER_HANDOFF_v9.1.0.md` § Wave 129
- Currently the frontend transparently falls back to a deterministic
  mock when `/api/cowork/*` 404s, so launch is not blocked — wiring the
  endpoints turns the mock off automatically (no FE change needed).

---

## What's already done (no work for you)

✅ Backend module fully implemented:

```
backend/core/cowork/
  __init__.py     — re-exports + emit_agent_frame() best-effort helper
  models.py       — Session/Member/Cursor/Handoff dataclasses + helpers
  store.py        — CoworkStore (SQLite, WAL, asyncio.to_thread)
  presence.py     — PresenceTracker (25s TTL, in-process)
  stream.py       — publish/subscribe (asyncio.Queue, 15s heartbeat)
  handoff.py      — create_handoff/accept_handoff with atomic accept
```

✅ Tests passing (26/26 pytest):
- `tests/test_cowork_store.py` — CRUD + handoff atomicity
- `tests/test_cowork_presence.py` — presence + stream fan-out

✅ Frontend complete with mock fallback:
- `/cowork` (list), `/cowork/:slug` (session), `/cowork/handoff/:token` (accept)
- Mock kicks in automatically when fetch fails — no FE change needed when
  you ship the real endpoints

✅ Orchestrator emits frames already:
- `backend/core/agents/runner.py` reads `metadata['cowork_session_id']` and
  calls `cowork.emit_agent_frame()` on `task.started`/`completed`/`failed`

---

## Your job: 10 FastAPI routes

The frontend already calls these exact paths (see `experiments/neural-showcase-v3/src/lib/cowork.ts`). All bodies are JSON. All non-stream responses are JSON.

| Method | Path                                          |
| ------ | --------------------------------------------- |
| POST   | `/api/cowork/sessions`                        |
| GET    | `/api/cowork/sessions`                        |
| GET    | `/api/cowork/sessions/:slug`                  |
| POST   | `/api/cowork/sessions/:id/members`            |
| GET    | `/api/cowork/sessions/:id/members`            |
| POST   | `/api/cowork/sessions/:id/heartbeat`          |
| POST   | `/api/cowork/sessions/:id/cursor`             |
| POST   | `/api/cowork/sessions/:id/handoff`            |
| POST   | `/api/cowork/handoff/:token/accept`           |
| GET    | `/api/cowork/sessions/:id/stream`             |

---

## Drop-in FastAPI scaffolding (paste-ready)

Create a new file `web_extras/routers/cowork.py` (or wherever the bridge
mounts its routers — same place as `cohort.py` and `webhooks.py`):

```python
"""TARS Cowork router (Wave 129 contract v1.0).

Exposes /api/cowork/* HTTP surface for the multiplayer agent session
feature. Backend logic lives in backend/core/cowork/ — this file is a
thin transport layer.

Auth: every member-scoped call carries a `member_token` (32-byte
URL-safe random) in the request body. The bridge can layer an outer
user-auth check on top (e.g. require a signed-in TARS user before
allowing session creation), but token-based member auth is what gates
write access at the row level.

Mounted at: app.include_router(cowork_router, prefix="/api/cowork")
"""

from __future__ import annotations

import asyncio
import json
import time
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
    subscribe,
)

router = APIRouter()


# ─── Pydantic models ──────────────────────────────────────────────────


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


# ─── Helpers ──────────────────────────────────────────────────────────


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
        # NOTE: do NOT leak token in list responses. Only the create
        # response includes it (so the member can stash it client-side).
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
        raise HTTPException(status_code=401, detail="invalid member_token")
    return m


# ─── Sessions ─────────────────────────────────────────────────────────


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


@router.get("/sessions/{slug}")
async def get_session(slug: str) -> dict[str, Any]:
    store = await get_store()
    # Allow either slug or id — frontend uses slug from the URL but
    # other backend callers might pass ids.
    s = await store.get_session_by_slug(slug)
    if s is None:
        s = await store.get_session(slug)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_to_dict(s)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str) -> dict[str, Any]:
    store = await get_store()
    ok = await store.end_session(session_id)
    return {"ok": ok}


# ─── Members ──────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/members")
async def add_member(session_id: str, body: AddMemberBody) -> dict[str, Any]:
    store = await get_store()
    s = await store.get_session(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    m = await store.add_member(
        session_id=session_id,
        display_name=body.display_name,
        user_id=body.user_id,
        email=body.email,
        role=body.role,
    )
    # First and only place the token is returned. Caller stashes it
    # client-side (memory or session storage).
    out = _member_to_dict(m)
    out["token"] = m.token
    return out


@router.get("/sessions/{session_id}/members")
async def list_members(session_id: str) -> dict[str, Any]:
    store = await get_store()
    members = await store.list_members(session_id=session_id)
    return {"members": [_member_to_dict(m) for m in members]}


# ─── Presence / cursor (member-token-scoped) ──────────────────────────


@router.post("/sessions/{session_id}/heartbeat")
async def heartbeat(session_id: str, body: HeartbeatBody) -> dict[str, Any]:
    m = await _resolve_member(body.member_token)
    if m.session_id != session_id:
        raise HTTPException(status_code=403, detail="member is in a different session")
    tracker = await get_tracker()
    tracker.heartbeat(
        session_id, m.id, typing=body.typing, focus_path=body.focus_path
    )
    # Touch the durable last_seen_at too so list_members reflects it.
    store = await get_store()
    await store.touch_member(m.id)
    return {"ok": True}


@router.post("/sessions/{session_id}/cursor")
async def publish_cursor(session_id: str, body: CursorBody) -> dict[str, Any]:
    m = await _resolve_member(body.member_token)
    if m.session_id != session_id:
        raise HTTPException(status_code=403, detail="member is in a different session")
    if m.role == MemberRole.VIEWER:
        raise HTTPException(status_code=403, detail="viewers cannot publish cursors")
    store = await get_store()
    c = await store.upsert_cursor(
        session_id=session_id,
        member_id=m.id,
        path=body.path,
        line=body.line,
        col=body.col,
        selection=body.selection,
    )
    # Fan-out the cursor move so other subscribers see it in real time.
    from backend.core.cowork import publish
    await publish(
        session_id,
        {
            "type": "cursor",
            "data": {
                "member_id": m.id,
                "path": c.path,
                "line": c.line,
                "col": c.col,
                "label": f"moved to line {c.line}",
            },
        },
    )
    return _cursor_to_dict(c)


# ─── Handoff ──────────────────────────────────────────────────────────


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


# ─── SSE stream ───────────────────────────────────────────────────────


@router.get("/sessions/{session_id}/stream")
async def stream(session_id: str, request: Request) -> StreamingResponse:
    async def event_source():
        # Advisory retry hint for the EventSource client.
        yield "retry: 15000\n\n"
        async for event in subscribe(session_id):
            # Bail out cleanly if the client disconnected.
            if await request.is_disconnected():
                return
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
```

---

## Mounting the router

Wherever the bridge wires routers (next to `cohort.py`, `webhooks.py`):

```python
from web_extras.routers.cowork import router as cowork_router

app.include_router(cowork_router, prefix="/api/cowork", tags=["cowork"])
```

---

## Verification curls (after deploy)

```bash
# 1. Create a session
curl -X POST https://tars.meeet.world/api/cowork/sessions \
  -H "content-type: application/json" \
  -d '{"name":"Smoke test","owner_user_id":"u_alice"}'
# expect: { id, slug, status:"live", ... }

# 2. Add a member (stash the token from the response)
SID=$(curl ... | jq -r .id)
curl -X POST https://tars.meeet.world/api/cowork/sessions/$SID/members \
  -H "content-type: application/json" \
  -d '{"display_name":"Bob","role":"editor"}'
# expect: { id, token: "...", color, role, ... }

# 3. Subscribe to the stream (in a separate terminal)
curl -N https://tars.meeet.world/api/cowork/sessions/$SID/stream
# expect: text/event-stream with `data: {...}\n\n` frames, heartbeat
# every 15s if no real events

# 4. Heartbeat using the token
MTOKEN="..."
curl -X POST https://tars.meeet.world/api/cowork/sessions/$SID/heartbeat \
  -H "content-type: application/json" \
  -d "{\"member_token\":\"$MTOKEN\"}"
# expect: {"ok":true}

# 5. Open a handoff (must be from the owner)
curl -X POST https://tars.meeet.world/api/cowork/sessions/$SID/handoff \
  -H "content-type: application/json" \
  -d '{"from_user_id":"u_alice","to_email":"bob@example.com"}'
# expect: { token, expires_at }

# 6. Accept the handoff
HTOKEN="..."
curl -X POST https://tars.meeet.world/api/cowork/handoff/$HTOKEN/accept \
  -H "content-type: application/json" \
  -d '{"accepted_by_user_id":"u_bob"}'
# expect: { handoff_id, accepted_at, accepted_by_user_id }
# Verify ownership transferred:
curl https://tars.meeet.world/api/cowork/sessions/$SID
# expect: owner_user_id == "u_bob"
```

---

## What to do if you hit an error

- **Module import fails** — confirm `backend/core/cowork/` exists in the
  deployed image. Re-pull from main if missing.
- **SQLite locked errors** — confirm WAL mode is enabled. Should be
  automatic via `PRAGMA journal_mode=WAL` in `store._connect()`.
- **SSE returns empty** — check `X-Accel-Buffering: no` on the reverse
  proxy + your Edge runtime supports streaming responses (Cloudflare
  Workers Edge supports it via `ReadableStream`).
- **Tests** — running `python -m unittest tests.test_cowork_store
  tests.test_cowork_presence` should give 26/26 PASS.

---

## After this ships → v9.1.1 release

1. Bump `tauri.conf.json` version to `9.1.1`.
2. Bump SW VERSION in `experiments/neural-showcase-v3/public/sw.js`.
3. Tag `v9.1.1` + push. CI release fires automatically (signing already
   set up via v9.1.0 work).
4. The frontend `mock fallback` in `src/lib/cowork.ts` self-deactivates —
   the real path is preferred, mock only kicks in on fetch failure. No
   FE change needed.

---

>>> SYNC: Claude · 2026-05-12 · Wave 133 cowork wiring handoff.
