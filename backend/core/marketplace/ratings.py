"""Local-only ratings store for the marketplace (Wave 106).

Rationale: v0 is operator-local. We don't have a centralised
ratings backend yet (that lands with payouts in v9.3) but
operators still want the rating affordance to feel real --
including the anti-double-vote semantic.

Schema:

- One row per (listing_id, rater_hash). Re-submitting from the
  same rater updates the existing row in-place rather than
  inserting a duplicate. ``UNIQUE`` constraint enforces this at
  the SQLite layer.
- Aggregates are computed on read; we don't denormalise into a
  ``listings_aggregates`` table because v0 has tens-of-thousands
  scale at most (most operators have <100 listings rated).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import (
    Rating,
    anonymise_rater,
    new_rating_id,
)


log = logging.getLogger("tars.marketplace.ratings")


DEFAULT_DB_PATH = "~/.tars/marketplace/ratings.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ratings (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL,
    rater TEXT NOT NULL,
    score INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    rated_at REAL NOT NULL,
    UNIQUE (listing_id, rater)
);

CREATE INDEX IF NOT EXISTS idx_ratings_listing ON ratings (listing_id, rated_at DESC);
"""


def _db_path() -> str:
    return os.path.expanduser(
        os.getenv("TARS_MARKETPLACE_RATINGS_DB") or DEFAULT_DB_PATH
    )


def _connect() -> sqlite3.Connection:
    p = _db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _row_to_rating(row: tuple) -> Rating:
    return Rating(
        id=row[0],
        listing_id=row[1],
        rater=row[2],
        score=int(row[3]),
        comment=row[4] or "",
        rated_at=float(row[5]),
    )


def _do_submit_sync(
    listing_id: str,
    score: int,
    comment: str,
    rater: str,
) -> dict[str, Any]:
    if not listing_id:
        return {"ok": False, "error": "listing_id_required"}
    if not isinstance(score, int) or score < 1 or score > 5:
        return {"ok": False, "error": "score_must_be_1_to_5"}

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM ratings WHERE listing_id = ? AND rater = ?",
            (listing_id, rater),
        )
        existing = cur.fetchone()
        now = time.time()
        if existing:
            rid = existing[0]
            cur.execute(
                "UPDATE ratings SET score = ?, comment = ?, rated_at = ? WHERE id = ?",
                (score, comment or "", now, rid),
            )
            updated = True
        else:
            rid = new_rating_id()
            cur.execute(
                """INSERT INTO ratings
                          (id, listing_id, rater, score, comment, rated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rid, listing_id, rater, score, comment or "", now),
            )
            updated = False
        conn.commit()
    finally:
        conn.close()

    aggregate = _do_get_aggregate_sync(listing_id)
    return {
        "ok": True,
        "rating_id": rid,
        "listing_id": listing_id,
        "score": score,
        "updated": updated,
        "aggregate": aggregate,
    }


async def submit_rating(
    listing_id: str,
    score: int,
    *,
    comment: str = "",
    rater_email: str = "",
) -> dict[str, Any]:
    """Insert / update a rating; returns the post-submit aggregate."""

    rater = anonymise_rater(rater_email)
    return await asyncio.to_thread(
        _do_submit_sync, listing_id, int(score), comment or "", rater
    )


def _do_get_aggregate_sync(listing_id: str) -> dict[str, Any]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*), AVG(score) FROM ratings WHERE listing_id = ?",
            (listing_id,),
        ).fetchone()
    finally:
        conn.close()
    count = int(row[0] or 0)
    avg = float(row[1] or 0.0)
    return {
        "listing_id": listing_id,
        "count": count,
        "avg": round(avg, 2),
    }


async def get_aggregate(listing_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(_do_get_aggregate_sync, listing_id)


def _do_list_for_listing_sync(listing_id: str, limit: int) -> list[Rating]:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT id, listing_id, rater, score, comment, rated_at
                   FROM ratings
                   WHERE listing_id = ?
                ORDER BY rated_at DESC
                   LIMIT ?""",
            (listing_id, max(1, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_rating(r) for r in rows]


async def list_for_listing(listing_id: str, *, limit: int = 50) -> list[Rating]:
    return await asyncio.to_thread(_do_list_for_listing_sync, listing_id, limit)


def reset_db() -> None:
    """Test helper -- wipe the ratings DB."""

    p = Path(_db_path())
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


__all__ = [
    "get_aggregate",
    "list_for_listing",
    "reset_db",
    "submit_rating",
]
