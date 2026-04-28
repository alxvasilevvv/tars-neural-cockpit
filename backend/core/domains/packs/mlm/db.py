"""SQLite-backed downline DB for the MLM pack.

The DB lives at ``~/.tars/downline.sqlite`` (override with
``MLM_DB_PATH``). On first read it self-seeds from
``data/mlm_network.csv`` so legacy callers keep working.

Every read/write is wrapped in :func:`asyncio.to_thread` to keep the
event loop free.

Schema (single table, forward-compatible):

    members(
        handle TEXT PRIMARY KEY,
        sponsor TEXT,
        joined_at TEXT,
        last_active_at TEXT,
        rank TEXT,
        volume_usd REAL,
        notes TEXT,
        updated_at REAL NOT NULL
    )
"""

from __future__ import annotations

import asyncio
import csv
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DB_PATH = "~/.tars/downline.sqlite"
DEFAULT_CSV_PATH = _REPO_ROOT / "data" / "mlm_network.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    handle TEXT PRIMARY KEY,
    sponsor TEXT,
    joined_at TEXT,
    last_active_at TEXT,
    rank TEXT,
    volume_usd REAL,
    notes TEXT,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_members_sponsor ON members (sponsor);
CREATE INDEX IF NOT EXISTS idx_members_rank    ON members (rank);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("MLM_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _csv_path(override: str | None = None) -> Path:
    raw = override or os.getenv("MLM_NETWORK_PATH")
    if raw:
        return Path(os.path.expanduser(raw))
    return DEFAULT_CSV_PATH


@dataclass(frozen=True)
class Member:
    handle: str
    sponsor: Optional[str]
    joined_at: Optional[str]
    last_active_at: Optional[str]
    rank: Optional[str]
    volume_usd: float
    notes: Optional[str]
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "sponsor": self.sponsor,
            "joined_at": self.joined_at,
            "last_active_at": self.last_active_at,
            "rank": self.rank,
            "volume_usd": self.volume_usd,
            "notes": self.notes,
            "updated_at": self.updated_at,
        }


class DownlineDB:
    """Downline DB with CSV bootstrap.

    Tests instantiate their own DB at ``tmp_path``; the host app uses
    :func:`get_downline_db` for the singleton.
    """

    def __init__(
        self,
        db_path: str | None = None,
        *,
        csv_seed_path: Path | None = None,
    ) -> None:
        self.db_path = (
            _resolve_db_path() if db_path is None else os.path.expanduser(db_path)
        )
        self.csv_seed_path = (
            csv_seed_path if csv_seed_path is not None else _csv_path()
        )
        self._ensure_schema()

    # -- internal sync helpers -------------------------------------------

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
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> Member:
        return Member(
            handle=row["handle"],
            sponsor=row["sponsor"],
            joined_at=row["joined_at"],
            last_active_at=row["last_active_at"],
            rank=row["rank"],
            volume_usd=float(row["volume_usd"] or 0.0),
            notes=row["notes"],
            updated_at=float(row["updated_at"] or 0.0),
        )

    def _count_sync(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM members").fetchone()
            return int(row["c"] or 0)
        finally:
            conn.close()

    def _list_sync(self) -> list[Member]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM members ORDER BY handle"
            ).fetchall()
        finally:
            conn.close()
        return [self._row(r) for r in rows]

    def _get_sync(self, handle: str) -> Optional[Member]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    def _upsert_sync(self, m: dict[str, Any], *, conflict_strategy: str) -> str:
        """Insert or update a member; returns ``inserted | updated | skipped``."""

        handle = (m.get("handle") or "").strip()
        if not handle:
            raise ValueError("handle_required")
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT 1 FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
            now = time.time()
            payload = (
                handle,
                (m.get("sponsor") or None),
                (m.get("joined_at") or None),
                (m.get("last_active_at") or None),
                (m.get("rank") or None),
                float(m.get("volume_usd") or 0.0),
                (m.get("notes") or None),
                now,
            )
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO members
                        (handle, sponsor, joined_at, last_active_at, rank,
                         volume_usd, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                return "inserted"
            if conflict_strategy == "skip":
                return "skipped"
            # "update" — overwrite all columns.
            conn.execute(
                """
                UPDATE members
                SET sponsor=?, joined_at=?, last_active_at=?, rank=?,
                    volume_usd=?, notes=?, updated_at=?
                WHERE handle=?
                """,
                (*payload[1:], handle),
            )
            return "updated"
        finally:
            conn.close()

    def _log_activity_sync(
        self,
        handle: str,
        ts: str,
        volume_delta: float,
    ) -> Optional[Member]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
            if row is None:
                return None
            volume = float(row["volume_usd"] or 0.0) + float(volume_delta or 0.0)
            conn.execute(
                """
                UPDATE members
                SET last_active_at=?, volume_usd=?, updated_at=?
                WHERE handle=?
                """,
                (ts, volume, time.time(), handle),
            )
            row = conn.execute(
                "SELECT * FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    # -- CSV bootstrap ----------------------------------------------------

    def _seed_from_csv_sync(self, csv_path: Path) -> int:
        if not csv_path.exists():
            return 0
        inserted = 0
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                try:
                    out = self._upsert_sync(
                        {
                            "handle": (r.get("handle") or "").strip(),
                            "sponsor": (r.get("sponsor") or "").strip() or None,
                            "joined_at": (r.get("joined_at") or "").strip() or None,
                            "last_active_at": (
                                (r.get("last_active_at") or "").strip() or None
                            ),
                            "rank": (r.get("rank") or "").strip().lower() or None,
                            "volume_usd": float(r.get("volume_usd") or 0.0),
                        },
                        conflict_strategy="skip",
                    )
                except (ValueError, TypeError):
                    continue
                if out == "inserted":
                    inserted += 1
        return inserted

    # -- async public API -------------------------------------------------

    async def ensure_seeded(self) -> dict[str, Any]:
        """Idempotent: if the DB is empty and a CSV is available, seed it."""

        n = await asyncio.to_thread(self._count_sync)
        if n > 0:
            return {"seeded": False, "members": n, "csv_path": str(self.csv_seed_path)}
        inserted = await asyncio.to_thread(
            self._seed_from_csv_sync, self.csv_seed_path
        )
        return {
            "seeded": True,
            "inserted": inserted,
            "members": inserted,
            "csv_path": str(self.csv_seed_path),
        }

    async def list_members(self) -> list[Member]:
        return await asyncio.to_thread(self._list_sync)

    async def get(self, handle: str) -> Optional[Member]:
        return await asyncio.to_thread(self._get_sync, handle)

    async def upsert(
        self,
        member: Mapping[str, Any],
        *,
        conflict_strategy: str = "update",
    ) -> str:
        return await asyncio.to_thread(
            self._upsert_sync, dict(member), conflict_strategy=conflict_strategy
        )

    async def log_activity(
        self,
        handle: str,
        *,
        ts: str | None = None,
        volume_delta: float = 0.0,
    ) -> Optional[Member]:
        ts_value = ts or datetime.now(timezone.utc).isoformat()
        return await asyncio.to_thread(
            self._log_activity_sync, handle, ts_value, float(volume_delta)
        )


_SINGLETON: Optional[DownlineDB] = None


def get_downline_db() -> DownlineDB:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = DownlineDB()
    return _SINGLETON


def reset_downline_db() -> None:
    global _SINGLETON
    _SINGLETON = None
