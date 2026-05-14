"""W243 — Notepad templates for TARS.

Cursor has Notepads: save an AI conversation / instruction as a
reusable template, recall later with one click. TARS adds:
domain-pack-aware templates (each pack can ship starter Notepads).

Storage
-------

``~/.tars/notepads.sqlite`` — single SQLite file with a regular
``notepads`` table plus an FTS5 contentless virtual table
``notepads_fts`` mirrored over ``title + body``. The store is
synchronous-but-fast: every cockpit click is one SQLite hit.

Variables in the body marked ``{name}`` are highlighted client-side
(see :func:`extract_variables`) and prompted before insertion.

The module is intentionally framework-free: the HTTP router
(``web_extras/routers/notepads.py``) is a thin wrapper around the
helpers exposed here.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Constants / seed
# ---------------------------------------------------------------------------


# Mirror :func:`backend.core.storage.bootstrap.tars_dir` semantics.
DEFAULT_TARS_DIR = Path.home() / ".tars"


VARIABLE_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
"""Match ``{name}`` placeholders — ASCII identifier inside braces."""


DEFAULT_SEEDS: list[dict[str, Any]] = [
    {
        "title": "Daily briefing",
        "body": "Summarize my last 24h: receipts, emails unread, calendar today.",
        "tags": ["briefing", "morning"],
        "pack": None,
    },
    {
        "title": "Cold outreach draft",
        "body": "Write a cold outreach email to {company} about {value_prop}.",
        "tags": ["outreach", "email"],
        "pack": "entrepreneur",
    },
    {
        "title": "Code review checklist",
        "body": (
            "Review this code: 1) security, 2) perf N+1, 3) error paths, "
            "4) tests."
        ),
        "tags": ["code", "review"],
        "pack": None,
    },
    {
        "title": "Doctor visit prep",
        "body": (
            "Help me prepare for {appointment_type}: list questions, "
            "current meds, symptoms timeline."
        ),
        "tags": ["health", "prep"],
        "pack": "health",
    },
    {
        "title": "Pack picker",
        "body": (
            "Recommend the right domain pack for my use case: {description}."
        ),
        "tags": ["meta", "onboarding"],
        "pack": None,
    },
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Notepad:
    """One reusable notepad template."""

    id: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    pack: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    usage_count: int = 0
    owner: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": list(self.tags),
            "pack": self.pack,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "owner": self.owner,
            "variables": extract_variables(self.body),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tars_home() -> Path:
    """Resolve ``~/.tars`` (or ``TARS_HOME`` override). Created on demand."""

    raw = os.environ.get("TARS_HOME")
    base = Path(raw).expanduser() if raw else DEFAULT_TARS_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def notepads_db_path() -> Path:
    """Return ``~/.tars/notepads.sqlite`` (override via ``TARS_HOME``)."""

    return _tars_home() / "notepads.sqlite"


def extract_variables(body: str) -> list[str]:
    """Return ordered unique list of ``{name}`` placeholders in ``body``.

    Order preserves first-appearance so the UI prompts variables in
    the order they show up — easier to reason about than alphabetic.
    """

    seen: dict[str, None] = {}
    for m in VARIABLE_RE.finditer(body or ""):
        seen.setdefault(m.group(1), None)
    return list(seen.keys())


def fill_variables(body: str, values: dict[str, str]) -> str:
    """Substitute ``{name}`` placeholders. Unknown names are left as-is.

    This is intentionally NOT ``str.format`` — operator bodies often
    contain JSON / curly-braces that aren't variables, and we don't
    want to KeyError on those.
    """

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in values:
            return str(values[name])
        return match.group(0)

    return VARIABLE_RE.sub(repl, body or "")


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


_DDL = """
CREATE TABLE IF NOT EXISTS notepads (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '',   -- newline-joined for sqlite simplicity
    pack          TEXT,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    usage_count   INTEGER NOT NULL DEFAULT 0,
    owner         TEXT NOT NULL DEFAULT 'local'
);

CREATE INDEX IF NOT EXISTS idx_notepads_pack ON notepads(pack);
CREATE INDEX IF NOT EXISTS idx_notepads_updated ON notepads(updated_at DESC);
"""


_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS notepads_fts USING fts5(
    title,
    body,
    pad_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""


def _serialise_tags(tags: Iterable[str] | None) -> str:
    if not tags:
        return ""
    return "\n".join(t.strip() for t in tags if t and t.strip())


def _deserialise_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [line for line in raw.splitlines() if line.strip()]


def _row_to_notepad(row: sqlite3.Row) -> Notepad:
    return Notepad(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        tags=_deserialise_tags(row["tags"]),
        pack=row["pack"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        usage_count=int(row["usage_count"]),
        owner=row["owner"],
    )


class NotepadStore:
    """SQLite-backed notepad store with FTS5 search.

    Reads / writes are synchronous and brief (single SQLite connection
    per call). For a personal cockpit this trades nothing against an
    async connection pool, and keeps the module dependency-free.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else notepads_db_path()
        self._ensure_schema()

    # -- internals ----------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)
            try:
                conn.executescript(_FTS_DDL)
                self._fts_enabled = True
            except sqlite3.OperationalError:
                # SQLite build without FTS5 — degrade to LIKE-search.
                self._fts_enabled = False

    @property
    def fts_enabled(self) -> bool:
        return getattr(self, "_fts_enabled", False)

    def _sync_fts(self, conn: sqlite3.Connection, pad: Notepad) -> None:
        if not self._fts_enabled:
            return
        conn.execute("DELETE FROM notepads_fts WHERE pad_id = ?", (pad.id,))
        conn.execute(
            "INSERT INTO notepads_fts(title, body, pad_id) VALUES (?,?,?)",
            (pad.title, pad.body, pad.id),
        )

    def _drop_fts(self, conn: sqlite3.Connection, pad_id: str) -> None:
        if not self._fts_enabled:
            return
        conn.execute("DELETE FROM notepads_fts WHERE pad_id = ?", (pad_id,))

    # -- public API ---------------------------------------------------

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM notepads").fetchone()
            return int(row[0]) if row else 0

    def create(
        self,
        *,
        title: str,
        body: str,
        tags: list[str] | None = None,
        pack: str | None = None,
        owner: str = "local",
        pad_id: str | None = None,
    ) -> Notepad:
        now = time.time()
        pad = Notepad(
            id=pad_id or f"np-{uuid.uuid4().hex[:12]}",
            title=str(title).strip() or "Untitled",
            body=str(body or ""),
            tags=[t.strip() for t in (tags or []) if t and t.strip()],
            pack=(pack.strip() if isinstance(pack, str) and pack.strip() else None),
            created_at=now,
            updated_at=now,
            usage_count=0,
            owner=owner or "local",
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notepads
                (id, title, body, tags, pack, created_at, updated_at, usage_count, owner)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    pad.id, pad.title, pad.body,
                    _serialise_tags(pad.tags), pad.pack,
                    pad.created_at, pad.updated_at,
                    pad.usage_count, pad.owner,
                ),
            )
            self._sync_fts(conn, pad)
        return pad

    def get(self, pad_id: str) -> Notepad | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notepads WHERE id = ?",
                (pad_id,),
            ).fetchone()
            return _row_to_notepad(row) if row else None

    def update(
        self,
        pad_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
        pack: str | None | object = ...,
    ) -> Notepad | None:
        existing = self.get(pad_id)
        if not existing:
            return None
        new_title = title.strip() if isinstance(title, str) else existing.title
        new_body = body if isinstance(body, str) else existing.body
        new_tags = (
            [t.strip() for t in tags if t and t.strip()]
            if isinstance(tags, list)
            else existing.tags
        )
        if pack is ...:
            new_pack: str | None = existing.pack
        elif pack is None:
            new_pack = None
        else:
            assert isinstance(pack, str)
            new_pack = pack.strip() or None
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notepads
                   SET title=?, body=?, tags=?, pack=?, updated_at=?
                 WHERE id=?
                """,
                (
                    new_title or "Untitled",
                    new_body,
                    _serialise_tags(new_tags),
                    new_pack,
                    now,
                    pad_id,
                ),
            )
            updated = Notepad(
                id=pad_id,
                title=new_title or "Untitled",
                body=new_body,
                tags=new_tags,
                pack=new_pack,
                created_at=existing.created_at,
                updated_at=now,
                usage_count=existing.usage_count,
                owner=existing.owner,
            )
            self._sync_fts(conn, updated)
        return updated

    def delete(self, pad_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM notepads WHERE id = ?", (pad_id,))
            ok = cur.rowcount > 0
            if ok:
                self._drop_fts(conn, pad_id)
            return ok

    def mark_used(self, pad_id: str) -> Notepad | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE notepads
                   SET usage_count = usage_count + 1,
                       updated_at  = ?
                 WHERE id = ?
                """,
                (time.time(), pad_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM notepads WHERE id = ?", (pad_id,)
            ).fetchone()
            return _row_to_notepad(row) if row else None

    def list(
        self,
        *,
        pack: str | None = None,
        q: str | None = None,
        limit: int = 100,
    ) -> list[Notepad]:
        """List notepads. ``pack`` filters exactly (including ``""`` for
        no-pack); ``q`` runs FTS5 if available, else a LIKE fallback.
        """

        limit = max(1, min(int(limit or 100), 500))
        with self._connect() as conn:
            # Search path
            if q and q.strip():
                if self._fts_enabled:
                    try:
                        rows = self._fts_search(conn, q.strip(), limit, pack)
                        if rows or pack is not None:
                            return rows
                    except sqlite3.OperationalError:
                        pass  # malformed FTS query — fall through to LIKE
                return self._like_search(conn, q.strip(), limit, pack)
            # Plain list
            sql = "SELECT * FROM notepads"
            args: list[Any] = []
            if pack is not None:
                if pack == "":
                    sql += " WHERE pack IS NULL"
                else:
                    sql += " WHERE pack = ?"
                    args.append(pack)
            sql += " ORDER BY usage_count DESC, updated_at DESC LIMIT ?"
            args.append(limit)
            rows = conn.execute(sql, args).fetchall()
            return [_row_to_notepad(r) for r in rows]

    def _fts_search(
        self,
        conn: sqlite3.Connection,
        q: str,
        limit: int,
        pack: str | None,
    ) -> list[Notepad]:
        # Quote each term so FTS5 doesn't reject punctuation; OR them.
        terms = [t for t in re.split(r"\s+", q) if t]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        sql = """
            SELECT n.* FROM notepads_fts f
              JOIN notepads n ON n.id = f.pad_id
             WHERE notepads_fts MATCH ?
        """
        args: list[Any] = [match]
        if pack is not None:
            if pack == "":
                sql += " AND n.pack IS NULL"
            else:
                sql += " AND n.pack = ?"
                args.append(pack)
        sql += " ORDER BY rank LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
        return [_row_to_notepad(r) for r in rows]

    def _like_search(
        self,
        conn: sqlite3.Connection,
        q: str,
        limit: int,
        pack: str | None,
    ) -> list[Notepad]:
        like = f"%{q.lower()}%"
        sql = (
            "SELECT * FROM notepads "
            "WHERE (lower(title) LIKE ? OR lower(body) LIKE ?)"
        )
        args: list[Any] = [like, like]
        if pack is not None:
            if pack == "":
                sql += " AND pack IS NULL"
            else:
                sql += " AND pack = ?"
                args.append(pack)
        sql += " ORDER BY usage_count DESC, updated_at DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
        return [_row_to_notepad(r) for r in rows]

    def seed_defaults(self) -> list[Notepad]:
        """Seed :data:`DEFAULT_SEEDS` if the table is empty.

        Returns the newly-created notepads (empty list when the table
        already has rows).
        """

        if self.count() > 0:
            return []
        out: list[Notepad] = []
        for s in DEFAULT_SEEDS:
            out.append(
                self.create(
                    title=str(s["title"]),
                    body=str(s["body"]),
                    tags=list(s.get("tags") or []),
                    pack=s.get("pack"),
                    owner="seed",
                )
            )
        return out


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


_STORE: NotepadStore | None = None


def get_notepad_store() -> NotepadStore:
    """Return the process-wide :class:`NotepadStore`.

    Honours the current ``TARS_HOME`` so tests can monkeypatch the env
    and get a fresh DB. Mutating the env after first access requires
    :func:`reset_store_for_tests`.
    """

    global _STORE
    if _STORE is None or _STORE.db_path != notepads_db_path():
        _STORE = NotepadStore()
    return _STORE


def reset_store_for_tests() -> None:
    """Drop the cached store so the next :func:`get_notepad_store` call
    re-resolves the DB path. Tests use this after ``monkeypatch.setenv``.
    """

    global _STORE
    _STORE = None


__all__ = [
    "DEFAULT_SEEDS",
    "Notepad",
    "NotepadStore",
    "VARIABLE_RE",
    "extract_variables",
    "fill_variables",
    "get_notepad_store",
    "notepads_db_path",
    "reset_store_for_tests",
]
