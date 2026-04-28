"""Business pack awareness sources.

Fetchers are implemented locally first (calendar/KPI sheet/HubSpot are
mirrored from JSON files in ``data/``). They graduate to live integrations
once the relevant secrets land in the vault. The contract stays
identical so the council/orchestrator does not change.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...base import AwarenessSource

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CALENDAR_PATH = _REPO_ROOT / "data" / "calendar_events.json"
_KPI_PATH = _REPO_ROOT / "data" / "business_kpi.json"
_DEALS_PATH = _REPO_ROOT / "data" / "business_deals.json"


def _read_json_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return None


async def _fetch_gmail(_args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "kind": "stub",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "messages": [],
        "hint": "wire IMAP/JMAP credentials to make this live",
    }


async def _fetch_calendar(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = Path(str(args.get("path") or os.getenv("CALENDAR_PATH") or _CALENDAR_PATH))
    data = _read_json_or_none(path)
    if data is None:
        return {
            "ok": False,
            "error": "calendar_unavailable",
            "path": str(path),
        }
    events = data.get("events") or []
    return {
        "ok": True,
        "as_of": data.get("as_of"),
        "count": len(events),
        "events": events,
        "path": str(path),
    }


async def _fetch_hubspot(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = Path(
        str(args.get("path") or os.getenv("BUSINESS_DEALS_PATH") or _DEALS_PATH)
    )
    data = _read_json_or_none(path)
    if data is None:
        return {
            "ok": False,
            "error": "hubspot_unavailable",
            "path": str(path),
            "hint": "drop a deals JSON or wire the real HubSpot API",
        }
    deals = [d for d in (data if isinstance(data, list) else []) if isinstance(d, dict)]
    by_stage: dict[str, list[dict[str, Any]]] = {}
    pipeline_total = 0.0
    for d in deals:
        by_stage.setdefault(str(d.get("stage", "?")), []).append(d)
        if d.get("stage") not in {"won", "lost"}:
            try:
                pipeline_total += float(d.get("amount") or 0)
            except (TypeError, ValueError):
                pass
    return {
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "deals_total": len(deals),
        "pipeline_usd": round(pipeline_total, 2),
        "by_stage": {k: len(v) for k, v in by_stage.items()},
        "deals": deals,
        "path": str(path),
    }


async def _fetch_gsheets_kpi(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = Path(
        str(args.get("path") or os.getenv("BUSINESS_KPI_PATH") or _KPI_PATH)
    )
    data = _read_json_or_none(path)
    if data is None:
        return {
            "ok": False,
            "error": "kpi_unavailable",
            "path": str(path),
        }
    return {
        "ok": True,
        "as_of": data.get("as_of"),
        "metrics": data.get("metrics") or {},
        "sources": data.get("sources") or ["local"],
        "path": str(path),
    }


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="gmail",
        name="Gmail",
        description="Inbox of the operator account (read-only).",
        kind="poll",
        config={"interval_s": 60, "scope": "read", "label": "INBOX"},
        fetcher=_fetch_gmail,
    ),
    AwarenessSource(
        id="gcalendar",
        name="Google Calendar",
        description="Primary calendar with event metadata.",
        kind="poll",
        config={"interval_s": 120, "calendar": "primary"},
        fetcher=_fetch_calendar,
    ),
    AwarenessSource(
        id="hubspot",
        name="HubSpot CRM",
        description="Deals, contacts and pipelines.",
        kind="poll",
        config={"interval_s": 300, "objects": ["deals", "contacts", "companies"]},
        fetcher=_fetch_hubspot,
    ),
    AwarenessSource(
        id="gsheets_kpi",
        name="KPI sheet",
        description="A Google Sheet treated as a KPI data source.",
        kind="poll",
        config={"interval_s": 600, "sheet_id": ""},
        fetcher=_fetch_gsheets_kpi,
    ),
)
