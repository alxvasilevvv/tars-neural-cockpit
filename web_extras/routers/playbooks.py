"""HTTP surface over the playbook runner.

- ``GET  /api/playbooks``               — list available playbooks.
- ``GET  /api/playbooks/{id}``          — show a single playbook.
- ``POST /api/playbooks/{id}/run``      — run it. Body:
       { "context": {...}, "mode": "confirm|autopilot|dry_run" }
   Header ``x-tars-policy-mode`` overrides the body field if both
   are provided. Default = confirm.
- ``POST /api/playbooks/_reload``       — re-scan the playbooks dir.
- ``POST /api/playbooks/_validate``     — strict-validate a JSON
       playbook payload (or a known ``id``) before authoring,
       returning structured errors / warnings.
- ``GET  /api/playbooks/_validate_all`` — validate every playbook
       on disk; useful as a CI gate so a malformed file never
       reaches the runner.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from backend.core.meeet import trace_scope
from backend.core.playbooks import (
    get_playbook,
    list_playbooks,
    reset_loader_cache,
    run_playbook,
    validate_payload,
)
from backend.core.policy import PolicyMode, resolve_mode

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@router.get("")
async def list_all() -> dict[str, Any]:
    items = list(list_playbooks())
    return {
        "ok": True,
        "count": len(items),
        "playbooks": [pb.to_dict() for pb in items],
    }


# IMPORTANT: register all static `_*` routes BEFORE any
# `/{playbook_id}` dynamic route so FastAPI's path matcher prefers
# the literal path. The previous layout shadowed `_validate_all`
# behind the dynamic `get_one` handler.


@router.post("/_reload")
async def reload_playbooks() -> dict[str, Any]:
    reset_loader_cache()
    items = list(list_playbooks(refresh=True))
    return {"ok": True, "count": len(items)}


@router.post("/_validate")
async def validate_endpoint(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Validate a playbook JSON payload without loading it.

    Body shapes (mutually exclusive):

    - ``{"playbook": <playbook-json>}`` — validate the literal
      payload.
    - ``{"id": "<playbook-id>"}`` — re-validate a known playbook
      from disk (helpful when a fresh file landed and the cache
      hasn't been reloaded yet).
    """

    pb_payload = payload.get("playbook")
    pb_id = payload.get("id")
    if pb_payload is None and not pb_id:
        raise HTTPException(
            status_code=400, detail="playbook_or_id_required"
        )
    if pb_payload is not None and pb_id:
        raise HTTPException(
            status_code=400, detail="playbook_and_id_exclusive"
        )

    if pb_id:
        target = get_playbook(str(pb_id), refresh=True)
        if target is None:
            raise HTTPException(status_code=404, detail="playbook_not_found")
        pb_payload = target.to_dict()

    result = validate_payload(pb_payload)
    return {**result.to_dict(), "id": pb_id or pb_payload.get("id")}


@router.get("/_validate_all")
async def validate_all_endpoint() -> dict[str, Any]:
    """Run the strict validator over every playbook on disk.

    Returns one entry per playbook with ``id``, ``ok``, error and
    warning lists. Operators can wire this into CI as a gate.
    """

    items = list(list_playbooks(refresh=True))
    out: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    for pb in items:
        result = validate_payload(pb.to_dict())
        out.append({"id": pb.id, **result.to_dict()})
        error_count += len(result.errors)
        warning_count += len(result.warnings)
    return {
        "ok": all(p["ok"] for p in out),
        "playbook_count": len(out),
        "error_count": error_count,
        "warning_count": warning_count,
        "playbooks": out,
    }


@router.get("/{playbook_id}")
async def get_one(playbook_id: str) -> dict[str, Any]:
    pb = get_playbook(playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="playbook_not_found")
    return {"ok": True, "playbook": pb.to_dict()}


@router.post("/{playbook_id}/run")
async def run(
    playbook_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_policy_mode: str | None = Header(default=None),
) -> dict[str, Any]:
    pb = get_playbook(playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="playbook_not_found")
    context = payload.get("context") or {}
    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context_must_be_object")
    mode = resolve_mode(
        header=x_tars_policy_mode,
        request_arg=str(payload.get("mode") or "") or None,
    )
    with trace_scope(parent=x_meeet_trace_id):
        return await run_playbook(pb, context=context, mode=mode)


# ---------- Wave 97 — scheduler convenience endpoints --------------------
#
# These delegate to the scheduler module so the FE doesn't need to
# hop between two REST namespaces just to wire a cron up to a known
# playbook id. The scheduler-side endpoints under ``/api/scheduler``
# remain the source of truth.


@router.post("/{playbook_id}/schedule")
async def schedule_playbook(
    playbook_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Create a schedule for ``playbook_id``.

    Body: ``{cron, timezone?, args?, max_concurrent?, enabled?}``.
    """

    pb = get_playbook(playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="playbook_not_found")
    from backend.core.scheduler import get_store as _get_sched_store

    store = _get_sched_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="scheduler_store_disabled")
    cron = str(payload.get("cron") or payload.get("cron_expression") or "").strip()
    if not cron:
        raise HTTPException(status_code=400, detail="cron_required")
    args = payload.get("args") or {}
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args_must_be_object")
    try:
        sched = await store.create_schedule(
            playbook_id=playbook_id,
            cron_expression=cron,
            timezone=str(payload.get("timezone") or "UTC"),
            args=args,
            max_concurrent=int(payload.get("max_concurrent") or 1),
            enabled=bool(payload.get("enabled", True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "schedule": sched.to_dict()}


@router.get("/{playbook_id}/schedules")
async def list_schedules_for_playbook(playbook_id: str) -> dict[str, Any]:
    """List every schedule attached to ``playbook_id``."""

    pb = get_playbook(playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="playbook_not_found")
    from backend.core.scheduler import get_store as _get_sched_store

    store = _get_sched_store()
    if not store.enabled:
        return {"ok": True, "playbook_id": playbook_id, "count": 0, "schedules": []}
    schedules = await store.list_schedules(playbook_id=playbook_id)
    return {
        "ok": True,
        "playbook_id": playbook_id,
        "count": len(schedules),
        "schedules": [s.to_dict() for s in schedules],
    }
