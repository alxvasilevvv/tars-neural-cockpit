"""HTTP surface for the planner.

Endpoints (v1 — synthesis + persistence only; the runner ships in a
follow-up PR):

- ``POST /api/planner/plan`` — synthesize a Plan from a goal + persist
  it. Body: ``{goal, pinned_pack?, thread_id?}``. Auto-discovers
  registered playbooks and pack actions; consumes
  ``x-tars-thread-id`` if the body field is omitted.
- ``GET  /api/planner/{plan_id}`` — read one Plan by id.
- ``GET  /api/planner`` — list Plans, newest first; filter by
  ``status`` and / or ``thread_id`` query params.
- ``GET  /api/planner/_stats`` — totals + by_status counts.
- ``POST /api/planner/{plan_id}/status`` — manually transition the
  Plan's status (``approved`` / ``rejected``); the runner will own
  the ``running``/``completed``/``aborted`` transitions in the
  follow-up PR.
- ``DELETE /api/planner/{plan_id}`` — drop a plan (operator can
  prune a no-longer-relevant proposal).

Every state-changing endpoint emits a ``planner.*`` meeet event so
the cockpit gold-pill audit lane sees the plan lifecycle.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs
from backend.core.meeet import get_client, thread_id_scope, trace_scope
from backend.core.planner import (
    Plan,
    PlannerError,
    PlannerSynthesisRequest,
    PlanStatus,
    PlanStep,
    get_planner_store,
    synthesize_plan,
)
from backend.core.playbooks import list_playbooks


router = APIRouter(prefix="/api/planner", tags=["planner"])


_SNAPSHOT_KEYWORDS = ("snapshot", "summarize", "list", "brief", "status")


def _is_snapshot_action(action_id: str, destructive: bool) -> bool:
    """Heuristic: a non-destructive action whose id sounds like a
    snapshot is a safe default for the planner's pack-fallback."""

    if destructive:
        return False
    aid = (action_id or "").lower()
    return any(kw in aid for kw in _SNAPSHOT_KEYWORDS)


def _enumerate_actions() -> tuple[tuple[str, str, bool, bool], ...]:
    """Build the ``(slug, action_id, destructive, is_snapshot)`` tuple
    list the synthesizer expects."""

    out: list[tuple[str, str, bool, bool]] = []
    for pack in all_packs():
        slug = pack.manifest.slug
        for spec in pack.actions():
            out.append(
                (
                    slug,
                    spec.id,
                    bool(getattr(spec, "destructive", False)),
                    _is_snapshot_action(
                        spec.id, bool(getattr(spec, "destructive", False))
                    ),
                )
            )
    return tuple(out)


@router.post("/plan")
async def create_plan(
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
) -> dict[str, Any]:
    goal = str(payload.get("goal") or "").strip()
    pinned_pack = payload.get("pinned_pack")
    thread_id = (
        str(payload.get("thread_id") or "").strip()
        or (x_tars_thread_id or "").strip()
        or None
    )

    if not goal:
        raise HTTPException(status_code=400, detail="goal_required")

    req = PlannerSynthesisRequest(
        goal=goal,
        thread_id=thread_id,
        pinned_pack=str(pinned_pack).strip() if pinned_pack else None,
        available_playbooks=tuple(list_playbooks()),
        available_actions=_enumerate_actions(),
    )

    with thread_id_scope(thread_id), trace_scope(parent=x_meeet_trace_id) as tid:
        try:
            plan = synthesize_plan(req)
        except PlannerError as exc:
            await get_client().emit(
                "planner.synthesis.failed",
                {
                    "goal": goal,
                    "reason": exc.reason,
                    "pinned_pack": req.pinned_pack,
                },
            )
            raise HTTPException(
                status_code=400,
                detail={"reason": exc.reason, "message": str(exc)},
            ) from exc

        # Persist with the live trace id so downstream events correlate.
        plan = Plan(
            id=plan.id,
            goal=plan.goal,
            steps=plan.steps,
            status=plan.status,
            rationale=plan.rationale,
            model=plan.model,
            pack_slug=plan.pack_slug,
            playbook_id=plan.playbook_id,
            thread_id=plan.thread_id,
            trace_id=tid,
            estimated_cost_usd=plan.estimated_cost_usd,
        )
        stored = await get_planner_store().insert(plan)
        await get_client().emit(
            "planner.synthesis.completed",
            {
                "plan_id": stored.id,
                "goal": stored.goal,
                "model": stored.model,
                "pack_slug": stored.pack_slug,
                "playbook_id": stored.playbook_id,
                "step_count": len(stored.steps),
                "destructive_step_count": sum(
                    1 for s in stored.steps if s.destructive
                ),
            },
        )
        return {"ok": True, "plan": stored.to_dict()}


@router.get("/_stats")
async def stats() -> dict[str, Any]:
    return {"ok": True, **await get_planner_store().stats()}


@router.get("")
async def list_plans(
    status: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
) -> dict[str, Any]:
    status_enum: PlanStatus | None = None
    if status is not None:
        try:
            status_enum = PlanStatus(status.lower())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="unknown_status") from exc
    plans = await get_planner_store().list(
        status=status_enum,
        thread_id=thread_id or None,
        limit=limit,
    )
    return {
        "ok": True,
        "count": len(plans),
        "plans": [p.to_dict() for p in plans],
    }


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict[str, Any]:
    plan = await get_planner_store().get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")
    return {"ok": True, "plan": plan.to_dict()}


_OPERATOR_TRANSITIONS = {
    PlanStatus.APPROVED.value,
    PlanStatus.REJECTED.value,
}


@router.post("/{plan_id}/status")
async def set_plan_status(
    plan_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    desired = str(payload.get("status") or "").strip().lower()
    if desired not in _OPERATOR_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid_status",
                "allowed": sorted(_OPERATOR_TRANSITIONS),
            },
        )
    store = get_planner_store()
    existing = await store.get(plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="plan_not_found")
    if existing.status.is_terminal():
        raise HTTPException(
            status_code=409,
            detail=f"plan_already_{existing.status.value}",
        )
    new_status = PlanStatus(desired)
    updated = await store.set_status(plan_id, new_status)
    if updated is None:
        raise HTTPException(status_code=500, detail="status_update_failed")

    with thread_id_scope(updated.thread_id), trace_scope(
        parent=x_meeet_trace_id
    ):
        await get_client().emit(
            f"planner.{new_status.value}",
            {
                "plan_id": plan_id,
                "model": updated.model,
                "pack_slug": updated.pack_slug,
                "playbook_id": updated.playbook_id,
                "step_count": len(updated.steps),
            },
        )
    return {"ok": True, "plan": updated.to_dict()}


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str) -> dict[str, Any]:
    store = get_planner_store()
    existing = await store.get(plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="plan_not_found")
    deleted = await store.delete(plan_id)
    with thread_id_scope(existing.thread_id), trace_scope():
        await get_client().emit(
            "planner.deleted",
            {
                "plan_id": plan_id,
                "model": existing.model,
                "pack_slug": existing.pack_slug,
                "status_at_delete": existing.status.value,
            },
        )
    return {"ok": deleted, "plan_id": plan_id}
