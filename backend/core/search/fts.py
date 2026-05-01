"""SQLite FTS5 helpers for chat + attachments + meeet events.

We use **content-less** FTS5 tables (no ``content=`` clause) and sync
manually from application code. The trade-off: a tiny duplicate of
the indexed text on disk in exchange for zero coupling between
schemas — drop-and-rebuild is one ``DELETE FROM fts; INSERT INTO fts
SELECT …`` away.

Three virtual tables are created lazily on first call:

- ``chunks_fts``   — over ``attachment_chunks.text`` (chat DB).
- ``messages_fts`` — over ``messages.content`` (chat DB).
- ``events_fts``   — over ``events.payload`` (meeet DB).

Each carries an ``UNINDEXED`` linking column with the source row id so
search results can join back without a SQLAlchemy-style ORM.

Scoring uses FTS5's built-in BM25 ranking via the magic ``rank``
column (lower = better, we negate and normalise so callers see "higher
= more relevant" everywhere).

Tokeniser: ``unicode61 remove_diacritics 2`` — sane defaults for
mixed-language operator text (Russian / English flow alongside).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Iterable

from backend.core.chat.store import ChatStore, get_chat_store


log = logging.getLogger("tars.search.fts")


# ---------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------


_DDL_CHUNKS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    chunk_id UNINDEXED,
    attachment_id UNINDEXED,
    thread_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""

_DDL_MESSAGES = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    msg_id UNINDEXED,
    thread_id UNINDEXED,
    role UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""

_DDL_EVENTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    payload,
    event_id UNINDEXED,
    kind UNINDEXED,
    trace_id UNINDEXED,
    session_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);
"""


# ---------------------------------------------------------------------
# Setup / backfill
# ---------------------------------------------------------------------


def ensure_fts_indexes(*, chat: ChatStore | None = None) -> None:
    """Create FTS5 tables on the chat DB and backfill if empty.

    Idempotent — safe to call on every startup. The meeet events table
    lives in a different DB; :func:`ensure_events_fts` handles it
    separately (it auto-runs from the events store).
    """

    chat = chat or get_chat_store()
    if not chat.enabled:
        return
    conn = chat._connect()
    try:
        conn.executescript(_DDL_CHUNKS)
        conn.executescript(_DDL_MESSAGES)
        # Backfill if empty.
        chunks_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        msgs_count = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        if chunks_count == 0:
            _backfill_chunks(conn)
        if msgs_count == 0:
            _backfill_messages(conn)
        conn.commit()
    finally:
        conn.close()


def ensure_events_fts(meeet_db_path: str) -> None:
    conn = sqlite3.connect(meeet_db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(_DDL_EVENTS)
        count = conn.execute("SELECT COUNT(*) FROM events_fts").fetchone()[0]
        if count == 0:
            _backfill_events(conn)
        conn.commit()
    finally:
        conn.close()


def drop_fts_tables(*, chat: ChatStore | None = None) -> None:
    """Test-only — wipe the indexes so a fresh run rebuilds from scratch."""

    chat = chat or get_chat_store()
    if not chat.enabled:
        return
    conn = chat._connect()
    try:
        conn.execute("DROP TABLE IF EXISTS chunks_fts")
        conn.execute("DROP TABLE IF EXISTS messages_fts")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Mutators (called from the chat / attachment write paths)
# ---------------------------------------------------------------------


def index_chunk(
    *,
    chunk_id: str,
    attachment_id: str,
    thread_id: str,
    text: str,
    chat: ChatStore | None = None,
) -> None:
    chat = chat or get_chat_store()
    if not chat.enabled or not text:
        return
    conn = chat._connect()
    try:
        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
        conn.execute(
            "INSERT INTO chunks_fts (text, chunk_id, attachment_id, thread_id) "
            "VALUES (?, ?, ?, ?)",
            (text, chunk_id, attachment_id, thread_id),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        # Table doesn't exist yet → trigger creation lazily.
        log.warning("chunks_fts insert failed: %s", exc)
    finally:
        conn.close()


def index_chunks_bulk(
    chunks: Iterable[tuple[str, str, str, str]],
    *,
    chat: ChatStore | None = None,
) -> None:
    """Bulk insert ``(chunk_id, attachment_id, thread_id, text)`` rows."""

    chat = chat or get_chat_store()
    if not chat.enabled:
        return
    items = list(chunks)
    if not items:
        return
    conn = chat._connect()
    try:
        ids = [r[0] for r in items]
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(
            f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})",
            ids,
        )
        conn.executemany(
            "INSERT INTO chunks_fts (text, chunk_id, attachment_id, thread_id) "
            "VALUES (?, ?, ?, ?)",
            [(text, cid, aid, tid) for (cid, aid, tid, text) in items],
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        log.warning("chunks_fts bulk insert failed: %s", exc)
    finally:
        conn.close()


def remove_chunks_for_attachment(
    attachment_id: str, *, chat: ChatStore | None = None
) -> None:
    chat = chat or get_chat_store()
    if not chat.enabled:
        return
    conn = chat._connect()
    try:
        conn.execute(
            "DELETE FROM chunks_fts WHERE attachment_id = ?",
            (attachment_id,),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def index_message(
    *,
    msg_id: str,
    thread_id: str,
    role: str,
    content: str,
    chat: ChatStore | None = None,
) -> None:
    chat = chat or get_chat_store()
    if not chat.enabled or not content:
        return
    conn = chat._connect()
    try:
        conn.execute("DELETE FROM messages_fts WHERE msg_id = ?", (msg_id,))
        conn.execute(
            "INSERT INTO messages_fts (content, msg_id, thread_id, role) "
            "VALUES (?, ?, ?, ?)",
            (content, msg_id, thread_id, role),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        log.warning("messages_fts insert failed: %s", exc)
    finally:
        conn.close()


def remove_messages_for_thread(
    thread_id: str, *, chat: ChatStore | None = None
) -> None:
    chat = chat or get_chat_store()
    if not chat.enabled:
        return
    conn = chat._connect()
    try:
        conn.execute(
            "DELETE FROM messages_fts WHERE thread_id = ?",
            (thread_id,),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def index_event(
    *,
    event_id: int,
    kind: str,
    trace_id: str | None,
    session_id: str | None,
    payload: str,
    meeet_db_path: str,
) -> None:
    if not payload or event_id <= 0:
        return
    conn = sqlite3.connect(meeet_db_path)
    try:
        conn.execute("DELETE FROM events_fts WHERE event_id = ?", (event_id,))
        conn.execute(
            "INSERT INTO events_fts (payload, event_id, kind, trace_id, session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (payload, event_id, kind, trace_id, session_id),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        log.warning("events_fts insert failed: %s", exc)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Backfill (one-time on first ensure)
# ---------------------------------------------------------------------


def backfill_chunk_fts(*, chat: ChatStore | None = None) -> int:
    """Force a full rebuild of chunks_fts from attachment_chunks."""

    chat = chat or get_chat_store()
    if not chat.enabled:
        return 0
    conn = chat._connect()
    try:
        conn.execute("DELETE FROM chunks_fts")
        return _backfill_chunks(conn)
    finally:
        conn.commit()
        conn.close()


def backfill_message_fts(*, chat: ChatStore | None = None) -> int:
    """Force a full rebuild of messages_fts from messages."""

    chat = chat or get_chat_store()
    if not chat.enabled:
        return 0
    conn = chat._connect()
    try:
        conn.execute("DELETE FROM messages_fts")
        return _backfill_messages(conn)
    finally:
        conn.commit()
        conn.close()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','virtual') "
        "AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return bool(row)


def _backfill_chunks(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "attachment_chunks"):
        return 0
    rows = conn.execute(
        "SELECT id, attachment_id, thread_id, text FROM attachment_chunks"
    ).fetchall()
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO chunks_fts (text, chunk_id, attachment_id, thread_id) "
        "VALUES (?, ?, ?, ?)",
        [(r["text"], r["id"], r["attachment_id"], r["thread_id"]) for r in rows],
    )
    return len(rows)


def _backfill_messages(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "messages"):
        return 0
    rows = conn.execute(
        "SELECT id, thread_id, role, content FROM messages"
    ).fetchall()
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO messages_fts (content, msg_id, thread_id, role) "
        "VALUES (?, ?, ?, ?)",
        [(r["content"], r["id"], r["thread_id"], r["role"]) for r in rows],
    )
    return len(rows)


def _backfill_events(conn: sqlite3.Connection) -> int:
    conn.row_factory = sqlite3.Row
    if not _table_exists(conn, "events"):
        return 0
    rows = conn.execute(
        "SELECT id, kind, trace_id, session_id, payload FROM events"
    ).fetchall()
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO events_fts (payload, event_id, kind, trace_id, session_id) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (r["payload"], r["id"], r["kind"], r["trace_id"], r["session_id"])
            for r in rows
        ],
    )
    return len(rows)


# ---------------------------------------------------------------------
# Query helpers — return raw (rowid_or_id, score) pairs.
# ---------------------------------------------------------------------


# FTS5 MATCH expects either bare tokens or quoted phrases. We sanitise
# operator queries to avoid blowing up on stray ``"``, ``*``, ``-``,
# ``(``, ``)``, ``:``, ``AND/OR/NOT`` keyword collisions, etc.
_FTS_SAFE_RE = re.compile(r"[^\w\s\u00C0-\uFFFF]+", re.UNICODE)


def sanitise_query(raw: str) -> str:
    """Make ``raw`` safe to drop into an FTS5 ``MATCH`` clause."""

    if not raw:
        return ""
    cleaned = _FTS_SAFE_RE.sub(" ", raw).strip()
    if not cleaned:
        return ""
    tokens = [
        t for t in cleaned.split() if t and t.upper() not in {"AND", "OR", "NOT", "NEAR"}
    ]
    if not tokens:
        return ""
    # Wrap each token in quotes so trailing punctuation doesn't matter.
    return " OR ".join(f'"{t}"' for t in tokens)


def fts_match_chunks(
    query: str,
    *,
    chat: ChatStore | None = None,
    limit: int = 50,
    thread_id: str | None = None,
) -> list[dict]:
    chat = chat or get_chat_store()
    sanitised = sanitise_query(query)
    if not chat.enabled or not sanitised:
        return []
    conn = chat._connect()
    try:
        params: list = [sanitised]
        clauses = ["chunks_fts MATCH ?"]
        if thread_id:
            clauses.append("thread_id = ?")
            params.append(thread_id)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT chunk_id, attachment_id, thread_id, rank,
                   snippet(chunks_fts, 0, '<mark>', '</mark>', '…', 16) AS snippet
            FROM chunks_fts
            WHERE {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        log.warning("chunks_fts MATCH failed: %s", exc)
        return []
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def fts_match_messages(
    query: str,
    *,
    chat: ChatStore | None = None,
    limit: int = 50,
    thread_id: str | None = None,
    role: str | None = None,
    pack: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[dict]:
    """FTS5 keyword match over messages.

    Supports time-window bounds (``since``/``until`` POSIX seconds) and
    a pack filter (resolves through ``threads.pack_slug`` via JOIN).
    Filters compose with AND semantics.
    """

    chat = chat or get_chat_store()
    sanitised = sanitise_query(query)
    if not chat.enabled or not sanitised:
        return []
    conn = chat._connect()
    try:
        params: list = [sanitised]
        clauses = ["messages_fts MATCH ?"]
        join = ""
        if thread_id:
            clauses.append("messages_fts.thread_id = ?")
            params.append(thread_id)
        if role:
            clauses.append("messages_fts.role = ?")
            params.append(role)
        if since is not None or until is not None or pack:
            join = (
                " JOIN messages m ON m.id = messages_fts.msg_id"
            )
            if since is not None:
                clauses.append("m.created_at >= ?")
                params.append(float(since))
            if until is not None:
                clauses.append("m.created_at <= ?")
                params.append(float(until))
        if pack:
            join += " JOIN threads t ON t.id = m.thread_id"
            clauses.append("t.pack_slug = ?")
            params.append(pack)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT messages_fts.msg_id AS msg_id,
                   messages_fts.thread_id AS thread_id,
                   messages_fts.role AS role,
                   rank,
                   snippet(messages_fts, 0, '<mark>', '</mark>', '…', 16) AS snippet
            FROM messages_fts{join}
            WHERE {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        log.warning("messages_fts MATCH failed: %s", exc)
        return []
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def fts_match_events(
    query: str,
    *,
    meeet_db_path: str,
    limit: int = 50,
    kind: str | None = None,
    trace_id: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[dict]:
    """FTS5 keyword match over the meeet event durable buffer.

    ``since`` / ``until`` (POSIX seconds) clamp ``events.ts`` via a
    JOIN into the events table. Compose with AND semantics.
    """

    sanitised = sanitise_query(query)
    if not sanitised:
        return []
    conn = sqlite3.connect(meeet_db_path)
    conn.row_factory = sqlite3.Row
    try:
        params: list = [sanitised]
        clauses = ["events_fts MATCH ?"]
        join = ""
        if kind:
            clauses.append("events_fts.kind = ?")
            params.append(kind)
        if trace_id:
            clauses.append("events_fts.trace_id = ?")
            params.append(trace_id)
        if since is not None or until is not None:
            join = " JOIN events e ON e.id = events_fts.event_id"
            if since is not None:
                clauses.append("e.ts >= ?")
                params.append(float(since))
            if until is not None:
                clauses.append("e.ts <= ?")
                params.append(float(until))
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT events_fts.event_id AS event_id,
                   events_fts.kind AS kind,
                   events_fts.trace_id AS trace_id,
                   events_fts.session_id AS session_id,
                   rank,
                   snippet(events_fts, 0, '<mark>', '</mark>', '…', 16) AS snippet
            FROM events_fts{join}
            WHERE {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        log.warning("events_fts MATCH failed: %s", exc)
        return []
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}
