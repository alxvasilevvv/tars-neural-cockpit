"""SQLite-backed store for the outreach module (Wave 98).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.cohort.store`. The DB lives at
``~/.tars/outreach.sqlite`` by default; override with
``TARS_OUTREACH_DB_PATH``. Disable the whole module with
``TARS_OUTREACH_STORE=disabled`` (the package-level helpers will
short-circuit on a disabled store).

Tables:

- ``templates``   reusable email prompts + variable schema.
- ``drafts``      per-recipient drafts (lifecycle column + send result).
- ``campaigns``   batch send orchestration (counters + recipient list).

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
    OutreachCampaign,
    OutreachDraft,
    OutreachTemplate,
    new_campaign_id,
    new_draft_id,
    new_template_id,
)


DEFAULT_DB_PATH = "~/.tars/outreach.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    use_case TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    variables_json TEXT NOT NULL DEFAULT '[]',
    default_subject_template TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    recipient_json TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at REAL NOT NULL,
    sent_at REAL,
    gmail_message_id TEXT,
    error TEXT,
    campaign_id TEXT,
    FOREIGN KEY (template_id) REFERENCES templates (id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    template_id TEXT NOT NULL,
    recipients_json TEXT NOT NULL DEFAULT '[]',
    schedule_at REAL,
    status TEXT NOT NULL DEFAULT 'planning',
    drafts_generated INTEGER NOT NULL DEFAULT 0,
    drafts_approved INTEGER NOT NULL DEFAULT 0,
    drafts_sent INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (template_id) REFERENCES templates (id)
);

CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_drafts_campaign ON drafts (campaign_id);
CREATE INDEX IF NOT EXISTS idx_drafts_sent_at ON drafts (sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_templates_use_case ON templates (use_case);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_OUTREACH_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_OUTREACH_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


# ---------- row mappers -----------------------------------------------------


def _row_to_template(row: sqlite3.Row | tuple) -> OutreachTemplate:
    return OutreachTemplate(
        id=row[0],
        name=row[1],
        slug=row[2],
        use_case=row[3],
        system_prompt=row[4],
        variables=json.loads(row[5] or "[]"),
        default_subject_template=row[6] or "",
        created_at=float(row[7]),
    )


def _row_to_draft(row: sqlite3.Row | tuple) -> OutreachDraft:
    return OutreachDraft(
        id=row[0],
        template_id=row[1],
        recipient=json.loads(row[2] or "{}"),
        context=json.loads(row[3] or "{}"),
        subject=row[4] or "",
        body=row[5] or "",
        status=row[6] or "draft",
        created_at=float(row[7]),
        sent_at=float(row[8]) if row[8] is not None else None,
        gmail_message_id=row[9],
        error=row[10],
        campaign_id=row[11],
    )


def _row_to_campaign(row: sqlite3.Row | tuple) -> OutreachCampaign:
    return OutreachCampaign(
        id=row[0],
        name=row[1],
        template_id=row[2],
        recipients=json.loads(row[3] or "[]"),
        schedule_at=float(row[4]) if row[4] is not None else None,
        status=row[5] or "planning",
        drafts_generated=int(row[6] or 0),
        drafts_approved=int(row[7] or 0),
        drafts_sent=int(row[8] or 0),
        created_at=float(row[9]),
    )


# ---------- store -----------------------------------------------------------


class OutreachStore:
    """SQLite-backed CRUD + queries for the outreach module."""

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
        use_case: str,
        system_prompt: str,
        variables: list[str] | None = None,
        default_subject_template: str = "",
        template_id: str | None = None,
    ) -> OutreachTemplate:
        if not self._enabled:
            raise RuntimeError("outreach_store_disabled")
        return await asyncio.to_thread(
            self._upsert_template_sync,
            template_id,
            name,
            slug,
            use_case,
            system_prompt,
            list(variables or []),
            default_subject_template,
        )

    def _upsert_template_sync(
        self,
        template_id: str | None,
        name: str,
        slug: str,
        use_case: str,
        system_prompt: str,
        variables: list[str],
        default_subject_template: str,
    ) -> OutreachTemplate:
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT id, created_at FROM templates WHERE slug=?", (slug,)
            ).fetchone()
            if existing:
                tid = existing[0]
                created_at = float(existing[1])
                conn.execute(
                    "UPDATE templates SET name=?, use_case=?, system_prompt=?, "
                    "variables_json=?, default_subject_template=? WHERE id=?",
                    (
                        name,
                        use_case,
                        system_prompt,
                        json.dumps(variables),
                        default_subject_template,
                        tid,
                    ),
                )
            else:
                tid = template_id or new_template_id()
                created_at = time.time()
                conn.execute(
                    "INSERT INTO templates (id, name, slug, use_case, system_prompt, "
                    "variables_json, default_subject_template, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tid,
                        name,
                        slug,
                        use_case,
                        system_prompt,
                        json.dumps(variables),
                        default_subject_template,
                        created_at,
                    ),
                )
            return OutreachTemplate(
                id=tid,
                name=name,
                slug=slug,
                use_case=use_case,
                system_prompt=system_prompt,
                variables=list(variables),
                default_subject_template=default_subject_template,
                created_at=created_at,
            )
        finally:
            conn.close()

    async def list_templates(self) -> list[OutreachTemplate]:
        if not self._enabled:
            return []
        return await asyncio.to_thread(self._list_templates_sync)

    def _list_templates_sync(self) -> list[OutreachTemplate]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, slug, use_case, system_prompt, variables_json, "
                "default_subject_template, created_at FROM templates "
                "ORDER BY created_at ASC"
            ).fetchall()
            return [_row_to_template(r) for r in rows]
        finally:
            conn.close()

    async def get_template(self, template_id: str) -> OutreachTemplate | None:
        if not self._enabled or not template_id:
            return None
        return await asyncio.to_thread(self._get_template_sync, template_id)

    def _get_template_sync(self, template_id: str) -> OutreachTemplate | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, name, slug, use_case, system_prompt, variables_json, "
                "default_subject_template, created_at FROM templates WHERE id=?",
                (template_id,),
            ).fetchone()
            return _row_to_template(row) if row else None
        finally:
            conn.close()

    async def get_template_by_slug(self, slug: str) -> OutreachTemplate | None:
        if not self._enabled or not slug:
            return None
        return await asyncio.to_thread(self._get_template_by_slug_sync, slug)

    def _get_template_by_slug_sync(self, slug: str) -> OutreachTemplate | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, name, slug, use_case, system_prompt, variables_json, "
                "default_subject_template, created_at FROM templates WHERE slug=?",
                (slug,),
            ).fetchone()
            return _row_to_template(row) if row else None
        finally:
            conn.close()

    async def update_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        system_prompt: str | None = None,
        variables: list[str] | None = None,
        default_subject_template: str | None = None,
    ) -> OutreachTemplate | None:
        if not self._enabled:
            return None
        return await asyncio.to_thread(
            self._update_template_sync,
            template_id,
            name,
            system_prompt,
            variables,
            default_subject_template,
        )

    def _update_template_sync(
        self,
        template_id: str,
        name: str | None,
        system_prompt: str | None,
        variables: list[str] | None,
        default_subject_template: str | None,
    ) -> OutreachTemplate | None:
        conn = self._connect()
        try:
            current = conn.execute(
                "SELECT id, name, slug, use_case, system_prompt, variables_json, "
                "default_subject_template, created_at FROM templates WHERE id=?",
                (template_id,),
            ).fetchone()
            if not current:
                return None
            new_name = name if name is not None else current[1]
            new_prompt = system_prompt if system_prompt is not None else current[4]
            new_vars = json.dumps(variables) if variables is not None else current[5]
            new_subj = (
                default_subject_template
                if default_subject_template is not None
                else current[6]
            )
            conn.execute(
                "UPDATE templates SET name=?, system_prompt=?, variables_json=?, "
                "default_subject_template=? WHERE id=?",
                (new_name, new_prompt, new_vars, new_subj, template_id),
            )
            row = conn.execute(
                "SELECT id, name, slug, use_case, system_prompt, variables_json, "
                "default_subject_template, created_at FROM templates WHERE id=?",
                (template_id,),
            ).fetchone()
            return _row_to_template(row) if row else None
        finally:
            conn.close()

    # -- drafts --------------------------------------------------------

    async def insert_draft(self, draft: OutreachDraft) -> OutreachDraft:
        if not self._enabled:
            raise RuntimeError("outreach_store_disabled")
        return await asyncio.to_thread(self._insert_draft_sync, draft)

    def _insert_draft_sync(self, draft: OutreachDraft) -> OutreachDraft:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO drafts (id, template_id, recipient_json, context_json, "
                "subject, body, status, created_at, sent_at, gmail_message_id, "
                "error, campaign_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    draft.id,
                    draft.template_id,
                    json.dumps(draft.recipient),
                    json.dumps(draft.context),
                    draft.subject,
                    draft.body,
                    draft.status,
                    draft.created_at,
                    draft.sent_at,
                    draft.gmail_message_id,
                    draft.error,
                    draft.campaign_id,
                ),
            )
            return draft
        finally:
            conn.close()

    async def get_draft(self, draft_id: str) -> OutreachDraft | None:
        if not self._enabled or not draft_id:
            return None
        return await asyncio.to_thread(self._get_draft_sync, draft_id)

    def _get_draft_sync(self, draft_id: str) -> OutreachDraft | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, template_id, recipient_json, context_json, subject, body, "
                "status, created_at, sent_at, gmail_message_id, error, campaign_id "
                "FROM drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
            return _row_to_draft(row) if row else None
        finally:
            conn.close()

    async def list_drafts(
        self,
        *,
        status: str | None = None,
        since_ts: float | None = None,
        limit: int = 200,
        campaign_id: str | None = None,
    ) -> list[OutreachDraft]:
        if not self._enabled:
            return []
        return await asyncio.to_thread(
            self._list_drafts_sync, status, since_ts, limit, campaign_id
        )

    def _list_drafts_sync(
        self,
        status: str | None,
        since_ts: float | None,
        limit: int,
        campaign_id: str | None,
    ) -> list[OutreachDraft]:
        conn = self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if status:
                clauses.append("status=?")
                params.append(status)
            if since_ts is not None:
                clauses.append("created_at>=?")
                params.append(float(since_ts))
            if campaign_id:
                clauses.append("campaign_id=?")
                params.append(campaign_id)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(int(max(1, min(limit, 1000))))
            rows = conn.execute(
                "SELECT id, template_id, recipient_json, context_json, subject, body, "
                "status, created_at, sent_at, gmail_message_id, error, campaign_id "
                f"FROM drafts {where} ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [_row_to_draft(r) for r in rows]
        finally:
            conn.close()

    async def update_draft(
        self,
        draft_id: str,
        *,
        subject: str | None = None,
        body: str | None = None,
        status: str | None = None,
        sent_at: float | None = None,
        gmail_message_id: str | None = None,
        error: str | None = None,
    ) -> OutreachDraft | None:
        if not self._enabled:
            return None
        return await asyncio.to_thread(
            self._update_draft_sync,
            draft_id,
            subject,
            body,
            status,
            sent_at,
            gmail_message_id,
            error,
        )

    def _update_draft_sync(
        self,
        draft_id: str,
        subject: str | None,
        body: str | None,
        status: str | None,
        sent_at: float | None,
        gmail_message_id: str | None,
        error: str | None,
    ) -> OutreachDraft | None:
        conn = self._connect()
        try:
            current = conn.execute(
                "SELECT id, template_id, recipient_json, context_json, subject, body, "
                "status, created_at, sent_at, gmail_message_id, error, campaign_id "
                "FROM drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
            if not current:
                return None
            sets: list[str] = []
            params: list[Any] = []
            if subject is not None:
                sets.append("subject=?")
                params.append(subject)
            if body is not None:
                sets.append("body=?")
                params.append(body)
            if status is not None:
                sets.append("status=?")
                params.append(status)
            if sent_at is not None:
                sets.append("sent_at=?")
                params.append(float(sent_at))
            if gmail_message_id is not None:
                sets.append("gmail_message_id=?")
                params.append(gmail_message_id)
            if error is not None:
                sets.append("error=?")
                params.append(error)
            if not sets:
                return _row_to_draft(current)
            params.append(draft_id)
            conn.execute(
                f"UPDATE drafts SET {', '.join(sets)} WHERE id=?",
                tuple(params),
            )
            row = conn.execute(
                "SELECT id, template_id, recipient_json, context_json, subject, body, "
                "status, created_at, sent_at, gmail_message_id, error, campaign_id "
                "FROM drafts WHERE id=?",
                (draft_id,),
            ).fetchone()
            return _row_to_draft(row) if row else None
        finally:
            conn.close()

    async def delete_draft(self, draft_id: str) -> bool:
        if not self._enabled or not draft_id:
            return False
        return await asyncio.to_thread(self._delete_draft_sync, draft_id)

    def _delete_draft_sync(self, draft_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
            return cur.rowcount > 0
        finally:
            conn.close()

    async def count_sent_since(self, since_ts: float) -> int:
        """Count drafts moved to ``sent`` since a unix-ts threshold.

        Used by the safety layer's daily-cap check.
        """

        if not self._enabled:
            return 0
        return await asyncio.to_thread(self._count_sent_since_sync, since_ts)

    def _count_sent_since_sync(self, since_ts: float) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM drafts WHERE status='sent' AND sent_at>=?",
                (float(since_ts),),
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    # -- campaigns -----------------------------------------------------

    async def insert_campaign(self, campaign: OutreachCampaign) -> OutreachCampaign:
        if not self._enabled:
            raise RuntimeError("outreach_store_disabled")
        return await asyncio.to_thread(self._insert_campaign_sync, campaign)

    def _insert_campaign_sync(self, campaign: OutreachCampaign) -> OutreachCampaign:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO campaigns (id, name, template_id, recipients_json, "
                "schedule_at, status, drafts_generated, drafts_approved, "
                "drafts_sent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    campaign.id,
                    campaign.name,
                    campaign.template_id,
                    json.dumps(campaign.recipients),
                    campaign.schedule_at,
                    campaign.status,
                    int(campaign.drafts_generated),
                    int(campaign.drafts_approved),
                    int(campaign.drafts_sent),
                    campaign.created_at,
                ),
            )
            return campaign
        finally:
            conn.close()

    async def get_campaign(self, campaign_id: str) -> OutreachCampaign | None:
        if not self._enabled or not campaign_id:
            return None
        return await asyncio.to_thread(self._get_campaign_sync, campaign_id)

    def _get_campaign_sync(self, campaign_id: str) -> OutreachCampaign | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, name, template_id, recipients_json, schedule_at, status, "
                "drafts_generated, drafts_approved, drafts_sent, created_at "
                "FROM campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone()
            return _row_to_campaign(row) if row else None
        finally:
            conn.close()

    async def list_campaigns(self) -> list[OutreachCampaign]:
        if not self._enabled:
            return []
        return await asyncio.to_thread(self._list_campaigns_sync)

    def _list_campaigns_sync(self) -> list[OutreachCampaign]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, template_id, recipients_json, schedule_at, status, "
                "drafts_generated, drafts_approved, drafts_sent, created_at "
                "FROM campaigns ORDER BY created_at DESC"
            ).fetchall()
            return [_row_to_campaign(r) for r in rows]
        finally:
            conn.close()

    async def update_campaign_counters(
        self,
        campaign_id: str,
        *,
        generated_delta: int = 0,
        approved_delta: int = 0,
        sent_delta: int = 0,
        status: str | None = None,
    ) -> OutreachCampaign | None:
        if not self._enabled:
            return None
        return await asyncio.to_thread(
            self._update_campaign_counters_sync,
            campaign_id,
            generated_delta,
            approved_delta,
            sent_delta,
            status,
        )

    def _update_campaign_counters_sync(
        self,
        campaign_id: str,
        generated_delta: int,
        approved_delta: int,
        sent_delta: int,
        status: str | None,
    ) -> OutreachCampaign | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT drafts_generated, drafts_approved, drafts_sent "
                "FROM campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            new_gen = max(0, int(row[0]) + int(generated_delta))
            new_app = max(0, int(row[1]) + int(approved_delta))
            new_sent = max(0, int(row[2]) + int(sent_delta))
            if status is not None:
                conn.execute(
                    "UPDATE campaigns SET drafts_generated=?, drafts_approved=?, "
                    "drafts_sent=?, status=? WHERE id=?",
                    (new_gen, new_app, new_sent, status, campaign_id),
                )
            else:
                conn.execute(
                    "UPDATE campaigns SET drafts_generated=?, drafts_approved=?, "
                    "drafts_sent=? WHERE id=?",
                    (new_gen, new_app, new_sent, campaign_id),
                )
            row2 = conn.execute(
                "SELECT id, name, template_id, recipients_json, schedule_at, status, "
                "drafts_generated, drafts_approved, drafts_sent, created_at "
                "FROM campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone()
            return _row_to_campaign(row2) if row2 else None
        finally:
            conn.close()


# ---------- module-level singleton -----------------------------------------


_singleton: OutreachStore | None = None


def get_store() -> OutreachStore:
    global _singleton
    if _singleton is None:
        _singleton = OutreachStore()
    return _singleton


def reset_store() -> None:
    """Clear cached singleton -- used by tests with isolated DBs."""

    global _singleton
    _singleton = None


__all__ = [
    "DEFAULT_DB_PATH",
    "OutreachStore",
    "get_store",
    "reset_store",
]
