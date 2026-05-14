"""Usage metering recorder + sinks (W235).

The hot path is :func:`record_usage`. Three sinks fire per call:

1. SQLite mirror at ``~/.tars/usage.sqlite`` (table ``usage_events``)
2. Receipt ledger (kind=``usage``) via best-effort dispatch
3. Async POST to meeet.world ``/api/billing/usage_event``; failures
   land in ``usage_retry_queue`` for manual sync.

Subscribers register via :func:`subscribe` to get an asyncio queue of
:class:`UsageEvent` instances — wired into ``/api/usage/stream`` SSE.

This module never raises into the caller. Anything that fails inside
``record_usage`` is logged at DEBUG and the call returns. The
middleware decorator relies on that contract — failing telemetry
must never block an LLM call.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


log = logging.getLogger("tars.metering")


# ── pricing + tier caps (W235 contract — matches PRICING_ECONOMICS_v9.2.md)

PRICING: dict[str, dict[str, float]] = {
    "anthropic:claude-sonnet-4-6": {"in_per_1k": 0.003, "out_per_1k": 0.015},
    "anthropic:claude-opus-4-6":   {"in_per_1k": 0.015, "out_per_1k": 0.075},
    "anthropic:claude-3-5-sonnet": {"in_per_1k": 0.003, "out_per_1k": 0.015},
    "anthropic:claude-3-5-haiku":  {"in_per_1k": 0.0008, "out_per_1k": 0.004},
    "openai:gpt-4o":               {"in_per_1k": 0.0025, "out_per_1k": 0.010},
    "openai:gpt-4o-mini":          {"in_per_1k": 0.00015, "out_per_1k": 0.0006},
    "openai:gpt-4.1":              {"in_per_1k": 0.002, "out_per_1k": 0.008},
    "openrouter:*":                {"surcharge_pct": 5.0},
    "google:gemini-1.5-pro":       {"in_per_1k": 0.00125, "out_per_1k": 0.005},
    "google:gemini-1.5-flash":     {"in_per_1k": 0.000075, "out_per_1k": 0.0003},
    "local:*":                     {"in_per_1k": 0.0, "out_per_1k": 0.0},
    "tars-local-v1":               {"in_per_1k": 0.0, "out_per_1k": 0.0},
}

TIER_CAPS: dict[str, dict[str, float]] = {
    "FREE":     {"requests_per_month": 50,   "soft_cap_usd": 1.50, "hard_cap_usd": 3.00},
    "PRO":      {"requests_per_month": 1000, "soft_cap_usd": 18.0, "hard_cap_usd": 25.0},
    "BUSINESS": {"requests_per_month": 5000, "soft_cap_usd": 38.0, "hard_cap_usd": 60.0},
    "LIFETIME": {"requests_per_month": 10000, "soft_cap_usd": 100.0, "hard_cap_usd": 200.0},
}

# Conversion rate from USD to $MEEET tokens (illustrative — 1 USD = 100 MEEET).
# Brother's edge is the source of truth; this is a local mirror.
MEEET_PER_USD = float(os.environ.get("TARS_MEEET_PER_USD") or "100.0")


# ── env helpers ────────────────────────────────────────────────────────

def _expand(p: str) -> str:
    return os.path.expanduser(p)


def _usage_db_path() -> str:
    raw = os.environ.get("TARS_USAGE_DB_PATH") or "~/.tars/usage.sqlite"
    return _expand(raw)


def _meeet_base() -> str:
    return (os.environ.get("MEEET_BASE_URL") or "").rstrip("/")


def _meeet_secret() -> str:
    return (
        os.environ.get("MEEET_BRIDGE_SHARED_SECRET")
        or os.environ.get("MEEET_BILLING_API_KEY")
        or ""
    ).strip()


def _meeet_mode() -> str:
    return (os.environ.get("MEEET_MODE") or "off").strip().lower()


def _meeet_token_path() -> str:
    return _expand(os.environ.get("TARS_MEEET_TOKEN_PATH") or "~/.tars/meeet_token")


def resolve_tier() -> str:
    """Read the operator tier from env first, then ``~/.tars/meeet_token``."""

    forced = (os.environ.get("TARS_TIER") or "").strip().upper()
    if forced in TIER_CAPS:
        return forced
    path = _meeet_token_path()
    try:
        if Path(path).is_file():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            tier = str(data.get("tier") or "").strip().upper()
            if tier in TIER_CAPS:
                return tier
    except Exception as exc:  # noqa: BLE001
        log.debug("metering.resolve_tier failed: %s", exc)
    return "FREE"


# ── event dataclass ────────────────────────────────────────────────────

@dataclass(frozen=True)
class UsageEvent:
    """A single metered LLM/agent action."""

    trace_id: str
    ts_utc: float
    provider: str
    model: str
    action: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    cost_meeet: float
    outcome: str          # "ok" | "provider_error" | "tars_error" | "user_cancel"
    tier: str
    agent_id: str = ""
    domain_pack: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["iso"] = datetime.fromtimestamp(self.ts_utc, tz=timezone.utc).isoformat()
        return d


# ── pricing ────────────────────────────────────────────────────────────

def compute_cost_usd(
    provider: str, model: str, tokens_in: int, tokens_out: int
) -> float:
    """Resolve cost from the inline ``PRICING`` table.

    Lookup order:
        1. ``"{provider}:{model}"`` exact match
        2. ``"{provider}:*"`` wildcard for the provider
        3. ``"local:*"`` for missing entries (defaults to 0)
    Returns USD rounded to 6 decimals.
    """

    if tokens_in <= 0 and tokens_out <= 0:
        return 0.0
    key = f"{provider}:{model}".lower() if provider else model.lower()
    entry = PRICING.get(key)
    surcharge_pct = 0.0
    if entry is None:
        # provider-wildcard, e.g. "openrouter:*"
        wildcard = f"{provider.lower()}:*"
        wild_entry = PRICING.get(wildcard)
        if wild_entry is not None:
            surcharge_pct = float(wild_entry.get("surcharge_pct", 0.0) or 0.0)
            # When the provider entry only carries a surcharge, fall back to the
            # bare-model entry (so an OpenRouter call still gets priced).
            entry = PRICING.get(model.lower()) or None
    if entry is None:
        # second-pass: scan for a prefix match (e.g. legacy keys).
        for k, v in PRICING.items():
            if model and k.endswith(model.lower()):
                entry = v
                break
    if entry is None:
        return 0.0
    in_rate = float(entry.get("in_per_1k", 0.0) or 0.0)
    out_rate = float(entry.get("out_per_1k", 0.0) or 0.0)
    base = (tokens_in / 1000.0) * in_rate + (tokens_out / 1000.0) * out_rate
    if surcharge_pct:
        base *= 1.0 + (surcharge_pct / 100.0)
    return round(base, 6)


def _usd_to_meeet(usd: float) -> float:
    return round(float(usd) * MEEET_PER_USD, 4)


# ── SQLite mirror ──────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
    trace_id    TEXT PRIMARY KEY,
    ts_utc      REAL NOT NULL,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    action      TEXT NOT NULL,
    tokens_in   INTEGER NOT NULL,
    tokens_out  INTEGER NOT NULL,
    latency_ms  REAL NOT NULL,
    cost_usd    REAL NOT NULL,
    cost_meeet  REAL NOT NULL,
    outcome     TEXT NOT NULL,
    tier        TEXT NOT NULL,
    agent_id    TEXT,
    domain_pack TEXT,
    day_iso     TEXT NOT NULL,
    month_iso   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_events (ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_events (day_iso);
CREATE INDEX IF NOT EXISTS idx_usage_month ON usage_events (month_iso);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_events (model);

CREATE TABLE IF NOT EXISTS usage_retry_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    last_error  TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retry_trace ON usage_retry_queue (trace_id);
"""

_db_lock = threading.Lock()


def _open_db() -> sqlite3.Connection:
    p = _usage_db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def _write_sqlite(ev: UsageEvent) -> None:
    day = datetime.fromtimestamp(ev.ts_utc, tz=timezone.utc).strftime("%Y-%m-%d")
    month = day[:7]
    with _db_lock:
        conn = _open_db()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO usage_events
                (trace_id, ts_utc, provider, model, action,
                 tokens_in, tokens_out, latency_ms, cost_usd, cost_meeet,
                 outcome, tier, agent_id, domain_pack, day_iso, month_iso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev.trace_id, ev.ts_utc, ev.provider, ev.model, ev.action,
                    int(ev.tokens_in), int(ev.tokens_out), float(ev.latency_ms),
                    float(ev.cost_usd), float(ev.cost_meeet),
                    ev.outcome, ev.tier, ev.agent_id, ev.domain_pack,
                    day, month,
                ),
            )
        finally:
            conn.close()


def _queue_retry(ev: UsageEvent, err: str) -> None:
    with _db_lock:
        conn = _open_db()
        try:
            conn.execute(
                "INSERT INTO usage_retry_queue (trace_id, payload_json, last_error, attempts, created_at)"
                " VALUES (?, ?, ?, 0, ?)",
                (ev.trace_id, json.dumps(ev.to_dict()), err[:512], time.time()),
            )
        finally:
            conn.close()


def _drain_retries() -> list[tuple[int, str, dict]]:
    """Return ``[(id, trace_id, payload)]`` rows still pending."""

    with _db_lock:
        conn = _open_db()
        try:
            cur = conn.execute(
                "SELECT id, trace_id, payload_json FROM usage_retry_queue ORDER BY id ASC"
            )
            return [(r[0], r[1], json.loads(r[2])) for r in cur.fetchall()]
        finally:
            conn.close()


def _delete_retry(row_id: int) -> None:
    with _db_lock:
        conn = _open_db()
        try:
            conn.execute("DELETE FROM usage_retry_queue WHERE id = ?", (row_id,))
        finally:
            conn.close()


def _bump_retry(row_id: int, err: str) -> None:
    with _db_lock:
        conn = _open_db()
        try:
            conn.execute(
                "UPDATE usage_retry_queue SET attempts = attempts + 1, last_error = ? WHERE id = ?",
                (err[:512], row_id),
            )
        finally:
            conn.close()


# ── HMAC POST to meeet.world ───────────────────────────────────────────

def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _post_sync(url: str, body: bytes, sig: str, timeout_s: float) -> None:
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-TARS-Signature": sig,
            "User-Agent": "TARS-metering/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        # 2xx is success; drain the body so the conn closes cleanly.
        _ = resp.read()


async def _post_to_meeet(ev: UsageEvent) -> None:
    base = _meeet_base()
    secret = _meeet_secret()
    mode = _meeet_mode()
    if mode != "live" or not base or not secret:
        return
    url = f"{base}/api/billing/usage_event"
    body = json.dumps(ev.to_dict(), separators=(",", ":")).encode("utf-8")
    sig = _sign(body, secret)
    timeout_s = float(os.environ.get("MEEET_USAGE_TIMEOUT_S") or "3.0")
    try:
        await asyncio.to_thread(_post_sync, url, body, sig, timeout_s)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        log.debug("metering.post_to_meeet failed: %s", exc)
        _queue_retry(ev, repr(exc))


# ── subscribe pattern for SSE ──────────────────────────────────────────

_subscribers: set[asyncio.Queue[UsageEvent]] = set()
_subscribers_lock = threading.Lock()


def subscribe() -> asyncio.Queue[UsageEvent]:
    """Register an asyncio queue that receives every new UsageEvent."""

    q: asyncio.Queue[UsageEvent] = asyncio.Queue(maxsize=256)
    with _subscribers_lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[UsageEvent]) -> None:
    with _subscribers_lock:
        _subscribers.discard(q)


def _fanout(ev: UsageEvent) -> None:
    with _subscribers_lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:  # pragma: no cover — backpressure
            log.debug("metering.fanout queue full; dropping for slow consumer")


# ── receipt ledger sink ────────────────────────────────────────────────

async def _emit_receipt(ev: UsageEvent) -> None:
    try:
        from backend.core.receipts.dispatch import record as receipt_record
    except Exception:  # pragma: no cover — receipts disabled
        return
    try:
        await receipt_record(
            type="usage",
            actor=ev.agent_id or "tars",
            resource=f"{ev.provider}/{ev.model}",
            payload=ev.to_dict(),
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("metering.emit_receipt failed: %s", exc)


# ── main entry point ───────────────────────────────────────────────────

def record_usage(event: UsageEvent) -> None:
    """Record a usage event to all three sinks.

    Synchronous on the SQLite + fanout legs; the receipt + meeet POST
    schedule as background tasks when an event loop is running.
    Never raises — telemetry failures must not break the caller.
    """

    try:
        _write_sqlite(event)
    except Exception as exc:  # noqa: BLE001
        log.debug("metering.sqlite failed: %s", exc)

    try:
        _fanout(event)
    except Exception as exc:  # noqa: BLE001
        log.debug("metering.fanout failed: %s", exc)

    # Async sinks — schedule when a loop is running, else fire-and-forget thread.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_emit_receipt(event))
        loop.create_task(_post_to_meeet(event))
    except RuntimeError:
        # Not in async context — receipt store is async too, run synchronously
        # in a fresh loop. Used by tests that call record_usage directly.
        try:
            asyncio.run(_emit_receipt(event))
        except Exception as exc:  # noqa: BLE001
            log.debug("metering.receipt sync failed: %s", exc)
        try:
            asyncio.run(_post_to_meeet(event))
        except Exception as exc:  # noqa: BLE001
            log.debug("metering.meeet sync failed: %s", exc)


# ── aggregation helpers ────────────────────────────────────────────────

def _aggregate(scope_col: str, scope_val: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "scope": scope_val,
        "events_count": 0,
        "cost_usd": 0.0,
        "cost_meeet": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "by_model": {},
        "by_action": {},
        "by_outcome": {},
    }
    with _db_lock:
        conn = _open_db()
        try:
            cur = conn.execute(
                f"SELECT model, action, outcome, tokens_in, tokens_out, cost_usd, cost_meeet"
                f" FROM usage_events WHERE {scope_col} = ?",
                (scope_val,),
            )
            for row in cur.fetchall():
                model, action, outcome, t_in, t_out, c_usd, c_meeet = row
                out["events_count"] += 1
                out["tokens_in"] += int(t_in or 0)
                out["tokens_out"] += int(t_out or 0)
                out["cost_usd"] += float(c_usd or 0.0)
                out["cost_meeet"] += float(c_meeet or 0.0)
                _bucket_add(out["by_model"], model or "(unknown)", c_usd, t_in, t_out)
                _bucket_add(out["by_action"], action or "(unknown)", c_usd, t_in, t_out)
                _bucket_add(out["by_outcome"], outcome or "(unknown)", c_usd, t_in, t_out)
        finally:
            conn.close()
    out["cost_usd"] = round(out["cost_usd"], 6)
    out["cost_meeet"] = round(out["cost_meeet"], 4)
    return out


def _bucket_add(
    b: dict[str, dict[str, float]],
    key: str,
    cost_usd: float,
    t_in: int,
    t_out: int,
) -> None:
    row = b.setdefault(
        key, {"events": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0}
    )
    row["events"] += 1
    row["cost_usd"] = round(row["cost_usd"] + float(cost_usd or 0.0), 6)
    row["tokens_in"] += int(t_in or 0)
    row["tokens_out"] += int(t_out or 0)


def aggregate_today() -> dict[str, Any]:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = _aggregate("day_iso", day)
    out["day"] = day
    return out


def aggregate_month() -> dict[str, Any]:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    out = _aggregate("month_iso", month)
    out["month"] = month
    return out


def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(1000, int(limit)))
    with _db_lock:
        conn = _open_db()
        try:
            cur = conn.execute(
                "SELECT trace_id, ts_utc, provider, model, action, tokens_in, tokens_out,"
                " latency_ms, cost_usd, cost_meeet, outcome, tier, agent_id, domain_pack"
                " FROM usage_events ORDER BY ts_utc DESC LIMIT ?",
                (limit,),
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()


def get_events_since(iso: str | None, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(1000, int(limit)))
    since_ts = 0.0
    if iso:
        try:
            since_ts = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            since_ts = 0.0
    with _db_lock:
        conn = _open_db()
        try:
            cur = conn.execute(
                "SELECT trace_id, ts_utc, provider, model, action, tokens_in, tokens_out,"
                " latency_ms, cost_usd, cost_meeet, outcome, tier, agent_id, domain_pack"
                " FROM usage_events WHERE ts_utc > ? ORDER BY ts_utc ASC LIMIT ?",
                (since_ts, limit),
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()


def current_balance_local() -> dict[str, Any]:
    """Local mirror of remaining budget — meeet.world is source of truth.

    Reads month spend + applies the tier cap; ``remote_available``
    indicates whether brother's edge could be queried for the
    authoritative balance.
    """

    tier = resolve_tier()
    caps = TIER_CAPS.get(tier, TIER_CAPS["FREE"])
    month = aggregate_month()
    spent_usd = float(month.get("cost_usd") or 0.0)
    requests_used = int(month.get("events_count") or 0)
    soft = float(caps["soft_cap_usd"])
    hard = float(caps["hard_cap_usd"])
    remaining = max(0.0, round(hard - spent_usd, 6))
    return {
        "tier": tier,
        "spent_usd": round(spent_usd, 6),
        "remaining_usd": remaining,
        "soft_cap_usd": soft,
        "hard_cap_usd": hard,
        "requests_used": requests_used,
        "requests_cap": int(caps["requests_per_month"]),
        "pct_of_hard": round(spent_usd / hard, 4) if hard > 0 else 0.0,
        "source": "local_mirror",
        "remote_available": bool(_meeet_base() and _meeet_secret() and _meeet_mode() == "live"),
    }


# ── retry queue manual sync ────────────────────────────────────────────

async def retry_failed_sync() -> dict[str, Any]:
    base = _meeet_base()
    secret = _meeet_secret()
    if _meeet_mode() != "live" or not base or not secret:
        return {"ok": False, "error": "meeet_not_live", "drained": 0, "remaining": len(_drain_retries())}
    url = f"{base}/api/billing/usage_event"
    timeout_s = float(os.environ.get("MEEET_USAGE_TIMEOUT_S") or "3.0")
    rows = _drain_retries()
    drained = 0
    remaining_errs = 0
    for row_id, trace_id, payload in rows:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = _sign(body, secret)
        try:
            await asyncio.to_thread(_post_sync, url, body, sig, timeout_s)
            _delete_retry(row_id)
            drained += 1
        except Exception as exc:  # noqa: BLE001
            _bump_retry(row_id, repr(exc))
            remaining_errs += 1
    return {"ok": True, "drained": drained, "still_failing": remaining_errs}


# ── healthz ────────────────────────────────────────────────────────────

def healthz() -> dict[str, Any]:
    try:
        conn = _open_db()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM usage_events")
            count = int(cur.fetchone()[0])
            cur = conn.execute("SELECT COUNT(*) FROM usage_retry_queue")
            pending = int(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}
    return {
        "ok": True,
        "db_path": _usage_db_path(),
        "events_total": count,
        "retry_pending": pending,
        "meeet_mode": _meeet_mode(),
        "meeet_configured": bool(_meeet_base() and _meeet_secret()),
        "tier": resolve_tier(),
        "subscribers": len(_subscribers),
    }


# ── ergonomic helper for middleware ────────────────────────────────────

def new_trace_id() -> str:
    return uuid.uuid4().hex
