"""Autopilot loop for the multi-agent surface.

Runs as a background task in :mod:`web_extras.app`. Every tick:

1. Lists agents with ``status=active`` and ``metadata.autopilot=True``.
2. For each, pops the oldest ``pending`` task and runs it through the
   council orchestrator.
3. Sleeps ``TARS_AGENTS_AUTOPILOT_INTERVAL_S`` (default 30s) before
   the next tick. Setting the interval to ``0`` disables the loop —
   manual ``POST /api/tasks/{id}/run`` still works.

Crash isolation: every per-agent run is wrapped in a try / except.
A single broken task can never starve the loop or kill the host.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from backend.core.meeet import get_client, trace_scope

from .models import AgentStatus, TaskStatus
from .runner import run_task
from .store import AgentStore, get_agent_store


log = logging.getLogger("tars.agents.autopilot")


def _interval_s() -> float:
    raw = os.getenv("TARS_AGENTS_AUTOPILOT_INTERVAL_S")
    if raw is None:
        return 30.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 30.0


def _is_autopilot(metadata_json: str | None) -> bool:
    if not metadata_json:
        return False
    try:
        meta = json.loads(metadata_json)
    except json.JSONDecodeError:
        return False
    return bool(meta.get("autopilot"))


async def tick_once(store: AgentStore | None = None) -> dict[str, Any]:
    """Run one autopilot tick.

    Returns a small dict with `agents_visited`, `tasks_run`, `tasks_failed`.
    Useful for HTTP introspection (`/api/agents/autopilot/status`) and
    integration tests that don't want to wait for the loop.
    """

    s = store or get_agent_store()
    visited = 0
    ran = 0
    failed = 0
    agents = await s.list_agents()
    client = get_client()
    for agent in agents:
        if agent.status != AgentStatus.ACTIVE:
            continue
        if not _is_autopilot(agent.metadata_json):
            continue
        visited += 1
        try:
            tasks = await s.list_tasks(
                agent_id=agent.id, status=TaskStatus.PENDING, limit=1
            )
        except Exception as exc:
            log.warning("autopilot list_tasks failed for %s: %s", agent.id, exc)
            continue
        if not tasks:
            continue
        target = tasks[0]
        with trace_scope() as tid:
            await client.emit(
                "agent.autopilot.dispatch",
                {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "task_id": target.id,
                },
            )
            try:
                final = await run_task(store=s, task_id=target.id)
                if final and final.status == TaskStatus.DONE:
                    ran += 1
                else:
                    failed += 1
            except Exception as exc:  # never crash the loop
                failed += 1
                log.exception("autopilot run failed for task %s: %s", target.id, exc)
                await client.emit(
                    "agent.autopilot.failed",
                    {"agent_id": agent.id, "task_id": target.id, "error": str(exc)},
                )
    return {
        "agents_visited": visited,
        "tasks_run": ran,
        "tasks_failed": failed,
    }


async def autopilot_loop() -> None:
    """Background coroutine; spawned from the FastAPI lifespan."""

    interval = _interval_s()
    if interval <= 0:
        log.info("agents autopilot disabled (interval=0)")
        return
    log.info("agents autopilot active: interval_s=%.1f", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            out = await tick_once()
            if out["agents_visited"] or out["tasks_run"] or out["tasks_failed"]:
                log.info(
                    "agents autopilot tick: visited=%s ran=%s failed=%s",
                    out["agents_visited"],
                    out["tasks_run"],
                    out["tasks_failed"],
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never propagate
            log.warning("agents autopilot loop tick failed: %s", exc)
