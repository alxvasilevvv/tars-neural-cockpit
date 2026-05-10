"""Async tick loop that fires due schedules.

The :class:`SchedulerRunner` ticks every ``TARS_SCHEDULER_TICK_S``
seconds (default 30s) and:

1. Asks the store for schedules where ``next_run_at <= now`` and
   ``enabled=true``.
2. For each, fires :func:`backend.core.playbooks.run_playbook` in a
   detached background task so a slow playbook never holds up the
   tick.
3. Records a ``RunRecord`` (started + finished + status + summary).
4. Recomputes ``next_run_at`` from the cron expression and writes it
   back to the schedule cache.

Same safety contract as the other lifespan loops in
:mod:`web_extras.app`: the module never propagates exceptions, never
crashes the host, logs once per anomaly. Disable the loop with
``TARS_SCHEDULER_ENABLED`` unset (default off).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from .cron import CronParseError, next_after
from .models import Schedule
from .store import SchedulerStore, get_store


log = logging.getLogger("tars.scheduler")


def _is_enabled() -> bool:
    flag = (os.getenv("TARS_SCHEDULER_ENABLED") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _tick_interval_s() -> float:
    raw = os.getenv("TARS_SCHEDULER_TICK_S")
    if raw is None:
        return 30.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 30.0


# ---------- Runner ---------------------------------------------------------


class SchedulerRunner:
    """Owns the periodic tick + per-schedule fire dispatch.

    Public surface intentionally tiny: ``tick()`` (used by tests) and
    ``fire_schedule()`` (used by the run-now endpoint). The lifespan
    helper :func:`scheduler_loop` wraps ``tick()`` with the asyncio
    sleep loop.
    """

    def __init__(self, store: SchedulerStore | None = None) -> None:
        self._store = store or get_store()
        self._inflight: dict[str, int] = {}

    @property
    def store(self) -> SchedulerStore:
        return self._store

    async def tick(self) -> dict[str, Any]:
        """Fire every schedule whose ``next_run_at <= now``.

        Returns a small ``{fired, scanned}`` summary so tests can
        assert behaviour without subscribing to logs.
        """

        if not self._store.enabled:
            return {"ok": False, "reason": "disabled", "fired": 0, "scanned": 0}
        due = await self._store.due_now()
        fired = 0
        for sched in due:
            inflight = self._inflight.get(sched.id, 0)
            if inflight >= sched.max_concurrent:
                # Skip — leave next_run_at where it is so the next
                # tick gets another shot once the in-flight run
                # finishes.
                continue
            asyncio.create_task(
                self._fire_and_track(sched),
                name=f"scheduler-fire-{sched.id}",
            )
            fired += 1
        return {"ok": True, "fired": fired, "scanned": len(due)}

    async def _fire_and_track(self, schedule: Schedule) -> None:
        self._inflight[schedule.id] = self._inflight.get(schedule.id, 0) + 1
        try:
            await self.fire_schedule(schedule)
        finally:
            self._inflight[schedule.id] = max(
                0, self._inflight.get(schedule.id, 0) - 1
            )

    async def fire_schedule(
        self,
        schedule: Schedule,
        *,
        update_next: bool = True,
    ) -> dict[str, Any]:
        """Run the playbook attached to ``schedule`` once.

        - ``update_next=True`` (default) — also recompute
          ``next_run_at`` from the cron expression. Set ``False`` for
          run-now invocations so the operator's manual fire doesn't
          shift the regular schedule.
        """

        started_at = time.time()
        status = "ok"
        summary: str | None = None
        trace_id: str | None = None
        try:
            from backend.core.playbooks import get_playbook, run_playbook
            from backend.core.policy import PolicyMode

            pb = get_playbook(schedule.playbook_id)
            if pb is None:
                status = "failed"
                summary = f"playbook_not_found: {schedule.playbook_id}"
            else:
                # Schedules run in autopilot mode — no human in the
                # loop; the policy gate's destructive-action logic
                # still applies via the runner.
                result = await run_playbook(
                    pb,
                    context=dict(schedule.args or {}),
                    mode=PolicyMode.AUTOPILOT,
                )
                trace_id = result.get("trace_id") if isinstance(result, dict) else None
                if not result.get("ok"):
                    failed = sum(
                        1
                        for s in result.get("steps", [])
                        if not s.get("ok") and not s.get("skipped")
                    )
                    status = "failed"
                    summary = f"playbook failed: {failed} step(s) failed"
                else:
                    blocked = sum(
                        1 for s in result.get("steps", []) if s.get("blocked")
                    )
                    if blocked:
                        status = "blocked"
                        summary = f"{blocked} step(s) blocked by policy"
                    else:
                        ran = sum(
                            1
                            for s in result.get("steps", [])
                            if not s.get("skipped")
                        )
                        summary = f"{ran} step(s) ran"
        except Exception as exc:
            status = "failed"
            summary = f"{type(exc).__name__}: {exc}"
            log.warning(
                "scheduler fire failed: schedule=%s playbook=%s exc=%s",
                schedule.id, schedule.playbook_id, exc,
            )

        finished_at = time.time()
        # Persist the run history row.
        try:
            await self._store.record_run(
                schedule_id=schedule.id,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                output_summary=summary,
                trace_id=trace_id,
            )
        except Exception as exc:  # never block the cache update
            log.warning(
                "scheduler record_run failed: schedule=%s exc=%s",
                schedule.id, exc,
            )

        # Recompute next_run_at from the cron expression so the next
        # tick has a fresh anchor.
        next_run_at: float | None = schedule.next_run_at
        if update_next:
            try:
                next_dt = next_after(
                    schedule.cron_expression,
                    datetime.now(timezone.utc),
                    tz=schedule.timezone,
                )
                next_run_at = next_dt.timestamp()
            except CronParseError as exc:
                log.warning(
                    "scheduler next_after failed: schedule=%s exc=%s",
                    schedule.id, exc,
                )
                next_run_at = None
            try:
                await self._store.record_fire(
                    schedule.id,
                    last_run_at=started_at,
                    last_status=status,
                    next_run_at=next_run_at,
                )
            except Exception as exc:
                log.warning(
                    "scheduler record_fire failed: schedule=%s exc=%s",
                    schedule.id, exc,
                )
        return {
            "ok": status == "ok",
            "status": status,
            "summary": summary,
            "started_at": started_at,
            "finished_at": finished_at,
            "next_run_at": next_run_at,
        }


# ---------- module-level singleton ------------------------------------------


_runner: SchedulerRunner | None = None


def get_runner() -> SchedulerRunner:
    global _runner
    if _runner is None:
        _runner = SchedulerRunner()
    return _runner


def reset_runner() -> None:
    global _runner
    _runner = None


# ---------- lifespan loop ---------------------------------------------------


async def scheduler_loop() -> None:
    """Periodic tick. Opt-in via ``TARS_SCHEDULER_ENABLED=1``.

    On first activation, calls :meth:`SchedulerStore.recover_state`
    so the post-restart ``next_run_at`` cache is fresh. Then ticks
    every ``TARS_SCHEDULER_TICK_S`` seconds (default 30s).
    """

    if not _is_enabled():
        return
    store = get_store()
    if not store.enabled:
        return
    interval = _tick_interval_s()
    log.info(
        "scheduler loop active: interval_s=%.1f db=%s",
        interval, store.db_path,
    )
    try:
        recovery = await store.recover_state()
        log.info(
            "scheduler recover_state: total=%s recovered=%s skipped=%s errors=%s",
            recovery.get("total"),
            recovery.get("recovered"),
            recovery.get("skipped_disabled"),
            recovery.get("errors"),
        )
    except Exception as exc:
        log.warning("scheduler recover_state failed: %s", exc)

    runner = get_runner()
    while True:
        try:
            await asyncio.sleep(interval)
            out = await runner.tick()
            if out.get("fired"):
                log.info(
                    "scheduler tick: fired=%s scanned=%s",
                    out.get("fired"),
                    out.get("scanned"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("scheduler tick failed: %s", exc)
