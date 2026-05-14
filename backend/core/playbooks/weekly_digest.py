"""W209 — Weekly digest playbook.

Runs every Sunday at 9am local. Generates a one-page reflection of the
user's TARS week (counts of actions, top packs, notable events) and
fanouts to whatever notification channels are configured (iMessage,
Telegram, Email — same fanout sibling used by doctor_watch).

Importable as a callable so the scheduler can pick it up:

    from backend.core.playbooks.weekly_digest import run_weekly_digest
    result = await run_weekly_digest()

Returns a structured dict so the scheduler can log it deterministically.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def run_weekly_digest(*, channels: list[str] | None = None) -> dict[str, Any]:
    """Produce + (optionally) fanout the weekly summary."""
    now = time.time()
    week_ago = now - 7 * 86400

    summary: dict[str, Any] = {
        "ok": True,
        "generated_at": int(now),
        "period_start": int(week_ago),
        "period_end": int(now),
        "sections": {},
    }

    # 1) Receipts in the last 7 days
    try:
        from backend.core.receipts.store import get_store

        s = get_store()
        recent = await s.list_recent(limit=1000) if hasattr(s, "list_recent") else []
        last7 = [r for r in recent if getattr(r, "ts", 0) >= week_ago]
        by_kind: dict[str, int] = {}
        for r in last7:
            k = getattr(r, "kind", None) or "unknown"
            by_kind[k] = by_kind.get(k, 0) + 1
        summary["sections"]["receipts"] = {
            "total": len(last7),
            "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])[:8]),
        }
    except Exception as exc:
        summary["sections"]["receipts"] = {"error": str(exc)[:120]}

    # 2) Doctor: any persistent failures?
    try:
        from backend.core.doctor.registry import run_all

        results = await run_all() if callable(run_all) else []
        failed = []
        for r in results:
            status = getattr(r, "status", None) or (r.get("status") if isinstance(r, dict) else None)
            if status in ("fail", "warn"):
                slug = getattr(r, "slug", None) or (r.get("slug") if isinstance(r, dict) else "?")
                summary_text = getattr(r, "summary", None) or (
                    r.get("summary") if isinstance(r, dict) else ""
                )
                failed.append({"slug": slug, "status": status, "summary": summary_text})
        summary["sections"]["doctor"] = {
            "total_checks": len(results),
            "issues": failed[:10],
        }
    except Exception as exc:
        summary["sections"]["doctor"] = {"error": str(exc)[:120]}

    # 3) Agents touched this week
    try:
        from backend.core.agents.store import get_store as get_agents

        a = get_agents()
        agents = await a.list_agents() if hasattr(a, "list_agents") else []
        active = [
            ag for ag in agents
            if getattr(ag, "updated_at", 0) >= week_ago
        ]
        summary["sections"]["agents"] = {
            "total_agents": len(agents),
            "active_this_week": len(active),
            "packs": sorted({getattr(a, "pack_slug", None) for a in active} - {None}),
        }
    except Exception as exc:
        summary["sections"]["agents"] = {"error": str(exc)[:120]}

    # ─── Build a human-readable digest text ────────────────────────────
    rec = summary["sections"].get("receipts", {})
    doc = summary["sections"].get("doctor", {})
    ag = summary["sections"].get("agents", {})
    lines = ["📅 TARS · Weekly Digest"]
    lines.append("─" * 36)
    if isinstance(rec.get("total"), int):
        lines.append(f"Actions this week: {rec['total']}")
        top = list(rec.get("by_kind", {}).items())[:3]
        if top:
            lines.append("Top: " + ", ".join(f"{k}×{v}" for k, v in top))
    if isinstance(ag.get("active_this_week"), int):
        lines.append(f"Active agents: {ag['active_this_week']}/{ag.get('total_agents', 0)}")
    issues = doc.get("issues", []) if isinstance(doc, dict) else []
    if issues:
        lines.append(f"\n⚠ {len(issues)} health issue(s):")
        for i in issues[:3]:
            lines.append(f"  · {i['slug']}: {i['summary'][:60]}")
    else:
        lines.append("\nAll health checks green ✓")
    digest_text = "\n".join(lines)
    summary["digest_text"] = digest_text

    # Persist for the cockpit's daily briefing & next-run delta detection.
    try:
        out_dir = Path(os.path.expanduser("~")) / ".tars"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "reflection_latest.json").write_text(
            json.dumps({"generated_at": summary["generated_at"], "summary": digest_text}, indent=2)
        )
    except Exception as exc:
        logger.warning("weekly_digest.persist_failed: %s", exc)

    # Fanout (best-effort)
    fanout_result: dict[str, Any] = {"attempted": False}
    if channels is None:
        env_ch = (os.getenv("TARS_DIGEST_CHANNELS") or "").strip()
        channels = [c.strip() for c in env_ch.split(",") if c.strip()] if env_ch else []
    if channels:
        try:
            from backend.core.notifications.fanout import fanout_all

            fanout_result = {
                "attempted": True,
                "results": await fanout_all(channels, digest_text, slug="weekly_digest"),
            }
        except Exception as exc:
            fanout_result = {"attempted": True, "error": str(exc)[:200]}
    summary["fanout"] = fanout_result

    return summary
