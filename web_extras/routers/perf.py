"""Performance dashboard HTTP surface (Wave 108).

Aggregates the operational health metrics surfaced by the
``/admin/perf`` page:

- Latency stats (P50/P95/P99/Max) for council / backtest / webhook /
  connector calls -- pulled from the in-process recorder
  :mod:`backend.core.observability.latency`.
- Connector health snapshot via :mod:`backend.core.connectors.registry`.
- Webhook delivery counters from
  :class:`backend.core.webhooks.WebhookStore`.
- Receipt-chain integrity from :class:`backend.core.receipts.ReceiptStore`.
- Scheduler / background-job status from
  :class:`backend.core.scheduler.SchedulerStore`.
- Best-effort host resource usage via :mod:`psutil` when present.

Endpoints:

    GET /api/perf/summary
    GET /api/perf/latency?op=<op>&window=24h
    GET /api/perf/health/connectors
    GET /api/perf/jobs

Read-only -- never raises a 5xx for missing optional deps; missing
modules degrade to ``{ok: true, available: false, reason: ...}``
shapes the FE can render without surprise.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.core.connectors import registry as connectors_registry
from backend.core.observability import latency as latency_mod
from backend.core.receipts import get_store as get_receipt_store
from backend.core.receipts.chain import verify_chain
from backend.core.scheduler import get_store as get_scheduler_store
from backend.core.webhooks import DeliveryStatus, get_store as get_webhook_store


log = logging.getLogger("tars.perf")

router = APIRouter(prefix="/api/perf", tags=["perf"])


# Canonical operation names tracked on the dashboard. New surfaces
# can be added freely; the FE renders any op the recorder knows.
TRACKED_OPS = ("council", "backtest", "webhook", "connector")
WINDOW_24H_S = 24 * 3600


# ---------- helpers ----------------------------------------------------


def _parse_window(raw: str | None) -> float | None:
    """Accept ``24h`` / ``1h`` / ``15m`` / ``300s`` / raw integer seconds."""

    if raw is None or not str(raw).strip():
        return WINDOW_24H_S
    s = str(raw).strip().lower()
    try:
        if s.endswith("h"):
            return float(s[:-1]) * 3600
        if s.endswith("m"):
            return float(s[:-1]) * 60
        if s.endswith("s"):
            return float(s[:-1])
        return float(s)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_window", "hint": "use 24h / 1h / 15m / 300s"},
        )


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _isoday_offset(days: int) -> str:
    return (datetime.now(timezone.utc).date()).isoformat()  # placeholder day_iso


# ---------- latency ----------------------------------------------------


def _latency_card(op: str, *, window_s: float) -> dict[str, Any]:
    return latency_mod.summary(op, window_s=window_s)


@router.get("/latency")
async def get_latency(
    op: str = Query(..., min_length=1),
    window: str | None = Query(default="24h"),
) -> dict[str, Any]:
    window_s = _parse_window(window)
    return {
        "ok": True,
        "op": op,
        "window_s": window_s,
        "summary": latency_mod.summary(op, window_s=window_s),
        "histogram": latency_mod.histogram(op, window_s=window_s),
    }


# ---------- connector health -------------------------------------------


async def _gather_connector_health() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for name in connectors_registry.list_connectors():
        spec = connectors_registry.get(name)
        configured = bool(spec.is_configured())
        connected = bool(spec.has_token())
        # Wave 108 -- never block on real network calls inside this
        # endpoint; just report the cached "would_call" status. The
        # explicit /api/connectors/{name}/health endpoint is the live
        # ping path.
        items.append(
            {
                "name": spec.name,
                "label": spec.label,
                "configured": configured,
                "connected": connected,
                "env_vars": list(spec.env_vars),
            }
        )
    return {"ok": True, "as_of": int(time.time()), "connectors": items}


@router.get("/health/connectors")
async def perf_connector_health() -> dict[str, Any]:
    return await _gather_connector_health()


# ---------- webhook stats ----------------------------------------------


async def _webhook_stats(window_s: float) -> dict[str, Any]:
    store = get_webhook_store()
    if not store.enabled:
        return {"ok": True, "available": False, "reason": "disabled"}

    cutoff = time.time() - window_s

    def _counts() -> dict[str, Any]:
        # Connect directly through the store to keep the SQL local.
        conn = sqlite3.connect(store.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM deliveries WHERE created_at >= ?",
                (cutoff,),
            ).fetchone()
            total = int(row["n"]) if row else 0
            counts: dict[str, int] = {}
            for status in (
                DeliveryStatus.PENDING.value,
                DeliveryStatus.SUCCESS.value,
                DeliveryStatus.RETRY.value,
                DeliveryStatus.FAILED.value,
            ):
                r = conn.execute(
                    "SELECT COUNT(*) AS n FROM deliveries"
                    " WHERE created_at >= ? AND status = ?",
                    (cutoff, status),
                ).fetchone()
                counts[status] = int(r["n"]) if r else 0
            failed_rows = conn.execute(
                "SELECT id, webhook_id, event_type, last_error, last_status_code, attempts"
                " FROM deliveries WHERE status = ? AND created_at >= ?"
                " ORDER BY last_attempt_at DESC LIMIT 25",
                (DeliveryStatus.FAILED.value, cutoff),
            ).fetchall()
            failed = [dict(r) for r in failed_rows]
            return {"total": total, "counts": counts, "failed": failed}
        finally:
            conn.close()

    try:
        data = await asyncio.to_thread(_counts)
    except sqlite3.Error as exc:
        log.warning("webhook stats query failed: %s", exc)
        return {"ok": True, "available": False, "reason": str(exc)}

    sig_summary = latency_mod.summary("webhook.signature", window_s=window_s)
    return {
        "ok": True,
        "available": True,
        "window_s": window_s,
        "total": data["total"],
        "success": data["counts"].get(DeliveryStatus.SUCCESS.value, 0),
        "pending": data["counts"].get(DeliveryStatus.PENDING.value, 0),
        "retrying": data["counts"].get(DeliveryStatus.RETRY.value, 0),
        "failed": data["counts"].get(DeliveryStatus.FAILED.value, 0),
        "failed_recent": data["failed"],
        "avg_signature_ms": sig_summary.get("avg"),
    }


# ---------- receipts ---------------------------------------------------


async def _receipt_integrity() -> dict[str, Any]:
    store = get_receipt_store()
    if store is None:
        return {"ok": True, "available": False, "reason": "disabled"}
    today = _today_iso()
    try:
        receipts = await store.replay_chain_for_day(today)
    except Exception as exc:  # pragma: no cover -- defensive
        log.warning("receipt replay failed: %s", exc)
        return {"ok": True, "available": False, "reason": str(exc)}
    chain = verify_chain(receipts) if receipts else {"ok": True, "issues": [], "count": 0}
    merkle = await store.get_merkle_root(today)
    last_anchor_at: float | None = None
    anchored = False
    if merkle is not None:
        anchored = bool(getattr(merkle, "solana_signature", None))
        last_anchor_at = getattr(merkle, "anchored_at", None) or getattr(merkle, "computed_at", None)
    return {
        "ok": True,
        "available": True,
        "day_iso": today,
        "today_count": len(receipts),
        "chain_valid": bool(chain.get("ok")),
        "chain_issues": chain.get("issues") or [],
        "merkle_root": getattr(merkle, "root_hex", None) if merkle else None,
        "anchored_to_solana": anchored,
        "last_anchor_at": last_anchor_at,
    }


# ---------- background jobs --------------------------------------------


async def _jobs_status() -> dict[str, Any]:
    sched_store = get_scheduler_store()
    if not sched_store.enabled:
        sched_summary: dict[str, Any] = {"available": False, "reason": "disabled"}
    else:
        try:
            schedules = await sched_store.list_schedules()
            now = time.time()
            next_due: float | None = None
            enabled = 0
            for s in schedules:
                if s.enabled:
                    enabled += 1
                    if s.next_run_at is not None and (next_due is None or s.next_run_at < next_due):
                        next_due = s.next_run_at
            sched_summary = {
                "available": True,
                "schedule_count": len(schedules),
                "enabled_count": enabled,
                "next_run_at": next_due,
                "next_run_in_s": (next_due - now) if next_due is not None else None,
                "tick_interval_s": float(os.getenv("TARS_SCHEDULER_TICK_S") or 30.0),
            }
        except Exception as exc:  # pragma: no cover -- defensive
            sched_summary = {"available": False, "reason": str(exc)}

    reflection = {
        "available": True,
        "enabled": (os.getenv("TARS_REFLECTION_ENABLED") or "").strip().lower()
        in {"1", "true", "yes", "on"},
        "interval_s": float(os.getenv("TARS_REFLECTION_INTERVAL_S") or 0)
        if (os.getenv("TARS_REFLECTION_INTERVAL_S") or "").strip()
        else None,
    }
    autopilot = {
        "available": True,
        "enabled": (os.getenv("TARS_AUTOPILOT_ENABLED") or "").strip().lower()
        in {"1", "true", "yes", "on"},
        "tick_s": float(os.getenv("TARS_AUTOPILOT_TICK_S") or 0)
        if (os.getenv("TARS_AUTOPILOT_TICK_S") or "").strip()
        else None,
    }
    return {
        "ok": True,
        "scheduler": sched_summary,
        "reflection": reflection,
        "autopilot": autopilot,
    }


@router.get("/jobs")
async def perf_jobs() -> dict[str, Any]:
    return await _jobs_status()


# ---------- resource usage (host) --------------------------------------


def _resource_usage() -> dict[str, Any]:
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return {"ok": True, "available": False, "reason": "psutil_not_installed"}

    try:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
    except Exception as exc:  # pragma: no cover -- defensive
        return {"ok": True, "available": False, "reason": str(exc)}

    tars_dir = os.path.expanduser("~/.tars")
    disk_total = disk_used = disk_free = None
    try:
        if os.path.isdir(tars_dir):
            usage = shutil.disk_usage(tars_dir)
            disk_total = usage.total
            disk_used = usage.used
            disk_free = usage.free
    except OSError:
        pass

    return {
        "ok": True,
        "available": True,
        "cpu_percent": cpu,
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
        },
        "disk": {
            "tars_dir": tars_dir,
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
        },
    }


# ---------- summary (everything in one shot) ---------------------------


@router.get("/summary")
async def perf_summary(
    window: str | None = Query(default="24h"),
) -> dict[str, Any]:
    window_s = _parse_window(window)
    latency_cards = {op: _latency_card(op, window_s=window_s) for op in TRACKED_OPS}
    connectors = await _gather_connector_health()
    webhooks = await _webhook_stats(window_s or WINDOW_24H_S)
    receipts = await _receipt_integrity()
    jobs = await _jobs_status()
    resources = _resource_usage()
    return {
        "ok": True,
        "as_of": int(time.time()),
        "window_s": window_s,
        "latency": latency_cards,
        "connectors": connectors,
        "webhooks": webhooks,
        "receipts": receipts,
        "jobs": jobs,
        "resources": resources,
    }


__all__ = ["router"]
