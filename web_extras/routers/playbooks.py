"""HTTP surface over the playbook runner.

- ``GET  /api/playbooks``               — list available playbooks.
- ``GET  /api/playbooks/{id}``          — show a single playbook.
- ``POST /api/playbooks/{id}/run``      — run it. Body:
       { "context": {...}, "mode": "confirm|autopilot|dry_run" }
   Header ``x-tars-policy-mode`` overrides the body field if both
   are provided. Default = confirm.
- ``POST /api/playbooks/_reload``       — re-scan the playbooks dir.
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


@router.get("/{playbook_id}")
async def get_one(playbook_id: str) -> dict[str, Any]:
    pb = get_playbook(playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="playbook_not_found")
    return {"ok": True, "playbook": pb.to_dict()}


@router.post("/_reload")
async def reload_playbooks() -> dict[str, Any]:
    reset_loader_cache()
    items = list(list_playbooks(refresh=True))
    return {"ok": True, "count": len(items)}


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
