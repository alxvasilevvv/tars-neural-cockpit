"""SQLite-backed durable store for chat threads, messages, tool-calls.

WAL mode + ``asyncio.to_thread`` for non-blocking access — same
discipline as :mod:`backend.core.meeet.store`. Disable with
``TARS_CHAT_STORE=disabled``; override path with
``TARS_CHAT_DB_PATH``.

Schema is forward-compatible: new columns get added with ``ALTER TABLE``
between table creation and index creation (see
``_ensure_schema``).
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import Any, Iterable, Mapping, Optional, Sequence

from .models import (
    Attachment,
    Message,
    SavedSearch,
    SavedSearchScope,
    Thread,
    ToolCall,
    new_attachment_id,
    new_message_id,
    new_saved_search_id,
    new_tool_call_id,
)


DEFAULT_DB_PATH = "~/.tars/chat.sqlite"


_SCHEMA_TABLES = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    title TEXT,
    pack_slug TEXT,
    project_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_session_id TEXT,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    trace_id TEXT,
    parent_msg_id TEXT,
    cost_usd REAL,
    route TEXT,
    council_id TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    voice_model TEXT,
    extra_json TEXT,
    FOREIGN KEY (thread_id) REFERENCES threads (id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    action_id TEXT NOT NULL,
    args_json TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    policy_token TEXT,
    result_json TEXT,
    cost_usd REAL,
    error TEXT,
    trace_id TEXT,
    FOREIGN KEY (message_id) REFERENCES messages (id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    message_id TEXT,
    mime TEXT NOT NULL,
    filename TEXT,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL,
    extracted_text TEXT,
    embedding_id TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads (id)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    query TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'all',
    filters_json TEXT NOT NULL DEFAULT '{}',
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_run_at REAL
);
"""

_SCHEMA_INDICES = """
CREATE INDEX IF NOT EXISTS idx_messages_thread_ts
    ON messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_trace
    ON messages (trace_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_message
    ON tool_calls (message_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_status
    ON tool_calls (status);
CREATE INDEX IF NOT EXISTS idx_attachments_thread
    ON attachments (thread_id);
CREATE INDEX IF NOT EXISTS idx_threads_updated
    ON threads (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_searches_order
    ON saved_searches (pinned DESC, updated_at DESC);
"""

# Forward-compat: ``ALTER TABLE`` lines run between table + index
# creation. Wrap each in try/except inside _ensure_schema so re-adds
# are silent.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE messages ADD COLUMN embedding_model TEXT",
    "ALTER TABLE messages ADD COLUMN embedding_dim INTEGER",
    "ALTER TABLE messages ADD COLUMN embedding_blob BLOB",
    "ALTER TABLE saved_searches ADD COLUMN seen_hits_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE saved_searches ADD COLUMN last_alert_at REAL",
    "ALTER TABLE saved_searches ADD COLUMN snoozed_until REAL",
)


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_CHAT_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_CHAT_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class ChatStore:
    """Durable conversation store.

    Singleton lives behind :func:`get_chat_store`; tests instantiate
    their own with an explicit path.
    """

    def __init__(
        self,
        db_path: str | None = None,
        *,
        enabled: bool | None = None,
    ) -> None:
        self.db_path = (
            _resolve_db_path(db_path)
            if db_path is None
            else os.path.expanduser(db_path)
        )
        self.enabled = (not _is_disabled()) if enabled is None else enabled
        if self.enabled:
            self._ensure_schema()

    # -- helpers ----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_TABLES)
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    continue
            conn.executescript(_SCHEMA_INDICES)
        finally:
            conn.close()

    # -- threads ---------------------------------------------------------

    def _insert_thread_sync(self, thread: Thread) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO threads (
                    id, title, pack_slug, project_id, created_at,
                    updated_at, last_session_id, archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.title,
                    thread.pack_slug,
                    thread.project_id,
                    thread.created_at,
                    thread.updated_at,
                    thread.last_session_id,
                    1 if thread.archived else 0,
                ),
            )
        finally:
            conn.close()

    async def insert_thread(self, thread: Thread) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(self._insert_thread_sync, thread)

    def _patch_thread_sync(
        self,
        thread_id: str,
        updates: Mapping[str, Any],
    ) -> Thread | None:
        if not updates:
            return self._get_thread_sync(thread_id)
        cols: list[str] = []
        params: list[Any] = []
        for k, v in updates.items():
            if k not in {
                "title",
                "pack_slug",
                "project_id",
                "last_session_id",
                "archived",
                "updated_at",
            }:
                continue
            cols.append(f"{k}=?")
            params.append(int(bool(v)) if k == "archived" else v)
        if not cols:
            return self._get_thread_sync(thread_id)
        cols.append("updated_at=?")
        params.append(updates.get("updated_at") or _now())
        params.append(thread_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE threads SET {', '.join(cols)} WHERE id = ?",
                params,
            )
        finally:
            conn.close()
        return self._get_thread_sync(thread_id)

    async def patch_thread(
        self, thread_id: str, updates: Mapping[str, Any]
    ) -> Thread | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._patch_thread_sync, thread_id, dict(updates)
        )

    def _get_thread_sync(self, thread_id: str) -> Thread | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM threads WHERE id=?", (thread_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_thread(row) if row else None

    async def get_thread(self, thread_id: str) -> Thread | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(self._get_thread_sync, thread_id)

    def _list_threads_sync(
        self,
        *,
        limit: int,
        archived: bool | None,
        pack_slug: str | None,
        project_id: str | None,
    ) -> list[Thread]:
        clauses: list[str] = []
        params: list[Any] = []
        if archived is not None:
            clauses.append("archived = ?")
            params.append(1 if archived else 0)
        if pack_slug:
            clauses.append("pack_slug = ?")
            params.append(pack_slug)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM threads {where} "
                f"ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_thread(r) for r in rows]

    async def list_threads(
        self,
        *,
        limit: int = 50,
        archived: bool | None = False,
        pack_slug: str | None = None,
        project_id: str | None = None,
    ) -> list[Thread]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._list_threads_sync,
            limit=max(1, min(int(limit), 500)),
            archived=archived,
            pack_slug=pack_slug,
            project_id=project_id,
        )

    @staticmethod
    def _row_to_thread(row: sqlite3.Row) -> Thread:
        return Thread(
            id=row["id"],
            title=row["title"],
            pack_slug=row["pack_slug"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_session_id=row["last_session_id"],
            archived=bool(row["archived"]),
        )

    # -- messages --------------------------------------------------------

    def _insert_message_sync(self, message: Message) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO messages (
                    id, thread_id, role, content, created_at,
                    trace_id, parent_msg_id, cost_usd, route,
                    council_id, tokens_in, tokens_out, voice_model,
                    extra_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.thread_id,
                    message.role,
                    message.content,
                    message.created_at,
                    message.trace_id,
                    message.parent_msg_id,
                    message.cost_usd,
                    message.route,
                    message.council_id,
                    message.tokens_in,
                    message.tokens_out,
                    message.voice_model,
                    json.dumps(dict(message.extra), separators=(",", ":")),
                ),
            )
            conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (message.created_at, message.thread_id),
            )
        finally:
            conn.close()

    async def insert_message(self, message: Message) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(self._insert_message_sync, message)
        # Mirror into the FTS5 keyword index — non-fatal if it fails
        # (search is observability, not the source of truth).
        try:
            from backend.core.search.fts import (
                ensure_fts_indexes,
                index_message,
            )

            ensure_fts_indexes(chat=self)
            index_message(
                msg_id=message.id,
                thread_id=message.thread_id,
                role=message.role,
                content=message.content or "",
                chat=self,
            )
        except Exception:
            pass

    def _list_messages_sync(
        self,
        thread_id: str,
        *,
        limit: int,
        before: float | None,
    ) -> list[Message]:
        clauses = ["thread_id = ?"]
        params: list[Any] = [thread_id]
        if before is not None:
            clauses.append("created_at < ?")
            params.append(float(before))
        params.append(int(limit))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM messages WHERE {' AND '.join(clauses)} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        finally:
            conn.close()
        # Return in chronological order — easier for the UI.
        return [self._row_to_message(r) for r in reversed(rows)]

    async def list_messages(
        self,
        thread_id: str,
        *,
        limit: int = 100,
        before: float | None = None,
    ) -> list[Message]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._list_messages_sync,
            thread_id,
            limit=max(1, min(int(limit), 1000)),
            before=before,
        )

    async def context_window(
        self, thread_id: str, *, limit: int = 30
    ) -> list[Message]:
        """Most-recent ``limit`` messages, oldest first.

        Used by :class:`ChatOrchestrator` to build voice context.
        """

        return await self.list_messages(thread_id, limit=limit)

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        try:
            extra = json.loads(row["extra_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            extra = {}
        return Message(
            id=row["id"],
            thread_id=row["thread_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            trace_id=row["trace_id"],
            parent_msg_id=row["parent_msg_id"],
            cost_usd=row["cost_usd"],
            route=row["route"],
            council_id=row["council_id"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            voice_model=row["voice_model"],
            extra=extra,
        )

    # -- message embeddings (vector + BM25 blend) ----------------------

    def _set_message_embedding_sync(
        self,
        msg_id: str,
        *,
        model: str,
        dim: int,
        blob: bytes,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE messages SET
                    embedding_model = ?,
                    embedding_dim = ?,
                    embedding_blob = ?
                WHERE id = ?
                """,
                (model, int(dim), blob, msg_id),
            )
        finally:
            conn.close()

    async def set_message_embedding(
        self,
        msg_id: str,
        *,
        model: str,
        dim: int,
        vector: Sequence[float],
    ) -> None:
        """Persist an embedding vector for a message.

        Re-importing here (rather than at module load) keeps the
        attachments package fully optional — the chat store stays
        usable even when ``backend.core.attachments`` is not on the
        path (e.g. tiny installs).
        """

        if not self.enabled or not msg_id or not vector:
            return
        from backend.core.attachments.index import pack_vector

        blob = pack_vector(list(vector))
        await asyncio.to_thread(
            self._set_message_embedding_sync,
            msg_id,
            model=model,
            dim=dim,
            blob=blob,
        )

    def _get_message_embeddings_sync(
        self, msg_ids: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        if not msg_ids:
            return {}
        from backend.core.attachments.index import unpack_vector

        placeholders = ",".join("?" for _ in msg_ids)
        sql = (
            f"SELECT id, embedding_model, embedding_dim, embedding_blob "
            f"FROM messages WHERE id IN ({placeholders})"
        )
        conn = self._connect()
        try:
            rows = conn.execute(sql, list(msg_ids)).fetchall()
        finally:
            conn.close()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            blob = row["embedding_blob"]
            if not blob:
                continue
            out[row["id"]] = {
                "model": row["embedding_model"],
                "dim": int(row["embedding_dim"] or 0),
                "vector": unpack_vector(blob),
            }
        return out

    async def get_message_embeddings(
        self, msg_ids: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        if not self.enabled or not msg_ids:
            return {}
        return await asyncio.to_thread(
            self._get_message_embeddings_sync, list(msg_ids)
        )

    def _list_messages_pending_embedding_sync(
        self, *, limit: int
    ) -> list[Message]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE embedding_blob IS NULL
                  AND content IS NOT NULL
                  AND length(content) > 0
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_message(r) for r in rows]

    async def list_messages_pending_embedding(
        self, *, limit: int = 100
    ) -> list[Message]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._list_messages_pending_embedding_sync,
            limit=max(1, min(int(limit), 1000)),
        )

    def _count_messages_pending_embedding_sync(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM messages
                WHERE embedding_blob IS NULL
                  AND content IS NOT NULL
                  AND length(content) > 0
                """
            ).fetchone()
        finally:
            conn.close()
        return int(row["c"]) if row else 0

    async def count_messages_pending_embedding(self) -> int:
        if not self.enabled:
            return 0
        return await asyncio.to_thread(
            self._count_messages_pending_embedding_sync
        )

    # -- tool calls -----------------------------------------------------

    def _upsert_tool_call_sync(self, call: ToolCall) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_calls (
                    id, message_id, slug, action_id, args_json, status,
                    started_at, completed_at, policy_token,
                    result_json, cost_usd, error, trace_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call.id,
                    call.message_id,
                    call.slug,
                    call.action_id,
                    json.dumps(dict(call.args), separators=(",", ":")),
                    call.status,
                    call.started_at,
                    call.completed_at,
                    call.policy_token,
                    json.dumps(dict(call.result), separators=(",", ":"))
                    if call.result is not None
                    else None,
                    call.cost_usd,
                    call.error,
                    call.trace_id,
                ),
            )
        finally:
            conn.close()

    async def upsert_tool_call(self, call: ToolCall) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(self._upsert_tool_call_sync, call)

    def _list_tool_calls_sync(self, message_id: str) -> list[ToolCall]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tool_calls WHERE message_id = ? "
                "ORDER BY started_at ASC",
                (message_id,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_tool_call(r) for r in rows]

    async def list_tool_calls(self, message_id: str) -> list[ToolCall]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(self._list_tool_calls_sync, message_id)

    @staticmethod
    def _row_to_tool_call(row: sqlite3.Row) -> ToolCall:
        try:
            args = json.loads(row["args_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            args = {}
        result = None
        if row["result_json"]:
            try:
                result = json.loads(row["result_json"])
            except (json.JSONDecodeError, TypeError):
                result = None
        return ToolCall(
            id=row["id"],
            message_id=row["message_id"],
            slug=row["slug"],
            action_id=row["action_id"],
            args=args,
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            policy_token=row["policy_token"],
            result=result,
            cost_usd=row["cost_usd"],
            error=row["error"],
            trace_id=row["trace_id"],
        )

    # -- attachments (L1 stub) ------------------------------------------

    def _insert_attachment_sync(self, att: Attachment) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO attachments (
                    id, thread_id, message_id, mime, filename,
                    bytes_total, storage_path, extracted_text,
                    embedding_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    att.id,
                    att.thread_id,
                    att.message_id,
                    att.mime,
                    att.filename,
                    att.bytes_total,
                    att.storage_path,
                    att.extracted_text,
                    att.embedding_id,
                    att.created_at,
                ),
            )
        finally:
            conn.close()

    async def insert_attachment(self, att: Attachment) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(self._insert_attachment_sync, att)

    async def list_attachments(self, thread_id: str) -> list[Attachment]:
        if not self.enabled:
            return []

        def _run() -> list[Attachment]:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM attachments WHERE thread_id = ? "
                    "ORDER BY created_at ASC",
                    (thread_id,),
                ).fetchall()
            finally:
                conn.close()
            return [
                Attachment(
                    id=r["id"],
                    thread_id=r["thread_id"],
                    message_id=r["message_id"],
                    mime=r["mime"],
                    filename=r["filename"],
                    bytes_total=r["bytes_total"],
                    storage_path=r["storage_path"],
                    extracted_text=r["extracted_text"],
                    embedding_id=r["embedding_id"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

        return await asyncio.to_thread(_run)

    # -- saved searches (cockpit ⌘K palette) ---------------------------

    @staticmethod
    def _row_to_saved_search(row: sqlite3.Row) -> SavedSearch:
        try:
            filters = json.loads(row["filters_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            filters = {}
        if not isinstance(filters, dict):
            filters = {}
        scope = (row["scope"] or "all").strip().lower()
        if scope not in ("all", "chunks", "messages", "traces"):
            scope = "all"
        seen_hits: tuple[str, ...] = ()
        try:
            keys = row.keys()
        except Exception:
            keys = []
        if "seen_hits_json" in keys:
            try:
                raw_seen = json.loads(row["seen_hits_json"] or "[]")
            except (json.JSONDecodeError, TypeError):
                raw_seen = []
            if isinstance(raw_seen, list):
                seen_hits = tuple(str(x) for x in raw_seen if x)
        last_alert_at: float | None = None
        if "last_alert_at" in keys:
            last_alert_at = row["last_alert_at"]
        snoozed_until: float | None = None
        if "snoozed_until" in keys:
            snoozed_until = row["snoozed_until"]
        return SavedSearch(
            id=row["id"],
            label=row["label"],
            query=row["query"],
            scope=scope,  # type: ignore[arg-type]
            filters=filters,
            pinned=bool(row["pinned"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_run_at=row["last_run_at"],
            seen_hits=seen_hits,
            last_alert_at=last_alert_at,
            snoozed_until=snoozed_until,
        )

    def _insert_saved_search_sync(self, saved: SavedSearch) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO saved_searches (
                    id, label, query, scope, filters_json, pinned,
                    created_at, updated_at, last_run_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    saved.id,
                    saved.label,
                    saved.query,
                    saved.scope,
                    json.dumps(dict(saved.filters), separators=(",", ":")),
                    1 if saved.pinned else 0,
                    saved.created_at,
                    saved.updated_at,
                    saved.last_run_at,
                ),
            )
        finally:
            conn.close()

    async def insert_saved_search(self, saved: SavedSearch) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(self._insert_saved_search_sync, saved)

    def _get_saved_search_sync(self, search_id: str) -> SavedSearch | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_saved_search(row) if row else None

    async def get_saved_search(self, search_id: str) -> SavedSearch | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._get_saved_search_sync, search_id
        )

    def _list_saved_searches_sync(self, *, limit: int) -> list[SavedSearch]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM saved_searches
                ORDER BY pinned DESC, updated_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_saved_search(r) for r in rows]

    async def list_saved_searches(
        self, *, limit: int = 100
    ) -> list[SavedSearch]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._list_saved_searches_sync,
            limit=max(1, min(int(limit), 500)),
        )

    def _update_saved_search_sync(
        self,
        search_id: str,
        *,
        fields: Mapping[str, Any],
    ) -> SavedSearch | None:
        if not fields:
            return self._get_saved_search_sync(search_id)
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            clauses.append(f"{key} = ?")
            params.append(value)
        clauses.append("updated_at = ?")
        params.append(_now())
        params.append(search_id)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE saved_searches SET {', '.join(clauses)} WHERE id = ?",
                params,
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_saved_search(row) if row else None

    async def update_saved_search(
        self,
        search_id: str,
        *,
        label: str | None = None,
        query: str | None = None,
        scope: SavedSearchScope | None = None,
        filters: Mapping[str, Any] | None = None,
        pinned: bool | None = None,
    ) -> SavedSearch | None:
        if not self.enabled:
            return None
        fields: dict[str, Any] = {}
        if label is not None:
            cleaned = label.strip() or "untitled"
            fields["label"] = cleaned
        if query is not None:
            fields["query"] = query
        if scope is not None:
            if scope not in ("all", "chunks", "messages", "traces"):
                raise ValueError(f"invalid_scope: {scope}")
            fields["scope"] = scope
        if filters is not None:
            fields["filters_json"] = json.dumps(
                dict(filters), separators=(",", ":")
            )
        if pinned is not None:
            fields["pinned"] = 1 if pinned else 0
        return await asyncio.to_thread(
            self._update_saved_search_sync,
            search_id,
            fields=fields,
        )

    def _delete_saved_search_sync(self, search_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM saved_searches WHERE id = ?",
                (search_id,),
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    async def delete_saved_search(self, search_id: str) -> bool:
        if not self.enabled:
            return False
        return await asyncio.to_thread(
            self._delete_saved_search_sync, search_id
        )

    def _stamp_saved_search_run_sync(
        self, search_id: str, *, ts: float
    ) -> SavedSearch | None:
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE saved_searches SET last_run_at = ? WHERE id = ?",
                (ts, search_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_saved_search(row) if row else None

    async def stamp_saved_search_run(
        self, search_id: str
    ) -> SavedSearch | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._stamp_saved_search_run_sync,
            search_id,
            ts=_now(),
        )

    def _record_saved_search_alert_sync(
        self,
        search_id: str,
        *,
        seen_hits: Sequence[str],
        had_new_hits: bool,
        ts: float,
    ) -> SavedSearch | None:
        """Persist the latest fingerprint snapshot + run/alert times.

        Always stamps ``last_run_at`` (poll happened); only stamps
        ``last_alert_at`` when ``had_new_hits`` so the cockpit can
        distinguish "polled and quiet" from "polled and surfaced new
        rows".
        """

        seen_json = json.dumps(
            [str(x) for x in seen_hits if x],
            separators=(",", ":"),
        )
        conn = self._connect()
        try:
            if had_new_hits:
                cur = conn.execute(
                    "UPDATE saved_searches "
                    "SET seen_hits_json = ?, last_run_at = ?, "
                    "    last_alert_at = ? "
                    "WHERE id = ?",
                    (seen_json, ts, ts, search_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE saved_searches "
                    "SET seen_hits_json = ?, last_run_at = ? "
                    "WHERE id = ?",
                    (seen_json, ts, search_id),
                )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_saved_search(row) if row else None

    async def record_saved_search_alert(
        self,
        search_id: str,
        *,
        seen_hits: Sequence[str],
        had_new_hits: bool,
    ) -> SavedSearch | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._record_saved_search_alert_sync,
            search_id,
            seen_hits=list(seen_hits),
            had_new_hits=had_new_hits,
            ts=_now(),
        )

    def _set_saved_search_snooze_sync(
        self,
        search_id: str,
        *,
        snoozed_until: float | None,
    ) -> SavedSearch | None:
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE saved_searches "
                "SET snoozed_until = ?, updated_at = ? "
                "WHERE id = ?",
                (snoozed_until, _now(), search_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_saved_search(row) if row else None

    async def set_saved_search_snooze(
        self,
        search_id: str,
        *,
        snoozed_until: float | None,
    ) -> SavedSearch | None:
        """Mute (or un-mute) saved-search alerts.

        ``snoozed_until=None`` clears the snooze. Polling continues
        regardless — the snapshot is still maintained so resuming
        alerts doesn't cause a flood of "everything is new" the
        moment the snooze ends.
        """

        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._set_saved_search_snooze_sync,
            search_id,
            snoozed_until=snoozed_until,
        )


def _now() -> float:
    import time

    return time.time()


_SINGLETON: Optional[ChatStore] = None


def get_chat_store() -> ChatStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ChatStore()
    return _SINGLETON


def reset_chat_store() -> None:
    global _SINGLETON
    _SINGLETON = None
