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


def _parse_iso_loose(s: str) -> datetime | None:
    """Parse an ISO-ish date / datetime; return ``None`` on failure.

    Tolerates ``YYYY-MM-DD``, ``YYYY-MM-DDTHH:MM:SS``, trailing ``Z``,
    and offset suffixes. Returned datetimes are always tz-aware (UTC
    assumed when no tzinfo is present).
    """

    raw = (s or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        cleaned = raw.replace("Z", "+00:00")
        out = datetime.fromisoformat(cleaned)
        if out.tzinfo is None:
            out = out.replace(tzinfo=timezone.utc)
        return out
    except ValueError:
        return None


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

    _UPDATABLE_MEMBER_FIELDS: tuple[str, ...] = (
        "sponsor",
        "rank",
        "joined_at",
        "last_active_at",
        "volume_usd",
        "notes",
    )

    @classmethod
    def _coerce_member_field(cls, field_name: str, value: Any) -> Any:
        """Coerce a user-supplied update value to its canonical shape.

        Returns ``...`` (Ellipsis) when the field should be left
        untouched (e.g. caller passed ``None`` for an optional string).
        Returns ``None`` to clear a nullable column; otherwise the
        coerced value.
        """

        if field_name == "volume_usd":
            try:
                val = float(value)
            except (TypeError, ValueError):
                raise ValueError("volume_invalid") from None
            if val < 0:
                raise ValueError("volume_invalid")
            return val
        if value is None:
            return ...
        if isinstance(value, str):
            s = value.strip()
            if field_name == "rank":
                return s.lower() if s else None
            return s if s else None
        return value

    def _update_member_sync(
        self,
        handle: str,
        updates: Mapping[str, Any],
    ) -> tuple[Optional[Member], list[str]]:
        """Patch a member row in-place. Returns ``(member, changed_fields)``.

        Returns ``(None, [])`` when the handle is not found. ``updates``
        only honours keys in :data:`_UPDATABLE_MEMBER_FIELDS`; other
        keys are silently ignored. ``handle`` itself can never be
        patched — change it via delete + add if you really need to.
        """

        coerced: dict[str, Any] = {}
        for field_name in self._UPDATABLE_MEMBER_FIELDS:
            if field_name not in updates:
                continue
            value = self._coerce_member_field(field_name, updates[field_name])
            if value is ...:
                continue
            coerced[field_name] = value

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
            if row is None:
                return None, []
            current = self._row(row)
            changed: list[str] = []
            for field_name, value in coerced.items():
                old = getattr(current, field_name, None)
                old_norm = float(old) if field_name == "volume_usd" else old
                new_norm = float(value) if (field_name == "volume_usd" and value is not None) else value
                if old_norm != new_norm:
                    changed.append(field_name)
            if not changed:
                return current, []
            assignments = ", ".join(f"{f}=?" for f in changed)
            params: list[Any] = [coerced[f] for f in changed]
            params.extend([time.time(), handle])
            conn.execute(
                f"UPDATE members SET {assignments}, updated_at=? WHERE handle=?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM members WHERE handle=?",
                (handle,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None, changed

    def _list_members_sync(
        self,
        *,
        sponsor: Optional[str],
        rank: Optional[str],
        recent_days: Optional[int],
        limit: Optional[int],
    ) -> list[Member]:
        clauses: list[str] = []
        params: list[Any] = []
        if sponsor is not None:
            clauses.append("LOWER(sponsor)=?")
            params.append(sponsor.lower())
        if rank is not None:
            clauses.append("LOWER(rank)=?")
            params.append(rank.lower())
        sql = "SELECT * FROM members"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY handle"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        members = [self._row(r) for r in rows]
        if recent_days is not None and recent_days > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - recent_days * 86400.0
            kept: list[Member] = []
            for m in members:
                ts = m.last_active_at or ""
                # Reuse the action-side parser via a local lazy import to
                # keep db.py free of the action module.
                parsed = _parse_iso_loose(ts)
                if parsed is None:
                    continue
                if parsed.timestamp() >= cutoff:
                    kept.append(m)
            members = kept
        if isinstance(limit, int) and limit > 0:
            members = members[:limit]
        return members

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

    async def list_members(
        self,
        *,
        sponsor: Optional[str] = None,
        rank: Optional[str] = None,
        recent_days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[Member]:
        """Return members with optional filters.

        - ``sponsor`` / ``rank``: case-insensitive equality.
        - ``recent_days``: keep only members with ``last_active_at``
          within this many days of "now".
        - ``limit``: positive integer cap on the result.
        """

        if sponsor is None and rank is None and recent_days is None and limit is None:
            return await asyncio.to_thread(self._list_sync)
        return await asyncio.to_thread(
            self._list_members_sync,
            sponsor=sponsor,
            rank=rank,
            recent_days=recent_days,
            limit=limit,
        )

    async def get(self, handle: str) -> Optional[Member]:
        return await asyncio.to_thread(self._get_sync, handle)

    async def update_member(
        self,
        handle: str,
        updates: Mapping[str, Any],
    ) -> tuple[Optional[Member], list[str]]:
        """Patch a member row in-place. Returns ``(member, changed_fields)``.

        Returns ``(None, [])`` when the handle is not found. Only
        keys in :data:`_UPDATABLE_MEMBER_FIELDS` are honoured;
        others are silently ignored. Raises :class:`ValueError`
        (``handle_required``, ``volume_invalid``) on bad inputs.
        """

        if not isinstance(handle, str) or not handle.strip():
            raise ValueError("handle_required")
        return await asyncio.to_thread(
            self._update_member_sync, handle.strip(), dict(updates)
        )

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
