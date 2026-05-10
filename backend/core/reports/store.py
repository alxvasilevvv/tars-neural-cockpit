"""SQLite-backed store for the reports module (Wave 103).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.outreach.store`. The DB lives at
``~/.tars/reports.sqlite`` by default; override with
``TARS_REPORTS_DB_PATH``. Disable the whole module with
``TARS_REPORTS_STORE=disabled`` (the package-level helpers will
short-circuit on a disabled store).

Tables:

- ``templates``  reusable report templates (built-ins + custom).
- ``runs``       one row per render; tracks lifecycle.

Auto-creates schema on first connect.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from typing import Any

from .models import (
    REPORT_KINDS,
    ReportRun,
    ReportTemplate,
    new_run_id,
    new_template_id,
)


DEFAULT_DB_PATH = "~/.tars/reports.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    schema_json TEXT NOT NULL DEFAULT '{}',
    template_path TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_builtin INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    inputs_json TEXT NOT NULL DEFAULT '{}',
    output_path TEXT NOT NULL DEFAULT '',
    output_kind TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    recipient_emails_json TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL,
    generated_at REAL,
    error TEXT,
    bytes_size INTEGER,
    FOREIGN KEY (template_id) REFERENCES templates (id)
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_template ON runs (template_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_templates_kind ON templates (kind);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_REPORTS_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_REPORTS_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


# ---------- row mappers -----------------------------------------------------


def _row_to_template(row: sqlite3.Row | tuple) -> ReportTemplate:
    return ReportTemplate(
        id=row[0],
        name=row[1],
        slug=row[2],
        kind=row[3],
        schema=json.loads(row[4] or "{}"),
        template_path=row[5] or "",
        description=row[6] or "",
        is_builtin=bool(row[7]),
        created_at=float(row[8]),
    )


def _row_to_run(row: sqlite3.Row | tuple) -> ReportRun:
    return ReportRun(
        id=row[0],
        template_id=row[1],
        inputs=json.loads(row[2] or "{}"),
        output_path=row[3] or "",
        output_kind=row[4] or "",
        status=row[5] or "pending",
        recipient_emails=json.loads(row[6] or "[]"),
        created_at=float(row[7]),
        generated_at=float(row[8]) if row[8] is not None else None,
        error=row[9],
        bytes_size=int(row[10]) if row[10] is not None else None,
    )


# ---------- store -----------------------------------------------------------


class ReportStore:
    """SQLite-backed CRUD + queries for the reports module."""

    def __init__(self, db_path: str | None = None) -> None:
        self._path = _resolve_db_path(db_path)
        self._enabled = not _is_disabled()
        if self._enabled:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._init_schema()

    # -- meta ----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> str:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- templates -----------------------------------------------------

    async def upsert_template(
        self,
        *,
        name: str,
        slug: str,
        kind: str,
        schema: dict[str, Any] | None = None,
        template_path: str = "",
        description: str = "",
        is_builtin: bool = False,
        template_id: str | None = None,
    ) -> ReportTemplate:
        if not self._enabled:
            raise RuntimeError("reports_store_disabled")
        if kind not in REPORT_KINDS:
            raise ValueError(f"unknown_kind:{kind}")
        return await asyncio.to_thread(
            self._upsert_template_sync,
            template_id,
            name,
            slug,
            kind,
            dict(schema or {}),
            template_path,
            description,
            bool(is_builtin),
        )

    def _upsert_template_sync(
        self,
        template_id: str | None,
        name: str,
        slug: str,
        kind: str,
        schema: dict[str, Any],
        template_path: str,
        description: str,
        is_builtin: bool,
    ) -> ReportTemplate:
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT id, created_at FROM templates WHERE slug=?", (slug,)
            ).fetchone()
            if existing:
                tid = existing[0]
                created_at = float(existing[1])
                conn.execute(
                    "UPDATE templates SET name=?, kind=?, schema_json=?, "
                    "template_path=?, description=?, is_builtin=? WHERE id=?",
                    (
                        name,
                        kind,
                        json.dumps(schema),
                        template_path,
                        description,
                        1 if is_builtin else 0,
                        tid,
                    ),
                )
            else:
                tid = template_id or new_template_id()
                created_at = time.time()
                conn.execute(
                    "INSERT INTO templates (id, name, slug, kind, schema_json, "
                    "template_path, description, is_builtin, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tid,
                        name,
                        slug,
                        kind,
                        json.dumps(schema),
                        template_path,
                        description,
                        1 if is_builtin else 0,
                        created_at,
                    ),
                )
            return ReportTemplate(
                id=tid,
                name=name,
                slug=slug,
                kind=kind,
                schema=dict(schema),
                template_path=template_path,
                description=description,
                is_builtin=is_builtin,
                created_at=created_at,
            )
        finally:
            conn.close()

    async def list_templates(self, *, kind: str | None = None) -> list[ReportTemplate]:
        if not self._enabled:
            return []
        return await asyncio.to_thread(self._list_templates_sync, kind)

    def _list_templates_sync(self, kind: str | None) -> list[ReportTemplate]:
        conn = self._connect()
        try:
            if kind:
                rows = conn.execute(
                    "SELECT id, name, slug, kind, schema_json, template_path, "
                    "description, is_builtin, created_at FROM templates "
                    "WHERE kind=? ORDER BY is_builtin DESC, created_at ASC",
                    (kind,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, slug, kind, schema_json, template_path, "
                    "description, is_builtin, created_at FROM templates "
                    "ORDER BY is_builtin DESC, created_at ASC"
                ).fetchall()
            return [_row_to_template(r) for r in rows]
        finally:
            conn.close()

    async def get_template(self, template_id: str) -> ReportTemplate | None:
        if not self._enabled or not template_id:
            return None
        return await asyncio.to_thread(self._get_template_sync, template_id)

    def _get_template_sync(self, template_id: str) -> ReportTemplate | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, name, slug, kind, schema_json, template_path, "
                "description, is_builtin, created_at FROM templates WHERE id=?",
                (template_id,),
            ).fetchone()
            return _row_to_template(row) if row else None
        finally:
            conn.close()

    async def get_template_by_slug(self, slug: str) -> ReportTemplate | None:
        if not self._enabled or not slug:
            return None
        return await asyncio.to_thread(self._get_template_by_slug_sync, slug)

    def _get_template_by_slug_sync(self, slug: str) -> ReportTemplate | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, name, slug, kind, schema_json, template_path, "
                "description, is_builtin, created_at FROM templates WHERE slug=?",
                (slug,),
            ).fetchone()
            return _row_to_template(row) if row else None
        finally:
            conn.close()

    async def delete_template(self, template_id: str) -> bool:
        if not self._enabled or not template_id:
            return False
        return await asyncio.to_thread(self._delete_template_sync, template_id)

    def _delete_template_sync(self, template_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM templates WHERE id=? AND is_builtin=0",
                (template_id,),
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    # -- runs ----------------------------------------------------------

    async def insert_run(self, run: ReportRun) -> ReportRun:
        if not self._enabled:
            raise RuntimeError("reports_store_disabled")
        return await asyncio.to_thread(self._insert_run_sync, run)

    def _insert_run_sync(self, run: ReportRun) -> ReportRun:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO runs (id, template_id, inputs_json, output_path, "
                "output_kind, status, recipient_emails_json, created_at, "
                "generated_at, error, bytes_size) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.id,
                    run.template_id,
                    json.dumps(run.inputs),
                    run.output_path,
                    run.output_kind,
                    run.status,
                    json.dumps(run.recipient_emails),
                    run.created_at,
                    run.generated_at,
                    run.error,
                    run.bytes_size,
                ),
            )
            return run
        finally:
            conn.close()

    async def get_run(self, run_id: str) -> ReportRun | None:
        if not self._enabled or not run_id:
            return None
        return await asyncio.to_thread(self._get_run_sync, run_id)

    def _get_run_sync(self, run_id: str) -> ReportRun | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, template_id, inputs_json, output_path, output_kind, "
                "status, recipient_emails_json, created_at, generated_at, error, "
                "bytes_size FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
            return _row_to_run(row) if row else None
        finally:
            conn.close()

    async def list_runs(
        self,
        *,
        status: str | None = None,
        template_id: str | None = None,
        since_ts: float | None = None,
        limit: int = 200,
    ) -> list[ReportRun]:
        if not self._enabled:
            return []
        return await asyncio.to_thread(
            self._list_runs_sync, status, template_id, since_ts, limit
        )

    def _list_runs_sync(
        self,
        status: str | None,
        template_id: str | None,
        since_ts: float | None,
        limit: int,
    ) -> list[ReportRun]:
        conn = self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if status:
                clauses.append("status=?")
                params.append(status)
            if template_id:
                clauses.append("template_id=?")
                params.append(template_id)
            if since_ts is not None:
                clauses.append("created_at>=?")
                params.append(float(since_ts))
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(int(max(1, min(limit, 1000))))
            rows = conn.execute(
                "SELECT id, template_id, inputs_json, output_path, output_kind, "
                "status, recipient_emails_json, created_at, generated_at, error, "
                f"bytes_size FROM runs {where} ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [_row_to_run(r) for r in rows]
        finally:
            conn.close()

    async def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        output_path: str | None = None,
        output_kind: str | None = None,
        generated_at: float | None = None,
        error: str | None = None,
        bytes_size: int | None = None,
        recipient_emails: list[str] | None = None,
    ) -> ReportRun | None:
        if not self._enabled:
            return None
        return await asyncio.to_thread(
            self._update_run_sync,
            run_id,
            status,
            output_path,
            output_kind,
            generated_at,
            error,
            bytes_size,
            recipient_emails,
        )

    def _update_run_sync(
        self,
        run_id: str,
        status: str | None,
        output_path: str | None,
        output_kind: str | None,
        generated_at: float | None,
        error: str | None,
        bytes_size: int | None,
        recipient_emails: list[str] | None,
    ) -> ReportRun | None:
        conn = self._connect()
        try:
            current = conn.execute(
                "SELECT id, template_id, inputs_json, output_path, output_kind, "
                "status, recipient_emails_json, created_at, generated_at, error, "
                "bytes_size FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
            if not current:
                return None
            sets: list[str] = []
            params: list[Any] = []
            if status is not None:
                sets.append("status=?")
                params.append(status)
            if output_path is not None:
                sets.append("output_path=?")
                params.append(output_path)
            if output_kind is not None:
                sets.append("output_kind=?")
                params.append(output_kind)
            if generated_at is not None:
                sets.append("generated_at=?")
                params.append(float(generated_at))
            if error is not None:
                sets.append("error=?")
                params.append(error)
            if bytes_size is not None:
                sets.append("bytes_size=?")
                params.append(int(bytes_size))
            if recipient_emails is not None:
                sets.append("recipient_emails_json=?")
                params.append(json.dumps(list(recipient_emails)))
            if not sets:
                return _row_to_run(current)
            params.append(run_id)
            conn.execute(
                f"UPDATE runs SET {', '.join(sets)} WHERE id=?",
                tuple(params),
            )
            row = conn.execute(
                "SELECT id, template_id, inputs_json, output_path, output_kind, "
                "status, recipient_emails_json, created_at, generated_at, error, "
                "bytes_size FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
            return _row_to_run(row) if row else None
        finally:
            conn.close()

    async def delete_run(self, run_id: str) -> bool:
        if not self._enabled or not run_id:
            return False
        return await asyncio.to_thread(self._delete_run_sync, run_id)

    def _delete_run_sync(self, run_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
            return cur.rowcount > 0
        finally:
            conn.close()

    async def count_by_status(self) -> dict[str, int]:
        if not self._enabled:
            return {}
        return await asyncio.to_thread(self._count_by_status_sync)

    def _count_by_status_sync(self) -> dict[str, int]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM runs GROUP BY status"
            ).fetchall()
            return {str(r[0]): int(r[1]) for r in rows}
        finally:
            conn.close()


# ---------- module-level singleton -----------------------------------------


_singleton: ReportStore | None = None


def get_store() -> ReportStore:
    global _singleton
    if _singleton is None:
        _singleton = ReportStore()
    return _singleton


def reset_store() -> None:
    """Clear cached singleton -- used by tests with isolated DBs."""

    global _singleton
    _singleton = None


__all__ = [
    "DEFAULT_DB_PATH",
    "ReportStore",
    "get_store",
    "reset_store",
]
