"""HTTP surface for the scheduler subsystem (Wave 97).

Endpoints:

- ``GET    /api/scheduler/schedules``                       list all
- ``POST   /api/scheduler/schedules``                       create
- ``GET    /api/scheduler/schedules/{id}``                  show one
- ``PATCH  /api/scheduler/schedules/{id}``                  update
- ``DELETE /api/scheduler/schedules/{id}``                  remove
- ``POST   /api/scheduler/schedules/{id}/run-now``          fire immediately
- ``GET    /api/scheduler/schedules/{id}/history?limit=20`` recent runs
- ``POST   /api/scheduler/validate-cron``                   validate + preview

The validate-cron endpoint also returns the next 5 firing times for
the supplied expression so the FE can render a "next runs" preview
without round-trips per row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.scheduler import (
    Schedule,
    get_runner,
    get_store,
    next_after,
    validate,
)
from backend.core.scheduler.cron import CronParseError


router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


# ---------- helpers --------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="scheduler_store_disabled")


def _schedule_to_dict(s: Schedule) -> dict[str, Any]:
    return s.to_dict()


# ---------- CRUD -----------------------------------------------------------


@router.get("/schedules")
async def list_schedules(
    playbook_id: str | None = Query(default=None),
    only_enabled: bool = Query(default=False),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    schedules = await store.list_schedules(
        playbook_id=playbook_id, only_enabled=only_enabled
    )
    return {
        "ok": True,
        "count": len(schedules),
        "schedules": [_schedule_to_dict(s) for s in schedules],
    }


@router.post("/schedules")
async def create_schedule(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    _ensure_enabled()
    playbook_id = str(payload.get("playbook_id") or "").strip()
    cron_expression = str(payload.get("cron_expression") or payload.get("cron") or "").strip()
    if not playbook_id:
        raise HTTPException(status_code=400, detail="playbook_id_required")
    if not cron_expression:
        raise HTTPException(status_code=400, detail="cron_expression_required")
    args = payload.get("args") or {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args_must_be_object")
    store = get_store()
    try:
        sched = await store.create_schedule(
            playbook_id=playbook_id,
            cron_expression=cron_expression,
            timezone=str(payload.get("timezone") or "UTC"),
            args=args,
            max_concurrent=int(payload.get("max_concurrent") or 1),
            enabled=bool(payload.get("enabled", True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "schedule": _schedule_to_dict(sched)}


@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str) -> dict[str, Any]:
    _ensure_enabled()
    sched = await get_store().get_schedule(schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    return {"ok": True, "schedule": _schedule_to_dict(sched)}


@router.patch("/schedules/{schedule_id}")
async def patch_schedule(
    schedule_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    _ensure_enabled()
    # Whitelist fields the client may patch.
    updates: dict[str, Any] = {}
    for key in (
        "cron_expression",
        "cron",
        "timezone",
        "enabled",
        "args",
        "max_concurrent",
    ):
        if key in payload:
            target = "cron_expression" if key == "cron" else key
            updates[target] = payload[key]
    try:
        sched = await get_store().update_schedule(schedule_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    return {"ok": True, "schedule": _schedule_to_dict(sched)}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str) -> dict[str, Any]:
    _ensure_enabled()
    deleted = await get_store().delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    return {"ok": True, "deleted": True}


# ---------- run-now + history ---------------------------------------------


@router.post("/schedules/{schedule_id}/run-now")
async def run_now(schedule_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    sched = await store.get_schedule(schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    runner = get_runner()
    # update_next=False so manual runs don't shift the cadence.
    out = await runner.fire_schedule(sched, update_next=False)
    return {"ok": True, "schedule_id": schedule_id, "result": out}


@router.get("/schedules/{schedule_id}/history")
async def history(
    schedule_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    sched = await store.get_schedule(schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    runs = await store.history(schedule_id, limit=limit)
    return {
        "ok": True,
        "schedule_id": schedule_id,
        "count": len(runs),
        "runs": [r.to_dict() for r in runs],
    }


# ---------- cron validation -----------------------------------------------


@router.post("/validate-cron")
async def validate_cron(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Validate a cron expression and preview the next 5 firing times.

    Body:

    - ``expression`` (required) — the cron expression to test.
    - ``timezone`` (optional, default ``UTC``) — TZ database name.
    """

    expression = str(payload.get("expression") or "").strip()
    tz_name = str(payload.get("timezone") or "UTC").strip() or "UTC"
    if not expression:
        return {"valid": False, "error": "expression_required"}
    if not validate(expression):
        return {"valid": False, "error": "invalid_cron_expression"}
    # Compute next 5 fires walking forward.
    next_runs: list[str] = []
    cursor = datetime.now(timezone.utc)
    try:
        for _ in range(5):
            nxt = next_after(expression, cursor, tz=tz_name)
            next_runs.append(nxt.isoformat())
            cursor = nxt
    except CronParseError as exc:
        return {"valid": False, "error": str(exc)}
    return {
        "valid": True,
        "expression": expression,
        "timezone": tz_name,
        "next_5_runs": next_runs,
    }
