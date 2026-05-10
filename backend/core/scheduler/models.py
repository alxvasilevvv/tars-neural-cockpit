"""Dataclasses + ID helpers for the scheduler module (Wave 97).

Two records:

- :class:`Schedule` — durable description of a recurring playbook
  invocation. Stores the cron expression + tz + opt-in args bag,
  plus the cached ``next_run_at`` so the runner doesn't have to
  re-parse on every tick.
- :class:`RunRecord` — append-only history row written each time a
  schedule fires (or fails to fire).

IDs are short ``sched_*`` / ``run_*`` strings so they read well in
URLs and logs.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_schedule_id() -> str:
    return _short_id("sched")


def new_run_id() -> str:
    return _short_id("run")


# ---------- Schedule --------------------------------------------------------


@dataclass
class Schedule:
    """A persisted cron-driven playbook trigger.

    ``last_run_at`` / ``next_run_at`` / ``last_status`` are caches the
    runner refreshes after each fire. ``args`` is passed verbatim into
    :func:`backend.core.playbooks.run_playbook` as the ``context``
    bag, so authors can e.g. embed an attendee email or a scenario
    label that the playbook templates use.
    """

    id: str
    playbook_id: str
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True
    last_run_at: float | None = None
    next_run_at: float | None = None
    last_status: str | None = None
    max_concurrent: int = 1
    args: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "playbook_id": self.playbook_id,
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "last_status": self.last_status,
            "max_concurrent": self.max_concurrent,
            "args": dict(self.args),
            "created_at": self.created_at,
        }


# ---------- RunRecord -------------------------------------------------------


# Canonical statuses. The router accepts any string, but these are the
# ones the dashboard knows how to color.
RUN_STATUSES: tuple[str, ...] = (
    "ok",
    "failed",
    "skipped",
    "running",
    "blocked",
)


@dataclass
class RunRecord:
    """One observed schedule firing — append-only log row."""

    id: str
    schedule_id: str
    started_at: float
    finished_at: float | None = None
    status: str = "running"
    output_summary: str | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "output_summary": self.output_summary,
            "trace_id": self.trace_id,
            "duration_ms": (
                None
                if self.finished_at is None
                else round((self.finished_at - self.started_at) * 1000.0, 3)
            ),
        }
