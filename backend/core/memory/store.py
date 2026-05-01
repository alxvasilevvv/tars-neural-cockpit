"""SQLite-backed per-pack memory store.

Schema lives at ``~/.tars/memory.sqlite`` (override via
``TARS_MEMORY_DB_PATH``, ``MEMORY_STORE=disabled`` to short-circuit
the entire layer for tests / packaged distros that don't want the
file).

The schema is deliberately minimal — one row per ``(pack_slug, key)``
with the value stored as a JSON blob. WAL journal mode + a busy
timeout matches the pattern used by other TARS stores
(``backend.core.chat.store``, ``backend.core.meeet.store``).

Methods are exposed through ``async def`` wrappers (using
``asyncio.to_thread``) so the chat / agents loops never block on
SQLite even when the WAL is contended.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from .models import MemoryEntry


log = logging.getLogger("tars.memory.store")


_DEFAULT_DB = Path.home() / ".tars" / "memory.sqlite"


def _is_disabled() -> bool:
    raw = (os.getenv("MEMORY_STORE") or "").strip().lower()
    return raw in {"disabled", "off", "0", "no", "false"}


def _resolve_db_path() -> Optional[Path]:
    if _is_disabled():
        return None
    override = os.getenv("TARS_MEMORY_DB_PATH")
    return Path(override) if override else _DEFAULT_DB


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pack_memory (
    id TEXT PRIMARY KEY,
    pack_slug TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'fact',
    ttl_until REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    source TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(pack_slug, key)
);
CREATE INDEX IF NOT EXISTS idx_pack_memory_pack ON pack_memory(pack_slug);
CREATE INDEX IF NOT EXISTS idx_pack_memory_kind ON pack_memory(pack_slug, kind);
CREATE INDEX IF NOT EXISTS idx_pack_memory_ttl ON pack_memory(ttl_until);
CREATE INDEX IF NOT EXISTS idx_pack_memory_updated ON pack_memory(updated_at);
"""


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return f"mem_{uuid.uuid4().hex[:14]}"


class MemoryStore:
    """Per-pack key-value store with TTL eviction."""

    def __init__(self, *, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path if db_path is not None else _resolve_db_path()
        self.enabled = self.db_path is not None
        if self.enabled:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()

    # -- connection helpers --

    def _connect(self) -> sqlite3.Connection:
        if not self.enabled:
            raise RuntimeError("memory store disabled")
        conn = sqlite3.connect(
            str(self.db_path), timeout=5.0, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- row mapping --

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        try:
            value = json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            value = None
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return MemoryEntry(
            id=row["id"],
            pack_slug=row["pack_slug"],
            key=row["key"],
            value=value,
            kind=row["kind"] or "fact",
            ttl_until=row["ttl_until"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source=row["source"],
            metadata=metadata,
        )

    # -- write API --

    def _upsert_sync(
        self,
        *,
        pack_slug: str,
        key: str,
        value: Any,
        kind: str,
        ttl_until: float | None,
        source: str | None,
        metadata: dict[str, Any] | None,
    ) -> MemoryEntry:
        now = _now()
        value_json = json.dumps(value, separators=(",", ":"), default=str)
        meta_json = json.dumps(
            metadata or {}, separators=(",", ":"), default=str
        )
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT id, created_at FROM pack_memory "
                "WHERE pack_slug = ? AND key = ?",
                (pack_slug, key),
            ).fetchone()
            if existing is None:
                row_id = _new_id()
                conn.execute(
                    """
                    INSERT INTO pack_memory (
                        id, pack_slug, key, value_json, kind,
                        ttl_until, created_at, updated_at, source,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id, pack_slug, key, value_json, kind,
                        ttl_until, now, now, source, meta_json,
                    ),
                )
            else:
                row_id = existing["id"]
                conn.execute(
                    """
                    UPDATE pack_memory
                    SET value_json = ?, kind = ?, ttl_until = ?,
                        updated_at = ?, source = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        value_json, kind, ttl_until, now, source,
                        meta_json, row_id,
                    ),
                )
            row = conn.execute(
                "SELECT * FROM pack_memory WHERE id = ?", (row_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_entry(row)

    async def upsert(
        self,
        *,
        pack_slug: str,
        key: str,
        value: Any,
        kind: str = "fact",
        ttl_until: float | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._upsert_sync,
            pack_slug=pack_slug.strip(),
            key=key.strip(),
            value=value,
            kind=(kind or "fact").strip() or "fact",
            ttl_until=ttl_until,
            source=source,
            metadata=metadata,
        )

    # -- read API --

    def _get_sync(
        self,
        *,
        pack_slug: str,
        key: str,
        include_expired: bool,
    ) -> MemoryEntry | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM pack_memory WHERE pack_slug = ? AND key = ?",
                (pack_slug, key),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        entry = self._row_to_entry(row)
        if not include_expired and entry.is_expired():
            return None
        return entry

    async def get(
        self,
        *,
        pack_slug: str,
        key: str,
        include_expired: bool = False,
    ) -> MemoryEntry | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._get_sync,
            pack_slug=pack_slug.strip(),
            key=key.strip(),
            include_expired=include_expired,
        )

    def _list_sync(
        self,
        *,
        pack_slug: str,
        kind: str | None,
        key_prefix: str | None,
        limit: int,
        include_expired: bool,
    ) -> list[MemoryEntry]:
        clauses = ["pack_slug = ?"]
        params: list[Any] = [pack_slug]
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if key_prefix:
            clauses.append("key LIKE ?")
            params.append(key_prefix + "%")
        if not include_expired:
            now = _now()
            clauses.append("(ttl_until IS NULL OR ttl_until > ?)")
            params.append(now)
        params.append(int(limit))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM pack_memory WHERE {' AND '.join(clauses)} "
                f"ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_entry(r) for r in rows]

    async def list(
        self,
        *,
        pack_slug: str,
        kind: str | None = None,
        key_prefix: str | None = None,
        limit: int = 100,
        include_expired: bool = False,
    ) -> list[MemoryEntry]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._list_sync,
            pack_slug=pack_slug.strip(),
            kind=kind,
            key_prefix=key_prefix,
            limit=max(1, min(int(limit), 1000)),
            include_expired=include_expired,
        )

    # -- delete / purge API --

    def _delete_sync(self, *, pack_slug: str, key: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM pack_memory WHERE pack_slug = ? AND key = ?",
                (pack_slug, key),
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    async def delete(self, *, pack_slug: str, key: str) -> bool:
        if not self.enabled:
            return False
        return await asyncio.to_thread(
            self._delete_sync,
            pack_slug=pack_slug.strip(),
            key=key.strip(),
        )

    def _purge_expired_sync(
        self, *, pack_slug: str | None
    ) -> int:
        clauses = ["ttl_until IS NOT NULL", "ttl_until <= ?"]
        params: list[Any] = [_now()]
        if pack_slug:
            clauses.append("pack_slug = ?")
            params.append(pack_slug)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"DELETE FROM pack_memory WHERE {' AND '.join(clauses)}",
                params,
            )
            return cur.rowcount
        finally:
            conn.close()

    async def purge_expired(
        self, *, pack_slug: str | None = None
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "memory_store_disabled"}
        deleted = await asyncio.to_thread(
            self._purge_expired_sync, pack_slug=pack_slug,
        )
        return {"ok": True, "deleted": deleted, "pack_slug": pack_slug}

    # -- summary helpers --

    def _stats_sync(self, *, pack_slug: str | None) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if pack_slug:
            clauses.append("pack_slug = ?")
            params.append(pack_slug)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = self._connect()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM pack_memory {where}", params,
            ).fetchone()[0]
            now = _now()
            live_params = list(params)
            live_clauses = list(clauses)
            live_clauses.append(
                "(ttl_until IS NULL OR ttl_until > ?)"
            )
            live_params.append(now)
            live_where = "WHERE " + " AND ".join(live_clauses)
            live = conn.execute(
                f"SELECT COUNT(*) FROM pack_memory {live_where}", live_params,
            ).fetchone()[0]
            kinds_rows = conn.execute(
                f"SELECT kind, COUNT(*) AS n FROM pack_memory {where} "
                f"GROUP BY kind ORDER BY n DESC", params,
            ).fetchall()
        finally:
            conn.close()
        return {
            "ok": True,
            "pack_slug": pack_slug,
            "total": total,
            "live": live,
            "expired": total - live,
            "kinds": {r["kind"]: r["n"] for r in kinds_rows},
        }

    async def stats(
        self, *, pack_slug: str | None = None
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "memory_store_disabled"}
        return await asyncio.to_thread(
            self._stats_sync, pack_slug=pack_slug,
        )


# ---------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------


_SINGLETON: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MemoryStore()
    return _SINGLETON


def reset_memory_store() -> None:
    """Test helper — drops the cached singleton."""

    global _SINGLETON
    _SINGLETON = None
