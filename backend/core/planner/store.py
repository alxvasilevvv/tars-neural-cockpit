"""SQLite-backed planner store.

The store persists every synthesized :class:`Plan` so the cockpit can
render an "approval inbox" of pending plans across process restarts,
and the runner (follow-up PR) can resume after a crash. Schema is
deliberately additive — new columns can land via the
``_ADDITIVE_COLUMNS`` migration tuple without rewriting the file.

The DB lives at ``~/.tars/planner.sqlite`` by default; override with
``TARS_PLANNER_DB_PATH``. Set ``PLANNER_STORE=disabled`` to short-
circuit (the synthesizer still works, but ``insert`` becomes a no-op
returning a transient in-memory plan id).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from .types import Plan, PlanStatus, PlanStep


_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    rationale TEXT,
    model TEXT NOT NULL DEFAULT 'heuristic-v1',
    pack_slug TEXT,
    playbook_id TEXT,
    thread_id TEXT,
    trace_id TEXT,
    estimated_cost_usd REAL,
    error TEXT,
    steps_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_thread ON plans(thread_id);
CREATE INDEX IF NOT EXISTS idx_plans_created ON plans(created_at DESC);
"""

# Additive migrations applied after the base schema. Append new
# (column_name, sqlite_type) tuples here when extending the row.
_ADDITIVE_COLUMNS: tuple[tuple[str, str], ...] = ()


def _new_plan_id() -> str:
    """Return a fresh plan id (``pln_<urlsafe>``)."""

    return f"pln_{secrets.token_urlsafe(8)}"


def _resolve_db_path(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.getenv("TARS_PLANNER_DB_PATH")
    if env:
        return env
    home = Path.home() / ".tars"
    home.mkdir(parents=True, exist_ok=True)
    return str(home / "planner.sqlite")


def _disabled() -> bool:
    return (os.getenv("PLANNER_STORE") or "").strip().lower() == "disabled"


class PlannerStore:
    """Async-friendly façade over the planner SQLite DB.

    Methods that read or write the DB are ``async`` and run the
    underlying SQLite calls via :func:`asyncio.to_thread` to keep the
    event loop snappy.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.enabled = not _disabled()
        self.db_path = _resolve_db_path(db_path) if self.enabled else ":memory:"
        if self.enabled:
            self._ensure_schema()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(plans)").fetchall()
            }
            for col, decl in _ADDITIVE_COLUMNS:
                if col not in existing:
                    conn.execute(f"ALTER TABLE plans ADD COLUMN {col} {decl}")

    @staticmethod
    def _row_to_plan(row: sqlite3.Row) -> Plan:
        steps_raw = json.loads(row["steps_json"] or "[]")
        steps = tuple(PlanStep.from_dict(s) for s in steps_raw)
        return Plan(
            id=row["id"],
            goal=row["goal"],
            steps=steps,
            status=PlanStatus(row["status"]),
            rationale=row["rationale"] or "",
            model=row["model"] or "heuristic-v1",
            pack_slug=row["pack_slug"],
            playbook_id=row["playbook_id"],
            thread_id=row["thread_id"],
            trace_id=row["trace_id"],
            estimated_cost_usd=(
                float(row["estimated_cost_usd"])
                if row["estimated_cost_usd"] is not None
                else None
            ),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            error=row["error"],
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _insert_sync(self, plan: Plan) -> Plan:
        now = time.time()
        plan_id = plan.id or _new_plan_id()
        steps_json = json.dumps([s.to_dict() for s in plan.steps])
        if not self.enabled:
            return Plan(
                id=plan_id,
                goal=plan.goal,
                steps=plan.steps,
                status=plan.status,
                rationale=plan.rationale,
                model=plan.model,
                pack_slug=plan.pack_slug,
                playbook_id=plan.playbook_id,
                thread_id=plan.thread_id,
                trace_id=plan.trace_id,
                estimated_cost_usd=plan.estimated_cost_usd,
                created_at=now,
                updated_at=now,
                error=plan.error,
            )
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO plans (
                    id, created_at, updated_at, goal, status, rationale, model,
                    pack_slug, playbook_id, thread_id, trace_id,
                    estimated_cost_usd, error, steps_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan_id,
                    now,
                    now,
                    plan.goal,
                    plan.status.value,
                    plan.rationale or None,
                    plan.model,
                    plan.pack_slug,
                    plan.playbook_id,
                    plan.thread_id,
                    plan.trace_id,
                    plan.estimated_cost_usd,
                    plan.error,
                    steps_json,
                ),
            )
            row = conn.execute(
                "SELECT * FROM plans WHERE id=?", (plan_id,)
            ).fetchone()
            assert row is not None  # we just inserted it
            return self._row_to_plan(row)

    async def insert(self, plan: Plan) -> Plan:
        return await asyncio.to_thread(self._insert_sync, plan)

    def _get_sync(self, plan_id: str) -> Optional[Plan]:
        if not self.enabled:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM plans WHERE id=?", (plan_id,)
            ).fetchone()
            return self._row_to_plan(row) if row else None

    async def get(self, plan_id: str) -> Optional[Plan]:
        return await asyncio.to_thread(self._get_sync, plan_id)

    def _list_sync(
        self,
        *,
        status: Optional[PlanStatus] = None,
        thread_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Plan]:
        if not self.enabled:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status=?")
            params.append(status.value)
        if thread_id is not None:
            clauses.append("thread_id=?")
            params.append(thread_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM plans {where} "
            f"ORDER BY created_at DESC LIMIT ?"
        )
        params.append(int(max(1, min(limit, 1000))))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_plan(r) for r in rows]

    async def list(
        self,
        *,
        status: Optional[PlanStatus] = None,
        thread_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Plan]:
        return await asyncio.to_thread(
            self._list_sync,
            status=status,
            thread_id=thread_id,
            limit=limit,
        )

    def _set_status_sync(
        self,
        plan_id: str,
        new_status: PlanStatus,
        *,
        error: Optional[str] = None,
    ) -> Optional[Plan]:
        if not self.enabled:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM plans WHERE id=?", (plan_id,)
            ).fetchone()
            if row is None:
                return None
            current = PlanStatus(row["status"])
            if current.is_terminal() and current != new_status:
                # Refuse silently: terminal statuses are immutable. The
                # caller can read it back via ``get(...)`` to confirm.
                return self._row_to_plan(
                    conn.execute(
                        "SELECT * FROM plans WHERE id=?", (plan_id,)
                    ).fetchone()
                )
            now = time.time()
            conn.execute(
                "UPDATE plans SET status=?, updated_at=?, error=? WHERE id=?",
                (new_status.value, now, error, plan_id),
            )
            row2 = conn.execute(
                "SELECT * FROM plans WHERE id=?", (plan_id,)
            ).fetchone()
            return self._row_to_plan(row2) if row2 else None

    async def set_status(
        self,
        plan_id: str,
        new_status: PlanStatus,
        *,
        error: Optional[str] = None,
    ) -> Optional[Plan]:
        return await asyncio.to_thread(
            self._set_status_sync, plan_id, new_status, error=error
        )

    def _delete_sync(self, plan_id: str) -> bool:
        if not self.enabled:
            return False
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM plans WHERE id=?", (plan_id,))
            return cur.rowcount > 0

    async def delete(self, plan_id: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, plan_id)

    def _stats_sync(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "total": 0, "by_status": {}}
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM plans GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: int(r["c"]) for r in by_status_rows}
        return {"enabled": True, "total": int(total), "by_status": by_status}

    async def stats(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync)


_SINGLETON: PlannerStore | None = None


def get_planner_store() -> PlannerStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = PlannerStore()
    return _SINGLETON


def reset_planner_store() -> None:
    """Test helper — drop the cached singleton so config is re-read."""

    global _SINGLETON
    _SINGLETON = None
