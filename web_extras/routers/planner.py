"""HTTP surface for the planner.

Endpoints:

- ``POST /api/planner/plan`` — synthesize a Plan from a goal + persist
  it. Body: ``{goal, pinned_pack?, thread_id?}``. Auto-discovers
  registered playbooks and pack actions; consumes
  ``x-tars-thread-id`` if the body field is omitted.
- ``GET  /api/planner/{plan_id}`` — read one Plan by id.
- ``GET  /api/planner`` — list Plans, newest first; filter by
  ``status`` and / or ``thread_id`` query params.
- ``GET  /api/planner/_stats`` — totals + by_status counts.
- ``POST /api/planner/{plan_id}/status`` — manually transition the
  Plan's status (``approved`` / ``rejected``); ``running`` /
  ``completed`` / ``aborted`` are runner-owned and refused here.
- ``POST /api/planner/{plan_id}/run`` — execute an *approved* plan
  through the policy gate. Body may include ``mode`` (one of
  ``autopilot`` / ``confirm`` / ``dry_run``); also resolved from
  the ``x-tars-policy-mode`` header. Returns the per-step result
  envelope, identical in shape to the playbook runner output.
- ``POST /api/planner/{plan_id}/abort`` — cooperative abort of a
  currently running plan. Sets the per-plan abort flag; the runner
  stops between groups and persists ``status=aborted``.
- ``DELETE /api/planner/{plan_id}`` — drop a plan (operator can
  prune a no-longer-relevant proposal).
- ``GET  /api/planner/events`` — Server-Sent Events stream of the
  ``plan.*`` event family (and ``planner.{approved,rejected}`` /
  ``planner.synthesis.{completed,failed}``). Optional query
  params: ``plan_id`` and ``thread_id`` (filter by exact match
  on the event payload), ``after_id`` (cursor; the stream only
  emits events with a row id strictly greater than this — pass
  the last id you saw to resume), ``poll_interval_s`` (default
  ``1.0``), ``max_duration_s`` (default ``120``). Each frame is
  JSON-encoded and includes the meeet store's row ``id`` so the
  cockpit can persist the cursor across reconnects. Also honours
  the standard ``Last-Event-ID`` HTTP header so a vanilla
  ``EventSource`` reconnect picks up where it left off without
  any cockpit-specific glue (header value wins over the
  ``after_id`` query param when both are supplied).
- ``GET  /api/planner/{plan_id}/runs`` — reconstructed past
  executions of one plan. Walks the meeet store and groups
  ``plan.run.started`` → ``plan.completed`` / ``plan.aborted``
  windows; each entry includes start/end timestamps, status,
  per-step results (id, action, ok, blocked, skipped, took_ms,
  error) and aggregate counters. Newest run first. Optional
  ``limit`` query param caps the per-event-kind fetch (default
  ``1000``).
- ``GET  /api/planner/{plan_id}/full`` — one-shot aggregate
  endpoint for the cockpit's plan-detail drawer. Returns the
  plan envelope + reconstructed runs (newest-first, with
  in_flight count) + a ``usage_lifetime`` block summing every
  run's per-run rollup. ``cost_usd`` is ``null`` when no run
  had a priced model so the cockpit can render "n/a" instead
  of misleading "$0.00". Same ``limit`` semantics as ``/runs``.
- ``POST /api/planner/{plan_id}/clone`` — snapshot the plan as
  a fresh ``proposed`` plan. Useful for "rerun" without
  mutating the original's terminal status. Body may include
  ``thread_id`` (rebind to a different chat) and
  ``goal_override``. Emits ``planner.cloned`` so the cockpit
  audit lane sees the relationship.
- ``POST /api/planner/{plan_id}/rerun`` — one-shot rerun:
  clone → approve → run, all in a single round-trip and inside
  one trace scope so the events stitch together. Body /
  header support mirrors ``/clone`` plus optional ``mode``
  (or ``x-tars-policy-mode`` header) to override the policy
  gate for the run portion. Returns the new plan, the run
  result envelope, and a ``source_plan_id`` pointer back to
  the original. ``planner.cloned`` is emitted with
  ``auto_approved=true`` and ``auto_run=true``.

Every state-changing endpoint emits a ``planner.*`` meeet event so
the cockpit gold-pill audit lane sees the plan lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs
from backend.core.meeet import (
    get_client,
    get_store as get_meeet_store,
    thread_id_scope,
    trace_scope,
)
from backend.core.planner import (
    Plan,
    PlannerError,
    PlannerSynthesisRequest,
    PlanRunError,
    PlanRunner,
    PlanStatus,
    PlanStep,
    aggregate_usage_lifetime,
    get_planner_store,
    get_run_registry,
    reconstruct_runs_async,
    synthesize_plan,
)
from backend.core.playbooks import list_playbooks
from backend.core.policy import PolicyMode, resolve_mode


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
        synth_payload = {
            "plan_id": stored.id,
            "goal": stored.goal,
            "model": stored.model,
            "pack_slug": stored.pack_slug,
            "playbook_id": stored.playbook_id,
            "step_count": len(stored.steps),
            "destructive_step_count": sum(
                1 for s in stored.steps if s.destructive
            ),
        }
        await get_client().emit("planner.synthesis.completed", synth_payload)
        # Spec event name from L6.2 — keeps cockpit subscribers
        # decoupled from the synthesizer's internal naming.
        await get_client().emit("plan.proposed", synth_payload)
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


def _resolve_after_id(
    *, query: int, header: str | None
) -> tuple[int, str]:
    """Pick the effective ``after_id`` cursor.

    The native ``EventSource`` API resumes by sending the last
    successfully-received ``id:`` line back as a
    ``Last-Event-ID`` header. We honour that here. When both the
    header and the ``after_id`` query param are supplied, the
    header wins — that's the spec-mandated behaviour for SSE
    reconnects, and it lets the cockpit pass an initial cursor
    via query while still benefiting from automatic resume.

    Returns a tuple of ``(cursor, source)`` where ``source`` is
    one of ``"query" | "header" | "default"`` so the ``hello``
    frame can advertise where the cursor came from.
    """

    if header is not None:
        try:
            parsed = int(str(header).strip())
        except (TypeError, ValueError):
            parsed = -1
        if parsed >= 0:
            return parsed, "header"
    if query > 0:
        return query, "query"
    return 0, "default"


@router.get("/events")
async def planner_events_stream(
    plan_id: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    after_id: int = Query(default=0, ge=0),
    poll_interval_s: float = Query(default=1.0, gt=0.0, le=10.0),
    max_duration_s: float = Query(default=120.0, gt=0.0, le=900.0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE feed of the ``plan.*`` event family.

    Declared before ``/{plan_id}`` so Starlette doesn't try to
    parse ``events`` as a plan id. See the module docstring for
    the contract.
    """

    cursor, cursor_source = _resolve_after_id(
        query=after_id, header=last_event_id
    )

    async def gen() -> AsyncIterator[str]:
        with trace_scope():
            try:
                async for frame in _planner_sse_producer(
                    plan_id=plan_id,
                    thread_id=thread_id,
                    after_id=cursor,
                    poll_interval_s=poll_interval_s,
                    max_duration_s=max_duration_s,
                    cursor_source=cursor_source,
                ):
                    yield frame
            except asyncio.CancelledError:
                yield _sse_frame(
                    "bye",
                    {"reason": "client_disconnect"},
                )
                raise

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict[str, Any]:
    plan = await get_planner_store().get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")
    return {"ok": True, "plan": plan.to_dict()}


@router.get("/{plan_id}/runs")
async def list_plan_runs(
    plan_id: str,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    """List past executions of one plan.

    Reconstructed from the meeet event store — no parallel
    "runs" table — so the data is always consistent with the
    timeline / SSE feed / gold-pill audit lane. Returns runs in
    newest-first order. The plan itself must exist; an unknown
    ``plan_id`` returns 404 even if there happen to be stale
    events lying around for it (defensive: keeps the cockpit
    from rendering ghosts of pruned plans).
    """

    plan = await get_planner_store().get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    runs = await reconstruct_runs_async(plan_id, limit=limit)
    in_flight = sum(1 for r in runs if r.status == "running")
    return {
        "ok": True,
        "plan_id": plan_id,
        "count": len(runs),
        "in_flight": in_flight,
        "runs": [r.to_dict() for r in runs],
    }


@router.get("/{plan_id}/full")
async def get_plan_full(
    plan_id: str,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    """One-shot aggregate: plan + reconstructed runs + lifetime usage.

    Single round-trip the cockpit's plan-detail drawer can hit on
    open instead of fanning out across ``GET /{plan_id}``,
    ``GET /{plan_id}/runs``, and a separate usage rollup query.

    Envelope:

    .. code-block:: json

       {
         "ok": true,
         "plan_id": "pln_…",
         "plan": {…},                # same shape as GET /{plan_id}
         "runs": {
           "count": N,
           "in_flight": M,
           "items": [PlanRun.to_dict(), …]   # newest-first
         },
         "usage_lifetime": {
           "calls": …,
           "tokens_in": …,
           "tokens_out": …,
           "cost_usd": float|null,    # null when no priced run fired
           "latency_ms_total": …,
           "has_priced_models": bool, # any run had a priced model
           "runs_aggregated": K       # how many runs contributed
         }
       }

    The lifetime block sums every reconstructed run's per-run
    rollup so the drawer can show "$X across N runs" without a
    second SQL query. ``cost_usd`` is ``null`` (rendered as
    "n/a" by the cockpit) when *no* run had ``has_priced_models``;
    otherwise it is the sum of the priced runs' costs.
    """

    store = get_planner_store()
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    runs = await reconstruct_runs_async(plan_id, limit=limit)
    in_flight = sum(1 for r in runs if r.status == "running")
    return {
        "ok": True,
        "plan_id": plan_id,
        "plan": plan.to_dict(),
        "runs": {
            "count": len(runs),
            "in_flight": in_flight,
            "items": [r.to_dict() for r in runs],
        },
        "usage_lifetime": aggregate_usage_lifetime(runs),
    }


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


@router.post("/{plan_id}/run")
async def run_plan_endpoint(
    plan_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
    x_tars_policy_mode: str | None = Header(default=None),
) -> dict[str, Any]:
    store = get_planner_store()
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    mode = resolve_mode(
        header=x_tars_policy_mode,
        request_arg=str(payload.get("mode") or "") or None,
    )

    # Prefer the request-supplied thread id, fall back to the plan's
    # persisted thread id so events stay correlated to the original
    # chat. Same for trace id.
    effective_thread_id = (
        (x_tars_thread_id or "").strip() or plan.thread_id or None
    )

    with thread_id_scope(effective_thread_id), trace_scope(
        parent=x_meeet_trace_id or plan.trace_id
    ):
        try:
            result = await PlanRunner().run(
                plan_id,
                mode=mode,
                context=payload.get("context") or None,
            )
        except PlanRunError as exc:
            raise HTTPException(
                status_code=409 if exc.reason != "plan_not_found" else 404,
                detail={"reason": exc.reason, "message": str(exc)},
            ) from exc
    return {"ok": result["ok"], "run": result}


@router.post("/{plan_id}/abort")
async def abort_plan_endpoint(
    plan_id: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    registry = get_run_registry()
    if not registry.is_running(plan_id):
        raise HTTPException(status_code=404, detail="plan_not_running")
    flipped = registry.abort(plan_id)
    plan = await get_planner_store().get(plan_id)
    with thread_id_scope(plan.thread_id if plan else None), trace_scope(
        parent=x_meeet_trace_id or (plan.trace_id if plan else None)
    ):
        await get_client().emit(
            "plan.abort.requested",
            {"plan_id": plan_id, "ok": flipped},
        )
    return {"ok": flipped, "plan_id": plan_id}


@router.post("/{plan_id}/clone")
async def clone_plan(
    plan_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Snapshot ``plan_id`` as a fresh ``proposed`` plan.

    The original is untouched; the returned plan has a brand new
    ``id``, ``status="proposed"``, ``created_at`` / ``updated_at``
    in the present, and a fresh ``trace_id`` derived from the
    current scope. ``thread_id`` defaults to the original's; a
    body / header value rebinds the clone to a different chat.
    Emits ``planner.cloned`` so the cockpit audit lane can render
    the parent → child relationship.
    """

    store = get_planner_store()
    original = await store.get(plan_id)
    if original is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    body_thread = payload.get("thread_id")
    rebound_thread = (
        str(body_thread).strip() if body_thread is not None else None
    ) or (x_tars_thread_id or "").strip() or None
    goal_override = payload.get("goal_override")
    goal_str = (
        str(goal_override).strip() if goal_override is not None else None
    ) or None

    with thread_id_scope(rebound_thread or original.thread_id), trace_scope(
        parent=x_meeet_trace_id
    ) as new_trace_id:
        clone = await store.clone(
            plan_id,
            thread_id=rebound_thread or original.thread_id,
            trace_id=new_trace_id,
            goal_override=goal_str,
        )
        if clone is None:
            # Race: another caller deleted the original between
            # the get(...) above and the clone(...) here. Surface
            # the same 404 the cockpit handles for the GET path.
            raise HTTPException(status_code=404, detail="plan_not_found")
        await get_client().emit(
            "planner.cloned",
            {
                "plan_id": clone.id,
                "source_plan_id": original.id,
                "source_status": original.status.value,
                "model": clone.model,
                "pack_slug": clone.pack_slug,
                "playbook_id": clone.playbook_id,
                "step_count": len(clone.steps),
                "thread_id_rebind": (
                    rebound_thread != original.thread_id
                    if rebound_thread is not None
                    else False
                ),
                "goal_overridden": goal_str is not None,
            },
        )
    return {"ok": True, "plan": clone.to_dict(), "source_plan_id": original.id}


@router.post("/{plan_id}/rerun")
async def rerun_plan(
    plan_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
    x_tars_policy_mode: str | None = Header(default=None),
) -> dict[str, Any]:
    """One-shot rerun: clone ``plan_id`` → approve → run.

    Convenience endpoint over ``POST /{plan_id}/clone`` for the
    cockpit's "Rerun" button. Equivalent to calling clone, then
    flipping the new plan to ``approved``, then ``POST /run`` —
    but in a single network round-trip and inside one trace
    scope so all of the resulting events stitch together.

    Body / header support mirrors ``/clone``:

    - ``thread_id`` (body) or ``x-tars-thread-id`` header rebinds
      the clone to a different chat thread.
    - ``goal_override`` (body) replaces the goal copy on the
      clone (steps stay verbatim).
    - ``mode`` (body) or ``x-tars-policy-mode`` header overrides
      the policy gate for the run portion.

    The response carries the new plan, the run result envelope
    (status, steps, usage rollup), and a ``source_plan_id``
    pointer back to the original. ``planner.cloned`` is emitted
    with ``auto_approved=true`` and ``auto_run=true`` so the
    timeline can label the relationship as a one-shot rerun.
    """

    store = get_planner_store()
    original = await store.get(plan_id)
    if original is None:
        raise HTTPException(status_code=404, detail="plan_not_found")

    body_thread = payload.get("thread_id")
    rebound_thread = (
        str(body_thread).strip() if body_thread is not None else None
    ) or (x_tars_thread_id or "").strip() or None
    goal_override = payload.get("goal_override")
    goal_str = (
        str(goal_override).strip() if goal_override is not None else None
    ) or None

    body_mode = payload.get("mode")
    mode_override = (
        str(body_mode).strip() if body_mode is not None else None
    ) or None
    # ``resolve_mode`` is permissive — unknown strings silently
    # fall through to the env / fallback chain so a stale cockpit
    # dropdown value can't lock the operator out of a rerun.
    policy_mode: PolicyMode = resolve_mode(
        header=x_tars_policy_mode,
        request_arg=mode_override,
    )

    with thread_id_scope(rebound_thread or original.thread_id), trace_scope(
        parent=x_meeet_trace_id
    ) as new_trace_id:
        clone = await store.clone(
            plan_id,
            thread_id=rebound_thread or original.thread_id,
            trace_id=new_trace_id,
            goal_override=goal_str,
        )
        if clone is None:  # race: original deleted between get + clone
            raise HTTPException(status_code=404, detail="plan_not_found")
        await get_client().emit(
            "planner.cloned",
            {
                "plan_id": clone.id,
                "source_plan_id": original.id,
                "source_status": original.status.value,
                "model": clone.model,
                "pack_slug": clone.pack_slug,
                "playbook_id": clone.playbook_id,
                "step_count": len(clone.steps),
                "thread_id_rebind": (
                    rebound_thread != original.thread_id
                    if rebound_thread is not None
                    else False
                ),
                "goal_overridden": goal_str is not None,
                "auto_approved": True,
                "auto_run": True,
            },
        )

        await store.set_status(clone.id, PlanStatus.APPROVED)
        clone = await store.get(clone.id) or clone

        try:
            run_result = await PlanRunner().run(clone.id, mode=policy_mode)
        except PlanRunError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": exc.reason,
                    "message": exc.message,
                    "plan_id": clone.id,
                    "source_plan_id": original.id,
                },
            ) from exc

        clone = await store.get(clone.id) or clone

    return {
        "ok": True,
        "plan": clone.to_dict(),
        "source_plan_id": original.id,
        "auto_approved": True,
        "auto_run": True,
        "run_result": run_result,
    }


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


# ---------------------------------------------------------------------------
# Server-Sent Events: live plan.* feed
# ---------------------------------------------------------------------------


# All event kinds the SSE stream may emit. Pulled from the SQLite
# meeet store; kept in sync with the timeline allow-list.
_PLAN_EVENT_KINDS: tuple[str, ...] = (
    "plan.proposed",
    "planner.synthesis.completed",
    "planner.synthesis.failed",
    "planner.approved",
    "planner.rejected",
    "planner.cloned",
    "planner.deleted",
    "plan.run.started",
    "plan.step.requested",
    "plan.step.allowed",
    "plan.step.completed",
    "plan.run.usage",
    "plan.completed",
    "plan.aborted",
    "plan.abort.requested",
)


def _sse_frame(kind: str, payload: dict[str, Any], *, event_id: int | None = None) -> str:
    """Render one SSE frame.

    ``event_id`` becomes the ``id:`` line so the cockpit can persist
    the cursor in ``Last-Event-ID`` / pass it back as ``after_id`` on
    reconnect.
    """

    body = {"kind": kind, **payload}
    out = ""
    if event_id is not None:
        out += f"id: {event_id}\n"
    out += f"data: {json.dumps(body, separators=(',', ':'))}\n\n"
    return out


def _payload_matches(
    payload: dict[str, Any],
    *,
    plan_id: str | None,
    thread_id: str | None,
) -> bool:
    if plan_id and str(payload.get("plan_id") or "") != plan_id:
        return False
    if thread_id and str(payload.get("thread_id") or "") != thread_id:
        return False
    return True


async def _planner_sse_producer(
    *,
    plan_id: str | None,
    thread_id: str | None,
    after_id: int,
    poll_interval_s: float,
    max_duration_s: float,
    cursor_source: str = "default",
) -> AsyncIterator[str]:
    """Yield SSE frames for the plan.* event family.

    The producer is polling-based: every ``poll_interval_s`` it asks
    the meeet store for events with ``id > cursor`` matching one of
    the ``_PLAN_EVENT_KINDS``. Filters on ``plan_id`` / ``thread_id``
    are applied in Python (the values live in the JSON payload).
    Closes after ``max_duration_s`` of wall-clock time.

    ``cursor_source`` is plumbed in by the HTTP handler so the
    ``hello`` frame can advertise where the resume cursor came
    from (``"header"`` for a ``Last-Event-ID`` reconnect,
    ``"query"`` for an explicit ``after_id`` param, ``"default"``
    when neither was supplied).
    """

    started = time.time()
    cursor = max(0, int(after_id))
    yield _sse_frame(
        "hello",
        {
            "service": "tars-planner-events",
            "after_id": cursor,
            "after_id_source": cursor_source,
            "poll_interval_s": poll_interval_s,
            "max_duration_s": max_duration_s,
            "filter": {
                "plan_id": plan_id,
                "thread_id": thread_id,
            },
        },
    )

    store = get_meeet_store()

    while True:
        elapsed = time.time() - started
        if elapsed >= max_duration_s:
            yield _sse_frame(
                "bye",
                {"reason": "max_duration_reached", "after_id": cursor},
            )
            return

        # Pull every plan.* kind. Each call is bounded by `limit`
        # so no single tick can stall the loop.
        new_events: list[Any] = []
        for kind in _PLAN_EVENT_KINDS:
            try:
                rows = await store.list_events(
                    kind=kind,
                    after_id=cursor,
                    limit=200,
                )
            except Exception:
                continue
            new_events.extend(rows)

        # The store returns newest-first inside each kind bucket, so
        # sort by id ascending before emitting.
        new_events.sort(key=lambda ev: ev.id)

        for ev in new_events:
            payload = ev.payload if isinstance(ev.payload, dict) else {}
            if not _payload_matches(
                payload, plan_id=plan_id, thread_id=thread_id
            ):
                cursor = max(cursor, ev.id)
                continue
            cursor = max(cursor, ev.id)
            yield _sse_frame(
                ev.kind,
                {
                    "id": ev.id,
                    "ts": ev.ts,
                    "trace_id": ev.trace_id,
                    "session_id": ev.session_id,
                    "payload": payload,
                },
                event_id=ev.id,
            )

        await asyncio.sleep(max(0.05, poll_interval_s))
