"""SQLite-backed store for the scheduler module (Wave 97).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.cohort.store`. The DB lives at
``~/.tars/scheduler.sqlite`` by default; override with
``TARS_SCHEDULER_DB_PATH``. Disable with
``TARS_SCHEDULER_STORE=disabled``.

Tables:

- ``schedules``    — one row per durable schedule.
- ``run_history``  — append-only log of fired runs.

Auto-creates schema on first connect. ``recover_state`` is the
restart-safe entry point: it loads every schedule, recomputes
``next_run_at`` from the cron expression + current time, and writes
the cache back so the runner can do a single ``SELECT`` on each tick.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from .cron import CronParseError, next_after, validate
from .models import (
    CONTRACT_VERSION,
    RunRecord,
    Schedule,
    new_run_id,
    new_schedule_id,
)


DEFAULT_DB_PATH = "~/.tars/scheduler.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    playbook_id TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run_at REAL,
    next_run_at REAL,
    last_status TEXT,
    max_concurrent INTEGER NOT NULL DEFAULT 1,
    args_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS run_history (
    id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL DEFAULT 'running',
    output_summary TEXT,
    trace_id TEXT,
    FOREIGN KEY (schedule_id) REFERENCES schedules (id)
);

CREATE INDEX IF NOT EXISTS idx_schedules_playbook
    ON schedules (playbook_id);
CREATE INDEX IF NOT EXISTS idx_schedules_due
    ON schedules (enabled, next_run_at);
CREATE INDEX IF NOT EXISTS idx_runs_schedule
    ON run_history (schedule_id, started_at DESC);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_SCHEDULER_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_SCHEDULER_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class SchedulerStore:
    """Durable scheduler store. Auto-initialised on first call."""

    contract_version = CONTRACT_VERSION

    def __init__(self, db_path: str | None = None) -> None:
        self._disabled = _is_disabled()
        self._db_path = _resolve_db_path(db_path)
        self._inited = False

    # ---------- meta ------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return not self._disabled

    @property
    def db_path(self) -> str:
        return self._db_path

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(self._db_path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        self._ensure_dir()
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        if not self._inited:
            conn.executescript(_SCHEMA)
            self._inited = True
        return conn

    # ---------- row mapping ---------------------------------------------

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> Schedule:
        try:
            args = json.loads(row["args_json"] or "{}")
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        return Schedule(
            id=row["id"],
            playbook_id=row["playbook_id"],
            cron_expression=row["cron_expression"],
            timezone=row["timezone"] or "UTC",
            enabled=bool(row["enabled"]),
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
            last_status=row["last_status"],
            max_concurrent=int(row["max_concurrent"] or 1),
            args=args,
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            id=row["id"],
            schedule_id=row["schedule_id"],
            started_at=float(row["started_at"]),
            finished_at=row["finished_at"],
            status=row["status"],
            output_summary=row["output_summary"],
            trace_id=row["trace_id"],
        )

    # ---------- schedule CRUD ------------------------------------------

    def _create_sync(
        self,
        *,
        playbook_id: str,
        cron_expression: str,
        timezone_name: str,
        args: dict[str, Any],
        max_concurrent: int,
        enabled: bool,
    ) -> Schedule:
        if not validate(cron_expression):
            raise ValueError(f"invalid cron_expression: {cron_expression!r}")
        rec = Schedule(
            id=new_schedule_id(),
            playbook_id=playbook_id.strip(),
            cron_expression=cron_expression.strip(),
            timezone=(timezone_name or "UTC").strip() or "UTC",
            enabled=bool(enabled),
            args=dict(args or {}),
            max_concurrent=max(1, int(max_concurrent)),
        )
        # Compute first next_run_at from now.
        try:
            rec.next_run_at = next_after(
                rec.cron_expression,
                datetime.now(timezone.utc),
                tz=rec.timezone,
            ).timestamp()
        except CronParseError as exc:
            raise ValueError(str(exc)) from exc
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO schedules (id, playbook_id, cron_expression,"
                " timezone, enabled, last_run_at, next_run_at, last_status,"
                " max_concurrent, args_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.playbook_id,
                    rec.cron_expression,
                    rec.timezone,
                    1 if rec.enabled else 0,
                    rec.last_run_at,
                    rec.next_run_at,
                    rec.last_status,
                    rec.max_concurrent,
                    json.dumps(rec.args),
                    rec.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def create_schedule(
        self,
        *,
        playbook_id: str,
        cron_expression: str,
        timezone: str = "UTC",
        args: dict[str, Any] | None = None,
        max_concurrent: int = 1,
        enabled: bool = True,
    ) -> Schedule:
        if not playbook_id.strip():
            raise ValueError("playbook_id must be non-empty")
        if not cron_expression.strip():
            raise ValueError("cron_expression must be non-empty")
        return await asyncio.to_thread(
            self._create_sync,
            playbook_id=playbook_id,
            cron_expression=cron_expression,
            timezone_name=timezone,
            args=dict(args or {}),
            max_concurrent=max_concurrent,
            enabled=enabled,
        )

    def _get_sync(self, schedule_id: str) -> Schedule | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id=?", (schedule_id,)
            ).fetchone()
            return self._row_to_schedule(row) if row else None
        finally:
            conn.close()

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        return await asyncio.to_thread(self._get_sync, schedule_id)

    def _list_sync(
        self,
        *,
        playbook_id: str | None,
        only_enabled: bool,
    ) -> list[Schedule]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM schedules WHERE 1=1"
            params: list[Any] = []
            if playbook_id is not None:
                sql += " AND playbook_id=?"
                params.append(playbook_id)
            if only_enabled:
                sql += " AND enabled=1"
            sql += " ORDER BY created_at ASC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_schedule(r) for r in rows]
        finally:
            conn.close()

    async def list_schedules(
        self,
        *,
        playbook_id: str | None = None,
        only_enabled: bool = False,
    ) -> list[Schedule]:
        return await asyncio.to_thread(
            self._list_sync,
            playbook_id=playbook_id,
            only_enabled=only_enabled,
        )

    def _update_sync(
        self, schedule_id: str, updates: dict[str, Any]
    ) -> Schedule | None:
        existing = self._get_sync(schedule_id)
        if existing is None:
            return None
        cols: list[str] = []
        params: list[Any] = []
        recompute_next = False
        if "cron_expression" in updates and updates["cron_expression"] is not None:
            new_cron = str(updates["cron_expression"]).strip()
            if not validate(new_cron):
                raise ValueError(f"invalid cron_expression: {new_cron!r}")
            cols.append("cron_expression=?")
            params.append(new_cron)
            existing.cron_expression = new_cron
            recompute_next = True
        if "timezone" in updates and updates["timezone"] is not None:
            new_tz = str(updates["timezone"]).strip() or "UTC"
            cols.append("timezone=?")
            params.append(new_tz)
            existing.timezone = new_tz
            recompute_next = True
        if "enabled" in updates and updates["enabled"] is not None:
            cols.append("enabled=?")
            params.append(1 if bool(updates["enabled"]) else 0)
            existing.enabled = bool(updates["enabled"])
            # Re-enable should refresh next_run_at relative to now.
            if existing.enabled:
                recompute_next = True
        if "args" in updates and updates["args"] is not None:
            args = dict(updates["args"])
            cols.append("args_json=?")
            params.append(json.dumps(args))
        if (
            "max_concurrent" in updates
            and updates["max_concurrent"] is not None
        ):
            cols.append("max_concurrent=?")
            params.append(max(1, int(updates["max_concurrent"])))
        if recompute_next:
            try:
                next_dt = next_after(
                    existing.cron_expression,
                    datetime.now(timezone.utc),
                    tz=existing.timezone,
                )
            except CronParseError as exc:
                raise ValueError(str(exc)) from exc
            cols.append("next_run_at=?")
            params.append(next_dt.timestamp())
        if not cols:
            return existing
        params.append(schedule_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE schedules SET {', '.join(cols)} WHERE id=?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_sync(schedule_id)

    async def update_schedule(
        self, schedule_id: str, updates: dict[str, Any]
    ) -> Schedule | None:
        return await asyncio.to_thread(
            self._update_sync, schedule_id, updates
        )

    def _delete_sync(self, schedule_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT id FROM schedules WHERE id=?", (schedule_id,)
            )
            if cur.fetchone() is None:
                return False
            conn.execute(
                "DELETE FROM run_history WHERE schedule_id=?",
                (schedule_id,),
            )
            conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    async def delete_schedule(self, schedule_id: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, schedule_id)

    # ---------- next_run_at helpers -------------------------------------

    def _set_next_run_sync(
        self, schedule_id: str, next_run_at: float | None
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE schedules SET next_run_at=? WHERE id=?",
                (next_run_at, schedule_id),
            )
            conn.commit()
        finally:
            conn.close()

    async def set_next_run(
        self, schedule_id: str, next_run_at: float | None
    ) -> None:
        await asyncio.to_thread(
            self._set_next_run_sync, schedule_id, next_run_at
        )

    def _due_now_sync(self, *, now: float) -> list[Schedule]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE enabled=1"
                " AND next_run_at IS NOT NULL"
                " AND next_run_at <= ?"
                " ORDER BY next_run_at ASC",
                (now,),
            ).fetchall()
            return [self._row_to_schedule(r) for r in rows]
        finally:
            conn.close()

    async def due_now(self, *, now: float | None = None) -> list[Schedule]:
        return await asyncio.to_thread(
            self._due_now_sync, now=(now if now is not None else time.time())
        )

    def _record_fire_sync(
        self,
        schedule_id: str,
        *,
        last_run_at: float,
        last_status: str,
        next_run_at: float | None,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE schedules SET last_run_at=?, last_status=?,"
                " next_run_at=? WHERE id=?",
                (last_run_at, last_status, next_run_at, schedule_id),
            )
            conn.commit()
        finally:
            conn.close()

    async def record_fire(
        self,
        schedule_id: str,
        *,
        last_run_at: float,
        last_status: str,
        next_run_at: float | None,
    ) -> None:
        await asyncio.to_thread(
            self._record_fire_sync,
            schedule_id,
            last_run_at=last_run_at,
            last_status=last_status,
            next_run_at=next_run_at,
        )

    # ---------- run history --------------------------------------------

    def _record_run_sync(
        self,
        *,
        schedule_id: str,
        started_at: float,
        finished_at: float | None,
        status: str,
        output_summary: str | None,
        trace_id: str | None,
    ) -> RunRecord:
        rec = RunRecord(
            id=new_run_id(),
            schedule_id=schedule_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_summary=output_summary,
            trace_id=trace_id,
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO run_history (id, schedule_id, started_at,"
                " finished_at, status, output_summary, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.schedule_id,
                    rec.started_at,
                    rec.finished_at,
                    rec.status,
                    rec.output_summary,
                    rec.trace_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def record_run(
        self,
        *,
        schedule_id: str,
        started_at: float,
        finished_at: float | None = None,
        status: str = "ok",
        output_summary: str | None = None,
        trace_id: str | None = None,
    ) -> RunRecord:
        return await asyncio.to_thread(
            self._record_run_sync,
            schedule_id=schedule_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_summary=output_summary,
            trace_id=trace_id,
        )

    def _history_sync(
        self, schedule_id: str, *, limit: int
    ) -> list[RunRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM run_history WHERE schedule_id=?"
                " ORDER BY started_at DESC LIMIT ?",
                (schedule_id, max(1, min(int(limit), 1000))),
            ).fetchall()
            return [self._row_to_run(r) for r in rows]
        finally:
            conn.close()

    async def history(
        self, schedule_id: str, *, limit: int = 20
    ) -> list[RunRecord]:
        return await asyncio.to_thread(
            self._history_sync, schedule_id, limit=limit
        )

    # ---------- recovery -----------------------------------------------

    async def recover_state(self) -> dict[str, Any]:
        """Recompute ``next_run_at`` for every schedule.

        Called once on startup so a process restart (and the resulting
        loss of in-memory cron clocks) doesn't drop scheduled fires
        on the floor. Disabled schedules are left alone so toggling
        them back on later doesn't immediately fire a stale tick.
        """

        schedules = await self.list_schedules()
        recovered = 0
        skipped = 0
        errors = 0
        now = datetime.now(timezone.utc)
        for sched in schedules:
            if not sched.enabled:
                skipped += 1
                continue
            try:
                next_dt = next_after(
                    sched.cron_expression, now, tz=sched.timezone
                )
            except CronParseError:
                errors += 1
                continue
            await self.set_next_run(sched.id, next_dt.timestamp())
            recovered += 1
        return {
            "ok": True,
            "total": len(schedules),
            "recovered": recovered,
            "skipped_disabled": skipped,
            "errors": errors,
        }


# ---------- module-level singleton ------------------------------------------


_singleton: SchedulerStore | None = None


def get_store() -> SchedulerStore:
    global _singleton
    if _singleton is None:
        _singleton = SchedulerStore()
    return _singleton


def reset_store() -> None:
    """Drop the cached singleton — used by tests + the
    ``TARS_SCHEDULER_DB_PATH`` env override."""

    global _singleton
    _singleton = None
