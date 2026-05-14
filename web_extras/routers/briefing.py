"""W206 — Daily briefing endpoint.

Aggregates a one-shot status summary across the user's TARS instance:
- Health: doctor counters + tier
- Activity: receipts in the last 24h (count + last anchor)
- Memory: latest reflection if available
- Agents: count + most recently active pack

Pure read-only, always returns 200 with whatever it could gather.
Cockpit shows this on the STATUS tab as "Today" card.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


@router.get("/today")
async def today() -> dict[str, Any]:
    """One-shot snapshot: health + activity + memory + agents."""
    now = time.time()
    out: dict[str, Any] = {"ok": True, "generated_at": int(now), "sections": {}}

    # Health from doctor
    # W271 fix: previously imported backend.core.doctor.registry (doesn't
    # exist) and awaited a sync function; outer except always swallowed
    # the TypeError, so health silently came back as 0/0/0/0.
    try:
        import asyncio as _asyncio
        from backend.core.doctor.checks import run_all  # type: ignore
        results = await _asyncio.to_thread(run_all) if callable(run_all) else []
        counts = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
        for r in results:
            status = getattr(r, "status", None) or (r.get("status") if isinstance(r, dict) else None)
            if status in counts:
                counts[status] += 1
        out["sections"]["health"] = {"ok": True, "counts": counts, "total": sum(counts.values())}
    except Exception as exc:
        out["sections"]["health"] = {"ok": False, "error": str(exc)[:120]}

    # Receipts last 24h
    # W271 fix: ReceiptStore has no `list_recent`; previously the hasattr
    # guard short-circuited every call to [] and the briefing always
    # showed receipts_24h=0. Switched to `query(since=...)` which exists.
    try:
        from backend.core.receipts.store import get_store  # type: ignore
        s = get_store()
        cutoff = now - 86400
        if s is None:
            out["sections"]["activity"] = {"ok": True, "receipts_24h": 0, "last_kind": None}
        else:
            last24 = []
            if hasattr(s, "query"):
                last24 = await s.query(since=cutoff, limit=200)
            elif hasattr(s, "list_recent"):
                recent = await s.list_recent(limit=200)
                last24 = [r for r in recent if getattr(r, "ts", 0) >= cutoff]
            out["sections"]["activity"] = {
                "ok": True,
                "receipts_24h": len(last24),
                "last_kind": getattr(last24[0], "type", None) if last24 else None,
            }
    except Exception as exc:
        out["sections"]["activity"] = {"ok": False, "error": str(exc)[:120]}

    # Memory reflection (if any)
    try:
        from pathlib import Path
        home = Path(os.path.expanduser("~"))
        refl_path = home / ".tars" / "reflection_latest.json"
        if refl_path.exists():
            import json
            with refl_path.open() as f:
                refl = json.load(f)
            out["sections"]["reflection"] = {
                "ok": True,
                "generated_at": refl.get("generated_at"),
                "summary": (refl.get("summary") or "")[:300],
            }
        else:
            out["sections"]["reflection"] = {"ok": True, "summary": None}
    except Exception as exc:
        out["sections"]["reflection"] = {"ok": False, "error": str(exc)[:120]}

    # Agents count
    try:
        from backend.core.agents import get_agent_store  # type: ignore
        a = get_agent_store()
        agents = await a.list_agents() if hasattr(a, "list_agents") else []
        last_pack = agents[0].pack_slug if agents and hasattr(agents[0], "pack_slug") else None
        out["sections"]["agents"] = {
            "ok": True,
            "count": len(agents),
            "last_pack": last_pack,
        }
    except Exception as exc:
        out["sections"]["agents"] = {"ok": False, "error": str(exc)[:120]}

    # Top-level "headline" — one sentence the cockpit can put bold at top.
    health = out["sections"].get("health", {})
    activity = out["sections"].get("activity", {})
    if health.get("ok") and activity.get("ok"):
        c = health.get("counts", {})
        rec = activity.get("receipts_24h", 0)
        if c.get("fail", 0) > 0:
            headline = f"{c['fail']} check(s) failing — review the Status tab."
        elif c.get("warn", 0) > 0:
            headline = f"{c['warn']} check(s) in warn state. {rec} receipts in last 24h."
        else:
            healthy = c.get("ok", 0)
            headline = f"All {healthy} checks green. {rec} receipts in last 24h."
    else:
        headline = "Backend partial — open Status tab for details."
    out["headline"] = headline

    return out
