"""SQLite-backed attachment + chunk store.

Lives inside the same DB as the chat tables (``~/.tars/chat.sqlite``)
because attachments are per-thread. Auto-migrates the existing
``attachments`` table with the new metadata columns and adds
``attachment_chunks``.

Embedding vectors are persisted as raw little-endian float32 blobs to
keep the schema stdlib-only (no NumPy dep on the storage layer; we
only convert to NumPy at retrieval time when it's already imported).
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from backend.core.chat.models import (
    Attachment,
    new_attachment_id,
)
from backend.core.chat.store import ChatStore, get_chat_store


# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------

_ATTACHMENTS_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE attachments ADD COLUMN content_hash TEXT",
    "ALTER TABLE attachments ADD COLUMN status TEXT NOT NULL DEFAULT 'ready'",
    "ALTER TABLE attachments ADD COLUMN error TEXT",
    "ALTER TABLE attachments ADD COLUMN meta_json TEXT",
    "ALTER TABLE attachments ADD COLUMN char_count INTEGER NOT NULL DEFAULT 0",
    # Wave 102 — file management UI columns. All additive with safe
    # defaults so existing rows stay valid; ALTER ... ADD COLUMN is
    # idempotent-by-failure (we swallow OperationalError below).
    "ALTER TABLE attachments ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE attachments ADD COLUMN category TEXT NOT NULL DEFAULT 'uncategorized'",
    "ALTER TABLE attachments ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE attachments ADD COLUMN deleted_at REAL",
)

_ATTACHMENTS_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_attachments_category ON attachments (category)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_pinned ON attachments (pinned)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_deleted ON attachments (deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_created ON attachments (created_at)",
)

_CHUNK_TABLE = """
CREATE TABLE IF NOT EXISTS attachment_chunks (
    id TEXT PRIMARY KEY,
    attachment_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    ord INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    heading TEXT,
    page INTEGER,
    embedding_model TEXT,
    embedding_dim INTEGER,
    embedding_blob BLOB,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (attachment_id) REFERENCES attachments (id)
);
"""

_CHUNK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_chunks_thread ON attachment_chunks (thread_id);
CREATE INDEX IF NOT EXISTS idx_chunks_attachment ON attachment_chunks (attachment_id);
CREATE INDEX IF NOT EXISTS idx_chunks_ord ON attachment_chunks (attachment_id, ord);
"""


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class AttachmentRecord:
    """One stored attachment + its extracted text + metadata."""

    id: str
    thread_id: str
    message_id: str | None
    mime: str
    filename: str | None
    bytes_total: int
    storage_path: str
    extracted_text: str | None
    embedding_id: str | None
    created_at: float
    content_hash: str | None
    status: str
    error: str | None
    meta: Mapping[str, Any]
    char_count: int
    # Wave 102 file management additions.
    tags: tuple[str, ...] = ()
    category: str = "uncategorized"
    pinned: bool = False
    deleted_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "message_id": self.message_id,
            "mime": self.mime,
            "filename": self.filename,
            "bytes_total": self.bytes_total,
            "char_count": self.char_count,
            "extracted_text_preview": (self.extracted_text or "")[:280],
            "status": self.status,
            "error": self.error,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "meta": dict(self.meta),
            # Wave 102.
            "tags": list(self.tags),
            "category": self.category,
            "pinned": bool(self.pinned),
            "deleted_at": self.deleted_at,
        }


@dataclass(frozen=True)
class Chunk:
    """A retrievable slice of an attachment."""

    id: str
    attachment_id: str
    thread_id: str
    ord: int
    text: str
    char_start: int
    char_end: int
    heading: str | None
    page: int | None
    embedding_model: str | None
    embedding_dim: int | None
    embedding: list[float] | None
    tokens_in: int
    created_at: float
    # joined from attachments — populated by retrieval/list helpers.
    filename: str | None = None
    mime: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "attachment_id": self.attachment_id,
            "thread_id": self.thread_id,
            "ord": self.ord,
            "text": self.text,
            "heading": self.heading,
            "page": self.page,
            "embedding_model": self.embedding_model,
            "filename": self.filename,
            "mime": self.mime,
        }


# ---------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------


class AttachmentStore:
    """Wraps the chat SQLite DB to manage attachments + chunks.

    Shares the same connection discipline as :class:`ChatStore`: every
    write is wrapped in ``asyncio.to_thread``; the store itself is a
    singleton via :func:`get_attachment_store`.
    """

    def __init__(self, chat_store: ChatStore | None = None) -> None:
        self.chat = chat_store or get_chat_store()
        if self.chat.enabled:
            self._migrate()

    # -- helpers --------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        # Reuse ChatStore's path / pragmas — the migration sits inside
        # the same DB so foreign keys to ``attachments`` resolve.
        return self.chat._connect()

    def _migrate(self) -> None:
        conn = self._connect()
        try:
            for stmt in _ATTACHMENTS_MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    continue
            for stmt in _ATTACHMENTS_INDEXES:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    continue
            conn.executescript(_CHUNK_TABLE)
            conn.executescript(_CHUNK_INDEX)
        finally:
            conn.close()

    # -- attachments ---------------------------------------------------

    async def upsert_attachment(self, record: AttachmentRecord) -> None:
        if not self.chat.enabled:
            return
        await asyncio.to_thread(self._upsert_attachment_sync, record)

    def _upsert_attachment_sync(self, record: AttachmentRecord) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO attachments (
                    id, thread_id, message_id, mime, filename, bytes_total,
                    storage_path, extracted_text, embedding_id, created_at,
                    content_hash, status, error, meta_json, char_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    extracted_text = excluded.extracted_text,
                    status = excluded.status,
                    error = excluded.error,
                    meta_json = excluded.meta_json,
                    char_count = excluded.char_count,
                    embedding_id = excluded.embedding_id
                """,
                (
                    record.id,
                    record.thread_id,
                    record.message_id,
                    record.mime,
                    record.filename,
                    record.bytes_total,
                    record.storage_path,
                    record.extracted_text,
                    record.embedding_id,
                    record.created_at,
                    record.content_hash,
                    record.status,
                    record.error,
                    json.dumps(dict(record.meta), separators=(",", ":")),
                    record.char_count,
                ),
            )
        finally:
            conn.close()

    async def get_attachment(self, attachment_id: str) -> AttachmentRecord | None:
        if not self.chat.enabled:
            return None
        return await asyncio.to_thread(self._get_attachment_sync, attachment_id)

    def _get_attachment_sync(self, attachment_id: str) -> AttachmentRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_record(row) if row else None

    async def list_attachments(
        self, thread_id: str
    ) -> list[AttachmentRecord]:
        if not self.chat.enabled:
            return []
        return await asyncio.to_thread(self._list_attachments_sync, thread_id)

    def _list_attachments_sync(self, thread_id: str) -> list[AttachmentRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM attachments WHERE thread_id = ? "
                "ORDER BY created_at ASC",
                (thread_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_record(r) for r in rows]

    async def find_by_hash(
        self, thread_id: str, content_hash: str
    ) -> AttachmentRecord | None:
        if not self.chat.enabled:
            return None

        def _run() -> AttachmentRecord | None:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM attachments WHERE thread_id = ? "
                    "AND content_hash = ? LIMIT 1",
                    (thread_id, content_hash),
                ).fetchone()
            finally:
                conn.close()
            return _row_to_record(row) if row else None

        return await asyncio.to_thread(_run)

    async def delete_attachment(self, attachment_id: str) -> bool:
        if not self.chat.enabled:
            return False
        return await asyncio.to_thread(
            self._delete_attachment_sync, attachment_id
        )

    def _delete_attachment_sync(self, attachment_id: str) -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM attachment_chunks WHERE attachment_id = ?",
                (attachment_id,),
            )
            cur = conn.execute(
                "DELETE FROM attachments WHERE id = ?", (attachment_id,)
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    # -- Wave 102 file-management helpers ------------------------------

    async def query_files(
        self,
        *,
        category: str | None = None,
        tag: str | None = None,
        since: float | None = None,
        until: float | None = None,
        pinned: bool | None = None,
        thread_id: str | None = None,
        include_deleted: bool = False,
        sort: str = "created_desc",
        limit: int = 200,
        offset: int = 0,
    ) -> list[AttachmentRecord]:
        """List attachments across all threads with file-browser filters.

        ``sort`` accepts ``created_desc`` (default), ``created_asc``,
        ``size_desc``, ``size_asc``, ``filename_asc``, ``filename_desc``.
        """

        if not self.chat.enabled:
            return []
        return await asyncio.to_thread(
            self._query_files_sync,
            category=category,
            tag=tag,
            since=since,
            until=until,
            pinned=pinned,
            thread_id=thread_id,
            include_deleted=include_deleted,
            sort=sort,
            limit=int(limit),
            offset=int(offset),
        )

    def _query_files_sync(
        self,
        *,
        category: str | None,
        tag: str | None,
        since: float | None,
        until: float | None,
        pinned: bool | None,
        thread_id: str | None,
        include_deleted: bool,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[AttachmentRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("(deleted_at IS NULL)")
        if category:
            clauses.append("category = ?")
            params.append(category)
        if pinned is not None:
            clauses.append("pinned = ?")
            params.append(1 if pinned else 0)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(float(since))
        if until is not None:
            clauses.append("created_at <= ?")
            params.append(float(until))
        if thread_id:
            clauses.append("thread_id = ?")
            params.append(thread_id)
        if tag:
            # JSON membership probe — works on stock SQLite without
            # JSON1 by string-matching the encoded literal. Tags are
            # stored as a JSON array of strings.
            clauses.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')

        order_map = {
            "created_desc": "created_at DESC",
            "created_asc": "created_at ASC",
            "size_desc": "bytes_total DESC",
            "size_asc": "bytes_total ASC",
            "filename_asc": "filename ASC",
            "filename_desc": "filename DESC",
        }
        order_sql = order_map.get(sort, "created_at DESC")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM attachments{where} "
            f"ORDER BY {order_sql} LIMIT ? OFFSET ?"
        )
        params.append(max(1, min(int(limit), 1000)))
        params.append(max(0, int(offset)))

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [_row_to_record(r) for r in rows]

    async def update_file_metadata(
        self,
        attachment_id: str,
        *,
        tags: Sequence[str] | None = None,
        category: str | None = None,
        pinned: bool | None = None,
        filename: str | None = None,
    ) -> AttachmentRecord | None:
        """Patch tags / category / pinned / filename on a single file."""

        if not self.chat.enabled:
            return None
        return await asyncio.to_thread(
            self._update_file_metadata_sync,
            attachment_id,
            tags=tags,
            category=category,
            pinned=pinned,
            filename=filename,
        )

    def _update_file_metadata_sync(
        self,
        attachment_id: str,
        *,
        tags: Sequence[str] | None,
        category: str | None,
        pinned: bool | None,
        filename: str | None,
    ) -> AttachmentRecord | None:
        sets: list[str] = []
        params: list[Any] = []
        if tags is not None:
            cleaned = _normalise_tags(tags)
            sets.append("tags_json = ?")
            params.append(json.dumps(cleaned, separators=(",", ":")))
        if category is not None:
            sets.append("category = ?")
            params.append(str(category)[:64])
        if pinned is not None:
            sets.append("pinned = ?")
            params.append(1 if pinned else 0)
        if filename is not None:
            sets.append("filename = ?")
            params.append(str(filename)[:512])
        if not sets:
            return self._get_attachment_sync(attachment_id)
        params.append(attachment_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE attachments SET {', '.join(sets)} WHERE id = ?",
                params,
            )
        finally:
            conn.close()
        return self._get_attachment_sync(attachment_id)

    async def soft_delete_attachment(
        self, attachment_id: str
    ) -> AttachmentRecord | None:
        """Mark file as deleted (deleted_at = now). Reversible."""

        if not self.chat.enabled:
            return None
        return await asyncio.to_thread(
            self._soft_delete_sync, attachment_id
        )

    def _soft_delete_sync(
        self, attachment_id: str
    ) -> AttachmentRecord | None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE attachments SET deleted_at = ? WHERE id = ?",
                (time.time(), attachment_id),
            )
        finally:
            conn.close()
        return self._get_attachment_sync(attachment_id)

    async def restore_attachment(
        self, attachment_id: str
    ) -> AttachmentRecord | None:
        """Undo a soft-delete."""

        if not self.chat.enabled:
            return None

        def _run() -> AttachmentRecord | None:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE attachments SET deleted_at = NULL WHERE id = ?",
                    (attachment_id,),
                )
            finally:
                conn.close()
            return self._get_attachment_sync(attachment_id)

        return await asyncio.to_thread(_run)

    async def file_stats(self) -> dict[str, Any]:
        """Aggregate counts + sizes for the file browser header strip.

        Returns ``{total_count, total_bytes, by_category, by_extension,
        deleted_count, pinned_count}``. Cheap — single DB pass.
        """

        if not self.chat.enabled:
            return {
                "total_count": 0,
                "total_bytes": 0,
                "by_category": {},
                "by_extension": {},
                "deleted_count": 0,
                "pinned_count": 0,
            }
        return await asyncio.to_thread(self._file_stats_sync)

    def _file_stats_sync(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            totals = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(bytes_total), 0) "
                "FROM attachments WHERE deleted_at IS NULL"
            ).fetchone()
            cat_rows = conn.execute(
                "SELECT category, COUNT(*) FROM attachments "
                "WHERE deleted_at IS NULL GROUP BY category"
            ).fetchall()
            file_rows = conn.execute(
                "SELECT filename FROM attachments WHERE deleted_at IS NULL"
            ).fetchall()
            deleted = conn.execute(
                "SELECT COUNT(*) FROM attachments WHERE deleted_at IS NOT NULL"
            ).fetchone()
            pinned = conn.execute(
                "SELECT COUNT(*) FROM attachments "
                "WHERE pinned = 1 AND deleted_at IS NULL"
            ).fetchone()
        finally:
            conn.close()

        by_ext: dict[str, int] = {}
        for (filename,) in file_rows:
            ext = _extension_of(filename)
            by_ext[ext] = by_ext.get(ext, 0) + 1

        by_cat = {row[0] or "uncategorized": int(row[1]) for row in cat_rows}
        return {
            "total_count": int(totals[0]) if totals else 0,
            "total_bytes": int(totals[1]) if totals else 0,
            "by_category": by_cat,
            "by_extension": by_ext,
            "deleted_count": int(deleted[0]) if deleted else 0,
            "pinned_count": int(pinned[0]) if pinned else 0,
        }

    # -- chunks --------------------------------------------------------

    async def replace_chunks(
        self,
        attachment_id: str,
        thread_id: str,
        chunks: Sequence[Chunk],
    ) -> None:
        if not self.chat.enabled:
            return
        await asyncio.to_thread(
            self._replace_chunks_sync, attachment_id, thread_id, list(chunks)
        )

    def _replace_chunks_sync(
        self,
        attachment_id: str,
        thread_id: str,
        chunks: list[Chunk],
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM attachment_chunks WHERE attachment_id = ?",
                (attachment_id,),
            )
            for chunk in chunks:
                blob = (
                    pack_vector(chunk.embedding) if chunk.embedding else None
                )
                conn.execute(
                    """
                    INSERT INTO attachment_chunks (
                        id, attachment_id, thread_id, ord, text,
                        char_start, char_end, heading, page,
                        embedding_model, embedding_dim, embedding_blob,
                        tokens_in, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        attachment_id,
                        thread_id,
                        chunk.ord,
                        chunk.text,
                        chunk.char_start,
                        chunk.char_end,
                        chunk.heading,
                        chunk.page,
                        chunk.embedding_model,
                        chunk.embedding_dim,
                        blob,
                        chunk.tokens_in,
                        chunk.created_at,
                    ),
                )
        finally:
            conn.close()

    async def list_chunks(
        self,
        thread_id: str,
        *,
        limit: int = 5000,
        attachment_id: str | None = None,
    ) -> list[Chunk]:
        if not self.chat.enabled:
            return []
        return await asyncio.to_thread(
            self._list_chunks_sync,
            thread_id,
            limit=limit,
            attachment_id=attachment_id,
        )

    def _list_chunks_sync(
        self,
        thread_id: str,
        *,
        limit: int,
        attachment_id: str | None,
    ) -> list[Chunk]:
        conn = self._connect()
        try:
            params: list[Any] = [thread_id]
            clauses = ["c.thread_id = ?"]
            if attachment_id:
                clauses.append("c.attachment_id = ?")
                params.append(attachment_id)
            params.append(int(limit))
            rows = conn.execute(
                f"""
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.attachment_id, c.ord
                LIMIT ?
                """,
                params,
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r) for r in rows]

    async def update_chunk_embedding(
        self,
        *,
        chunk_id: str,
        model: str,
        dim: int,
        vector: Sequence[float],
    ) -> bool:
        """Rewrite a single chunk's vector in place.

        Used by the re-embed pipeline (operator promotes from
        the offline ``HashEmbedder`` to OpenAI once a key is set).
        Returns ``True`` when the row was found and updated.
        """

        if not self.chat.enabled:
            return False
        return await asyncio.to_thread(
            self._update_chunk_embedding_sync,
            chunk_id=chunk_id,
            model=model,
            dim=int(dim),
            blob=pack_vector(vector),
        )

    def _update_chunk_embedding_sync(
        self,
        *,
        chunk_id: str,
        model: str,
        dim: int,
        blob: bytes,
    ) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                UPDATE attachment_chunks
                SET embedding_model = ?,
                    embedding_dim = ?,
                    embedding_blob = ?
                WHERE id = ?
                """,
                (model, dim, blob, chunk_id),
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    async def list_chunks_by_model(
        self,
        *,
        embedding_model: str | None,
        thread_id: str | None = None,
        limit: int = 500,
    ) -> list[Chunk]:
        """List chunks whose current ``embedding_model`` matches.

        ``embedding_model=None`` matches rows that have never been
        embedded (useful for backfill paths). The optional
        ``thread_id`` narrows the scope.
        """

        if not self.chat.enabled:
            return []
        return await asyncio.to_thread(
            self._list_chunks_by_model_sync,
            embedding_model=embedding_model,
            thread_id=thread_id,
            limit=int(limit),
        )

    def _list_chunks_by_model_sync(
        self,
        *,
        embedding_model: str | None,
        thread_id: str | None,
        limit: int,
    ) -> list[Chunk]:
        conn = self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if embedding_model is None:
                clauses.append("c.embedding_model IS NULL")
            else:
                clauses.append("c.embedding_model = ?")
                params.append(embedding_model)
            if thread_id is not None:
                clauses.append("c.thread_id = ?")
                params.append(thread_id)
            params.append(int(limit))
            where = " AND ".join(clauses)
            rows = conn.execute(
                f"""
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE {where}
                ORDER BY c.created_at ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r) for r in rows]

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Fetch a single chunk by id, or ``None`` if missing."""

        if not self.chat.enabled:
            return None
        return await asyncio.to_thread(self._get_chunk_sync, chunk_id)

    def _get_chunk_sync(self, chunk_id: str) -> Chunk | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE c.id = ?
                LIMIT 1
                """,
                (chunk_id,),
            ).fetchone()
        finally:
            conn.close()
        return _row_to_chunk(row) if row else None

    async def get_chunk_neighbours(
        self,
        chunk_id: str,
        *,
        before: int = 1,
        after: int = 1,
    ) -> tuple[Chunk, list[Chunk], list[Chunk]] | None:
        """Return (chunk, before, after) by ``ord`` adjacency.

        ``before`` / ``after`` clamp to ``[0, 10]`` -- large windows
        defeat the purpose of a hover preview and would also force
        the cockpit to load too much text. The lists are sorted in
        ord-ascending order, so ``before[-1]`` is the chunk
        immediately preceding the queried one and ``after[0]`` is
        the one immediately following it. Returns ``None`` when
        the chunk is not found (so the HTTP layer can map it to a
        404).
        """

        if not self.chat.enabled:
            return None
        before_n = max(0, min(int(before), 10))
        after_n = max(0, min(int(after), 10))
        return await asyncio.to_thread(
            self._get_chunk_neighbours_sync,
            chunk_id,
            before_n,
            after_n,
        )

    def _get_chunk_neighbours_sync(
        self,
        chunk_id: str,
        before: int,
        after: int,
    ) -> tuple[Chunk, list[Chunk], list[Chunk]] | None:
        conn = self._connect()
        try:
            target_row = conn.execute(
                """
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE c.id = ?
                LIMIT 1
                """,
                (chunk_id,),
            ).fetchone()
            if target_row is None:
                return None
            target = _row_to_chunk(target_row)

            before_rows: list[sqlite3.Row] = []
            if before > 0:
                before_rows = list(
                    conn.execute(
                        """
                        SELECT
                            c.*,
                            a.filename AS att_filename,
                            a.mime AS att_mime
                        FROM attachment_chunks c
                        LEFT JOIN attachments a ON a.id = c.attachment_id
                        WHERE c.attachment_id = ? AND c.ord < ?
                        ORDER BY c.ord DESC
                        LIMIT ?
                        """,
                        (target.attachment_id, target.ord, before),
                    ).fetchall()
                )

            after_rows: list[sqlite3.Row] = []
            if after > 0:
                after_rows = list(
                    conn.execute(
                        """
                        SELECT
                            c.*,
                            a.filename AS att_filename,
                            a.mime AS att_mime
                        FROM attachment_chunks c
                        LEFT JOIN attachments a ON a.id = c.attachment_id
                        WHERE c.attachment_id = ? AND c.ord > ?
                        ORDER BY c.ord ASC
                        LIMIT ?
                        """,
                        (target.attachment_id, target.ord, after),
                    ).fetchall()
                )
        finally:
            conn.close()

        before_chunks = [_row_to_chunk(r) for r in before_rows]
        before_chunks.reverse()  # ord ascending for the caller.
        after_chunks = [_row_to_chunk(r) for r in after_rows]
        return target, before_chunks, after_chunks

    async def chunk_count(self, thread_id: str) -> int:
        if not self.chat.enabled:
            return 0

        def _run() -> int:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM attachment_chunks WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
            finally:
                conn.close()
            return int(row[0]) if row else 0

        return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------
# Row → dataclass helpers
# ---------------------------------------------------------------------


def _row_to_record(row: sqlite3.Row) -> AttachmentRecord:
    meta_raw = (
        row["meta_json"]
        if "meta_json" in row.keys()
        else None
    )
    try:
        meta = json.loads(meta_raw) if meta_raw else {}
    except (TypeError, json.JSONDecodeError):
        meta = {}

    tags_raw = _safe(row, "tags_json")
    try:
        tags_list = json.loads(tags_raw) if tags_raw else []
        if not isinstance(tags_list, list):
            tags_list = []
    except (TypeError, json.JSONDecodeError):
        tags_list = []
    tags_tuple = tuple(str(t) for t in tags_list)

    pinned_raw = _safe(row, "pinned")
    deleted_at_raw = _safe(row, "deleted_at")

    return AttachmentRecord(
        id=row["id"],
        thread_id=row["thread_id"],
        message_id=row["message_id"],
        mime=row["mime"],
        filename=row["filename"],
        bytes_total=row["bytes_total"],
        storage_path=row["storage_path"],
        extracted_text=row["extracted_text"],
        embedding_id=row["embedding_id"],
        created_at=row["created_at"],
        content_hash=_safe(row, "content_hash"),
        status=_safe(row, "status") or "ready",
        error=_safe(row, "error"),
        meta=meta,
        char_count=int(_safe(row, "char_count") or 0),
        tags=tags_tuple,
        category=_safe(row, "category") or "uncategorized",
        pinned=bool(int(pinned_raw or 0)),
        deleted_at=float(deleted_at_raw) if deleted_at_raw is not None else None,
    )


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    blob = row["embedding_blob"]
    embedding = unpack_vector(blob) if blob else None
    return Chunk(
        id=row["id"],
        attachment_id=row["attachment_id"],
        thread_id=row["thread_id"],
        ord=int(row["ord"]),
        text=row["text"],
        char_start=int(row["char_start"]),
        char_end=int(row["char_end"]),
        heading=row["heading"],
        page=row["page"],
        embedding_model=row["embedding_model"],
        embedding_dim=int(row["embedding_dim"]) if row["embedding_dim"] else None,
        embedding=embedding,
        tokens_in=int(row["tokens_in"] or 0),
        created_at=float(row["created_at"]),
        filename=_safe(row, "att_filename"),
        mime=_safe(row, "att_mime"),
    )


def _safe(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _normalise_tags(tags: Iterable[Any]) -> list[str]:
    """Strip / dedup / cap tag list per the public contract.

    Rules: each tag is a string of length 1..32, lowercase-folded
    only on whitespace. Order preserved (operator-meaningful).
    """

    seen: set[str] = set()
    out: list[str] = []
    for raw in tags or ():
        if raw is None:
            continue
        t = str(raw).strip()
        if not t:
            continue
        if len(t) > 32:
            t = t[:32]
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= 64:
            break
    return out


def _extension_of(filename: str | None) -> str:
    if not filename:
        return ""
    name = str(filename).rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()[:16]


# ---------------------------------------------------------------------
# Vector packing helpers
# ---------------------------------------------------------------------


def pack_vector(values: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(blob: bytes) -> list[float]:
    if not blob:
        return []
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


# ---------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------


_SINGLETON: Optional[AttachmentStore] = None


def get_attachment_store() -> AttachmentStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = AttachmentStore()
    return _SINGLETON


def reset_attachment_store() -> None:
    global _SINGLETON
    _SINGLETON = None
