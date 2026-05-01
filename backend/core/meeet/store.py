"""SQLite-backed durable buffer for meeet events.

The store is the local-first guarantee: every event flows through the
SQLite WAL DB before any network attempt. If the meeet ingest is offline
or unset, events sit on disk with ``pushed=0`` and can be flushed later
via :meth:`MeeetStore.replay_unpushed` or the
``POST /api/meeet/replay`` endpoint.

Disable with ``MEEET_STORE=disabled`` (events go straight to ingest /
local-log only). DB path is ``MEEET_STORE_PATH`` (default
``~/.tars/meeet.sqlite``).

The store is intentionally stdlib-only — sqlite3 + asyncio.to_thread.
No SQLAlchemy, no migrations framework. Schema is single-table-ish and
forward-compatible: new columns get added with ``IF NOT EXISTS`` guards.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


DEFAULT_DB_PATH = "~/.tars/meeet.sqlite"

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    trace_id TEXT,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    payload TEXT NOT NULL,
    pushed INTEGER NOT NULL DEFAULT 0,
    pushed_at REAL,
    last_error TEXT,
    session_id TEXT,
    route TEXT,
    ciphertext TEXT,
    envelope TEXT
);
"""

_SCHEMA_INDICES = """
CREATE INDEX IF NOT EXISTS idx_events_pushed_ts
    ON events (pushed, ts);

CREATE INDEX IF NOT EXISTS idx_events_trace
    ON events (trace_id);

CREATE INDEX IF NOT EXISTS idx_events_kind_ts
    ON events (kind, ts DESC);

CREATE INDEX IF NOT EXISTS idx_events_session_ts
    ON events (session_id, ts);
"""

# Forward-compat: if the DB existed before K1 the events table is missing
# session_id / route. Run these between table creation and index creation.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE events ADD COLUMN session_id TEXT",
    "ALTER TABLE events ADD COLUMN route TEXT",
    # Phase L5 — encrypted sync envelope (contract 1.1.0).
    "ALTER TABLE events ADD COLUMN ciphertext TEXT",
    "ALTER TABLE events ADD COLUMN envelope TEXT",
)

# Kept for callers that still reference SCHEMA (e.g. old tests).
SCHEMA = _SCHEMA_TABLE + _SCHEMA_INDICES


@dataclass(frozen=True)
class StoredEvent:
    id: int
    ts: float
    trace_id: str | None
    kind: str
    source: str
    contract_version: str
    payload: dict[str, Any]
    pushed: bool
    pushed_at: float | None
    last_error: str | None
    session_id: str | None = None
    route: str | None = None
    ciphertext: str | None = None
    envelope: dict[str, Any] | None = None


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("MEEET_STORE_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("MEEET_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class MeeetStore:
    """Durable event buffer.

    The store is process-wide; the singleton helper at the bottom is
    enough for the host app. Tests instantiate their own with an
    explicit path.
    """

    def __init__(self, db_path: str | None = None, *, enabled: bool | None = None) -> None:
        self.db_path = _resolve_db_path(db_path) if db_path is None else os.path.expanduser(db_path)
        if enabled is None:
            self.enabled = not _is_disabled()
        else:
            self.enabled = enabled
        if self.enabled:
            self._ensure_schema()

    # -- internal helpers -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            # 1. Table first — IF NOT EXISTS no-ops on an existing DB.
            conn.executescript(_SCHEMA_TABLE)
            # 2. Migrations — ALTER TABLE adds missing columns when the
            #    DB was created before K1. Skip silently when columns
            #    already exist.
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    continue
            # 3. Indices last — they may reference newly-added columns.
            conn.executescript(_SCHEMA_INDICES)
        finally:
            conn.close()

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> StoredEvent:
        try:
            payload = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            payload = {}
        keys = row.keys()
        envelope: dict[str, Any] | None = None
        if "envelope" in keys and row["envelope"]:
            try:
                env_raw = json.loads(row["envelope"])
                if isinstance(env_raw, dict):
                    envelope = env_raw
            except (json.JSONDecodeError, TypeError):
                envelope = None
        return StoredEvent(
            id=row["id"],
            ts=row["ts"],
            trace_id=row["trace_id"],
            kind=row["kind"],
            source=row["source"],
            contract_version=row["contract_version"],
            payload=payload,
            pushed=bool(row["pushed"]),
            pushed_at=row["pushed_at"],
            last_error=row["last_error"],
            session_id=row["session_id"] if "session_id" in keys else None,
            route=row["route"] if "route" in keys else None,
            ciphertext=row["ciphertext"] if "ciphertext" in keys else None,
            envelope=envelope,
        )

    # -- sync impls (run in to_thread) -----------------------------------

    def _insert_sync(self, event: dict[str, Any]) -> int:
        conn = self._connect()
        try:
            envelope = event.get("envelope")
            envelope_json: str | None = None
            if envelope:
                envelope_json = json.dumps(envelope, separators=(",", ":"))
            cur = conn.execute(
                """
                INSERT INTO events (
                    ts, trace_id, kind, source, contract_version, payload,
                    pushed, session_id, route, ciphertext, envelope
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    float(event.get("ts") or time.time()),
                    event.get("trace_id"),
                    str(event.get("kind", "")),
                    str(event.get("source", "tars")),
                    str(event.get("contract_version", "1.0.0")),
                    json.dumps(event.get("payload") or {}, separators=(",", ":")),
                    event.get("session_id"),
                    event.get("route"),
                    event.get("ciphertext"),
                    envelope_json,
                ),
            )
            return cur.lastrowid or 0
        finally:
            conn.close()

    def _mark_pushed_sync(self, event_id: int, error: str | None = None) -> None:
        conn = self._connect()
        try:
            if error is None:
                conn.execute(
                    "UPDATE events SET pushed=1, pushed_at=?, last_error=NULL WHERE id=?",
                    (time.time(), event_id),
                )
            else:
                conn.execute(
                    "UPDATE events SET last_error=? WHERE id=?",
                    (error[:512], event_id),
                )
        finally:
            conn.close()

    def _list_sync(
        self,
        *,
        limit: int,
        since: float | None,
        trace_id: str | None,
        kind: str | None,
        kind_prefix: str | None,
        session_id: str | None,
        only_unpushed: bool,
    ) -> list[StoredEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if since is not None:
            clauses.append("ts >= ?")
            params.append(float(since))
        if trace_id:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if kind_prefix:
            # Defensive escape: SQLite ``LIKE`` treats ``%`` and ``_``
            # (and the explicit escape char) as wildcards. The cockpit
            # passes literal prefixes like ``pair.`` / ``recovery.``
            # so escaping is belt-and-braces, but keeps the contract
            # honest if a future caller uses a stranger prefix.
            escaped = (
                kind_prefix.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            clauses.append("kind LIKE ? ESCAPE '\\'")
            params.append(escaped + "%")
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if only_unpushed:
            clauses.append("pushed = 0")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM events {where} "
            f"ORDER BY id DESC LIMIT ?"
        )
        params.append(int(limit))
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_event(r) for r in rows]

    def _stats_sync(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
            unpushed = conn.execute(
                "SELECT COUNT(*) AS c FROM events WHERE pushed=0"
            ).fetchone()["c"]
            row = conn.execute(
                "SELECT MIN(ts) AS first_ts, MAX(ts) AS last_ts FROM events"
            ).fetchone()
        finally:
            conn.close()
        return {
            "total": total,
            "unpushed": unpushed,
            "first_ts": row["first_ts"],
            "last_ts": row["last_ts"],
            "db_path": self.db_path,
        }

    # -- async public API -------------------------------------------------

    async def insert(self, event: Mapping[str, Any]) -> int | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(self._insert_sync, dict(event))

    async def mark_pushed(self, event_id: int, error: str | None = None) -> None:
        if not self.enabled or event_id <= 0:
            return
        await asyncio.to_thread(self._mark_pushed_sync, event_id, error)

    async def list_events(
        self,
        *,
        limit: int = 100,
        since: float | None = None,
        trace_id: str | None = None,
        kind: str | None = None,
        kind_prefix: str | None = None,
        session_id: str | None = None,
        only_unpushed: bool = False,
    ) -> list[StoredEvent]:
        if not self.enabled:
            return []
        limit = max(1, min(int(limit), 1000))
        return await asyncio.to_thread(
            self._list_sync,
            limit=limit,
            since=since,
            trace_id=trace_id,
            kind=kind,
            kind_prefix=kind_prefix,
            session_id=session_id,
            only_unpushed=only_unpushed,
        )

    async def stats(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        out = await asyncio.to_thread(self._stats_sync)
        out["enabled"] = True
        return out

    async def replay_unpushed(
        self,
        push_callable,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Push pending events through ``push_callable``.

        ``push_callable`` is async and accepts the event payload dict;
        it must raise on transport failure (the store leaves the row
        as unpushed and records ``last_error``). Returns counts.
        """

        if not self.enabled:
            return {"enabled": False, "pushed": 0, "failed": 0, "remaining": 0}
        events = await self.list_events(limit=limit, only_unpushed=True)
        pushed = 0
        failed = 0
        for ev in reversed(events):  # oldest first
            body: dict[str, Any] = {
                "trace_id": ev.trace_id,
                "kind": ev.kind,
                "source": ev.source,
                "contract_version": ev.contract_version,
                "ts": ev.ts,
                "payload": ev.payload,
            }
            if ev.session_id:
                body["session_id"] = ev.session_id
            if ev.route:
                body["route"] = ev.route
            if ev.ciphertext and ev.envelope:
                body["ciphertext"] = ev.ciphertext
                body["envelope"] = ev.envelope
            try:
                await push_callable(body)
            except Exception as exc:
                failed += 1
                await self.mark_pushed(ev.id, error=str(exc))
                continue
            await self.mark_pushed(ev.id)
            pushed += 1
        stats = await self.stats()
        return {
            "enabled": True,
            "scanned": len(events),
            "pushed": pushed,
            "failed": failed,
            "remaining": stats.get("unpushed"),
        }


    async def prune_kind_before(
        self,
        *,
        kind_prefix: str = "",
        kind_suffix: str = "",
        before_unix: float,
    ) -> int:
        """Drop events with ``kind LIKE prefix%suffix`` older than ``before_unix``.

        Returns the number of rows removed. No-op when the store is
        disabled or ``before_unix`` is in the future.
        """

        if not self.enabled:
            return 0
        return await asyncio.to_thread(
            self._prune_sync,
            kind_prefix=kind_prefix,
            kind_suffix=kind_suffix,
            before_unix=float(before_unix),
        )

    def _prune_sync(
        self,
        *,
        kind_prefix: str,
        kind_suffix: str,
        before_unix: float,
    ) -> int:
        # Use LIKE with escaped wildcards. SQLite parameter binding
        # protects us from injection.
        pattern = f"{kind_prefix}%{kind_suffix}"
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM events WHERE kind LIKE ? AND ts < ?",
                (pattern, before_unix),
            )
            return cur.rowcount or 0
        finally:
            conn.close()


_SINGLETON: Optional[MeeetStore] = None


def get_store() -> MeeetStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MeeetStore()
    return _SINGLETON


def reset_store() -> None:
    """Test helper: drop the cached singleton so a new path/env is read."""

    global _SINGLETON
    _SINGLETON = None
