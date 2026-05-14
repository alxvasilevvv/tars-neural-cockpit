"""W260 — outbox: pending outgoing reviews from this TARS to peers.

Two tables share ``~/.tars/t2t_reviews.sqlite``:

- ``outbox``    -- rows for reviews we *sent*. State machine:
                   ``pending`` -> ``approved`` | ``rejected`` |
                   ``failed`` (peer not reachable) | ``applied``
                   (plan auto-applied locally after approval).
- ``responses`` -- raw signed-envelope ``ReviewResponse`` payloads we
                   received from peers, keyed by ``review_id``.

The store is intentionally synchronous; the router wraps calls in
``asyncio.to_thread`` exactly like W253 does.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = "~/.tars/t2t_reviews.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    review_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    recipient_tars_id TEXT NOT NULL,
    peer_url TEXT,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    request_envelope_json TEXT NOT NULL,
    comment TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_state
    ON outbox (state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_plan ON outbox (plan_id);

CREATE TABLE IF NOT EXISTS inbox (
    review_id TEXT PRIMARY KEY,
    sender_tars_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    state TEXT NOT NULL,
    received_at REAL NOT NULL,
    decided_at REAL,
    request_envelope_json TEXT NOT NULL,
    response_envelope_json TEXT,
    reviewer_comment TEXT
);
CREATE INDEX IF NOT EXISTS idx_inbox_state
    ON inbox (state, received_at DESC);

CREATE TABLE IF NOT EXISTS responses (
    review_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    received_at REAL NOT NULL,
    response_envelope_json TEXT NOT NULL
);
"""


def _is_disabled() -> bool:
    raw = (os.environ.get("TARS_T2T_REVIEW_DB") or "").strip().lower()
    return raw in {"disabled", "off", "0", "no", "false"}


def _resolve_db_path(override: str | None = None) -> str:
    raw = (
        override
        or os.environ.get("TARS_T2T_REVIEW_DB_PATH")
        or DEFAULT_DB_PATH
    )
    return os.path.expanduser(raw)


class OutboxStore:
    """SQLite-backed pending-outgoing-reviews store."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self.db_path = _resolve_db_path(db_path)
        self._lock = threading.Lock()
        self._init_done = False

    # ---- init --------------------------------------------------------

    def _init(self) -> None:
        if self._init_done:
            return
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("PRAGMA journal_mode=WAL;")
            conn.executescript(_SCHEMA)
            conn.commit()
        self._init_done = True

    def _connect(self) -> sqlite3.Connection:
        self._init()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- outbox writes ----------------------------------------------

    def insert_outgoing(
        self,
        *,
        review_id: str,
        plan_id: str,
        recipient_tars_id: str,
        peer_url: str | None,
        comment: str | None,
        request_envelope: dict[str, Any],
    ) -> None:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO outbox "
                    "(review_id, plan_id, recipient_tars_id, peer_url, "
                    " state, created_at, updated_at, "
                    " request_envelope_json, comment) "
                    "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
                    (
                        review_id,
                        plan_id,
                        recipient_tars_id,
                        peer_url,
                        now,
                        now,
                        json.dumps(request_envelope),
                        comment,
                    ),
                )
                conn.commit()

    def set_state(self, review_id: str, state: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE outbox SET state = ?, updated_at = ? "
                    "WHERE review_id = ?",
                    (state, time.time(), review_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def record_response(
        self,
        *,
        review_id: str,
        decision: str,
        response_envelope: dict[str, Any],
    ) -> None:
        """Mark outbox row with the decision + persist the raw
        response envelope so the receipt anchor can re-verify later.
        """

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO responses "
                    "(review_id, decision, received_at, "
                    " response_envelope_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        review_id,
                        decision,
                        time.time(),
                        json.dumps(response_envelope),
                    ),
                )
                target_state = "approved" if decision == "approve" else "rejected"
                conn.execute(
                    "UPDATE outbox SET state = ?, updated_at = ? "
                    "WHERE review_id = ?",
                    (target_state, time.time(), review_id),
                )
                conn.commit()

    # ---- outbox reads -----------------------------------------------

    def list_outbox(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT review_id, plan_id, recipient_tars_id, "
                    " peer_url, state, created_at, updated_at, "
                    " comment "
                    "FROM outbox "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_outbox(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT review_id, plan_id, recipient_tars_id, "
                    " peer_url, state, created_at, updated_at, "
                    " comment, request_envelope_json "
                    "FROM outbox WHERE review_id = ?",
                    (review_id,),
                ).fetchone()
                resp = conn.execute(
                    "SELECT decision, received_at, response_envelope_json "
                    "FROM responses WHERE review_id = ?",
                    (review_id,),
                ).fetchone()
        if row is None:
            return None
        out = dict(row)
        try:
            out["request_envelope"] = json.loads(out.pop("request_envelope_json"))
        except (json.JSONDecodeError, TypeError, KeyError):
            out["request_envelope"] = None
        if resp is not None:
            out["response"] = {
                "decision": resp["decision"],
                "received_at": resp["received_at"],
            }
            try:
                out["response"]["envelope"] = json.loads(
                    resp["response_envelope_json"]
                )
            except (json.JSONDecodeError, TypeError):
                out["response"]["envelope"] = None
        else:
            out["response"] = None
        return out


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_OUTBOX: OutboxStore | None = None
_OUTBOX_LOCK = threading.Lock()


def get_outbox() -> OutboxStore | None:
    """Return process-wide outbox store, or ``None`` when disabled."""

    if _is_disabled():
        return None
    global _OUTBOX
    if _OUTBOX is not None:
        return _OUTBOX
    with _OUTBOX_LOCK:
        if _OUTBOX is None:
            _OUTBOX = OutboxStore()
    return _OUTBOX


def reset_outbox() -> None:
    """Drop the singleton so tests can rebind to a temp DB."""

    global _OUTBOX
    _OUTBOX = None
