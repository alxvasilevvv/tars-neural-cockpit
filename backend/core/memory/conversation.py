"""W274 — Persistent conversation memory layer for TARS.

Every chat turn (user input + TARS response) lands in a SQLite store
at ``~/.tars/conversations.sqlite``. The store powers three reads:

  * ``recent(session_id)``  — last N turns for prompt context.
  * ``search(query)``       — FTS5 full-text + lightweight semantic
                              score (sqlite-vec if available, else
                              token-overlap heuristic).
  * ``summarize_session(id)`` — LLM-style summary cached on the
                              ``conv_session`` row.

Schema is created lazily on first call. FTS5 is optional; the module
falls back to a LIKE-based search if the SQLite build doesn't expose
it. This keeps the store cross-platform without a hard dependency.

The store is intentionally tiny — just the rows + helpers. The chat
orchestrator + router glue lives elsewhere (W274 §4 wiring point).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

log = logging.getLogger("tars.memory.conversation")


_DEFAULT_DB = Path.home() / ".tars" / "conversations.sqlite"


def _resolve_db_path() -> Path:
    override = os.getenv("TARS_CONVERSATIONS_DB_PATH")
    return Path(override) if override else _DEFAULT_DB


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conv_session (
    id TEXT PRIMARY KEY,
    label TEXT,
    started_utc REAL NOT NULL,
    last_utc REAL NOT NULL,
    turn_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    summary_updated_utc REAL
);
CREATE INDEX IF NOT EXISTS idx_conv_session_last ON conv_session(last_utc DESC);

CREATE TABLE IF NOT EXISTS conv_turn (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    audio_url TEXT,
    ts_utc REAL NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    embedding BLOB,
    FOREIGN KEY(session_id) REFERENCES conv_session(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv_turn_session ON conv_turn(session_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_conv_turn_ts ON conv_turn(ts_utc DESC);
"""


_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS conv_turn_fts USING fts5(
    text, role, session_id,
    content='conv_turn',
    content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS conv_turn_ai AFTER INSERT ON conv_turn BEGIN
    INSERT INTO conv_turn_fts(rowid, text, role, session_id)
    VALUES (new.rowid, new.text, new.role, new.session_id);
END;
CREATE TRIGGER IF NOT EXISTS conv_turn_ad AFTER DELETE ON conv_turn BEGIN
    INSERT INTO conv_turn_fts(conv_turn_fts, rowid, text, role, session_id)
    VALUES('delete', old.rowid, old.text, old.role, old.session_id);
END;
"""


@dataclasses.dataclass
class ConversationTurn:
    """One side of an exchange (user input OR TARS response)."""

    id: str
    session_id: str
    role: str  # "user" or "tars" (also accept "system")
    text: str
    audio_url: Optional[str] = None
    ts_utc: float = dataclasses.field(default_factory=lambda: time.time())
    tokens_in: int = 0
    tokens_out: int = 0
    embedding: Optional[bytes] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "text": self.text,
            "audio_url": self.audio_url,
            "ts_utc": self.ts_utc,
            "ts_iso": datetime.fromtimestamp(self.ts_utc, tz=timezone.utc).isoformat(),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Zа-яА-Я0-9]{2,}", text.lower()))


class ConversationMemory:
    """Persistent, session-aware conversation store.

    Thread-safe per-connection — each method opens a fresh connection
    (the store is small; this avoids the asyncio thread-affinity gotcha).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else _resolve_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._init_schema()

    # --- schema -------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.executescript(_FTS_SCHEMA)
                self._fts_available = True
            except sqlite3.OperationalError as exc:
                log.info("conv_memory.fts_unavailable: %s", exc)
                self._fts_available = False

    # --- session housekeeping -----------------------------------
    def ensure_session(self, session_id: str, *, label: Optional[str] = None) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conv_session(id, label, started_utc, last_utc, turn_count)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET
                    label = COALESCE(excluded.label, conv_session.label),
                    last_utc = excluded.last_utc
                """,
                (session_id, label, now, now),
            )

    # --- CRUD ---------------------------------------------------
    def add_turn(self, turn: ConversationTurn) -> ConversationTurn:
        if not turn.id:
            turn.id = _new_id("turn")
        self.ensure_session(turn.session_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conv_turn(
                    id, session_id, role, text, audio_url, ts_utc,
                    tokens_in, tokens_out, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.id,
                    turn.session_id,
                    turn.role,
                    turn.text,
                    turn.audio_url,
                    turn.ts_utc,
                    turn.tokens_in,
                    turn.tokens_out,
                    turn.embedding,
                ),
            )
            conn.execute(
                """
                UPDATE conv_session
                SET last_utc = ?, turn_count = turn_count + 1
                WHERE id = ?
                """,
                (turn.ts_utc, turn.session_id),
            )
        return turn

    def recent(self, session_id: str, limit: int = 10) -> list[ConversationTurn]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conv_turn
                WHERE session_id = ?
                ORDER BY ts_utc DESC
                LIMIT ?
                """,
                (session_id, max(1, int(limit))),
            ).fetchall()
        # Return chronological order (oldest first) for prompt-building.
        return [_row_to_turn(r) for r in reversed(rows)]

    def search(self, query: str, limit: int = 5) -> list[ConversationTurn]:
        """Search across all sessions.

        Uses FTS5 when available; falls back to ranked LIKE + token
        overlap when FTS5 isn't compiled in. ``limit`` is clamped.
        """
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            if self._fts_available:
                try:
                    # Quote each token so FTS treats them as literals.
                    tokens = [t for t in re.findall(r"[\wЀ-ӿ]+", q) if t]
                    if not tokens:
                        return []
                    match = " OR ".join(f'"{t}"' for t in tokens)
                    rows = conn.execute(
                        """
                        SELECT t.* FROM conv_turn t
                        JOIN conv_turn_fts f ON f.rowid = t.rowid
                        WHERE conv_turn_fts MATCH ?
                        ORDER BY bm25(conv_turn_fts), t.ts_utc DESC
                        LIMIT ?
                        """,
                        (match, limit),
                    ).fetchall()
                    return [_row_to_turn(r) for r in rows]
                except sqlite3.OperationalError as exc:
                    log.info("conv_memory.fts_query_failed: %s", exc)
            # Fallback: pull rows, rank by token-overlap.
            qtok = _tokens(q)
            rows = conn.execute(
                "SELECT * FROM conv_turn ORDER BY ts_utc DESC LIMIT 500"
            ).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for r in rows:
            tt = _tokens(r["text"])
            if not tt:
                continue
            overlap = len(qtok & tt) / max(1, len(qtok))
            if overlap > 0:
                scored.append((overlap, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_row_to_turn(r) for _s, r in scored[:limit]]

    def summarize_session(self, session_id: str) -> str:
        """Produce a short human summary of a session.

        Heuristic for the v1 demo: first user turn topic + turn count
        + relative time. Stored on the session row so subsequent calls
        return the cached value. The chat orchestrator can override
        with a real LLM call later.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conv_session WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return ""
            if row["summary"] and (
                row["summary_updated_utc"] and (_now() - row["summary_updated_utc"]) < 86_400
            ):
                return row["summary"]
            first = conn.execute(
                """
                SELECT text FROM conv_turn
                WHERE session_id = ? AND role = 'user'
                ORDER BY ts_utc ASC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            topic = (first["text"] if first else "").strip()
            topic = re.split(r"[\.\?\!\n]", topic, maxsplit=1)[0][:80]
            count = row["turn_count"]
            when = _humanize_age(row["last_utc"])
            label = row["label"] or topic or "(no topic)"
            summary = f"{when} — {count} turns about {label}"
            conn.execute(
                """
                UPDATE conv_session SET summary = ?, summary_updated_utc = ?
                WHERE id = ?
                """,
                (summary, _now(), session_id),
            )
        return summary

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, label, started_utc, last_utc, turn_count, summary
                FROM conv_session
                ORDER BY last_utc DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if not d.get("summary"):
                try:
                    d["summary"] = self.summarize_session(d["id"])
                except sqlite3.Error:
                    d["summary"] = ""
            out.append(d)
        return out

    def delete_session(self, session_id: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM conv_session WHERE id = ?", (session_id,))
            # cascade handles conv_turn; explicit just in case FK PRAGMA missed.
            conn.execute("DELETE FROM conv_turn WHERE session_id = ?", (session_id,))
            return int(cur.rowcount or 0)

    # --- bulk helpers ------------------------------------------
    def add_exchange(
        self,
        *,
        session_id: str,
        user_text: str,
        tars_text: str,
        audio_url: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> tuple[ConversationTurn, ConversationTurn]:
        u = ConversationTurn(
            id=_new_id("turn"),
            session_id=session_id,
            role="user",
            text=user_text,
            tokens_in=tokens_in,
        )
        self.add_turn(u)
        t = ConversationTurn(
            id=_new_id("turn"),
            session_id=session_id,
            role="tars",
            text=tars_text,
            audio_url=audio_url,
            tokens_out=tokens_out,
        )
        self.add_turn(t)
        return u, t

    def context_for(
        self,
        *,
        session_id: str,
        query: str = "",
        recent_limit: int = 10,
        search_limit: int = 5,
    ) -> dict[str, Any]:
        """Build a context blob the orchestrator can inject into the LLM."""
        recent = [t.to_dict() for t in self.recent(session_id, recent_limit)]
        related: list[dict[str, Any]] = []
        if query:
            seen = {r["id"] for r in recent}
            for t in self.search(query, search_limit):
                if t.id in seen:
                    continue
                related.append(t.to_dict())
        return {
            "session_id": session_id,
            "recent": recent,
            "related": related,
            "summary": self.summarize_session(session_id),
        }


# --- helpers --------------------------------------------------------
def _row_to_turn(row: sqlite3.Row) -> ConversationTurn:
    return ConversationTurn(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        text=row["text"],
        audio_url=row["audio_url"],
        ts_utc=float(row["ts_utc"]),
        tokens_in=int(row["tokens_in"] or 0),
        tokens_out=int(row["tokens_out"] or 0),
        embedding=row["embedding"],
    )


def _humanize_age(ts: float) -> str:
    delta = max(0.0, _now() - ts)
    if delta < 60:
        return "Just now"
    if delta < 3600:
        return f"{int(delta / 60)} min ago"
    if delta < 86_400:
        return f"{int(delta / 3600)}h ago"
    if delta < 7 * 86_400:
        days = int(delta / 86_400)
        return "Yesterday" if days == 1 else f"{days} days ago"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# --- singleton accessor --------------------------------------------
_SINGLETON: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ConversationMemory()
    return _SINGLETON


def reset_conversation_memory() -> None:
    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "ConversationTurn",
    "ConversationMemory",
    "get_conversation_memory",
    "reset_conversation_memory",
]
