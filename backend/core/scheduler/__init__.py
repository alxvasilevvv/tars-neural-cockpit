"""TARS playbook scheduler engine (Wave 97).

Real cron-based scheduling for playbook runs. Replaces the tick-based
autopilot loop for time-driven triggers. Persisted to
``~/.tars/scheduler.sqlite`` (override via ``TARS_SCHEDULER_DB_PATH``).
The lifespan loop is opt-in via ``TARS_SCHEDULER_ENABLED=1``.

Public surface:

- :mod:`.models`  — :class:`Schedule` dataclass + ID helpers.
- :mod:`.cron`    — pure-stdlib 5-field cron parser + ``next_after``
  (supports lists, ranges, steps, ``@hourly``, ``@daily`` etc.).
- :mod:`.store`   — SQLite-backed CRUD + run history + recovery.
- :mod:`.runner`  — async tick loop that fires due schedules.

Contract version: 1.0 (see ``docs/contracts/SCHEDULER.md``).
"""

from __future__ import annotations

from .cron import (
    CronExpression,
    SHORTCUTS,
    next_after,
    parse,
    validate,
)
from .models import (
    CONTRACT_VERSION,
    RunRecord,
    Schedule,
    new_run_id,
    new_schedule_id,
)
from .runner import SchedulerRunner, get_runner, scheduler_loop
from .store import SchedulerStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "CronExpression",
    "RunRecord",
    "SHORTCUTS",
    "Schedule",
    "SchedulerRunner",
    "SchedulerStore",
    "get_runner",
    "get_store",
    "new_run_id",
    "new_schedule_id",
    "next_after",
    "parse",
    "reset_store",
    "scheduler_loop",
    "validate",
]
