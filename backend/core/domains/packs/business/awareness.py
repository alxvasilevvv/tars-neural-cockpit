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
from .local_deals import (
    DEFAULT_LOCAL_DEALS_PATH,
    read_local_deals,
    resolve_local_deals_path,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CALENDAR_PATH = _REPO_ROOT / "data" / "calendar_events.json"
_KPI_PATH = _REPO_ROOT / "data" / "business_kpi.json"
_DEALS_PATH = _REPO_ROOT / "data" / "business_deals.json"

_TERMINAL_STAGES: frozenset[str] = frozenset({"won", "lost"})


def _read_json_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return None


async def _fetch_gmail(_args: Mapping[str, Any]) -> Mapping[str, Any]:
    # Wave 91: try the real Gmail connector first, fall back to stub.
    try:
        from backend.core.connectors import gmail as _gmail

        if _gmail.is_configured() and _gmail.has_token():
            client = _gmail.GmailClient.from_stored_token()
            return client.summarize_unread(max_results=5)
    except Exception:
        # Fall through to stub on any error -- dev/local must keep
        # working without Google OAuth credentials.
        pass
    return {
        "ok": True,
        "kind": "stub",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "messages": [],
        "hint": "configure Gmail connector via /api/connectors/gmail/auth-url",
    }


async def _fetch_calendar(args: Mapping[str, Any]) -> Mapping[str, Any]:
    # Wave 91: try the real Google Calendar connector first.
    try:
        from backend.core.connectors import calendar as _cal

        if _cal.is_configured() and _cal.has_token():
            client = _cal.CalendarClient.from_stored_token()
            cal_id = str(args.get("calendar") or "primary")
            return client.today_summary(calendar_id=cal_id)
    except Exception:
        pass
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


async def _fetch_local_deals(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Snapshot the local-first business deals store.

    Defaults to ``active_only=True`` so the cockpit ticker only
    surfaces deals still in flight; pass ``active_only=False`` to
    inspect won / lost rows. ``stage`` filters to a single stage
    (case-insensitive). ``owner`` filters case-insensitively. ``limit``
    is clamped to the conservative range ``[1, 200]`` because the
    awareness snapshot is meant for the cockpit ticker, not bulk
    export.

    Always returns a structurally-stable envelope so the cockpit can
    bind unconditionally.
    """

    path_arg = str(args.get("path") or "").strip() or None
    target = resolve_local_deals_path(path_arg)

    active_only_raw = args.get("active_only")
    active_only = True if active_only_raw is None else bool(active_only_raw)

    stage_arg = args.get("stage")
    stage = stage_arg if isinstance(stage_arg, str) and stage_arg.strip() else None
    owner_arg = args.get("owner")
    owner = owner_arg if isinstance(owner_arg, str) and owner_arg.strip() else None

    limit_arg = args.get("limit")
    if isinstance(limit_arg, bool):
        limit: int | None = None
    elif isinstance(limit_arg, int) and limit_arg > 0:
        limit = min(limit_arg, 200)
    else:
        limit = 50

    try:
        rows = read_local_deals(
            path=target,
            active_only=active_only,
            stage=stage,
            owner=owner,
            limit=limit,
        )
    except OSError:
        return {
            "ok": False,
            "error": "local_deals_unreadable",
            "path": str(target),
        }

    by_stage: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    pipeline_total = 0.0
    for row in rows:
        st = str(row.get("stage") or "")
        if st:
            by_stage[st] = by_stage.get(st, 0) + 1
        ow = row.get("owner")
        if isinstance(ow, str) and ow.strip():
            key = ow.strip()
            by_owner[key] = by_owner.get(key, 0) + 1
        if st not in _TERMINAL_STAGES:
            try:
                pipeline_total += float(row.get("amount") or 0)
            except (TypeError, ValueError):
                pass

    return {
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "path": str(target),
        "exists": target.exists(),
        "count": len(rows),
        "pipeline_usd": round(pipeline_total, 2),
        "by_stage": by_stage,
        "by_owner": by_owner,
        "filters": {
            "active_only": active_only,
            "stage": stage.lower() if stage else None,
            "owner": owner.lower() if owner else None,
            "limit": limit,
        },
        "deals": rows,
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
    AwarenessSource(
        id="local_deals",
        name="Local deals",
        description=(
            "Snapshot the local-first business deals store. Defaults to "
            "active_only=True so the cockpit ticker only shows deals "
            "still in flight."
        ),
        kind="local",
        config={
            "path": DEFAULT_LOCAL_DEALS_PATH,
            "active_only": True,
            "limit": 50,
        },
        fetcher=_fetch_local_deals,
    ),
)
