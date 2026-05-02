"""Reconstruct past plan runs from the durable meeet event store.

The :class:`backend.core.planner.PlanRunner` does not persist a
"runs" table of its own. Instead it emits a :term:`plan.*` event
family during execution, and we lean on the SQLite-backed meeet
store as the source of truth for "what happened when". This module
walks those events and groups them into per-run dicts the cockpit
can render in an inbox / activity stream.

Why event-sourced (vs a dedicated runs table)?

- Single source of truth: the meeet store already powers the
  timeline, the SSE feed and the gold-pill audit lane. Adding a
  parallel ``planner_runs`` table would mean keeping two stores in
  sync and would silently lie when one of them lags.
- Cheap retrofit: every existing event already includes the data we
  need (``plan_id``, ``step_id``, ``took_ms``, ``ok``, ``blocked``,
  ``error``). We just have to group them.

Run boundaries are detected by walking events in id-ascending order:

- A ``plan.run.started`` opens a new run.
- Every ``plan.step.*`` event that follows is attributed to the
  open run.
- A ``plan.completed`` or ``plan.aborted`` event closes the run.
- A run that has no terminal event yet is still returned, with
  ``status="running"`` — useful for "in flight" badges in the UI.

We do NOT trust ``trace_id`` for grouping even though the runner
now mints a fresh trace per run (the plan's birth trace travels
along as ``parent_trace_id`` on ``plan.run.started``). Walking
events in chronological order is the simpler and more robust
signal — it works for legacy events that pre-date per-run traces
and degrades gracefully when an event is missing a trace at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from backend.core.meeet import get_store as get_meeet_store
from backend.core.meeet.store import MeeetStore, StoredEvent


# Event kinds the reconstructor cares about. Kept in sync with the
# runner's emit calls in :mod:`backend.core.planner.runner`.
_RUN_EVENT_KINDS: frozenset[str] = frozenset(
    {
        "plan.run.started",
        "plan.step.requested",
        "plan.step.allowed",
        "plan.step.completed",
        "plan.completed",
        "plan.aborted",
        "plan.run.exception",
        "plan.abort.requested",
    }
)


@dataclass(frozen=True)
class RunStep:
    """One step reconstructed from ``plan.step.completed``.

    Mirrors ``StepResult.to_dict`` but is constrained to the fields
    the events actually carry, so the reconstructor stays robust
    even if a future event drops or renames keys.
    """

    id: str
    action: str
    ok: bool
    skipped: bool
    blocked: bool
    took_ms: float
    error: Optional[str] = None
    # ``True`` once the gate emitted a ``plan.step.allowed`` for this
    # step in the current run. Useful for the cockpit to render a
    # green check on the policy lane.
    allowed: Optional[bool] = None
    allow_reason: Optional[str] = None
    parallel: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "ok": self.ok,
            "skipped": self.skipped,
            "blocked": self.blocked,
            "took_ms": self.took_ms,
            "error": self.error,
            "allowed": self.allowed,
            "allow_reason": self.allow_reason,
            "parallel": self.parallel,
        }


@dataclass
class PlanRun:
    """One reconstructed run of a single plan.

    Mutable on purpose — the reconstructor builds it up step by step
    while walking events, then we freeze the picture by calling
    :meth:`to_dict` on the way out.

    The ``usage`` block (calls / tokens / cost / latency) lives on
    the terminal event the runner emits and is copied here verbatim
    when present. ``cost_usd`` may be ``None`` when no priced model
    fired — the cockpit renders "n/a" instead of "$0.00" so we
    don't falsely advertise a free run.
    """

    plan_id: str
    started_at: float
    started_event_id: int
    trace_id: Optional[str] = None
    mode: Optional[str] = None
    step_count: Optional[int] = None
    completed_at: Optional[float] = None
    completed_event_id: Optional[int] = None
    status: str = "running"  # running | completed | aborted
    abort_reason: Optional[str] = None
    abort_requested: bool = False
    exception: Optional[str] = None
    steps_run: int = 0
    steps_blocked: int = 0
    steps_failed: int = 0
    usage_calls: int = 0
    usage_tokens_in: int = 0
    usage_tokens_out: int = 0
    usage_cost_usd: Optional[float] = None
    usage_latency_ms_total: float = 0.0
    usage_has_priced_models: bool = False
    steps: list[RunStep] = field(default_factory=list)
    _step_index: dict[str, int] = field(default_factory=dict)

    def took_ms(self) -> Optional[float]:
        if self.completed_at is None:
            return None
        return max(0.0, (self.completed_at - self.started_at) * 1000.0)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "plan_id": self.plan_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "trace_id": self.trace_id,
            "mode": self.mode,
            "step_count": self.step_count,
            "steps_run": self.steps_run,
            "steps_blocked": self.steps_blocked,
            "steps_failed": self.steps_failed,
            "abort_reason": self.abort_reason,
            "abort_requested": self.abort_requested,
            "exception": self.exception,
            "took_ms": self.took_ms(),
            "usage": {
                "calls": self.usage_calls,
                "tokens_in": self.usage_tokens_in,
                "tokens_out": self.usage_tokens_out,
                "cost_usd": self.usage_cost_usd,
                "latency_ms_total": self.usage_latency_ms_total,
                "has_priced_models": self.usage_has_priced_models,
            },
            "steps": [s.to_dict() for s in self.steps],
        }
        return out


def _payload(ev: StoredEvent) -> Mapping[str, Any]:
    p = ev.payload
    return p if isinstance(p, dict) else {}


def _matches_plan(payload: Mapping[str, Any], plan_id: str) -> bool:
    return str(payload.get("plan_id") or "") == plan_id


def _apply_step_completed(run: PlanRun, payload: Mapping[str, Any]) -> None:
    step_id = str(payload.get("step_id") or "")
    if not step_id:
        return
    step = RunStep(
        id=step_id,
        action=str(payload.get("action") or ""),
        ok=bool(payload.get("ok", False)),
        skipped=bool(payload.get("skipped", False)),
        blocked=bool(payload.get("blocked", False)),
        took_ms=float(payload.get("took_ms") or 0.0),
        error=(
            str(payload["error"]) if payload.get("error") is not None else None
        ),
        parallel=bool(payload.get("parallel", False)),
    )
    # Preserve the allowed verdict if a previous plan.step.allowed
    # already populated it.
    if step.id in run._step_index:
        prior = run.steps[run._step_index[step.id]]
        step = RunStep(
            id=step.id,
            action=step.action or prior.action,
            ok=step.ok,
            skipped=step.skipped,
            blocked=step.blocked,
            took_ms=step.took_ms,
            error=step.error,
            allowed=prior.allowed,
            allow_reason=prior.allow_reason,
            parallel=step.parallel or prior.parallel,
        )
        run.steps[run._step_index[step.id]] = step
    else:
        run._step_index[step.id] = len(run.steps)
        run.steps.append(step)

    if not step.skipped:
        run.steps_run += 1
    if step.blocked:
        run.steps_blocked += 1
    if not step.ok and not step.skipped and not step.blocked:
        run.steps_failed += 1


def _apply_step_allowed(run: PlanRun, payload: Mapping[str, Any]) -> None:
    step_id = str(payload.get("step_id") or "")
    if not step_id:
        return
    allowed = bool(payload.get("allowed", False))
    reason = payload.get("reason")
    reason_s = str(reason) if reason is not None else None
    if step_id in run._step_index:
        idx = run._step_index[step_id]
        prior = run.steps[idx]
        run.steps[idx] = RunStep(
            id=prior.id,
            action=prior.action,
            ok=prior.ok,
            skipped=prior.skipped,
            blocked=prior.blocked,
            took_ms=prior.took_ms,
            error=prior.error,
            allowed=allowed,
            allow_reason=reason_s,
            parallel=prior.parallel,
        )
    else:
        # ``allowed`` arrived before ``completed`` (this is the
        # normal ordering) — stash the verdict on a placeholder so
        # we can merge it when the completed event lands.
        placeholder = RunStep(
            id=step_id,
            action=str(payload.get("action") or ""),
            ok=False,
            skipped=False,
            blocked=False,
            took_ms=0.0,
            allowed=allowed,
            allow_reason=reason_s,
        )
        run._step_index[step_id] = len(run.steps)
        run.steps.append(placeholder)


def _close_run(
    run: PlanRun, payload: Mapping[str, Any], *, ev: StoredEvent, status: str
) -> None:
    run.status = status
    run.completed_at = ev.ts
    run.completed_event_id = ev.id
    if status == "aborted":
        reason = payload.get("reason")
        if reason is not None:
            run.abort_reason = str(reason)
    # The terminal event also reports authoritative counters.
    if "steps_run" in payload:
        run.steps_run = int(payload.get("steps_run") or 0)
    if "steps_blocked" in payload:
        run.steps_blocked = int(payload.get("steps_blocked") or 0)
    if "steps_failed" in payload:
        run.steps_failed = int(payload.get("steps_failed") or 0)
    # Usage rollup — runner stamps this on the terminal event.
    usage = payload.get("usage")
    if isinstance(usage, Mapping):
        run.usage_calls = int(usage.get("calls") or 0)
        run.usage_tokens_in = int(usage.get("tokens_in") or 0)
        run.usage_tokens_out = int(usage.get("tokens_out") or 0)
        cost = usage.get("cost_usd")
        if cost is None:
            run.usage_cost_usd = None
        else:
            try:
                run.usage_cost_usd = float(cost)
            except (TypeError, ValueError):
                run.usage_cost_usd = None
        run.usage_latency_ms_total = float(
            usage.get("latency_ms_total") or 0.0
        )
        run.usage_has_priced_models = bool(
            usage.get("has_priced_models", False)
        )


def reconstruct_runs(
    plan_id: str,
    *,
    store: MeeetStore | None = None,
    limit: int = 1000,
) -> list[PlanRun]:
    """Walk the meeet store and reconstruct all runs for one plan.

    ``limit`` caps the *per-kind* fetch so a misbehaving plan can't
    drag every plan event into memory. Default 1000 covers the
    deepest expected run (≈100 steps × 4 events × a handful of
    runs).

    Returned runs are ordered newest-first by ``started_at`` so the
    cockpit can render the latest run on top.
    """

    s = store or get_meeet_store()
    plan_id = str(plan_id)
    if not plan_id:
        return []

    # Collect every relevant event for this plan id. We pull each
    # kind independently so the per-kind index is hit, then we
    # merge + sort by id ascending so the walk is chronological.
    rows: list[StoredEvent] = []
    for kind in _RUN_EVENT_KINDS:
        try:
            batch = _list_events_blocking(s, kind=kind, limit=limit)
        except Exception:
            continue
        for ev in batch:
            if _matches_plan(_payload(ev), plan_id):
                rows.append(ev)
    rows.sort(key=lambda ev: ev.id)

    runs: list[PlanRun] = []
    open_run: PlanRun | None = None
    for ev in rows:
        payload = _payload(ev)
        if ev.kind == "plan.run.started":
            if open_run is not None:
                # No terminal event landed before the next start —
                # treat the previous run as aborted with reason
                # ``no_terminal_event`` so the UI can flag it.
                open_run.status = "aborted"
                open_run.abort_reason = (
                    open_run.abort_reason or "no_terminal_event"
                )
                runs.append(open_run)
            open_run = PlanRun(
                plan_id=plan_id,
                started_at=ev.ts,
                started_event_id=ev.id,
                trace_id=ev.trace_id,
                mode=(
                    str(payload["mode"]) if payload.get("mode") is not None
                    else None
                ),
                step_count=(
                    int(payload["step_count"])
                    if payload.get("step_count") is not None
                    else None
                ),
            )
        elif open_run is None:
            # An orphan step / completion event with no preceding
            # ``plan.run.started`` — skip rather than fabricate a
            # synthetic run. Real-world cause: the store was
            # partially pruned.
            continue
        elif ev.kind == "plan.step.completed":
            _apply_step_completed(open_run, payload)
        elif ev.kind == "plan.step.allowed":
            _apply_step_allowed(open_run, payload)
        elif ev.kind == "plan.abort.requested":
            open_run.abort_requested = True
        elif ev.kind == "plan.run.exception":
            open_run.exception = (
                str(payload.get("error"))
                if payload.get("error") is not None
                else "unknown"
            )
        elif ev.kind == "plan.completed":
            _close_run(open_run, payload, ev=ev, status="completed")
            runs.append(open_run)
            open_run = None
        elif ev.kind == "plan.aborted":
            _close_run(open_run, payload, ev=ev, status="aborted")
            runs.append(open_run)
            open_run = None
        # plan.step.requested is informational — covered by the
        # subsequent allowed/completed pair.

    if open_run is not None:
        runs.append(open_run)

    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _list_events_blocking(
    store: MeeetStore, *, kind: str, limit: int
) -> Iterable[StoredEvent]:
    """Synchronous shim over :meth:`MeeetStore.list_events`.

    The reconstructor is called from a sync HTTP handler context
    (``await reconstruct_runs_async`` would push the cost back onto
    the event loop for no benefit), so we hop into the store's sync
    layer directly. The store guards the connection per-call, so
    this is safe alongside in-flight async writers.
    """

    if not store.enabled:
        return []
    return store._list_sync(  # noqa: SLF001 — intentional fast path
        limit=limit,
        since=None,
        trace_id=None,
        kind=kind,
        kind_prefix=None,
        session_id=None,
        only_unpushed=False,
        after_id=None,
    )


async def reconstruct_runs_async(
    plan_id: str,
    *,
    store: MeeetStore | None = None,
    limit: int = 1000,
) -> list[PlanRun]:
    """Async-friendly wrapper around :func:`reconstruct_runs`.

    Uses the store's async ``list_events`` so we don't block the
    event loop when called from a FastAPI route handler.
    """

    import asyncio

    s = store or get_meeet_store()
    plan_id = str(plan_id)
    if not plan_id:
        return []

    rows: list[StoredEvent] = []
    for kind in _RUN_EVENT_KINDS:
        try:
            batch = await s.list_events(kind=kind, limit=limit)
        except Exception:
            continue
        for ev in batch:
            if _matches_plan(_payload(ev), plan_id):
                rows.append(ev)
    # Hand the rest off to the (synchronous) reducer to keep the
    # logic in exactly one place.
    return await asyncio.to_thread(_reduce_rows, rows, plan_id)


def _reduce_rows(rows: list[StoredEvent], plan_id: str) -> list[PlanRun]:
    rows = sorted(rows, key=lambda ev: ev.id)
    runs: list[PlanRun] = []
    open_run: PlanRun | None = None
    for ev in rows:
        payload = _payload(ev)
        if ev.kind == "plan.run.started":
            if open_run is not None:
                open_run.status = "aborted"
                open_run.abort_reason = (
                    open_run.abort_reason or "no_terminal_event"
                )
                runs.append(open_run)
            open_run = PlanRun(
                plan_id=plan_id,
                started_at=ev.ts,
                started_event_id=ev.id,
                trace_id=ev.trace_id,
                mode=(
                    str(payload["mode"]) if payload.get("mode") is not None
                    else None
                ),
                step_count=(
                    int(payload["step_count"])
                    if payload.get("step_count") is not None
                    else None
                ),
            )
        elif open_run is None:
            continue
        elif ev.kind == "plan.step.completed":
            _apply_step_completed(open_run, payload)
        elif ev.kind == "plan.step.allowed":
            _apply_step_allowed(open_run, payload)
        elif ev.kind == "plan.abort.requested":
            open_run.abort_requested = True
        elif ev.kind == "plan.run.exception":
            open_run.exception = (
                str(payload.get("error"))
                if payload.get("error") is not None
                else "unknown"
            )
        elif ev.kind == "plan.completed":
            _close_run(open_run, payload, ev=ev, status="completed")
            runs.append(open_run)
            open_run = None
        elif ev.kind == "plan.aborted":
            _close_run(open_run, payload, ev=ev, status="aborted")
            runs.append(open_run)
            open_run = None

    if open_run is not None:
        runs.append(open_run)

    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs


__all__ = [
    "PlanRun",
    "RunStep",
    "reconstruct_runs",
    "reconstruct_runs_async",
]
