"""Derived ``trace_summary`` materialised view over the meeet event store.

The events table is the source of truth. Walking it for every
trace-explorer request is wasteful: production cockpits accumulate
thousands of events per day and the trace explorer only needs the
roll-up. This module maintains a denormalised ``trace_summary`` table
that an operator-side scheduler refreshes every few minutes.

Wire shape (per row):

- ``trace_id`` — primary key, mirrors the events column.
- ``event_count`` — number of events with this trace_id.
- ``kinds_json`` — sorted list of distinct event kinds (JSON array).
- ``routes_json`` — distinct routes that participated (JSON array).
- ``primary_route`` — single route label (``edge`` / ``cloud`` /
  ``fallback`` / ``mixed`` if more than one is present, else
  ``None``).
- ``total_cost_usd`` — sum of ``payload.cost_usd`` from
  ``usage.tokens`` events for this trace (0.0 when none).
- ``tokens_in`` / ``tokens_out`` — sum of the same.
- ``contradictions`` — sum of ``payload.contradictions`` from
  ``sampler.decision`` events.
- ``error_count`` — events whose ``kind`` ends with ``.failed`` /
  ``.error``, plus events with ``last_error`` set.
- ``last_session_id`` — most recent ``session_id`` observed.
- ``started_at`` / ``ended_at`` / ``duration_ms`` — first / last ts
  of any event in the trace.
- ``updated_at`` — when the rollup row was last written.

The table is recomputed from scratch on each rebuild (idempotent
``INSERT OR REPLACE``). Future optimisation: keep a high-water mark
and only re-process traces with new events; for now the brute-force
walk costs O(events) and runs in milliseconds for normal local stores.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .store import MeeetStore, get_store


_TRACE_SUMMARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS trace_summary (
    trace_id TEXT PRIMARY KEY,
    event_count INTEGER NOT NULL,
    kinds_json TEXT NOT NULL,
    routes_json TEXT NOT NULL,
    primary_route TEXT,
    total_cost_usd REAL NOT NULL DEFAULT 0,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    contradictions INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_session_id TEXT,
    started_at REAL,
    ended_at REAL,
    duration_ms INTEGER,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trace_summary_started
    ON trace_summary (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_trace_summary_route
    ON trace_summary (primary_route);

CREATE INDEX IF NOT EXISTS idx_trace_summary_session
    ON trace_summary (last_session_id);
"""


def _ensure_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    try:
        conn.executescript(_TRACE_SUMMARY_SCHEMA)
    finally:
        conn.close()


@dataclass(frozen=True)
class TraceSummary:
    trace_id: str
    event_count: int
    kinds: list[str]
    routes: list[str]
    primary_route: str | None
    total_cost_usd: float
    tokens_in: int
    tokens_out: int
    contradictions: int
    error_count: int
    last_session_id: str | None
    started_at: float | None
    ended_at: float | None
    duration_ms: int | None
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "event_count": self.event_count,
            "kinds": list(self.kinds),
            "routes": list(self.routes),
            "primary_route": self.primary_route,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "contradictions": self.contradictions,
            "error_count": self.error_count,
            "last_session_id": self.last_session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "updated_at": self.updated_at,
        }


def _kind_is_error(kind: str) -> bool:
    return kind.endswith(".failed") or kind.endswith(".error")


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _classify_route(routes: Iterable[str]) -> str | None:
    seen = sorted({r for r in routes if r})
    if not seen:
        return None
    if len(seen) == 1:
        return seen[0]
    if "fallback" in seen:
        return "fallback"
    return "mixed"


def _rebuild_sync(db_path: str, *, since: float | None = None) -> dict[str, Any]:
    _ensure_schema(db_path)
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    started = time.perf_counter()
    try:
        clauses: list[str] = ["trace_id IS NOT NULL"]
        params: list[Any] = []
        if since is not None:
            clauses.append("ts >= ?")
            params.append(float(since))
        sql = (
            f"SELECT trace_id, ts, kind, payload, route, session_id, "
            f"last_error FROM events WHERE {' AND '.join(clauses)} "
            f"ORDER BY ts ASC"
        )
        cur = conn.execute(sql, params)
        rollup: dict[str, dict[str, Any]] = {}
        for row in cur:
            tid = row["trace_id"]
            if not tid:
                continue
            bucket = rollup.setdefault(
                tid,
                {
                    "event_count": 0,
                    "kinds": set(),
                    "routes": set(),
                    "total_cost_usd": 0.0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "contradictions": 0,
                    "error_count": 0,
                    "last_session_id": None,
                    "started_at": None,
                    "ended_at": None,
                },
            )
            bucket["event_count"] += 1
            kind = row["kind"] or ""
            bucket["kinds"].add(kind)
            route = row["route"]
            if route:
                bucket["routes"].add(route)
            ts = float(row["ts"] or 0.0)
            if bucket["started_at"] is None or ts < bucket["started_at"]:
                bucket["started_at"] = ts
            if bucket["ended_at"] is None or ts > bucket["ended_at"]:
                bucket["ended_at"] = ts
            session_id = row["session_id"]
            if session_id:
                bucket["last_session_id"] = session_id

            payload = _parse_payload(row["payload"])
            if kind == "usage.tokens":
                bucket["total_cost_usd"] += _coerce_float(payload.get("cost_usd"))
                bucket["tokens_in"] += _coerce_int(payload.get("tokens_in"))
                bucket["tokens_out"] += _coerce_int(payload.get("tokens_out"))
            if kind == "sampler.decision":
                bucket["contradictions"] += _coerce_int(
                    payload.get("contradictions")
                )

            if _kind_is_error(kind) or row["last_error"]:
                bucket["error_count"] += 1

        if not rollup:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return {
                "ok": True,
                "scanned_events": 0,
                "traces": 0,
                "elapsed_ms": round(elapsed_ms, 3),
            }

        now = time.time()
        rows: list[tuple[Any, ...]] = []
        for tid, b in rollup.items():
            kinds_json = json.dumps(sorted(b["kinds"]), separators=(",", ":"))
            routes_sorted = sorted(b["routes"])
            routes_json = json.dumps(routes_sorted, separators=(",", ":"))
            primary = _classify_route(routes_sorted)
            duration_ms: int | None = None
            if (
                b["started_at"] is not None
                and b["ended_at"] is not None
                and b["ended_at"] >= b["started_at"]
            ):
                duration_ms = int(round((b["ended_at"] - b["started_at"]) * 1000))
            rows.append(
                (
                    tid,
                    b["event_count"],
                    kinds_json,
                    routes_json,
                    primary,
                    round(b["total_cost_usd"], 6),
                    b["tokens_in"],
                    b["tokens_out"],
                    b["contradictions"],
                    b["error_count"],
                    b["last_session_id"],
                    b["started_at"],
                    b["ended_at"],
                    duration_ms,
                    now,
                )
            )

        conn.executemany(
            """
            INSERT OR REPLACE INTO trace_summary (
                trace_id, event_count, kinds_json, routes_json,
                primary_route, total_cost_usd, tokens_in, tokens_out,
                contradictions, error_count, last_session_id,
                started_at, ended_at, duration_ms, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        scanned = sum(b["event_count"] for b in rollup.values())
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "ok": True,
            "scanned_events": scanned,
            "traces": len(rollup),
            "elapsed_ms": round(elapsed_ms, 3),
        }
    finally:
        conn.close()


def _row_to_summary(row: sqlite3.Row) -> TraceSummary:
    def _json_list(raw: Any) -> list[str]:
        try:
            data = json.loads(raw or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return [str(x) for x in data] if isinstance(data, list) else []

    return TraceSummary(
        trace_id=row["trace_id"],
        event_count=int(row["event_count"]),
        kinds=_json_list(row["kinds_json"]),
        routes=_json_list(row["routes_json"]),
        primary_route=row["primary_route"],
        total_cost_usd=float(row["total_cost_usd"] or 0.0),
        tokens_in=int(row["tokens_in"] or 0),
        tokens_out=int(row["tokens_out"] or 0),
        contradictions=int(row["contradictions"] or 0),
        error_count=int(row["error_count"] or 0),
        last_session_id=row["last_session_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration_ms=row["duration_ms"],
        updated_at=float(row["updated_at"] or 0.0),
    )


def _list_sync(
    db_path: str,
    *,
    limit: int,
    since: float | None,
    primary_route: str | None,
    session_id: str | None,
) -> list[TraceSummary]:
    _ensure_schema(db_path)
    clauses: list[str] = []
    params: list[Any] = []
    if since is not None:
        clauses.append("started_at >= ?")
        params.append(float(since))
    if primary_route:
        clauses.append("primary_route = ?")
        params.append(primary_route)
    if session_id:
        clauses.append("last_session_id = ?")
        params.append(session_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM trace_summary {where} "
        f"ORDER BY started_at DESC NULLS LAST LIMIT ?"
    )
    params.append(int(limit))
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_summary(r) for r in rows]


def _get_sync(db_path: str, trace_id: str) -> TraceSummary | None:
    _ensure_schema(db_path)
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM trace_summary WHERE trace_id = ?", (trace_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_summary(row) if row is not None else None


class TraceSummaryStore:
    """Thin async wrapper around the materialised view.

    Shares the SQLite DB with :class:`MeeetStore` so the operator only
    runs one durable buffer file. The store is *derived* — every cell
    can be reconstructed from the events table, no migration risk.
    """

    def __init__(
        self,
        db_path: str | None = None,
        *,
        events_store: MeeetStore | None = None,
    ) -> None:
        self.events_store = events_store
        if db_path is not None:
            self.db_path = os.path.expanduser(db_path)
        elif events_store is not None:
            self.db_path = events_store.db_path
        else:
            self.db_path = get_store().db_path
        self.enabled = (
            events_store.enabled
            if events_store is not None
            else get_store().enabled
        )
        if self.enabled:
            _ensure_schema(self.db_path)

    async def rebuild(self, *, since: float | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "store_disabled"}
        return await asyncio.to_thread(_rebuild_sync, self.db_path, since=since)

    async def list_summaries(
        self,
        *,
        limit: int = 50,
        since: float | None = None,
        primary_route: str | None = None,
        session_id: str | None = None,
    ) -> list[TraceSummary]:
        if not self.enabled:
            return []
        limit = max(1, min(int(limit), 500))
        return await asyncio.to_thread(
            _list_sync,
            self.db_path,
            limit=limit,
            since=since,
            primary_route=primary_route,
            session_id=session_id,
        )

    async def get(self, trace_id: str) -> TraceSummary | None:
        if not self.enabled or not trace_id:
            return None
        return await asyncio.to_thread(_get_sync, self.db_path, trace_id)


_SINGLETON: Optional[TraceSummaryStore] = None


def get_trace_summary_store() -> TraceSummaryStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = TraceSummaryStore()
    return _SINGLETON


def reset_trace_summary_store() -> None:
    """Test helper: drop the cached singleton so a new path/env is read."""

    global _SINGLETON
    _SINGLETON = None
