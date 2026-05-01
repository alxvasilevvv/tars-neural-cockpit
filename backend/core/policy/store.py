"""SQLite-backed confirmation queue for the policy gate.

Reuses the meeet SQLite DB so local-first persistence stays in one
place. Single-table schema kept on top of the existing one with
``CREATE TABLE IF NOT EXISTS``.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from backend.core.meeet.store import _resolve_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS confirmations (
    token TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    slug TEXT NOT NULL,
    action_id TEXT NOT NULL,
    args TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at REAL,
    result TEXT,
    expires_at REAL,
    requested_by TEXT,
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_confirmations_status_ts
    ON confirmations (status, created_at);
"""


DEFAULT_TTL_S = 300.0  # 5 minutes


def _new_token() -> str:
    return "cfm_" + secrets.token_urlsafe(9)


@dataclass(frozen=True)
class PendingConfirmation:
    token: str
    created_at: float
    slug: str
    action_id: str
    args: dict[str, Any]
    status: str
    resolved_at: float | None
    result: dict[str, Any] | None
    expires_at: float | None
    requested_by: str | None
    trace_id: str | None


class PolicyStore:
    """Confirmation queue persisted in the meeet sqlite DB."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = (
            _resolve_db_path() if db_path is None else os.path.expanduser(db_path)
        )
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> PendingConfirmation:
        try:
            args = json.loads(row["args"])
        except (json.JSONDecodeError, TypeError):
            args = {}
        result = None
        if row["result"]:
            try:
                result = json.loads(row["result"])
            except (json.JSONDecodeError, TypeError):
                result = None
        return PendingConfirmation(
            token=row["token"],
            created_at=row["created_at"],
            slug=row["slug"],
            action_id=row["action_id"],
            args=args,
            status=row["status"],
            resolved_at=row["resolved_at"],
            result=result,
            expires_at=row["expires_at"],
            requested_by=row["requested_by"],
            trace_id=row["trace_id"],
        )

    # -- sync helpers -----------------------------------------------------

    def _create_sync(
        self,
        *,
        slug: str,
        action_id: str,
        args: dict[str, Any],
        ttl_s: float,
        requested_by: str | None,
        trace_id: str | None,
    ) -> str:
        token = _new_token()
        now = time.time()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO confirmations
                    (token, created_at, slug, action_id, args, status, expires_at, requested_by, trace_id)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    token,
                    now,
                    slug,
                    action_id,
                    json.dumps(args, separators=(",", ":")),
                    now + ttl_s,
                    requested_by,
                    trace_id,
                ),
            )
        finally:
            conn.close()
        return token

    def _get_sync(self, token: str) -> Optional[PendingConfirmation]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM confirmations WHERE token=?",
                (token,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    def _resolve_sync(
        self, token: str, status: str, result: Mapping[str, Any] | None
    ) -> Optional[PendingConfirmation]:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                UPDATE confirmations
                SET status=?, resolved_at=?, result=?
                WHERE token=? AND status='pending'
                """,
                (
                    status,
                    time.time(),
                    json.dumps(dict(result or {}), separators=(",", ":")),
                    token,
                ),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM confirmations WHERE token=?",
                (token,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    def _list_sync(self, status: str | None, limit: int) -> list[PendingConfirmation]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM confirmations WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM confirmations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        finally:
            conn.close()
        return [self._row(r) for r in rows]

    def _expire_sync(self, before_ts: float) -> list[PendingConfirmation]:
        """Atomically expire any ``pending`` rows whose TTL has elapsed.

        Two-step inside one connection so a concurrent confirm/cancel
        cannot win the race: first ``SELECT`` the candidates (so we can
        emit per-token ``policy.expired`` events upstream), then
        ``UPDATE`` them by primary key. The previous one-step UPDATE
        returned only a count and left the cockpit timeline silent
        about which tokens just expired.
        """

        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT * FROM confirmations
                WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < ?
                ORDER BY expires_at ASC
                """,
                (before_ts,),
            )
            rows = cur.fetchall()
            if not rows:
                return []
            now = time.time()
            tokens = [r["token"] for r in rows]
            placeholders = ",".join("?" for _ in tokens)
            conn.execute(
                f"""
                UPDATE confirmations
                SET status='expired', resolved_at=?
                WHERE status='pending' AND token IN ({placeholders})
                """,
                (now, *tokens),
            )
            # Re-fetch the freshly updated rows so the caller's
            # PendingConfirmation views carry status='expired' /
            # resolved_at=now (not the pre-update snapshot).
            cur2 = conn.execute(
                f"SELECT * FROM confirmations WHERE token IN ({placeholders}) "
                "ORDER BY resolved_at ASC",
                tokens,
            )
            return [self._row(r) for r in cur2.fetchall()]
        finally:
            conn.close()

    # -- async API --------------------------------------------------------

    async def create(
        self,
        *,
        slug: str,
        action_id: str,
        args: Mapping[str, Any],
        ttl_s: float = DEFAULT_TTL_S,
        requested_by: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self._create_sync,
            slug=slug,
            action_id=action_id,
            args=dict(args),
            ttl_s=ttl_s,
            requested_by=requested_by,
            trace_id=trace_id,
        )

    async def get(self, token: str) -> Optional[PendingConfirmation]:
        return await asyncio.to_thread(self._get_sync, token)

    async def resolve(
        self,
        token: str,
        *,
        status: str,
        result: Mapping[str, Any] | None = None,
    ) -> Optional[PendingConfirmation]:
        if status not in {"confirmed", "cancelled", "expired", "failed"}:
            raise ValueError(f"unknown resolution status: {status}")
        return await asyncio.to_thread(self._resolve_sync, token, status, result)

    async def list_pending(self, limit: int = 50) -> list[PendingConfirmation]:
        return await asyncio.to_thread(self._list_sync, "pending", max(1, min(limit, 1000)))

    async def list_recent(self, limit: int = 50) -> list[PendingConfirmation]:
        return await asyncio.to_thread(self._list_sync, None, max(1, min(limit, 1000)))

    async def expire_stale(self) -> list[PendingConfirmation]:
        """Expire any pending confirmation whose TTL has elapsed.

        Returns the list of newly-expired rows. Callers that only care
        about the count should use ``len(await store.expire_stale())``.
        """

        return await asyncio.to_thread(self._expire_sync, time.time())


_SINGLETON: Optional[PolicyStore] = None


def get_policy_store() -> PolicyStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = PolicyStore()
    return _SINGLETON


def reset_policy_store() -> None:
    global _SINGLETON
    _SINGLETON = None
