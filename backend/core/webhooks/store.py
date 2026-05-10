"""SQLite-backed store for webhooks (outgoing + incoming + deliveries).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.agents.store`. The DB lives at
``~/.tars/webhooks.sqlite`` by default; override with
``TARS_WEBHOOKS_DB_PATH``. Disable the whole module with
``TARS_WEBHOOKS_STORE=disabled`` (the public ``emit()`` helper
short-circuits in that case).
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from typing import Any, Iterable

from .models import (
    CONTRACT_VERSION,
    Delivery,
    DeliveryStatus,
    IncomingWebhook,
    OutgoingWebhook,
    new_delivery_id,
    new_incoming_id,
    new_outgoing_id,
    new_token,
)

DEFAULT_DB_PATH = "~/.tars/webhooks.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS outgoing_webhooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret BLOB NOT NULL,
    event_filter_json TEXT NOT NULL DEFAULT '[]',
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS incoming_webhooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    trigger_playbook_id TEXT,
    allowed_event_schemas_json TEXT NOT NULL DEFAULT '[]',
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY,
    webhook_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at REAL,
    next_attempt_at REAL,
    last_error TEXT,
    last_status_code INTEGER,
    signature_used TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (webhook_id) REFERENCES outgoing_webhooks (id)
);

CREATE INDEX IF NOT EXISTS idx_outgoing_active ON outgoing_webhooks (active);
CREATE INDEX IF NOT EXISTS idx_incoming_token ON incoming_webhooks (token);
CREATE INDEX IF NOT EXISTS idx_deliveries_webhook ON deliveries (webhook_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries (status, next_attempt_at);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_WEBHOOKS_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_WEBHOOKS_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class WebhookStore:
    """Durable webhook store. Auto-initialised on first call."""

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

    # ---------- row mapping ---------------------------------------------

    @staticmethod
    def _row_to_outgoing(row: sqlite3.Row) -> OutgoingWebhook:
        try:
            event_filter = json.loads(row["event_filter_json"] or "[]")
        except json.JSONDecodeError:
            event_filter = []
        if not isinstance(event_filter, list):
            event_filter = []
        return OutgoingWebhook(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            secret=bytes(row["secret"]),
            event_filter=[str(p) for p in event_filter],
            active=bool(row["active"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _row_to_incoming(row: sqlite3.Row) -> IncomingWebhook:
        try:
            schemas = json.loads(row["allowed_event_schemas_json"] or "[]")
        except json.JSONDecodeError:
            schemas = []
        if not isinstance(schemas, list):
            schemas = []
        return IncomingWebhook(
            id=row["id"],
            name=row["name"],
            token=row["token"],
            trigger_playbook_id=row["trigger_playbook_id"],
            allowed_event_schemas=[s for s in schemas if isinstance(s, dict)],
            active=bool(row["active"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _row_to_delivery(row: sqlite3.Row) -> Delivery:
        try:
            status = DeliveryStatus(row["status"])
        except ValueError:
            status = DeliveryStatus.PENDING
        return Delivery(
            id=row["id"],
            webhook_id=row["webhook_id"],
            event_id=row["event_id"],
            event_type=row["event_type"],
            payload_json=row["payload_json"],
            status=status,
            attempts=int(row["attempts"] or 0),
            last_attempt_at=row["last_attempt_at"],
            next_attempt_at=row["next_attempt_at"],
            last_error=row["last_error"],
            last_status_code=row["last_status_code"],
            signature_used=row["signature_used"],
            created_at=float(row["created_at"]),
        )

    # ---------- outgoing CRUD ------------------------------------------

    def _create_outgoing_sync(
        self,
        *,
        name: str,
        url: str,
        secret: bytes,
        event_filter: Iterable[str],
        active: bool,
    ) -> OutgoingWebhook:
        rec = OutgoingWebhook(
            id=new_outgoing_id(),
            name=name.strip(),
            url=url.strip(),
            secret=bytes(secret),
            event_filter=[str(p).strip() for p in event_filter if str(p).strip()],
            active=bool(active),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO outgoing_webhooks (id, name, url, secret, event_filter_json, active, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.name,
                    rec.url,
                    rec.secret,
                    json.dumps(rec.event_filter),
                    1 if rec.active else 0,
                    rec.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def create_outgoing(
        self,
        *,
        name: str,
        url: str,
        secret: bytes,
        event_filter: Iterable[str] = (),
        active: bool = True,
    ) -> OutgoingWebhook:
        if not name.strip():
            raise ValueError("webhook name must be non-empty")
        if not url.strip():
            raise ValueError("webhook url must be non-empty")
        if not secret:
            raise ValueError("webhook secret must be non-empty")
        return await asyncio.to_thread(
            self._create_outgoing_sync,
            name=name,
            url=url,
            secret=secret,
            event_filter=list(event_filter),
            active=active,
        )

    def _list_outgoing_sync(self, *, include_inactive: bool) -> list[OutgoingWebhook]:
        conn = self._connect()
        try:
            if include_inactive:
                rows = conn.execute(
                    "SELECT * FROM outgoing_webhooks ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM outgoing_webhooks WHERE active=1 ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_outgoing(r) for r in rows]
        finally:
            conn.close()

    async def list_outgoing(
        self, *, include_inactive: bool = True
    ) -> list[OutgoingWebhook]:
        return await asyncio.to_thread(
            self._list_outgoing_sync, include_inactive=include_inactive
        )

    def _get_outgoing_sync(self, webhook_id: str) -> OutgoingWebhook | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM outgoing_webhooks WHERE id=?", (webhook_id,)
            ).fetchone()
            return self._row_to_outgoing(row) if row else None
        finally:
            conn.close()

    async def get_outgoing(self, webhook_id: str) -> OutgoingWebhook | None:
        return await asyncio.to_thread(self._get_outgoing_sync, webhook_id)

    def _patch_outgoing_sync(
        self, webhook_id: str, updates: dict[str, Any]
    ) -> OutgoingWebhook | None:
        existing = self._get_outgoing_sync(webhook_id)
        if existing is None:
            return None
        cols: list[str] = []
        params: list[Any] = []
        if "url" in updates and updates["url"] is not None:
            cols.append("url=?")
            params.append(str(updates["url"]).strip())
        if "name" in updates and updates["name"] is not None:
            cols.append("name=?")
            params.append(str(updates["name"]).strip())
        if "active" in updates and updates["active"] is not None:
            cols.append("active=?")
            params.append(1 if bool(updates["active"]) else 0)
        if "event_filter" in updates and updates["event_filter"] is not None:
            ef = updates["event_filter"]
            if not isinstance(ef, (list, tuple)):
                raise ValueError("event_filter must be a list of strings")
            cleaned = [str(p).strip() for p in ef if str(p).strip()]
            cols.append("event_filter_json=?")
            params.append(json.dumps(cleaned))
        if not cols:
            return existing
        params.append(webhook_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE outgoing_webhooks SET {', '.join(cols)} WHERE id=?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_outgoing_sync(webhook_id)

    async def patch_outgoing(
        self, webhook_id: str, updates: dict[str, Any]
    ) -> OutgoingWebhook | None:
        return await asyncio.to_thread(self._patch_outgoing_sync, webhook_id, updates)

    async def deactivate_outgoing(self, webhook_id: str) -> OutgoingWebhook | None:
        return await self.patch_outgoing(webhook_id, {"active": False})

    async def list_active_outgoing_for(
        self, event_type: str
    ) -> list[OutgoingWebhook]:
        all_active = await asyncio.to_thread(
            self._list_outgoing_sync, include_inactive=False
        )
        return [w for w in all_active if w.matches(event_type)]

    # ---------- incoming CRUD ------------------------------------------

    def _create_incoming_sync(
        self,
        *,
        name: str,
        token: str,
        trigger_playbook_id: str | None,
        allowed_event_schemas: list[dict[str, Any]],
        active: bool,
    ) -> IncomingWebhook:
        rec = IncomingWebhook(
            id=new_incoming_id(),
            name=name.strip(),
            token=token,
            trigger_playbook_id=trigger_playbook_id,
            allowed_event_schemas=allowed_event_schemas,
            active=bool(active),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO incoming_webhooks (id, name, token, trigger_playbook_id,"
                " allowed_event_schemas_json, active, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.name,
                    rec.token,
                    rec.trigger_playbook_id,
                    json.dumps(rec.allowed_event_schemas),
                    1 if rec.active else 0,
                    rec.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def create_incoming(
        self,
        *,
        name: str,
        trigger_playbook_id: str | None = None,
        allowed_event_schemas: list[dict[str, Any]] | None = None,
        token: str | None = None,
        active: bool = True,
    ) -> IncomingWebhook:
        if not name.strip():
            raise ValueError("incoming webhook name must be non-empty")
        return await asyncio.to_thread(
            self._create_incoming_sync,
            name=name,
            token=token or new_token(),
            trigger_playbook_id=trigger_playbook_id,
            allowed_event_schemas=list(allowed_event_schemas or []),
            active=active,
        )

    def _list_incoming_sync(self, *, include_inactive: bool) -> list[IncomingWebhook]:
        conn = self._connect()
        try:
            if include_inactive:
                rows = conn.execute(
                    "SELECT * FROM incoming_webhooks ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM incoming_webhooks WHERE active=1 ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_incoming(r) for r in rows]
        finally:
            conn.close()

    async def list_incoming(
        self, *, include_inactive: bool = True
    ) -> list[IncomingWebhook]:
        return await asyncio.to_thread(
            self._list_incoming_sync, include_inactive=include_inactive
        )

    def _get_incoming_sync(self, webhook_id: str) -> IncomingWebhook | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM incoming_webhooks WHERE id=?", (webhook_id,)
            ).fetchone()
            return self._row_to_incoming(row) if row else None
        finally:
            conn.close()

    async def get_incoming(self, webhook_id: str) -> IncomingWebhook | None:
        return await asyncio.to_thread(self._get_incoming_sync, webhook_id)

    def _get_incoming_by_token_sync(self, token: str) -> IncomingWebhook | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM incoming_webhooks WHERE token=?", (token,)
            ).fetchone()
            return self._row_to_incoming(row) if row else None
        finally:
            conn.close()

    async def get_incoming_by_token(self, token: str) -> IncomingWebhook | None:
        return await asyncio.to_thread(self._get_incoming_by_token_sync, token)

    def _deactivate_incoming_sync(self, webhook_id: str) -> IncomingWebhook | None:
        existing = self._get_incoming_sync(webhook_id)
        if existing is None:
            return None
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE incoming_webhooks SET active=0 WHERE id=?", (webhook_id,)
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_incoming_sync(webhook_id)

    async def deactivate_incoming(self, webhook_id: str) -> IncomingWebhook | None:
        return await asyncio.to_thread(self._deactivate_incoming_sync, webhook_id)

    # ---------- deliveries ---------------------------------------------

    def _create_delivery_sync(
        self,
        *,
        webhook_id: str,
        event_id: str,
        event_type: str,
        payload_json: str,
    ) -> Delivery:
        rec = Delivery(
            id=new_delivery_id(),
            webhook_id=webhook_id,
            event_id=event_id,
            event_type=event_type,
            payload_json=payload_json,
            status=DeliveryStatus.PENDING,
            next_attempt_at=time.time(),  # eligible for immediate dispatch
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO deliveries (id, webhook_id, event_id, event_type,"
                " payload_json, status, attempts, last_attempt_at, next_attempt_at,"
                " last_error, last_status_code, signature_used, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.webhook_id,
                    rec.event_id,
                    rec.event_type,
                    rec.payload_json,
                    rec.status.value,
                    rec.attempts,
                    rec.last_attempt_at,
                    rec.next_attempt_at,
                    rec.last_error,
                    rec.last_status_code,
                    rec.signature_used,
                    rec.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def create_delivery(
        self,
        *,
        webhook_id: str,
        event_id: str,
        event_type: str,
        payload_json: str,
    ) -> Delivery:
        return await asyncio.to_thread(
            self._create_delivery_sync,
            webhook_id=webhook_id,
            event_id=event_id,
            event_type=event_type,
            payload_json=payload_json,
        )

    def _patch_delivery_sync(
        self, delivery_id: str, updates: dict[str, Any]
    ) -> Delivery | None:
        cols: list[str] = []
        params: list[Any] = []
        for key in (
            "status",
            "attempts",
            "last_attempt_at",
            "next_attempt_at",
            "last_error",
            "last_status_code",
            "signature_used",
        ):
            if key in updates:
                value = updates[key]
                if key == "status" and isinstance(value, DeliveryStatus):
                    value = value.value
                cols.append(f"{key}=?")
                params.append(value)
        if not cols:
            return self._get_delivery_sync(delivery_id)
        params.append(delivery_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE deliveries SET {', '.join(cols)} WHERE id=?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_delivery_sync(delivery_id)

    async def patch_delivery(
        self, delivery_id: str, updates: dict[str, Any]
    ) -> Delivery | None:
        return await asyncio.to_thread(self._patch_delivery_sync, delivery_id, updates)

    def _get_delivery_sync(self, delivery_id: str) -> Delivery | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM deliveries WHERE id=?", (delivery_id,)
            ).fetchone()
            return self._row_to_delivery(row) if row else None
        finally:
            conn.close()

    async def get_delivery(self, delivery_id: str) -> Delivery | None:
        return await asyncio.to_thread(self._get_delivery_sync, delivery_id)

    def _list_deliveries_for_webhook_sync(
        self, webhook_id: str, *, limit: int
    ) -> list[Delivery]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM deliveries WHERE webhook_id=? ORDER BY created_at DESC LIMIT ?",
                (webhook_id, max(1, min(int(limit), 1000))),
            ).fetchall()
            return [self._row_to_delivery(r) for r in rows]
        finally:
            conn.close()

    async def list_deliveries_for_webhook(
        self, webhook_id: str, *, limit: int = 50
    ) -> list[Delivery]:
        return await asyncio.to_thread(
            self._list_deliveries_for_webhook_sync, webhook_id, limit=limit
        )

    def _list_due_sync(self, *, now_seconds: float, limit: int) -> list[Delivery]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM deliveries WHERE status IN (?, ?)"
                " AND (next_attempt_at IS NULL OR next_attempt_at <= ?)"
                " ORDER BY created_at ASC LIMIT ?",
                (
                    DeliveryStatus.PENDING.value,
                    DeliveryStatus.RETRY.value,
                    now_seconds,
                    max(1, min(int(limit), 500)),
                ),
            ).fetchall()
            return [self._row_to_delivery(r) for r in rows]
        finally:
            conn.close()

    async def list_due_deliveries(
        self, *, now_seconds: float | None = None, limit: int = 100
    ) -> list[Delivery]:
        return await asyncio.to_thread(
            self._list_due_sync,
            now_seconds=time.time() if now_seconds is None else now_seconds,
            limit=limit,
        )


# ---------- module-level singleton helpers ----------------------------------


_singleton: WebhookStore | None = None


def get_store() -> WebhookStore:
    global _singleton
    if _singleton is None:
        _singleton = WebhookStore()
    return _singleton


def reset_store() -> None:
    """Drop the cached singleton — used by tests + the
    ``TARS_WEBHOOKS_DB_PATH`` env override."""

    global _singleton
    _singleton = None
