"""W260 — inbox: incoming review requests from peer TARS instances.

Shares ``~/.tars/t2t_reviews.sqlite`` with :mod:`outbox` (schema is
defined once in ``outbox._SCHEMA`` and both modules call ``_init``
through their own store class — SQLite handles concurrent table
creation via ``CREATE TABLE IF NOT EXISTS``).

State machine for inbox rows:

- ``pending``  -- received, awaiting reviewer decision.
- ``approved`` -- reviewer approved, signed response was returned.
- ``rejected`` -- reviewer rejected with a reason.

Note: we never auto-apply the embedded plan on the inbox side. The
sender's TARS A is the one that owns the project tree; the receiver
just signs a verdict. The auto-apply step happens on the *outbox*
side via the router once the response envelope returns.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .outbox import _SCHEMA, _is_disabled, _resolve_db_path


class InboxStore:
    """SQLite-backed incoming-reviews store."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self.db_path = _resolve_db_path(db_path)
        self._lock = threading.Lock()
        self._init_done = False

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

    # ---- writes ------------------------------------------------------

    def insert_incoming(
        self,
        *,
        review_id: str,
        sender_tars_id: str,
        plan_id: str,
        request_envelope: dict[str, Any],
    ) -> None:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO inbox "
                    "(review_id, sender_tars_id, plan_id, state, "
                    " received_at, request_envelope_json) "
                    "VALUES (?, ?, ?, 'pending', ?, ?)",
                    (
                        review_id,
                        sender_tars_id,
                        plan_id,
                        now,
                        json.dumps(request_envelope),
                    ),
                )
                conn.commit()

    def mark_decided(
        self,
        *,
        review_id: str,
        decision: str,
        response_envelope: dict[str, Any],
        comment: str | None = None,
    ) -> bool:
        """Persist the reviewer's decision + the signed response we
        returned to the sender. Returns ``False`` when no inbox row
        exists for ``review_id`` (caller should 404 in that case).
        """

        target_state = "approved" if decision == "approve" else "rejected"
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE inbox SET state = ?, decided_at = ?, "
                    " response_envelope_json = ?, reviewer_comment = ? "
                    "WHERE review_id = ?",
                    (
                        target_state,
                        time.time(),
                        json.dumps(response_envelope),
                        comment,
                        review_id,
                    ),
                )
                conn.commit()
                return cur.rowcount > 0

    # ---- reads -------------------------------------------------------

    def list_inbox(
        self,
        *,
        state: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            with self._connect() as conn:
                if state is None:
                    rows = conn.execute(
                        "SELECT review_id, sender_tars_id, plan_id, "
                        " state, received_at, decided_at, "
                        " reviewer_comment "
                        "FROM inbox ORDER BY received_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT review_id, sender_tars_id, plan_id, "
                        " state, received_at, decided_at, "
                        " reviewer_comment "
                        "FROM inbox WHERE state = ? "
                        "ORDER BY received_at DESC LIMIT ?",
                        (state, limit),
                    ).fetchall()
        return [dict(r) for r in rows]

    def get_inbox(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT review_id, sender_tars_id, plan_id, state, "
                    " received_at, decided_at, request_envelope_json, "
                    " response_envelope_json, reviewer_comment "
                    "FROM inbox WHERE review_id = ?",
                    (review_id,),
                ).fetchone()
        if row is None:
            return None
        out = dict(row)
        try:
            out["request_envelope"] = json.loads(
                out.pop("request_envelope_json")
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            out["request_envelope"] = None
        raw_resp = out.pop("response_envelope_json", None)
        if raw_resp:
            try:
                out["response_envelope"] = json.loads(raw_resp)
            except (json.JSONDecodeError, TypeError):
                out["response_envelope"] = None
        else:
            out["response_envelope"] = None
        return out


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_INBOX: InboxStore | None = None
_INBOX_LOCK = threading.Lock()


def get_inbox() -> InboxStore | None:
    if _is_disabled():
        return None
    global _INBOX
    if _INBOX is not None:
        return _INBOX
    with _INBOX_LOCK:
        if _INBOX is None:
            _INBOX = InboxStore()
    return _INBOX


def reset_inbox() -> None:
    global _INBOX
    _INBOX = None
