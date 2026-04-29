"""HTTP surface for the multi-agent system (Phase M).

Endpoints:

- ``POST   /api/agents``                       create
- ``GET    /api/agents``                       list
- ``GET    /api/agents/{agent_id}``            single
- ``PATCH  /api/agents/{agent_id}``            rename / pause / archive / wallet
- ``POST   /api/agents/{agent_id}/tasks``      assign a task
- ``GET    /api/agents/{agent_id}/tasks``      list tasks for the agent
- ``GET    /api/tasks/{task_id}``              single task
- ``POST   /api/tasks/{task_id}/run``          execute the task
- ``POST   /api/tasks/{task_id}/cancel``       cancel pending/running task

Every state transition emits ``agent.*`` / ``agent.task.*`` events
into the meeet store so replay on a paired device gives the same
audit trail that already exists for tool calls and policy actions.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from backend.core.agents import (
    AgentStatus,
    Task,
    TaskStatus,
    get_agent_store,
)
from backend.core.agents.autopilot import tick_once as _autopilot_tick_once
from backend.core.agents.runner import run_task
from backend.core.domains.registry import all_packs, get_pack
from backend.core.meeet import get_client, trace_scope


router = APIRouter(prefix="/api", tags=["agents"])


# ---------- request models ----------------------------------------------------


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    pack_slug: str = Field(..., min_length=1, max_length=60)
    description: str = Field(default="")
    system_prompt: Optional[str] = None
    wallet_address: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PatchAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    wallet_address: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CreateTaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    metadata: Optional[dict[str, Any]] = None


class RunTaskRequest(BaseModel):
    council_mode: str = Field(default="dual_vote")


# ---------- helpers -----------------------------------------------------------


def _check_pack(slug: str) -> None:
    if get_pack(slug) is None:
        registered = sorted(p.manifest.slug for p in all_packs())
        raise HTTPException(
            status_code=400,
            detail=f"unknown pack_slug: {slug} (known: {registered})",
        )


def _task_payload(task: Task) -> dict[str, Any]:
    return task.to_dict()


# ---------- endpoints ---------------------------------------------------------


@router.post("/agents")
async def create_agent(
    body: CreateAgentRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _check_pack(body.pack_slug)
    store = get_agent_store()
    try:
        agent = await store.create_agent(
            name=body.name,
            pack_slug=body.pack_slug,
            description=body.description or "",
            system_prompt=body.system_prompt,
            wallet_address=body.wallet_address,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "agent.created",
            {
                "agent_id": agent.id,
                "name": agent.name,
                "pack_slug": agent.pack_slug,
                "wallet_address": agent.wallet_address,
            },
        )
        return {"ok": True, "trace_id": tid, "agent": agent.to_dict()}


@router.get("/agents")
async def list_agents(include_archived: bool = False) -> dict[str, Any]:
    store = get_agent_store()
    items = await store.list_agents(include_archived=include_archived)
    return {
        "ok": True,
        "count": len(items),
        "agents": [a.to_dict() for a in items],
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return {"ok": True, "agent": agent.to_dict()}


@router.patch("/agents/{agent_id}")
async def patch_agent(
    agent_id: str,
    body: PatchAgentRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_agent_store()
    updates = body.model_dump(exclude_none=True)
    try:
        agent = await store.patch_agent(agent_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "agent.patched",
            {
                "agent_id": agent.id,
                "status": agent.status.value,
                "fields": sorted(updates.keys()),
            },
        )
        return {"ok": True, "trace_id": tid, "agent": agent.to_dict()}


@router.post("/agents/{agent_id}/tasks")
async def create_task(
    agent_id: str,
    body: CreateTaskRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    if agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=409,
            detail=f"agent_not_active (status={agent.status.value})",
        )
    try:
        task = await store.create_task(
            agent_id=agent_id, prompt=body.prompt, metadata=body.metadata
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "agent.task.queued",
            {
                "task_id": task.id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "prompt": body.prompt[:160],
            },
        )
        return {"ok": True, "trace_id": tid, "task": _task_payload(task)}


@router.get("/agents/{agent_id}/tasks")
async def list_agent_tasks(
    agent_id: str,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    parsed_status: TaskStatus | None = None
    if status:
        try:
            parsed_status = TaskStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from exc
    items = await store.list_tasks(agent_id=agent_id, status=parsed_status, limit=limit)
    return {
        "ok": True,
        "count": len(items),
        "tasks": [_task_payload(t) for t in items],
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    store = get_agent_store()
    task = await store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"ok": True, "task": _task_payload(task)}


@router.post("/tasks/{task_id}/run")
async def execute_task(
    task_id: str,
    body: RunTaskRequest = Body(default=RunTaskRequest()),
) -> dict[str, Any]:
    store = get_agent_store()
    task = await store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.status not in {TaskStatus.PENDING, TaskStatus.FAILED}:
        raise HTTPException(
            status_code=409,
            detail=f"task_not_runnable (status={task.status.value})",
        )
    if body.council_mode not in {"single", "dual_vote", "n_vote"}:
        raise HTTPException(status_code=400, detail="invalid council_mode")
    final = await run_task(store=store, task_id=task_id, council_mode=body.council_mode)
    if final is None:
        raise HTTPException(status_code=500, detail="task_disappeared")
    return {"ok": True, "task": _task_payload(final)}


@router.post("/agents/{agent_id}/autopilot")
async def set_autopilot(
    agent_id: str,
    enabled: bool = True,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Toggle the autopilot flag.

    With autopilot on, the background loop in ``backend.core.agents.
    autopilot`` picks up the agent's pending tasks and runs them
    every ``TARS_AGENTS_AUTOPILOT_INTERVAL_S`` seconds.
    """

    import json

    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    try:
        meta = json.loads(agent.metadata_json or "{}")
    except json.JSONDecodeError:
        meta = {}
    meta["autopilot"] = bool(enabled)
    updated = await store.patch_agent(agent_id, {"metadata": meta})
    if updated is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "agent.autopilot.toggled",
            {"agent_id": agent_id, "enabled": bool(enabled)},
        )
        return {
            "ok": True,
            "trace_id": tid,
            "agent": updated.to_dict(),
            "autopilot": bool(enabled),
        }


@router.post("/agents/autopilot/tick")
async def autopilot_tick() -> dict[str, Any]:
    """Force one autopilot tick now.

    Mostly useful for tests + manual debugging — the background loop
    fires the same ``tick_once`` every interval.
    """

    out = await _autopilot_tick_once()
    return {"ok": True, **out}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_agent_store()
    task = await store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.status in {
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    }:
        raise HTTPException(
            status_code=409, detail=f"task_terminal (status={task.status.value})"
        )
    try:
        cancelled = await store.patch_task(task_id, {"status": TaskStatus.CANCELLED.value})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if cancelled is None:
        raise HTTPException(status_code=404, detail="task_not_found")

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "agent.task.cancelled",
            {"task_id": task_id, "agent_id": cancelled.agent_id},
        )
        return {"ok": True, "trace_id": tid, "task": _task_payload(cancelled)}
