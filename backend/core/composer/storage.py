"""Composer SQLite persistence — :class:`ComposerStore`.

Two tables in ``~/.tars/composer.sqlite``:

- ``plans`` — full ``ComposerPlan`` JSON keyed by ``plan_id``. The
  ``state`` and ``created_at`` columns are mirrored so the recent
  list can be paged without parsing JSON.
- ``applied_ops`` — one row per ``apply_plan`` success, recording
  the op indices, backup dir, and emitted receipt ids. Used by the
  rollback path and the receipts-correlation panel.

CRUD is synchronous on purpose — the request handlers wrap calls
in ``asyncio.to_thread`` when they need to. The module exposes a
process-wide singleton via :func:`get_store` so the HTTP router and
the executor can share a single SQLite connection pool.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import threading
from pathlib import Path
from typing import Any, Iterable

from .types import ComposerPlan


DEFAULT_DB_PATH = "~/.tars/composer.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    transcript TEXT NOT NULL,
    intent_summary TEXT NOT NULL,
    plan_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plans_state ON plans (state);
CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans (created_at DESC);

CREATE TABLE IF NOT EXISTS applied_ops (
    plan_id TEXT PRIMARY KEY,
    applied_at REAL NOT NULL,
    op_indices TEXT NOT NULL,
    backup_dir TEXT,
    receipts TEXT NOT NULL,
    rolled_back_at REAL
);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.environ.get("TARS_COMPOSER_DB") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


class ComposerStore:
    """Thread-safe SQLite mirror of composer plans + applied-op log."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self.db_path = _resolve_db_path(db_path)
        self._lock = threading.Lock()
        self._init_done = False

    # ---- init --------------------------------------------------------

    def _init(self) -> None:
        if self._init_done:
            return
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("PRAGMA journal_mode=WAL;")
            conn.executescript(_SCHEMA)
            conn.commit()
        self._init_done = True

    def _connect(self) -> sqlite3.Connection:
        self._init()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- plans -------------------------------------------------------

    def save_plan(self, plan: ComposerPlan) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO plans "
                    "(plan_id, state, created_at, transcript, "
                    " intent_summary, plan_json) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(plan_id) DO UPDATE SET "
                    "  state=excluded.state, "
                    "  intent_summary=excluded.intent_summary, "
                    "  plan_json=excluded.plan_json",
                    (
                        plan.plan_id,
                        plan.state,
                        plan.created_at.timestamp(),
                        plan.transcript,
                        plan.intent_summary,
                        json.dumps(plan.to_dict()),
                    ),
                )
                conn.commit()

    def load_plan(self, plan_id: str) -> ComposerPlan | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT plan_json FROM plans WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
        if row is None:
            return None
        try:
            return ComposerPlan.from_dict(json.loads(row["plan_json"]))
        except (json.JSONDecodeError, ValueError):
            return None

    def list_plans(self, *, limit: int = 20) -> list[ComposerPlan]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT plan_json FROM plans "
                    "ORDER BY created_at DESC LIMIT ?",
                    (max(1, int(limit)),),
                ).fetchall()
        out: list[ComposerPlan] = []
        for r in rows:
            try:
                out.append(ComposerPlan.from_dict(json.loads(r["plan_json"])))
            except (json.JSONDecodeError, ValueError):
                continue
        return out

    def set_state(self, plan_id: str, state: str) -> bool:
        """Persist a state transition without re-serialising the body."""

        plan = self.load_plan(plan_id)
        if plan is None:
            return False
        plan.state = state
        self.save_plan(plan)
        return True

    # ---- applied ops -------------------------------------------------

    def record_applied(
        self,
        *,
        plan_id: str,
        applied_ops: Iterable[int],
        backup_dir: str | None,
        receipts: Iterable[str],
    ) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO applied_ops "
                    "(plan_id, applied_at, op_indices, backup_dir, receipts) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(plan_id) DO UPDATE SET "
                    "  applied_at=excluded.applied_at, "
                    "  op_indices=excluded.op_indices, "
                    "  backup_dir=excluded.backup_dir, "
                    "  receipts=excluded.receipts",
                    (
                        plan_id,
                        time.time(),
                        json.dumps(list(int(i) for i in applied_ops)),
                        backup_dir,
                        json.dumps(list(receipts)),
                    ),
                )
                conn.commit()

    def get_applied(self, plan_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT plan_id, applied_at, op_indices, backup_dir, "
                    " receipts, rolled_back_at FROM applied_ops "
                    "WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
        if row is None:
            return None
        return {
            "plan_id": row["plan_id"],
            "applied_at": float(row["applied_at"]),
            "op_indices": json.loads(row["op_indices"] or "[]"),
            "backup_dir": row["backup_dir"],
            "receipts": json.loads(row["receipts"] or "[]"),
            "rolled_back_at": row["rolled_back_at"],
        }

    def mark_rolled_back(self, plan_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE applied_ops SET rolled_back_at = ? "
                    "WHERE plan_id = ?",
                    (time.time(), plan_id),
                )
                conn.commit()

    def delete_plan(self, plan_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))
                conn.execute(
                    "DELETE FROM applied_ops WHERE plan_id = ?", (plan_id,)
                )
                conn.commit()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_STORE: ComposerStore | None = None
_STORE_LOCK = threading.Lock()


def get_store() -> ComposerStore | None:
    """Return the process-wide composer store. ``None`` when disabled.

    Disabling is opt-in via ``TARS_COMPOSER_STORE=disabled`` so the
    rest of the surface can degrade to in-memory operation in tests
    that don't care about persistence.
    """

    flag = (os.environ.get("TARS_COMPOSER_STORE") or "").strip().lower()
    if flag in ("disabled", "off", "0", "false", "no"):
        return None
    global _STORE
    if _STORE is not None:
        return _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ComposerStore()
    return _STORE


def reset_store() -> None:
    """Clear the singleton — used by tests pointing at temp DBs."""

    global _STORE
    _STORE = None
