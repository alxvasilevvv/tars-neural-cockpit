"""SQLite-backed store for the org onboarding wizard (Wave 99).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.cohort.store`. The DB lives at
``~/.tars/org.sqlite`` by default; override with
``TARS_ORG_DB_PATH``. Disable with ``TARS_ORG_STORE=disabled``.

Single-tenant: at most one ``Org`` row exists at a time. Calling
:meth:`OrgStore.upsert_org` either creates the row (first time the
operator finishes Step 1) or patches the existing row (re-runs of
Step 1 from /onboard/org should not duplicate).

Tables:

- ``orgs``    — single org row.
- ``invites`` — Step 3 intents (no FK into a real users table — the
  backend doesn't yet model users; v9.3 multi-tenant adds them).
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from typing import Any

from .models import (
    CONTRACT_VERSION,
    Invite,
    Org,
    new_invite_id,
    new_org_id,
    normalize_org_type,
    normalize_role,
)

DEFAULT_DB_PATH = "~/.tars/org.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'other',
    size TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    primary_use_case TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    invited_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_invites_org ON invites (org_id, invited_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_invites_org_email ON invites (org_id, email);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_ORG_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_ORG_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class OrgStore:
    """Durable org store. Auto-initialised on first call."""

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

    # ---------- row mapping ----------------------------------------------

    @staticmethod
    def _row_to_org(row: sqlite3.Row) -> Org:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return Org(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            size=row["size"] or "",
            timezone=row["timezone"] or "UTC",
            primary_use_case=row["primary_use_case"] or "",
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            metadata=metadata,
        )

    @staticmethod
    def _row_to_invite(row: sqlite3.Row) -> Invite:
        return Invite(
            id=row["id"],
            org_id=row["org_id"],
            email=row["email"],
            role=row["role"],
            invited_at=float(row["invited_at"]),
            status=row["status"],
        )

    # ---------- org CRUD --------------------------------------------------

    def _get_org_sync(self) -> Org | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM orgs ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            return self._row_to_org(row) if row else None
        finally:
            conn.close()

    async def get_org(self) -> Org | None:
        return await asyncio.to_thread(self._get_org_sync)

    def _upsert_org_sync(
        self,
        *,
        name: str,
        type: str,
        size: str,
        timezone: str,
        primary_use_case: str,
        metadata: dict[str, Any],
    ) -> Org:
        existing = self._get_org_sync()
        now = time.time()
        type_n = normalize_org_type(type)
        merged_meta: dict[str, Any] = {}
        if existing is not None:
            merged_meta.update(existing.metadata)
        merged_meta.update(metadata or {})
        conn = self._connect()
        try:
            if existing is None:
                rec = Org(
                    id=new_org_id(),
                    name=name.strip(),
                    type=type_n,
                    size=size.strip(),
                    timezone=timezone.strip() or "UTC",
                    primary_use_case=primary_use_case.strip(),
                    created_at=now,
                    updated_at=now,
                    metadata=merged_meta,
                )
                conn.execute(
                    "INSERT INTO orgs (id, name, type, size, timezone,"
                    " primary_use_case, created_at, updated_at, metadata_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rec.id,
                        rec.name,
                        rec.type,
                        rec.size,
                        rec.timezone,
                        rec.primary_use_case,
                        rec.created_at,
                        rec.updated_at,
                        json.dumps(rec.metadata),
                    ),
                )
                conn.commit()
                return rec
            # Patch in place; preserve created_at + id.
            conn.execute(
                "UPDATE orgs SET name=?, type=?, size=?, timezone=?,"
                " primary_use_case=?, updated_at=?, metadata_json=?"
                " WHERE id=?",
                (
                    name.strip(),
                    type_n,
                    size.strip(),
                    timezone.strip() or "UTC",
                    primary_use_case.strip(),
                    now,
                    json.dumps(merged_meta),
                    existing.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        out = self._get_org_sync()
        assert out is not None
        return out

    async def upsert_org(
        self,
        *,
        name: str,
        type: str = "other",
        size: str = "",
        timezone: str = "UTC",
        primary_use_case: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Org:
        if not name.strip():
            raise ValueError("org name must be non-empty")
        return await asyncio.to_thread(
            self._upsert_org_sync,
            name=name,
            type=type,
            size=size,
            timezone=timezone,
            primary_use_case=primary_use_case,
            metadata=dict(metadata or {}),
        )

    def _patch_metadata_sync(self, patch: dict[str, Any]) -> Org | None:
        existing = self._get_org_sync()
        if existing is None:
            return None
        merged = dict(existing.metadata)
        merged.update(patch or {})
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE orgs SET metadata_json=?, updated_at=? WHERE id=?",
                (json.dumps(merged), time.time(), existing.id),
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_org_sync()

    async def patch_metadata(self, patch: dict[str, Any]) -> Org | None:
        return await asyncio.to_thread(self._patch_metadata_sync, patch)

    def _delete_org_sync(self) -> bool:
        existing = self._get_org_sync()
        if existing is None:
            return False
        conn = self._connect()
        try:
            conn.execute("DELETE FROM invites WHERE org_id=?", (existing.id,))
            conn.execute("DELETE FROM orgs WHERE id=?", (existing.id,))
            conn.commit()
        finally:
            conn.close()
        return True

    async def delete_org(self) -> bool:
        return await asyncio.to_thread(self._delete_org_sync)

    # ---------- invites ---------------------------------------------------

    def _add_invites_sync(
        self, *, org_id: str, items: list[dict[str, Any]]
    ) -> list[Invite]:
        out: list[Invite] = []
        conn = self._connect()
        try:
            for raw in items:
                email = str(raw.get("email") or "").strip().lower()
                if not email or "@" not in email:
                    continue
                role = normalize_role(raw.get("role"))
                # Idempotent: replace existing invite for the same
                # org+email pair so re-submitting Step 3 doesn't pile
                # duplicates. The unique index would otherwise IntegrityError.
                conn.execute(
                    "DELETE FROM invites WHERE org_id=? AND email=?",
                    (org_id, email),
                )
                rec = Invite(
                    id=new_invite_id(),
                    org_id=org_id,
                    email=email,
                    role=role,
                )
                conn.execute(
                    "INSERT INTO invites (id, org_id, email, role,"
                    " invited_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        rec.id,
                        rec.org_id,
                        rec.email,
                        rec.role,
                        rec.invited_at,
                        rec.status,
                    ),
                )
                out.append(rec)
            conn.commit()
        finally:
            conn.close()
        return out

    async def add_invites(
        self, *, org_id: str, items: list[dict[str, Any]]
    ) -> list[Invite]:
        if not org_id:
            raise ValueError("org_id required")
        return await asyncio.to_thread(
            self._add_invites_sync, org_id=org_id, items=items
        )

    def _list_invites_sync(self, org_id: str) -> list[Invite]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM invites WHERE org_id=? ORDER BY invited_at DESC",
                (org_id,),
            ).fetchall()
            return [self._row_to_invite(r) for r in rows]
        finally:
            conn.close()

    async def list_invites(self, org_id: str) -> list[Invite]:
        return await asyncio.to_thread(self._list_invites_sync, org_id)

    def _delete_invite_sync(self, invite_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT id FROM invites WHERE id=?", (invite_id,)
            )
            if cur.fetchone() is None:
                return False
            conn.execute("DELETE FROM invites WHERE id=?", (invite_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    async def delete_invite(self, invite_id: str) -> bool:
        return await asyncio.to_thread(self._delete_invite_sync, invite_id)


# ---------- module-level singleton helpers ----------------------------------


_singleton: OrgStore | None = None


def get_store() -> OrgStore:
    global _singleton
    if _singleton is None:
        _singleton = OrgStore()
    return _singleton


def reset_store() -> None:
    """Drop the cached singleton — used by tests + the
    ``TARS_ORG_DB_PATH`` env override."""

    global _singleton
    _singleton = None
