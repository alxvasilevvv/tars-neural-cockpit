"""W241 — Background agents tray.

Long-running agent tasks live in their own SQLite (separate from the
`backend.core.agents.store` which models the full agent lifecycle).
This module exists so the cockpit tray can poll a tiny, write-cheap
table without touching the heavier agent/task store.

Endpoints
---------

- ``GET    /api/bg_agents``                    list of recent tasks
- ``POST   /api/bg_agents/start``              spawn a new background task
- ``GET    /api/bg_agents/{task_id}``          single task + event log
- ``POST   /api/bg_agents/{task_id}/cancel``   transition → cancelled
- ``GET    /api/bg_agents/stream``             SSE stream of state changes

Persistence: ``~/.tars/bg_agents.sqlite`` (override via
``TARS_BG_AGENTS_DB_PATH``; disable via
``TARS_BG_AGENTS_STORE=disabled`` — in-memory fallback).

The store also bridges into ``backend.core.agents.store`` so existing
agent + task records get a parallel ``bg`` shadow when ``Agent.run()``
is invoked (best-effort; missing pieces never break this surface).
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Mapping

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/bg_agents", tags=["bg_agents"])


# ---------- store ------------------------------------------------------------


DEFAULT_DB_PATH = "~/.tars/bg_agents.sqlite"

_VALID_STATES = {"running", "awaiting_input", "done", "error", "cancelled"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    agent_id        TEXT NOT NULL,
    pack            TEXT NOT NULL,
    instructions    TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    progress_pct    INTEGER,
    current_step    TEXT,
    result_summary  TEXT,
    trace_id        TEXT NOT NULL,
    params_json     TEXT NOT NULL DEFAULT '{}',
    events_json     TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_bg_tasks_started ON tasks (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_bg_tasks_status ON tasks (status);
"""


def _resolve_db_path() -> str:
    raw = os.getenv("TARS_BG_AGENTS_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_BG_AGENTS_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BgAgentStore:
    """Tiny WAL'd SQLite store for the cockpit tray.

    All writes wrapped in ``asyncio.to_thread`` so we never block the
    event loop. On disabled-store environments (``TARS_BG_AGENTS_STORE
    =disabled``) the in-memory ``_mem`` dict takes over so tests still
    have a working surface.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _resolve_db_path()
        self.enabled = not _is_disabled()
        self._mem: dict[str, dict[str, Any]] = {}
        if self.enabled:
            self._ensure_schema()

    # -- helpers ----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- row → payload ----------------------------------------------------

    @staticmethod
    def _row_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "agent_id": row["agent_id"],
            "pack": row["pack"],
            "status": row["status"],
            "started_at": row["started_at"],
            "updated_at": row["updated_at"],
            "progress_pct": row["progress_pct"],
            "current_step": row["current_step"],
            "result_summary": row["result_summary"],
            "trace_id": row["trace_id"],
        }

    @staticmethod
    def _row_to_full(row: Mapping[str, Any]) -> dict[str, Any]:
        base = BgAgentStore._row_to_dict(row)
        try:
            params = json.loads(row["params_json"] or "{}")
        except (TypeError, ValueError):
            params = {}
        try:
            events = json.loads(row["events_json"] or "[]")
        except (TypeError, ValueError):
            events = []
        base["instructions"] = row["instructions"] or ""
        base["params"] = params
        base["events"] = events
        return base

    # -- sync ops (run inside to_thread) ---------------------------------

    def _create_sync(
        self,
        *,
        agent_id: str,
        pack: str,
        instructions: str,
        params: dict[str, Any],
        title: str | None,
    ) -> dict[str, Any]:
        tid = uuid.uuid4().hex
        trace_id = uuid.uuid4().hex
        now = _now_iso()
        title = (title or instructions or f"agent {agent_id[:6]}").strip()
        if len(title) > 120:
            title = title[:117] + "..."
        record = {
            "id": tid,
            "title": title,
            "agent_id": agent_id,
            "pack": pack,
            "instructions": instructions,
            "status": "running",
            "started_at": now,
            "updated_at": now,
            "progress_pct": 0,
            "current_step": "queued",
            "result_summary": None,
            "trace_id": trace_id,
            "params_json": json.dumps(params or {}),
            "events_json": json.dumps([
                {"ts": now, "kind": "started", "step": "queued", "pct": 0}
            ]),
        }
        if self.enabled:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        id, title, agent_id, pack, instructions, status,
                        started_at, updated_at, progress_pct, current_step,
                        result_summary, trace_id, params_json, events_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], record["title"], record["agent_id"],
                        record["pack"], record["instructions"], record["status"],
                        record["started_at"], record["updated_at"],
                        record["progress_pct"], record["current_step"],
                        record["result_summary"], record["trace_id"],
                        record["params_json"], record["events_json"],
                    ),
                )
            finally:
                conn.close()
        else:
            self._mem[tid] = record
        return record

    def _list_sync(self, *, limit: int) -> list[dict[str, Any]]:
        if self.enabled:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY started_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()
        recs = sorted(
            self._mem.values(), key=lambda r: r["started_at"], reverse=True
        )[:limit]
        return [self._row_to_dict(r) for r in recs]

    def _get_sync(self, task_id: str) -> dict[str, Any] | None:
        if self.enabled:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                return self._row_to_full(row) if row else None
            finally:
                conn.close()
        rec = self._mem.get(task_id)
        return self._row_to_full(rec) if rec else None

    def _update_sync(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        current_step: str | None = None,
        result_summary: str | None = None,
        event: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if status is not None and status not in _VALID_STATES:
            raise ValueError(f"invalid status: {status}")
        # Load existing for events_json merge.
        existing = self._get_sync(task_id)
        if existing is None:
            return None
        events = list(existing.get("events", []))
        if event is not None:
            event_row = {"ts": _now_iso(), **event}
            events.append(event_row)
        new_status = status if status is not None else existing["status"]
        new_pct = progress_pct if progress_pct is not None else existing["progress_pct"]
        new_step = current_step if current_step is not None else existing["current_step"]
        new_summary = (
            result_summary if result_summary is not None else existing.get("result_summary")
        )
        now = _now_iso()
        if self.enabled:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status=?, progress_pct=?, current_step=?,
                        result_summary=?, updated_at=?, events_json=?
                    WHERE id=?
                    """,
                    (
                        new_status, new_pct, new_step, new_summary,
                        now, json.dumps(events), task_id,
                    ),
                )
            finally:
                conn.close()
        else:
            rec = self._mem[task_id]
            rec["status"] = new_status
            rec["progress_pct"] = new_pct
            rec["current_step"] = new_step
            rec["result_summary"] = new_summary
            rec["updated_at"] = now
            rec["events_json"] = json.dumps(events)
        return self._get_sync(task_id)

    # -- async surface ----------------------------------------------------

    async def create_task(
        self,
        *,
        agent_id: str,
        pack: str,
        instructions: str,
        params: dict[str, Any] | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._create_sync,
            agent_id=agent_id,
            pack=pack,
            instructions=instructions,
            params=params or {},
            title=title,
        )

    async def list_tasks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_sync, limit=limit)

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_sync, task_id)

    async def update_task_status(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        current_step: str | None = None,
        result_summary: str | None = None,
        event: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        out = await asyncio.to_thread(
            self._update_sync,
            task_id,
            status=status,
            progress_pct=progress_pct,
            current_step=current_step,
            result_summary=result_summary,
            event=event,
        )
        # Best-effort SSE broadcast.
        if out is not None:
            _broadcaster.publish(out)
        return out


_SINGLETON: BgAgentStore | None = None


def get_bg_store() -> BgAgentStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = BgAgentStore()
    return _SINGLETON


def reset_singleton_for_tests() -> None:
    """Test-only: drop the module-level singleton so each test gets a
    fresh ``BgAgentStore`` that honours the current env.
    """

    global _SINGLETON
    _SINGLETON = None


# ---------- SSE broadcaster --------------------------------------------------


class _Broadcaster:
    """Tiny in-process pub/sub for SSE clients.

    Each connected client owns one ``asyncio.Queue``; ``publish`` fan-
    outs the payload to every queue with a short timeout so a slow
    client cannot stall the writer.
    """

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subs.discard(q)

    def publish(self, payload: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop the slow consumer's update — they'll catch up on
                # next state change. Never block the producer.
                pass
        # W248 — fan-out onto the unified WS event bus too.
        try:
            from backend.core.realtime import publish_event as _rt_publish
            _rt_publish("bg_agents", payload)
        except Exception:
            pass


_broadcaster = _Broadcaster()


# ---------- request models ---------------------------------------------------


class StartTaskRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=120)
    pack: str = Field(..., min_length=1, max_length=60)
    instructions: str = Field(..., min_length=1, max_length=8000)
    params: dict[str, Any] | None = None
    title: str | None = Field(default=None, max_length=160)


# W258 — managed launchd agent register payload.
class RegisterManagedAgentRequest(BaseModel):
    """Register a long-running background process under launchd.

    Distinct from ``StartTaskRequest`` — that one spawns a single
    finite agent *task* recorded in our SQLite store; this one
    installs a launchd plist so a process gets respawned across
    reboots.
    """

    id: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$",
        description="Stable id; becomes part of the launchd label.",
    )
    command: list[str] = Field(
        ..., min_length=1, max_length=64,
        description="argv to exec — list, not a shell string.",
    )
    schedule: str | None = Field(
        default=None, max_length=80,
        description='cron-ish "min hr dom mon dow"; omit for RunAtLoad.',
    )
    env: dict[str, str] | None = Field(default=None)
    keep_alive: bool = False
    run_at_load: bool = True
    working_directory: str | None = Field(default=None, max_length=512)
    dry_run: bool = False


# ---------- endpoints --------------------------------------------------------


@router.get("")
async def list_bg_tasks(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    store = get_bg_store()
    return await store.list_tasks(limit=limit)


@router.post("/start")
async def start_bg_task(body: StartTaskRequest = Body(...)) -> dict[str, Any]:
    store = get_bg_store()
    task = await store.create_task(
        agent_id=body.agent_id,
        pack=body.pack,
        instructions=body.instructions,
        params=body.params,
        title=body.title,
    )
    _broadcaster.publish(task)
    return {"ok": True, "task_id": task["id"], "task": task}


@router.get("/stream")
async def stream_bg_tasks() -> StreamingResponse:
    """Server-Sent Events stream of state changes.

    Each event is a JSON-serialised task row. A heartbeat comment
    (``:keepalive``) goes out every 15 s so proxies that close idle
    connections don't kill long-lived dashboards.
    """

    async def gen() -> AsyncIterator[bytes]:
        q = await _broadcaster.subscribe()
        try:
            # Prime with current snapshot so the client renders
            # immediately, not after the next state change.
            snapshot = await get_bg_store().list_tasks(limit=20)
            for row in snapshot:
                yield f"data: {json.dumps(row)}\n\n".encode("utf-8")
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n".encode("utf-8")
                except asyncio.TimeoutError:
                    yield b":keepalive\n\n"
        finally:
            await _broadcaster.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{task_id}")
async def get_bg_task(task_id: str) -> dict[str, Any]:
    store = get_bg_store()
    task = await store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="bg_task_not_found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_bg_task(task_id: str) -> dict[str, Any]:
    store = get_bg_store()
    task = await store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="bg_task_not_found")
    if task["status"] in {"done", "error", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"bg_task_terminal (status={task['status']})",
        )
    updated = await store.update_task_status(
        task_id,
        status="cancelled",
        current_step="cancelled",
        event={"kind": "cancelled", "step": "cancelled"},
    )
    return {"ok": True, "task": updated}


# ---------- integration helper -----------------------------------------------


async def shadow_agent_run_step(
    task_id: str,
    *,
    step: str,
    pct: int | None = None,
    status: str | None = None,
    summary: str | None = None,
) -> None:
    """Convenience for the agent runner.

    Existing call sites in ``backend/core/agents/runner.py`` can drop
    in:

        from web_extras.routers.bg_agents import shadow_agent_run_step
        await shadow_agent_run_step(bg_task_id, step="deliberating", pct=40)

    without coupling the runner to the FastAPI router beyond an import.
    Errors are swallowed so a missing bg_task_id never breaks the
    council loop.
    """

    try:
        store = get_bg_store()
        await store.update_task_status(
            task_id,
            status=status,
            progress_pct=pct,
            current_step=step,
            result_summary=summary,
            event={"kind": "step", "step": step, "pct": pct},
        )
    except Exception:
        # Never fail an agent run because of tray bookkeeping.
        pass


# ---------- W258 — managed launchd agents ------------------------------------
#
# Distinct router prefix (`/api/bg-agents`, hyphen) so the existing
# `/api/bg_agents` (underscore) task-tray surface keeps working
# untouched. The cockpit calls both: the tray polls
# ``/api/bg_agents`` for task rows and ``/api/bg-agents`` for
# managed launchd processes.


managed_router = APIRouter(prefix="/api/bg-agents", tags=["bg_agents_managed"])


def _bg_launchd():
    """Late import so unit tests can monkey-patch the module."""

    from backend.core import bg_agents as _bg
    return _bg


@managed_router.get("")
async def list_managed_agents() -> dict[str, Any]:
    """List all TARS-managed launchd agents with live status.

    Returns ``{"supported": bool, "agents": [...]}``. On non-Darwin
    the platform flag flips false but we still return an empty
    list so the frontend can render a friendly message instead of
    a 500.
    """

    bg = _bg_launchd()
    return {
        "supported": bg.is_supported(),
        "agents": await asyncio.to_thread(bg.list_managed),
    }


@managed_router.post("/register")
async def register_managed_agent(
    body: RegisterManagedAgentRequest = Body(...),
) -> dict[str, Any]:
    """Register (or replace) a managed launchd agent."""

    bg = _bg_launchd()
    result = await asyncio.to_thread(
        bg.register,
        agent_id=body.id,
        command=list(body.command),
        schedule=body.schedule,
        env=body.env,
        keep_alive=body.keep_alive,
        run_at_load=body.run_at_load,
        working_directory=body.working_directory,
        dry_run=body.dry_run,
    )
    # Fan out a status change so the cockpit tray refreshes
    # without waiting for the next poll.
    try:
        _broadcaster.publish({"kind": "managed.registered", "agent": result})
    except Exception:
        pass
    return result


@managed_router.delete("/{agent_id}")
async def unregister_managed_agent(agent_id: str) -> dict[str, Any]:
    """Unload + delete a managed launchd agent's plist."""

    bg = _bg_launchd()
    try:
        result = await asyncio.to_thread(
            bg.unregister, agent_id=agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        _broadcaster.publish({"kind": "managed.unregistered", "agent": result})
    except Exception:
        pass
    return result


@managed_router.get("/{agent_id}/status")
async def managed_agent_status(agent_id: str) -> dict[str, Any]:
    bg = _bg_launchd()
    try:
        return await asyncio.to_thread(bg.status, agent_id=agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@managed_router.get("/{agent_id}/logs")
async def managed_agent_logs(
    agent_id: str, tail: int = 200,
) -> dict[str, Any]:
    bg = _bg_launchd()
    try:
        return await asyncio.to_thread(bg.tail_logs, agent_id=agent_id, tail=tail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


__all__ = [
    "router",
    "managed_router",
    "BgAgentStore",
    "RegisterManagedAgentRequest",
    "get_bg_store",
    "reset_singleton_for_tests",
    "shadow_agent_run_step",
]
