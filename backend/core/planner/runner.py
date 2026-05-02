"""Planner run loop — drives an approved Plan through the policy gate.

The :class:`PlanRunner` mirrors :class:`backend.core.playbooks.PlaybookRunner`
but emits ``plan.*`` lifecycle events keyed by ``plan_id`` and persists
status transitions to the :class:`PlannerStore`. It supports cooperative
abort via a per-plan :class:`asyncio.Event` registered in
:class:`PlanRunRegistry`.

Status transitions owned by the runner:

- ``approved → running`` on entry.
- ``running → completed`` if no step is blocked / failed (or all such
  steps had ``on_error="continue"`` so the run never short-circuited).
- ``running → aborted``  if a step failed with ``on_error="stop"``,
  was blocked under a ``stop`` ``on_block`` policy, the operator
  triggered :meth:`PlanRunRegistry.abort`, or the run raised.

Events emitted, all inside ``trace_scope`` + ``thread_id_scope``:

- ``plan.run.started``    — once per ``run(plan_id, …)`` call.
- ``plan.step.requested`` — per executable step, before policy check.
- ``plan.step.allowed``   — per step, after policy check (carries
  ``allowed`` boolean and gate ``reason``).
- ``plan.step.completed`` — per step, after dispatch.
- ``plan.completed``      — terminal happy path.
- ``plan.aborted``        — terminal sad path (with ``reason``).

Skipped steps (``when`` clause false, or skipped because a previous
step aborted the run) emit ``plan.step.completed`` with
``skipped=True`` so the cockpit can render them gray.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from backend.core.meeet import (
    get_client,
    get_store as get_meeet_store,
    thread_id_scope,
    trace_scope,
)
from backend.core.playbooks.runner import (
    PlaybookRunner,
    StepResult,
    _check_when,
    _group_steps,
    _resolve_args,
)
from backend.core.policy import PolicyMode, get_gate

from .store import PlannerStore, get_planner_store
from .types import Plan, PlanStatus, PlanStep


class PlanRunError(Exception):
    """Raised by :meth:`PlanRunner.run` when the Plan can't be entered.

    Carries a stable ``reason`` so the HTTP layer can map it to a
    structured error envelope.
    """

    def __init__(self, reason: str, *, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# Abort registry
# ---------------------------------------------------------------------------


class PlanRunRegistry:
    """Tracks in-flight plan runs so the HTTP layer can request an abort.

    The registry stores one :class:`asyncio.Event` per ``plan_id`` while
    the run is alive. :meth:`abort` flips that event; the runner observes
    it between groups (cooperative abort — never mid-step).
    """

    def __init__(self) -> None:
        self._aborts: dict[str, asyncio.Event] = {}

    def register(self, plan_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._aborts[plan_id] = event
        return event

    def unregister(self, plan_id: str) -> None:
        self._aborts.pop(plan_id, None)

    def abort(self, plan_id: str) -> bool:
        ev = self._aborts.get(plan_id)
        if ev is None:
            return False
        ev.set()
        return True

    def is_running(self, plan_id: str) -> bool:
        return plan_id in self._aborts

    def in_flight(self) -> tuple[str, ...]:
        return tuple(self._aborts.keys())


_REGISTRY: PlanRunRegistry | None = None


def get_run_registry() -> PlanRunRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PlanRunRegistry()
    return _REGISTRY


def reset_run_registry() -> None:
    """Test helper — drop the cached singleton."""

    global _REGISTRY
    _REGISTRY = None


# ---------------------------------------------------------------------------
# Synthetic Playbook adapter (so we can reuse PlaybookRunner._dispatch)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AdaptedStep:
    """Quack-typed PlaybookStep for the existing dispatcher.

    ``PlaybookRunner._dispatch`` only reads ``id`` / ``action`` / ``args``
    / ``store_as`` / ``when`` / ``on_error`` / ``parallel`` off the step,
    so a plain dataclass with the same shape is enough.
    """

    id: str
    action: str
    args: Mapping[str, Any] = field(default_factory=dict)
    store_as: Optional[str] = None
    when: Optional[str] = None
    on_error: str = "stop"
    parallel: bool = False


def _plan_step_to_adapter(step: PlanStep) -> _AdaptedStep:
    return _AdaptedStep(
        id=step.id,
        action=step.action,
        args=dict(step.args),
        store_as=step.store_as,
        when=step.when,
        on_error=step.on_error,
        parallel=step.parallel,
    )


# ---------------------------------------------------------------------------
# Per-run usage rollup
# ---------------------------------------------------------------------------


async def _compute_run_usage(
    *,
    trace_id: str | None,
    started_at: float,
    finished_at: float,
) -> dict[str, Any]:
    """Roll up ``usage.tokens`` events that fired during this run.

    The runner currently inherits the plan's birth ``trace_id`` (so
    the synthesis events and every run share it). Filtering by
    ``trace_id`` alone would mix runs of the same plan together, so
    we *also* clamp by the run's wall-clock window — the
    ``usage.tokens`` event is emitted with the trace context active
    at the moment of the LLM call, so its ``ts`` falls inside the
    ``started_at..finished_at`` window iff it belongs to this run.

    Returns a dict with ``calls`` / ``tokens_in`` / ``tokens_out``
    / ``cost_usd`` / ``latency_ms_total`` / ``has_priced_models``.
    The ``cost_usd`` value is ``None`` (rather than ``0.0``) when no
    matching event was found *and* no priced models could be
    summed — the cockpit renders "n/a" in that case so we don't
    falsely advertise a free run for a paid model whose price is
    missing from the table.
    """

    if not trace_id:
        return {
            "calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": None,
            "latency_ms_total": 0.0,
            "has_priced_models": False,
        }

    try:
        events = await get_meeet_store().list_events(
            kind="usage.tokens",
            trace_id=trace_id,
            since=started_at,
            limit=1000,
        )
    except Exception:
        events = []

    calls = 0
    tokens_in = 0
    tokens_out = 0
    cost_total = 0.0
    latency_total = 0.0
    priced = False
    # Add a tiny grace margin for clock skew between the runner
    # finishing the loop and the terminal emit landing on disk.
    finished_clamp = max(finished_at, started_at) + 1.0

    for ev in events:
        if ev.ts > finished_clamp:
            continue
        payload = ev.payload if isinstance(ev.payload, dict) else {}
        calls += 1
        tokens_in += int(payload.get("tokens_in") or 0)
        tokens_out += int(payload.get("tokens_out") or 0)
        latency_total += float(payload.get("latency_ms") or 0.0)
        cost = payload.get("cost_usd")
        if cost is not None:
            try:
                cost_total += float(cost)
                priced = True
            except (TypeError, ValueError):
                pass

    return {
        "calls": calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost_total, 6) if priced else None,
        "latency_ms_total": round(latency_total, 3),
        "has_priced_models": priced,
    }


# ---------------------------------------------------------------------------
# PlanRunner
# ---------------------------------------------------------------------------


@dataclass
class PlanRunner:
    """Drives an approved :class:`Plan` through the policy gate.

    Reuses :meth:`PlaybookRunner._dispatch` for the actual action call
    so the planner inherits all the existing semantics (awareness
    snapshots, policy gate, error mapping) for free.
    """

    store: PlannerStore | None = None
    registry: PlanRunRegistry | None = None

    def _store(self) -> PlannerStore:
        return self.store or get_planner_store()

    def _registry(self) -> PlanRunRegistry:
        return self.registry or get_run_registry()

    async def run(
        self,
        plan_id: str,
        *,
        mode: PolicyMode = PolicyMode.CONFIRM,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the Plan with the given ``plan_id``.

        Raises :class:`PlanRunError` (``plan_not_found`` /
        ``plan_not_runnable`` / ``plan_already_running``) when the plan
        cannot be entered. Otherwise returns a dict shaped like
        :meth:`PlaybookRunner.run`'s result, augmented with the
        canonical ``plan_id`` / ``status`` keys.
        """

        store = self._store()
        registry = self._registry()

        plan = await store.get(plan_id)
        if plan is None:
            raise PlanRunError("plan_not_found")
        if plan.status != PlanStatus.APPROVED:
            # Already running, completed, aborted, rejected, or
            # still proposed — refuse, but return the live status
            # to the caller via the error envelope.
            raise PlanRunError(
                "plan_not_runnable",
                message=(
                    f"plan is in status {plan.status.value!r}; "
                    "must be 'approved' to run"
                ),
            )
        if registry.is_running(plan_id):
            raise PlanRunError("plan_already_running")

        # Flip approved → running.
        running_plan = await store.set_status(plan_id, PlanStatus.RUNNING)
        if running_plan is None:
            raise PlanRunError("status_update_failed")
        plan = running_plan

        client = get_client()
        gate = get_gate()
        abort_event = registry.register(plan_id)

        ctx: dict[str, Any] = {
            "context": dict(context or {}),
            "steps": {},
        }
        results_by_id: dict[str, StepResult] = {}
        results_in_order: list[StepResult] = []

        # Reuse PlaybookRunner just for ``_dispatch``.
        dispatcher = PlaybookRunner()

        ok = True
        abort_reason: str | None = None
        adapted_steps = tuple(_plan_step_to_adapter(s) for s in plan.steps)

        run_started_at = time.time()

        with thread_id_scope(plan.thread_id), trace_scope(
            parent=plan.trace_id
        ) as trace_id:
            await client.emit(
                "plan.run.started",
                {
                    "plan_id": plan.id,
                    "model": plan.model,
                    "pack_slug": plan.pack_slug,
                    "playbook_id": plan.playbook_id,
                    "step_count": len(plan.steps),
                    "mode": mode.value,
                },
            )

            stop = False
            groups = _group_steps(adapted_steps)
            try:
                for group in groups:
                    if abort_event.is_set():
                        stop = True
                        abort_reason = abort_reason or "operator_abort"

                    if stop:
                        for step in group:
                            sr = StepResult(
                                id=step.id,
                                action=step.action,
                                ok=False,
                                skipped=True,
                                blocked=False,
                                took_ms=0.0,
                                error="aborted_by_previous_step",
                            )
                            results_in_order.append(sr)
                            results_by_id[step.id] = sr
                            await client.emit(
                                "plan.step.completed",
                                {
                                    "plan_id": plan.id,
                                    "step_id": step.id,
                                    "action": step.action,
                                    "ok": False,
                                    "skipped": True,
                                    "blocked": False,
                                    "took_ms": 0.0,
                                    "error": "aborted_by_previous_step",
                                },
                            )
                        continue

                    # Filter by ``when`` clauses.
                    executable: list[_AdaptedStep] = []
                    for step in group:
                        if _check_when(step.when, ctx):
                            executable.append(step)
                        else:
                            sr = StepResult(
                                id=step.id,
                                action=step.action,
                                ok=True,
                                skipped=True,
                                blocked=False,
                                took_ms=0.0,
                            )
                            results_in_order.append(sr)
                            results_by_id[step.id] = sr
                            await client.emit(
                                "plan.step.completed",
                                {
                                    "plan_id": plan.id,
                                    "step_id": step.id,
                                    "action": step.action,
                                    "ok": True,
                                    "skipped": True,
                                    "blocked": False,
                                    "took_ms": 0.0,
                                    "skip_reason": "when_false",
                                },
                            )

                    if not executable:
                        continue

                    # Emit a ``plan.step.requested`` for every
                    # executable step in this group (parallel siblings
                    # all log "requested" before any of them runs).
                    for step in executable:
                        await client.emit(
                            "plan.step.requested",
                            {
                                "plan_id": plan.id,
                                "step_id": step.id,
                                "action": step.action,
                                "parallel": step.parallel
                                or len(executable) > 1,
                            },
                        )

                    if len(executable) == 1:
                        step = executable[0]
                        started = time.perf_counter()
                        args = _resolve_args(dict(step.args), ctx)
                        sr = await dispatcher._dispatch(
                            step, args, gate=gate, mode=mode
                        )
                        sr.took_ms = (
                            time.perf_counter() - started
                        ) * 1000.0
                        finished_now: list[
                            tuple[_AdaptedStep, StepResult]
                        ] = [(step, sr)]
                    else:

                        async def _run_one(
                            step: _AdaptedStep,
                        ) -> tuple[_AdaptedStep, StepResult]:
                            started = time.perf_counter()
                            args = _resolve_args(dict(step.args), ctx)
                            sr = await dispatcher._dispatch(
                                step, args, gate=gate, mode=mode
                            )
                            sr.took_ms = (
                                time.perf_counter() - started
                            ) * 1000.0
                            return step, sr

                        finished_now = list(
                            await asyncio.gather(
                                *(_run_one(s) for s in executable)
                            )
                        )

                    for step, sr in finished_now:
                        results_in_order.append(sr)
                        results_by_id[step.id] = sr
                        if step.store_as and sr.ok and not sr.blocked:
                            ctx["steps"][step.store_as] = sr.result
                        # plan.step.allowed reflects the gate decision:
                        # True  → action ran (or was non-destructive),
                        # False → blocked by policy gate.
                        await client.emit(
                            "plan.step.allowed",
                            {
                                "plan_id": plan.id,
                                "step_id": step.id,
                                "action": step.action,
                                "allowed": not sr.blocked,
                                "reason": (
                                    "blocked_by_policy"
                                    if sr.blocked
                                    else (
                                        "executed"
                                        if sr.ok
                                        else "execution_failed"
                                    )
                                ),
                            },
                        )
                        await client.emit(
                            "plan.step.completed",
                            {
                                "plan_id": plan.id,
                                "step_id": step.id,
                                "action": step.action,
                                "ok": sr.ok,
                                "skipped": False,
                                "blocked": sr.blocked,
                                "took_ms": round(sr.took_ms, 3),
                                "parallel": step.parallel
                                or len(executable) > 1,
                                "error": sr.error,
                            },
                        )

                    # Decide if we should stop after this group.
                    for step, sr in finished_now:
                        if sr.blocked:
                            # Plans always treat blocked steps as
                            # stop-the-run unless on_error=continue;
                            # the cockpit re-runs after operator
                            # confirms the policy token.
                            if step.on_error != "continue":
                                stop = True
                                ok = False
                                abort_reason = abort_reason or (
                                    "blocked_by_policy"
                                )
                                break
                        elif not sr.ok:
                            ok = False
                            if step.on_error == "stop":
                                stop = True
                                abort_reason = abort_reason or (
                                    "step_failed"
                                )
                                break

            except Exception as exc:  # pragma: no cover - safety net
                stop = True
                ok = False
                abort_reason = f"runner_exception:{exc!r}"
                await client.emit(
                    "plan.run.exception",
                    {"plan_id": plan.id, "error": repr(exc)},
                )
            finally:
                registry.unregister(plan_id)

            steps_run = sum(1 for r in results_in_order if not r.skipped)
            steps_blocked = sum(1 for r in results_in_order if r.blocked)
            steps_failed = sum(
                1
                for r in results_in_order
                if not r.ok and not r.skipped and not r.blocked
            )

            if stop:
                final_status = PlanStatus.ABORTED
                error_msg = abort_reason or "aborted"
            else:
                final_status = PlanStatus.COMPLETED
                error_msg = None

            await self._store().set_status(
                plan.id, final_status, error=error_msg
            )

            run_finished_at = time.time()
            usage = await _compute_run_usage(
                trace_id=trace_id,
                started_at=run_started_at,
                finished_at=run_finished_at,
            )

            if final_status == PlanStatus.COMPLETED:
                await client.emit(
                    "plan.completed",
                    {
                        "plan_id": plan.id,
                        "ok": True,
                        "steps_run": steps_run,
                        "steps_blocked": steps_blocked,
                        "steps_failed": steps_failed,
                        "usage": usage,
                    },
                )
            else:
                await client.emit(
                    "plan.aborted",
                    {
                        "plan_id": plan.id,
                        "reason": error_msg or "aborted",
                        "steps_run": steps_run,
                        "steps_blocked": steps_blocked,
                        "steps_failed": steps_failed,
                        "usage": usage,
                    },
                )

            ordered = [
                results_by_id[s.id]
                for s in plan.steps
                if s.id in results_by_id
            ]

            return {
                "ok": ok and not stop,
                "plan_id": plan.id,
                "status": final_status.value,
                "trace_id": trace_id,
                "mode": mode.value,
                "steps": [r.to_dict() for r in ordered],
                "context": ctx,
                "abort_reason": error_msg,
                "usage": usage,
            }


async def run_plan(
    plan_id: str,
    *,
    mode: PolicyMode = PolicyMode.CONFIRM,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper around :meth:`PlanRunner.run`."""

    return await PlanRunner().run(plan_id, mode=mode, context=context)
