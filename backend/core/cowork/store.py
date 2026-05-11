"""SQLite-backed store for cowork sessions (Wave 129).

Same WAL + ``asyncio.to_thread`` discipline as the rest of the
W90+ stack. DB at ``~/.tars/cowork.sqlite`` by default; override
with ``TARS_COWORK_DB_PATH``. Disable the module with
``TARS_COWORK_STORE=disabled`` (the module helpers in
:mod:`__init__` short-circuit in that case).

Tables:

- ``sessions``      — shared cowork sessions.
- ``members``       — humans in each session (with join token).
- ``cursors``       — last-known cursor position per (member, path).
  Composite uniqueness on (session_id, member_id, path); upsert on
  cursor publish.
- ``handoffs``      — pending ownership transfers.

Schema is created on first connect. The store is intentionally
small: we don't persist the agent-run frame stream (that's
ephemeral in :mod:`stream`), only the durable session structure.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from .models import (
    CONTRACT_VERSION,
    Cursor,
    Handoff,
    Member,
    MemberRole,
    Session,
    SessionStatus,
    assign_color,
    new_cursor_id,
    new_handoff_id,
    new_member_id,
    new_session_id,
    new_token,
    normalize_role,
    slugify,
)

DEFAULT_DB_PATH = "~/.tars/cowork.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    owner_user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'live',
    created_at REAL NOT NULL,
    ended_at REAL,
    workspace_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_workspace ON sessions(workspace_id);

CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT,
    display_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'editor',
    token TEXT NOT NULL UNIQUE,
    joined_at REAL NOT NULL,
    color TEXT,
    last_seen_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_members_session ON members(session_id);
CREATE INDEX IF NOT EXISTS idx_members_user ON members(user_id);

CREATE TABLE IF NOT EXISTS cursors (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    path TEXT NOT NULL,
    line INTEGER NOT NULL DEFAULT 0,
    col INTEGER NOT NULL DEFAULT 0,
    selection_json TEXT,
    updated_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (member_id) REFERENCES members(id),
    UNIQUE (session_id, member_id, path)
);

CREATE INDEX IF NOT EXISTS idx_cursors_session ON cursors(session_id);

CREATE TABLE IF NOT EXISTS handoffs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    from_user_id TEXT NOT NULL,
    to_email TEXT,
    token TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    accepted_at REAL,
    accepted_by_user_id TEXT,
    revoked_at REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_handoffs_session ON handoffs(session_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_token ON handoffs(token);
"""


def _resolve_db_path() -> str:
    raw = os.environ.get("TARS_COWORK_DB_PATH", DEFAULT_DB_PATH)
    path = Path(raw).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def is_disabled() -> bool:
    return os.environ.get("TARS_COWORK_STORE", "").strip().lower() == "disabled"


class CoworkStore:
    """SQLite-backed CRUD for cowork sessions, members, cursors, handoffs.

    All public methods are ``async`` and offload I/O to ``asyncio.to_thread``
    to keep the FastAPI event loop responsive even on cold caches.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or _resolve_db_path()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    # ------------------------------------------------------------------ low-level

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema_sync(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._ensure_schema_sync)
            self._initialized = True

    # ------------------------------------------------------------------ sessions

    async def create_session(
        self,
        *,
        name: str,
        owner_user_id: str,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        await self._ensure_schema()
        session = Session(
            id=new_session_id(),
            name=name or "Cowork session",
            slug=slugify(name or "session"),
            owner_user_id=owner_user_id,
            status=SessionStatus.LIVE,
            workspace_id=workspace_id,
            metadata=metadata or {},
        )

        def _insert() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sessions
                      (id, name, slug, owner_user_id, status, created_at,
                       ended_at, workspace_id, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.id,
                        session.name,
                        session.slug,
                        session.owner_user_id,
                        session.status.value,
                        session.created_at,
                        session.ended_at,
                        session.workspace_id,
                        json.dumps(session.metadata),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_insert)
        return session

    async def get_session(self, session_id: str) -> Session | None:
        await self._ensure_schema()

        def _read() -> Session | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                return _row_to_session(row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def get_session_by_slug(self, slug: str) -> Session | None:
        await self._ensure_schema()

        def _read() -> Session | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE slug = ?", (slug,)
                ).fetchone()
                return _row_to_session(row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def list_sessions(
        self,
        *,
        owner_user_id: str | None = None,
        workspace_id: str | None = None,
        active_only: bool = False,
    ) -> list[Session]:
        await self._ensure_schema()

        def _read() -> list[Session]:
            conn = self._connect()
            try:
                where: list[str] = []
                params: list[Any] = []
                if owner_user_id:
                    where.append("owner_user_id = ?")
                    params.append(owner_user_id)
                if workspace_id:
                    where.append("workspace_id = ?")
                    params.append(workspace_id)
                if active_only:
                    where.append("status = 'live'")
                sql = "SELECT * FROM sessions"
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY created_at DESC"
                rows = conn.execute(sql, params).fetchall()
                return [_row_to_session(r) for r in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def end_session(self, session_id: str) -> bool:
        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    UPDATE sessions
                       SET status='ended', ended_at=?
                     WHERE id=? AND status != 'ended'
                    """,
                    (time.time(), session_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)

    async def set_session_status(
        self, session_id: str, status: SessionStatus
    ) -> bool:
        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE sessions SET status=? WHERE id=?",
                    (status.value, session_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)

    async def transfer_ownership(
        self, session_id: str, new_owner_user_id: str
    ) -> bool:
        """Atomic owner swap — used by :func:`handoff.accept_handoff`."""

        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE sessions SET owner_user_id=? WHERE id=?",
                    (new_owner_user_id, session_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)

    # ------------------------------------------------------------------ members

    async def add_member(
        self,
        *,
        session_id: str,
        display_name: str,
        user_id: str | None = None,
        email: str | None = None,
        role: str | MemberRole = MemberRole.EDITOR,
    ) -> Member:
        await self._ensure_schema()

        # Snapshot existing seat count to assign a stable colour. The
        # palette wraps so this is racy under heavy concurrency, but
        # colour is a UX hint, not a primary key.
        existing = await self.list_members(session_id=session_id)
        member = Member(
            id=new_member_id(),
            session_id=session_id,
            display_name=display_name or "Member",
            user_id=user_id,
            email=email,
            role=normalize_role(role),
            color=assign_color(len(existing)),
        )

        def _insert() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO members
                      (id, session_id, user_id, display_name, email,
                       role, token, joined_at, color, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        member.id,
                        member.session_id,
                        member.user_id,
                        member.display_name,
                        member.email,
                        member.role.value,
                        member.token,
                        member.joined_at,
                        member.color,
                        member.last_seen_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_insert)
        return member

    async def get_member(self, member_id: str) -> Member | None:
        await self._ensure_schema()

        def _read() -> Member | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM members WHERE id = ?", (member_id,)
                ).fetchone()
                return _row_to_member(row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def get_member_by_token(self, token: str) -> Member | None:
        await self._ensure_schema()

        def _read() -> Member | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM members WHERE token = ?", (token,)
                ).fetchone()
                return _row_to_member(row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def list_members(
        self, *, session_id: str
    ) -> list[Member]:
        await self._ensure_schema()

        def _read() -> list[Member]:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM members WHERE session_id=? ORDER BY joined_at",
                    (session_id,),
                ).fetchall()
                return [_row_to_member(r) for r in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def touch_member(self, member_id: str) -> None:
        await self._ensure_schema()

        def _write() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE members SET last_seen_at=? WHERE id=?",
                    (time.time(), member_id),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)

    async def remove_member(self, member_id: str) -> bool:
        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                # Cursors cascade out — drop them first to avoid FK
                # constraint failures when foreign_keys=ON.
                conn.execute("DELETE FROM cursors WHERE member_id=?", (member_id,))
                cur = conn.execute("DELETE FROM members WHERE id=?", (member_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)

    # ------------------------------------------------------------------ cursors

    async def upsert_cursor(
        self,
        *,
        session_id: str,
        member_id: str,
        path: str,
        line: int,
        col: int,
        selection: dict[str, Any] | None = None,
    ) -> Cursor:
        await self._ensure_schema()
        cursor = Cursor(
            id=new_cursor_id(),
            session_id=session_id,
            member_id=member_id,
            path=path,
            line=max(0, int(line)),
            col=max(0, int(col)),
            selection=selection,
        )

        def _write() -> None:
            conn = self._connect()
            try:
                # SQLite ON CONFLICT requires explicit conflict target.
                conn.execute(
                    """
                    INSERT INTO cursors
                      (id, session_id, member_id, path, line, col,
                       selection_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (session_id, member_id, path) DO UPDATE SET
                      line = excluded.line,
                      col = excluded.col,
                      selection_json = excluded.selection_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        cursor.id,
                        cursor.session_id,
                        cursor.member_id,
                        cursor.path,
                        cursor.line,
                        cursor.col,
                        json.dumps(cursor.selection) if cursor.selection else None,
                        cursor.updated_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)
        return cursor

    async def list_cursors(
        self, *, session_id: str, path: str | None = None
    ) -> list[Cursor]:
        await self._ensure_schema()

        def _read() -> list[Cursor]:
            conn = self._connect()
            try:
                if path:
                    rows = conn.execute(
                        """
                        SELECT * FROM cursors
                         WHERE session_id=? AND path=?
                         ORDER BY updated_at DESC
                        """,
                        (session_id, path),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM cursors
                         WHERE session_id=?
                         ORDER BY updated_at DESC
                        """,
                        (session_id,),
                    ).fetchall()
                return [_row_to_cursor(r) for r in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    # ------------------------------------------------------------------ handoffs

    async def insert_handoff(self, handoff: Handoff) -> None:
        await self._ensure_schema()

        def _write() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO handoffs
                      (id, session_id, from_user_id, to_email, token,
                       created_at, expires_at, accepted_at,
                       accepted_by_user_id, revoked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        handoff.id,
                        handoff.session_id,
                        handoff.from_user_id,
                        handoff.to_email,
                        handoff.token,
                        handoff.created_at,
                        handoff.expires_at,
                        handoff.accepted_at,
                        handoff.accepted_by_user_id,
                        handoff.revoked_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)

    async def get_handoff_by_token(self, token: str) -> Handoff | None:
        await self._ensure_schema()

        def _read() -> Handoff | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM handoffs WHERE token=?", (token,)
                ).fetchone()
                return _row_to_handoff(row) if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def mark_handoff_accepted(
        self, handoff_id: str, accepted_by_user_id: str
    ) -> bool:
        """Atomic accept: only succeeds if handoff is still pending.

        Uses a conditional UPDATE so two concurrent accepts can't both
        win the race.
        """

        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                now = time.time()
                cur = conn.execute(
                    """
                    UPDATE handoffs
                       SET accepted_at=?, accepted_by_user_id=?
                     WHERE id=?
                       AND accepted_at IS NULL
                       AND revoked_at IS NULL
                       AND expires_at > ?
                    """,
                    (now, accepted_by_user_id, handoff_id, now),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)

    async def revoke_handoff(self, handoff_id: str) -> bool:
        await self._ensure_schema()

        def _write() -> bool:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    UPDATE handoffs SET revoked_at=?
                     WHERE id=? AND revoked_at IS NULL AND accepted_at IS NULL
                    """,
                    (time.time(), handoff_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

        return await asyncio.to_thread(_write)


# ---------- Row → dataclass helpers -----------------------------------------


def _row_to_session(row: sqlite3.Row) -> Session:
    try:
        meta = json.loads(row["metadata_json"] or "{}")
    except (TypeError, ValueError):
        meta = {}
    return Session(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        owner_user_id=row["owner_user_id"],
        status=SessionStatus(row["status"]),
        created_at=row["created_at"],
        ended_at=row["ended_at"],
        workspace_id=row["workspace_id"],
        metadata=meta,
    )


def _row_to_member(row: sqlite3.Row) -> Member:
    return Member(
        id=row["id"],
        session_id=row["session_id"],
        display_name=row["display_name"],
        user_id=row["user_id"],
        email=row["email"],
        role=MemberRole(row["role"]),
        token=row["token"],
        joined_at=row["joined_at"],
        color=row["color"],
        last_seen_at=row["last_seen_at"],
    )


def _row_to_cursor(row: sqlite3.Row) -> Cursor:
    sel: dict[str, Any] | None = None
    if row["selection_json"]:
        try:
            sel = json.loads(row["selection_json"])
        except (TypeError, ValueError):
            sel = None
    return Cursor(
        id=row["id"],
        session_id=row["session_id"],
        member_id=row["member_id"],
        path=row["path"],
        line=int(row["line"]),
        col=int(row["col"]),
        selection=sel,
        updated_at=row["updated_at"],
    )


def _row_to_handoff(row: sqlite3.Row) -> Handoff:
    return Handoff(
        id=row["id"],
        session_id=row["session_id"],
        from_user_id=row["from_user_id"],
        to_email=row["to_email"],
        token=row["token"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        accepted_at=row["accepted_at"],
        accepted_by_user_id=row["accepted_by_user_id"],
        revoked_at=row["revoked_at"],
    )


# ---------- Module singleton -------------------------------------------------


_store_singleton: CoworkStore | None = None
_store_lock = asyncio.Lock()


async def get_store() -> CoworkStore:
    """Return the lazily-initialised module singleton."""

    global _store_singleton
    if _store_singleton is not None:
        return _store_singleton
    async with _store_lock:
        if _store_singleton is None:
            _store_singleton = CoworkStore()
        return _store_singleton


def reset_store() -> None:
    """Test helper: drop the cached singleton so the next call rebinds."""

    global _store_singleton
    _store_singleton = None
