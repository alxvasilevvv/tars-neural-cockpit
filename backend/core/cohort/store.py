"""SQLite-backed store for cohort tracking (Wave 94).

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.webhooks.store`. The DB lives at
``~/.tars/cohort.sqlite`` by default; override with
``TARS_COHORT_DB_PATH``. Disable the whole module with
``TARS_COHORT_STORE=disabled`` (the module-level helpers in
``__init__`` will short-circuit in that case).

Tables:

- ``cohorts``           — workshop sessions.
- ``attendees``         — participants per cohort, with join token.
- ``attendee_actions``  — append-only event log per attendee.

Auto-creates schema on first connect.
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
    Attendee,
    AttendeeAction,
    Cohort,
    PHASES,
    new_action_id,
    new_attendee_id,
    new_cohort_id,
    new_token,
    normalize_phase,
)

DEFAULT_DB_PATH = "~/.tars/cohort.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cohorts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    started_at REAL NOT NULL,
    ended_at REAL,
    facilitator_user_id TEXT,
    max_attendees INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS attendees (
    id TEXT PRIMARY KEY,
    cohort_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    token TEXT NOT NULL UNIQUE,
    joined_at REAL NOT NULL,
    current_phase TEXT NOT NULL DEFAULT 'intake',
    last_activity_at REAL NOT NULL,
    playbook_runs INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0,
    flag_reason TEXT,
    FOREIGN KEY (cohort_id) REFERENCES cohorts (id)
);

CREATE TABLE IF NOT EXISTS attendee_actions (
    id TEXT PRIMARY KEY,
    attendee_id TEXT NOT NULL,
    type TEXT NOT NULL,
    occurred_at REAL NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (attendee_id) REFERENCES attendees (id)
);

CREATE INDEX IF NOT EXISTS idx_attendees_cohort ON attendees (cohort_id, joined_at);
CREATE INDEX IF NOT EXISTS idx_attendees_email ON attendees (email);
CREATE INDEX IF NOT EXISTS idx_attendees_token ON attendees (token);
CREATE INDEX IF NOT EXISTS idx_actions_attendee ON attendee_actions (attendee_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_type ON attendee_actions (type);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_COHORT_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_COHORT_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


# Active-now window: an attendee with an action in the last N seconds is
# considered active. 5 minutes matches the FE Wave 89 ACTIVE_THRESHOLD_MIN.
ACTIVE_NOW_WINDOW_S = 300


class CohortStore:
    """Durable cohort store. Auto-initialised on first call."""

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
    def _row_to_cohort(row: sqlite3.Row) -> Cohort:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return Cohort(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            started_at=float(row["started_at"]),
            ended_at=row["ended_at"],
            facilitator_user_id=row["facilitator_user_id"],
            max_attendees=row["max_attendees"],
            metadata=metadata,
        )

    @staticmethod
    def _row_to_attendee(row: sqlite3.Row) -> Attendee:
        return Attendee(
            id=row["id"],
            cohort_id=row["cohort_id"],
            display_name=row["display_name"],
            email=row["email"],
            token=row["token"],
            joined_at=float(row["joined_at"]),
            current_phase=normalize_phase(row["current_phase"]),
            last_activity_at=float(row["last_activity_at"]),
            playbook_runs=int(row["playbook_runs"] or 0),
            errors=int(row["errors"] or 0),
            flagged=bool(row["flagged"]),
            flag_reason=row["flag_reason"],
        )

    @staticmethod
    def _row_to_action(row: sqlite3.Row) -> AttendeeAction:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return AttendeeAction(
            id=row["id"],
            attendee_id=row["attendee_id"],
            type=row["type"],
            occurred_at=float(row["occurred_at"]),
            payload=payload,
        )

    # ---------- cohort CRUD --------------------------------------------

    def _create_cohort_sync(
        self,
        *,
        name: str,
        slug: str,
        facilitator_user_id: str | None,
        max_attendees: int | None,
        metadata: dict[str, Any],
    ) -> Cohort:
        rec = Cohort(
            id=new_cohort_id(),
            name=name.strip(),
            slug=slug.strip().lower(),
            facilitator_user_id=facilitator_user_id,
            max_attendees=max_attendees,
            metadata=dict(metadata or {}),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO cohorts (id, name, slug, started_at, ended_at,"
                " facilitator_user_id, max_attendees, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.name,
                    rec.slug,
                    rec.started_at,
                    rec.ended_at,
                    rec.facilitator_user_id,
                    rec.max_attendees,
                    json.dumps(rec.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def create_cohort(
        self,
        *,
        name: str,
        slug: str,
        facilitator_user_id: str | None = None,
        max_attendees: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Cohort:
        if not name.strip():
            raise ValueError("cohort name must be non-empty")
        if not slug.strip():
            raise ValueError("cohort slug must be non-empty")
        return await asyncio.to_thread(
            self._create_cohort_sync,
            name=name,
            slug=slug,
            facilitator_user_id=facilitator_user_id,
            max_attendees=max_attendees,
            metadata=dict(metadata or {}),
        )

    def _get_cohort_sync(self, cohort_id: str) -> Cohort | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM cohorts WHERE id=?", (cohort_id,)
            ).fetchone()
            return self._row_to_cohort(row) if row else None
        finally:
            conn.close()

    async def get_cohort(self, cohort_id: str) -> Cohort | None:
        return await asyncio.to_thread(self._get_cohort_sync, cohort_id)

    def _get_cohort_by_slug_sync(self, slug: str) -> Cohort | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM cohorts WHERE slug=?", (slug.strip().lower(),)
            ).fetchone()
            return self._row_to_cohort(row) if row else None
        finally:
            conn.close()

    async def get_cohort_by_slug(self, slug: str) -> Cohort | None:
        return await asyncio.to_thread(self._get_cohort_by_slug_sync, slug)

    def _list_cohorts_sync(
        self, *, facilitator_user_id: str | None, include_ended: bool
    ) -> list[Cohort]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM cohorts WHERE 1=1"
            params: list[Any] = []
            if facilitator_user_id is not None:
                sql += " AND facilitator_user_id=?"
                params.append(facilitator_user_id)
            if not include_ended:
                sql += " AND ended_at IS NULL"
            sql += " ORDER BY started_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_cohort(r) for r in rows]
        finally:
            conn.close()

    async def list_cohorts(
        self,
        *,
        facilitator_user_id: str | None = None,
        include_ended: bool = True,
    ) -> list[Cohort]:
        return await asyncio.to_thread(
            self._list_cohorts_sync,
            facilitator_user_id=facilitator_user_id,
            include_ended=include_ended,
        )

    def _end_cohort_sync(self, cohort_id: str) -> Cohort | None:
        existing = self._get_cohort_sync(cohort_id)
        if existing is None:
            return None
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE cohorts SET ended_at=? WHERE id=?",
                (time.time(), cohort_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_cohort_sync(cohort_id)

    async def end_cohort(self, cohort_id: str) -> Cohort | None:
        return await asyncio.to_thread(self._end_cohort_sync, cohort_id)

    def _delete_cohort_sync(self, cohort_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT id FROM cohorts WHERE id=?", (cohort_id,))
            if cur.fetchone() is None:
                return False
            # Cascade: kill actions → attendees → cohort.
            conn.execute(
                "DELETE FROM attendee_actions WHERE attendee_id IN"
                " (SELECT id FROM attendees WHERE cohort_id=?)",
                (cohort_id,),
            )
            conn.execute("DELETE FROM attendees WHERE cohort_id=?", (cohort_id,))
            conn.execute("DELETE FROM cohorts WHERE id=?", (cohort_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    async def delete_cohort(self, cohort_id: str) -> bool:
        return await asyncio.to_thread(self._delete_cohort_sync, cohort_id)

    # ---------- attendee CRUD ------------------------------------------

    def _add_attendee_sync(
        self,
        *,
        cohort_id: str,
        display_name: str,
        email: str | None,
        token: str | None,
    ) -> Attendee:
        rec = Attendee(
            id=new_attendee_id(),
            cohort_id=cohort_id,
            display_name=display_name.strip(),
            email=(email or "").strip().lower() or None,
            token=token or new_token(),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO attendees (id, cohort_id, display_name, email, token,"
                " joined_at, current_phase, last_activity_at, playbook_runs, errors,"
                " flagged, flag_reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.cohort_id,
                    rec.display_name,
                    rec.email,
                    rec.token,
                    rec.joined_at,
                    rec.current_phase,
                    rec.last_activity_at,
                    rec.playbook_runs,
                    rec.errors,
                    1 if rec.flagged else 0,
                    rec.flag_reason,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def add_attendee(
        self,
        *,
        cohort_id: str,
        display_name: str,
        email: str | None = None,
        token: str | None = None,
    ) -> Attendee:
        if not display_name.strip():
            raise ValueError("attendee display_name must be non-empty")
        cohort = await self.get_cohort(cohort_id)
        if cohort is None:
            raise ValueError(f"unknown cohort: {cohort_id}")
        return await asyncio.to_thread(
            self._add_attendee_sync,
            cohort_id=cohort_id,
            display_name=display_name,
            email=email,
            token=token,
        )

    def _get_attendee_sync(self, attendee_id: str) -> Attendee | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM attendees WHERE id=?", (attendee_id,)
            ).fetchone()
            return self._row_to_attendee(row) if row else None
        finally:
            conn.close()

    async def get_attendee(self, attendee_id: str) -> Attendee | None:
        return await asyncio.to_thread(self._get_attendee_sync, attendee_id)

    def _get_attendee_by_token_sync(self, token: str) -> Attendee | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM attendees WHERE token=?", (token,)
            ).fetchone()
            return self._row_to_attendee(row) if row else None
        finally:
            conn.close()

    async def get_attendee_by_token(self, token: str) -> Attendee | None:
        return await asyncio.to_thread(self._get_attendee_by_token_sync, token)

    def _find_attendee_by_email_sync(self, email: str) -> Attendee | None:
        if not email:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM attendees WHERE email=? ORDER BY joined_at DESC LIMIT 1",
                (email.strip().lower(),),
            ).fetchone()
            return self._row_to_attendee(row) if row else None
        finally:
            conn.close()

    async def find_attendee_by_email(self, email: str) -> Attendee | None:
        return await asyncio.to_thread(self._find_attendee_by_email_sync, email)

    def _list_attendees_sync(
        self,
        cohort_id: str,
        *,
        filter_kind: str | None,
        active_window_s: int,
    ) -> list[Attendee]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM attendees WHERE cohort_id=? ORDER BY joined_at ASC",
                (cohort_id,),
            ).fetchall()
            attendees = [self._row_to_attendee(r) for r in rows]
        finally:
            conn.close()
        if not filter_kind or filter_kind == "all":
            return attendees
        now = time.time()
        kind = filter_kind.strip().lower()
        if kind == "active":
            return [a for a in attendees if (now - a.last_activity_at) <= active_window_s]
        if kind == "idle":
            return [a for a in attendees if (now - a.last_activity_at) > active_window_s]
        if kind == "error":
            return [a for a in attendees if a.errors > 0]
        if kind == "flagged":
            return [a for a in attendees if a.flagged]
        if kind in PHASES:
            return [a for a in attendees if a.current_phase == kind]
        return attendees

    async def list_attendees(
        self,
        cohort_id: str,
        *,
        filter: str | None = None,
        active_window_s: int = ACTIVE_NOW_WINDOW_S,
    ) -> list[Attendee]:
        return await asyncio.to_thread(
            self._list_attendees_sync,
            cohort_id,
            filter_kind=filter,
            active_window_s=active_window_s,
        )

    def _patch_attendee_sync(
        self, attendee_id: str, updates: dict[str, Any]
    ) -> Attendee | None:
        existing = self._get_attendee_sync(attendee_id)
        if existing is None:
            return None
        cols: list[str] = []
        params: list[Any] = []
        if "display_name" in updates and updates["display_name"] is not None:
            cols.append("display_name=?")
            params.append(str(updates["display_name"]).strip())
        if "current_phase" in updates and updates["current_phase"] is not None:
            cols.append("current_phase=?")
            params.append(normalize_phase(updates["current_phase"]))
        if "last_activity_at" in updates and updates["last_activity_at"] is not None:
            cols.append("last_activity_at=?")
            params.append(float(updates["last_activity_at"]))
        if "playbook_runs" in updates and updates["playbook_runs"] is not None:
            cols.append("playbook_runs=?")
            params.append(int(updates["playbook_runs"]))
        if "errors" in updates and updates["errors"] is not None:
            cols.append("errors=?")
            params.append(int(updates["errors"]))
        if "flagged" in updates and updates["flagged"] is not None:
            cols.append("flagged=?")
            params.append(1 if bool(updates["flagged"]) else 0)
        if "flag_reason" in updates:
            cols.append("flag_reason=?")
            params.append(updates["flag_reason"])
        if not cols:
            return existing
        params.append(attendee_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE attendees SET {', '.join(cols)} WHERE id=?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return self._get_attendee_sync(attendee_id)

    async def patch_attendee(
        self, attendee_id: str, updates: dict[str, Any]
    ) -> Attendee | None:
        return await asyncio.to_thread(self._patch_attendee_sync, attendee_id, updates)

    async def flag_attendee(
        self, attendee_id: str, reason: str | None = None
    ) -> Attendee | None:
        return await self.patch_attendee(
            attendee_id,
            {"flagged": True, "flag_reason": (reason or "").strip() or None},
        )

    async def unflag_attendee(self, attendee_id: str) -> Attendee | None:
        return await self.patch_attendee(
            attendee_id, {"flagged": False, "flag_reason": None}
        )

    # ---------- actions -------------------------------------------------

    def _record_action_sync(
        self,
        *,
        attendee_id: str,
        action_type: str,
        payload: dict[str, Any],
        occurred_at: float | None,
    ) -> AttendeeAction:
        rec = AttendeeAction(
            id=new_action_id(),
            attendee_id=attendee_id,
            type=action_type.strip(),
            occurred_at=occurred_at if occurred_at is not None else time.time(),
            payload=dict(payload or {}),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO attendee_actions (id, attendee_id, type, occurred_at,"
                " payload_json) VALUES (?, ?, ?, ?, ?)",
                (
                    rec.id,
                    rec.attendee_id,
                    rec.type,
                    rec.occurred_at,
                    json.dumps(rec.payload),
                ),
            )
            # Roll counters into the attendee row so the dashboard can
            # render at-a-glance stats without having to re-aggregate
            # the actions table on every render.
            updates: list[str] = ["last_activity_at=?"]
            params: list[Any] = [rec.occurred_at]
            if rec.type == "playbook_finish":
                updates.append("playbook_runs=playbook_runs+1")
            if rec.type == "error":
                updates.append("errors=errors+1")
            if rec.type == "phase_advance":
                new_phase = normalize_phase(rec.payload.get("to") or rec.payload.get("phase"))
                updates.append("current_phase=?")
                params.append(new_phase)
            params.append(attendee_id)
            conn.execute(
                f"UPDATE attendees SET {', '.join(updates)} WHERE id=?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    async def record_action(
        self,
        *,
        attendee_id: str,
        action_type: str,
        payload: dict[str, Any] | None = None,
        occurred_at: float | None = None,
    ) -> AttendeeAction:
        if not action_type.strip():
            raise ValueError("action_type must be non-empty")
        # Verify the attendee exists so we don't dangle FK rows.
        att = await self.get_attendee(attendee_id)
        if att is None:
            raise ValueError(f"unknown attendee: {attendee_id}")
        return await asyncio.to_thread(
            self._record_action_sync,
            attendee_id=attendee_id,
            action_type=action_type,
            payload=dict(payload or {}),
            occurred_at=occurred_at,
        )

    def _attendee_timeline_sync(
        self, attendee_id: str, *, limit: int
    ) -> list[AttendeeAction]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM attendee_actions WHERE attendee_id=?"
                " ORDER BY occurred_at DESC LIMIT ?",
                (attendee_id, max(1, min(int(limit), 1000))),
            ).fetchall()
            return [self._row_to_action(r) for r in rows]
        finally:
            conn.close()

    async def attendee_timeline(
        self, attendee_id: str, *, limit: int = 50
    ) -> list[AttendeeAction]:
        return await asyncio.to_thread(
            self._attendee_timeline_sync, attendee_id, limit=limit
        )

    def _recent_actions_for_cohort_sync(
        self, cohort_id: str, *, limit: int
    ) -> list[AttendeeAction]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT a.* FROM attendee_actions a"
                " JOIN attendees t ON a.attendee_id=t.id"
                " WHERE t.cohort_id=?"
                " ORDER BY a.occurred_at DESC LIMIT ?",
                (cohort_id, max(1, min(int(limit), 1000))),
            ).fetchall()
            return [self._row_to_action(r) for r in rows]
        finally:
            conn.close()

    async def recent_actions_for_cohort(
        self, cohort_id: str, *, limit: int = 100
    ) -> list[AttendeeAction]:
        return await asyncio.to_thread(
            self._recent_actions_for_cohort_sync, cohort_id, limit=limit
        )

    # ---------- aggregates ----------------------------------------------

    def _get_cohort_status_sync(
        self, cohort_id: str, *, active_window_s: int
    ) -> dict[str, Any]:
        conn = self._connect()
        try:
            cohort_row = conn.execute(
                "SELECT * FROM cohorts WHERE id=?", (cohort_id,)
            ).fetchone()
            if cohort_row is None:
                return {"ok": False, "reason": "not_found"}
            cohort = self._row_to_cohort(cohort_row)
            attendee_rows = conn.execute(
                "SELECT * FROM attendees WHERE cohort_id=?", (cohort_id,)
            ).fetchall()
            attendees = [self._row_to_attendee(r) for r in attendee_rows]
            now = time.time()
            by_phase: dict[str, int] = {p: 0 for p in PHASES}
            error_count = 0
            flagged_count = 0
            active_now = 0
            playbook_runs_total = 0
            for a in attendees:
                by_phase[a.current_phase] = by_phase.get(a.current_phase, 0) + 1
                error_count += a.errors
                playbook_runs_total += a.playbook_runs
                if a.flagged:
                    flagged_count += 1
                if (now - a.last_activity_at) <= active_window_s:
                    active_now += 1
            return {
                "ok": True,
                "cohort": {
                    "id": cohort.id,
                    "name": cohort.name,
                    "slug": cohort.slug,
                    "started_at": cohort.started_at,
                    "ended_at": cohort.ended_at,
                    "facilitator_user_id": cohort.facilitator_user_id,
                    "max_attendees": cohort.max_attendees,
                    "metadata": cohort.metadata,
                },
                "total_attendees": len(attendees),
                "active_now": active_now,
                "active_window_s": active_window_s,
                "by_phase": by_phase,
                "errors": error_count,
                "flagged": flagged_count,
                "playbook_runs_total": playbook_runs_total,
            }
        finally:
            conn.close()

    async def get_cohort_status(
        self,
        cohort_id: str,
        *,
        active_window_s: int = ACTIVE_NOW_WINDOW_S,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._get_cohort_status_sync, cohort_id, active_window_s=active_window_s
        )

    async def broadcast_message(
        self,
        cohort_id: str,
        *,
        message: str,
        sender_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Append a broadcast row to every attendee's timeline.

        The fan-out is store-only here; the router additionally calls
        ``sse.publish`` so subscribed dashboards see the broadcast
        live. Returns ``{ok, count, action_ids}``.
        """

        if not message.strip():
            raise ValueError("broadcast message must be non-empty")
        attendees = await self.list_attendees(cohort_id)
        action_ids: list[str] = []
        for att in attendees:
            action = await self.record_action(
                attendee_id=att.id,
                action_type="broadcast",
                payload={
                    "message": message.strip(),
                    "sender_user_id": sender_user_id,
                },
            )
            action_ids.append(action.id)
        return {
            "ok": True,
            "count": len(action_ids),
            "action_ids": action_ids,
            "cohort_id": cohort_id,
        }


# ---------- module-level singleton helpers ----------------------------------


_singleton: CohortStore | None = None


def get_store() -> CohortStore:
    global _singleton
    if _singleton is None:
        _singleton = CohortStore()
    return _singleton


def reset_store() -> None:
    """Drop the cached singleton — used by tests + the
    ``TARS_COHORT_DB_PATH`` env override."""

    global _singleton
    _singleton = None
