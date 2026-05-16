"""W269 -- TTFV onboarding telemetry.

Backs the 60-second voice-first first-launch tour rendered in the
desktop cockpit (`desktop/src-tauri/web/index.html`). Three endpoints:

- ``POST /api/onboarding/event``  -- one row per step. Body:
  ``{step: 1..5, elapsed_ms: int, completed?: bool, meta?: object}``.
- ``GET  /api/onboarding/stats``  -- aggregate TTFV stats over the
  recorded sessions: completion rate per step, median + p95 of total
  elapsed_ms among completed sessions.
- ``POST /api/onboarding/skip``   -- mark this session as skipped
  (separate row so the funnel is honest about drop-off).

Storage is a tiny SQLite DB at ``~/.tars/onboarding.sqlite`` (override
via ``TARS_ONBOARDING_DB``). Pure stdlib + FastAPI -- no extra deps.

Why a dedicated table instead of riding W235 metering:

W235 metering is tuned for ``usage.tokens`` cost rollups (cost_usd,
provider, model). TTFV is a UX funnel metric -- different cardinality,
different retention story, and we want per-step granularity even after
the user has moved on. We DO still call ``record_usage`` at step 5
completion so the consumption console shows a single ``onboarding.ttfv``
data point alongside the rest -- that gives marketing the headline
number without polluting the cost ledger.
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


# ─── W285 — first-boot voice-onboarding state ──────────────────────────
# The desktop client uses this to decide whether to show the splash +
# Iron-Man-style English greeting + language picker. Persists across
# reinstalls because it lives at ~/.tars/state.json, outside the app
# bundle and outside browser storage.

def _state_path() -> Path:
    raw = os.environ.get("TARS_STATE_FILE", "~/.tars/state.json")
    p = Path(os.path.expanduser(raw))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_state() -> dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_state(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _read_state()
    cur.update(patch)
    p = _state_path()
    p.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    return cur


class W285FirstBootState(BaseModel):
    """W285 — first-boot voice-onboarding state."""

    first_boot_done: bool = False
    lang: str | None = None


@router.get("/state")
async def get_onboarding_state() -> dict[str, Any]:
    """Return whether the first-boot voice onboarding flow has been completed.

    W285. The desktop client calls this on every boot; if `first_boot_done`
    is True, it skips the splash + greeting + language picker flow.
    """
    s = _read_state()
    return {
        "ok": True,
        "first_boot_done": bool(s.get("first_boot_done")),
        "lang": s.get("lang"),
        "first_boot_at": s.get("first_boot_at"),
    }


@router.post("/state")
async def post_onboarding_state(body: W285FirstBootState) -> dict[str, Any]:
    """Persist first-boot completion (or any later flag patches).

    W285. Idempotent — called by the desktop client once the user picks a
    language and the localized intro audio finishes playing.
    """
    patch: dict[str, Any] = {}
    if body.first_boot_done:
        patch["first_boot_done"] = True
        patch["first_boot_at"] = time.time()
    if body.lang:
        patch["lang"] = body.lang
    out = _write_state(patch)
    return {"ok": True, **out}



# --- storage ------------------------------------------------------


def _db_path() -> Path:
    raw = os.environ.get("TARS_ONBOARDING_DB", "~/.tars/onboarding.sqlite")
    p = Path(os.path.expanduser(raw))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS onboarding_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            step       INTEGER NOT NULL,        -- 1..5; 0 = skip marker
            elapsed_ms INTEGER NOT NULL,        -- since session start
            completed  INTEGER NOT NULL DEFAULT 0,
            meta       TEXT NOT NULL DEFAULT '{}',
            ts         REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS onb_session_idx ON onboarding_events(session_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS onb_step_idx ON onboarding_events(step)"
    )
    return conn


# --- request models -----------------------------------------------


class EventBody(BaseModel):
    step: int = Field(..., ge=1, le=5)
    elapsed_ms: int = Field(..., ge=0, le=10 * 60 * 1000)  # cap at 10 min
    completed: bool = False
    session_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def _trim_session(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 64:
            raise ValueError("session_id too long")
        return v


class SkipBody(BaseModel):
    session_id: str | None = None
    elapsed_ms: int = Field(0, ge=0, le=10 * 60 * 1000)
    reason: str = ""

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, v: str) -> str:
        return (v or "")[:120]


# --- endpoints ----------------------------------------------------


@router.post("/event")
def record_event(body: EventBody) -> dict[str, Any]:
    """Log a single step's timing. Returns the session_id (new or echoed)."""
    sid = body.session_id or uuid.uuid4().hex[:16]
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO onboarding_events
                  (session_id, step, elapsed_ms, completed, meta, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    int(body.step),
                    int(body.elapsed_ms),
                    1 if body.completed else 0,
                    _json_dumps(body.meta),
                    time.time(),
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        raise HTTPException(500, f"onboarding_db_error: {e}") from e

    # On final step completion, feed W235 metering so the TTFV shows
    # up in the consumption console as a single observable data point.
    if body.step == 5 and body.completed:
        _emit_ttfv_metering(sid, body.elapsed_ms)

    return {"ok": True, "session_id": sid, "step": body.step}


@router.get("/stats")
def stats() -> dict[str, Any]:
    """Aggregate TTFV stats: per-step completion + median/p95 totals."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT session_id, step, elapsed_ms, completed FROM onboarding_events"
            ).fetchall()
    except sqlite3.Error as e:
        raise HTTPException(500, f"onboarding_db_error: {e}") from e

    # Sessions that hit a particular step at least once.
    per_step: dict[int, set[str]] = {i: set() for i in range(1, 6)}
    per_step_completed: dict[int, set[str]] = {i: set() for i in range(1, 6)}
    skipped: set[str] = set()
    finished_elapsed: list[int] = []

    for r in rows:
        step = int(r["step"])
        sid = r["session_id"]
        if step == 0:
            skipped.add(sid)
            continue
        if step in per_step:
            per_step[step].add(sid)
            if int(r["completed"]) == 1:
                per_step_completed[step].add(sid)
        if step == 5 and int(r["completed"]) == 1:
            finished_elapsed.append(int(r["elapsed_ms"]))

    started = sorted(per_step[1] | skipped)
    total_starts = len(started)
    completion_rate = (
        (len(per_step_completed[5]) / total_starts) if total_starts else 0.0
    )

    out: dict[str, Any] = {
        "total_sessions_started": total_starts,
        "total_sessions_completed": len(per_step_completed[5]),
        "total_sessions_skipped": len(skipped),
        "completion_rate": round(completion_rate, 4),
        "median_ttfv_ms": int(statistics.median(finished_elapsed))
        if finished_elapsed
        else None,
        "p95_ttfv_ms": int(_p95(finished_elapsed)) if finished_elapsed else None,
        "steps": {
            str(i): {
                "reached": len(per_step[i]),
                "completed": len(per_step_completed[i]),
            }
            for i in range(1, 6)
        },
    }
    return out


@router.post("/skip")
def skip(body: SkipBody) -> dict[str, Any]:
    """Mark the current session as skipped (drop-off accounting)."""
    sid = body.session_id or uuid.uuid4().hex[:16]
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO onboarding_events
                  (session_id, step, elapsed_ms, completed, meta, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    0,
                    int(body.elapsed_ms),
                    0,
                    _json_dumps({"reason": body.reason}),
                    time.time(),
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        raise HTTPException(500, f"onboarding_db_error: {e}") from e
    return {"ok": True, "session_id": sid, "skipped": True}


# --- helpers ------------------------------------------------------


def _json_dumps(obj: Any) -> str:
    import json

    try:
        return json.dumps(obj, separators=(",", ":"), default=str)
    except Exception:
        return "{}"


def _p95(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    # Linear-interpolation p95 -- good enough for a tiny sample.
    k = (len(s) - 1) * 0.95
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _emit_ttfv_metering(session_id: str, elapsed_ms: int) -> None:
    """Best-effort: drop a single ``onboarding.ttfv`` event into W235.

    Failures are swallowed -- the metering subsystem may not be wired
    in every environment (tests, on-prem subset), and the TTFV row is
    already persisted in our own DB.
    """
    try:
        from backend.core.metering.recorder import (
            UsageEvent,
            record_usage,
            resolve_tier,
        )

        evt = UsageEvent(
            trace_id=f"onb-{session_id}",
            ts_utc=time.time(),
            provider="tars",
            model="onboarding",
            action="onboarding.ttfv",
            tokens_in=0,
            tokens_out=0,
            latency_ms=float(elapsed_ms),
            cost_usd=0.0,
            cost_meeet=0.0,
            outcome="ok",
            tier=resolve_tier(),
            agent_id="onboarding",
            domain_pack="",
        )
        record_usage(evt)
    except Exception:
        # Metering may be absent / disabled; ignore.
        return
