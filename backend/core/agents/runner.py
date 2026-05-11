"""Run a queued task by routing it through the council orchestrator.

The runner is intentionally thin: it picks the agent's domain pack
persona, builds a context that includes the agent's wallet binding +
optional system-prompt override, then asks the council to deliberate.
The orchestrator already emits ``council.deliberation.{started,
completed}``; the runner adds two ``agent.task.*`` events so meeet
ingest can build per-agent timelines.

Destructive work that an agent decides to do still flows through the
existing domain action HTTP path (or the policy gate inside an action
handler) — this runner is "thinking only".
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from backend.core.council.orchestrator import CouncilOrchestrator
from backend.core.domains.registry import get_pack
from backend.core.meeet import get_client, trace_scope

from .models import Task, TaskStatus
from .store import AgentStore

# Wave 129 — best-effort cowork fan-out. Import is wrapped in try so a
# stripped-down deployment that disables cowork (TARS_COWORK_STORE=
# disabled) doesn't fail to import the runner. Same defensive pattern
# as the W90 webhook emit.
try:
    from backend.core.cowork import emit_agent_frame as _cowork_emit
except Exception:  # noqa: BLE001 — defensive: never break runner import

    async def _cowork_emit(  # type: ignore[no-redef]
        session_id: str,
        frame_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        return 0


def _build_context(*, agent_id: str, agent_name: str, wallet_address: str | None,
                   pack_slug: str, system_prompt: str | None,
                   metadata: Mapping[str, Any]) -> dict[str, Any]:
    pack = get_pack(pack_slug)
    base_prompt = system_prompt
    if not base_prompt and pack is not None:
        base_prompt = pack.system_prompt()
    return {
        "topic": metadata.get("topic", "agent_task"),
        "agent_id": agent_id,
        "agent_name": agent_name,
        "wallet_address": wallet_address,
        "pack_slug": pack_slug,
        "system_prompt": base_prompt,
        **{k: v for k, v in metadata.items() if k != "topic"},
    }


async def run_task(
    *,
    store: AgentStore,
    task_id: str,
    council: CouncilOrchestrator | None = None,
    council_mode: str = "dual_vote",
) -> Task | None:
    """Execute the task.

    Returns the final Task or None if the task does not exist. Always
    transitions through ``running`` and lands on ``done`` or
    ``failed``; emits ``agent.task.started`` + ``agent.task.completed``
    with `trace_id` so the meeet replay timeline is per-task accurate.
    """

    task = await store.get_task(task_id)
    if task is None:
        return None
    if task.status not in {TaskStatus.PENDING, TaskStatus.FAILED}:
        return task

    agent = await store.get_agent(task.agent_id)
    if agent is None:
        await store.patch_task(task_id, {"status": TaskStatus.FAILED.value, "error": "agent_not_found"})
        return await store.get_task(task_id)

    # PENDING/FAILED → RUNNING
    await store.patch_task(task_id, {"status": TaskStatus.RUNNING.value, "error": None})

    client = get_client()
    metadata: dict[str, Any] = {}
    try:
        metadata = json.loads(task.metadata_json or "{}")
    except json.JSONDecodeError:
        metadata = {}

    council = council or CouncilOrchestrator()

    # Wave 129 — opt-in cowork fan-out. Callers attach
    # ``cowork_session_id`` to the task metadata when they want this
    # task's lifecycle to stream onto a shared cowork session.
    cowork_session_id = metadata.get("cowork_session_id") if isinstance(metadata, dict) else None
    cowork_session_id = str(cowork_session_id) if cowork_session_id else None

    with trace_scope() as tid:
        await client.emit(
            "agent.task.started",
            {
                "task_id": task.id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "pack_slug": agent.pack_slug,
            },
        )
        if cowork_session_id:
            await _cowork_emit(
                cowork_session_id,
                "task.started",
                {
                    "task_id": task.id,
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "label": f"{agent.name} started a task",
                },
            )
        try:
            ctx = _build_context(
                agent_id=agent.id,
                agent_name=agent.name,
                wallet_address=agent.wallet_address,
                pack_slug=agent.pack_slug,
                system_prompt=agent.system_prompt,
                metadata=metadata,
            )
            deliberation = await council.deliberate(
                prompt=task.prompt,
                context=ctx,
                mode=council_mode,
            )
            payload = deliberation.to_dict()
            await store.patch_task(
                task_id,
                {
                    "status": TaskStatus.DONE.value,
                    "result": payload,
                    "trace_id": tid,
                },
            )
            await client.emit(
                "agent.task.completed",
                {
                    "task_id": task.id,
                    "agent_id": agent.id,
                    "chosen": payload.get("chosen"),
                    "agreement": payload.get("agreement"),
                    "cost_usd": payload.get("cost_usd"),
                },
            )
            if cowork_session_id:
                await _cowork_emit(
                    cowork_session_id,
                    "task.completed",
                    {
                        "task_id": task.id,
                        "agent_id": agent.id,
                        "label": f"{agent.name} finished — {str(payload.get('chosen', ''))[:80]}",
                        "agreement": payload.get("agreement"),
                    },
                )
        except Exception as exc:  # never crash the host
            await store.patch_task(
                task_id,
                {
                    "status": TaskStatus.FAILED.value,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace_id": tid,
                },
            )
            await client.emit(
                "agent.task.failed",
                {
                    "task_id": task.id,
                    "agent_id": agent.id,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            if cowork_session_id:
                await _cowork_emit(
                    cowork_session_id,
                    "task.failed",
                    {
                        "task_id": task.id,
                        "agent_id": agent.id,
                        "label": f"{agent.name} errored — {type(exc).__name__}",
                    },
                )

    return await store.get_task(task_id)
