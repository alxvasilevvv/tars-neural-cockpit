"""Action handlers for the business pack.

Real adapters land here progressively. Two are implemented now:

- ``kpi_snapshot`` reads ``data/business_kpi.json`` (path overridable via
  ``BUSINESS_KPI_PATH`` env or the ``path`` arg).
- ``daily_brief`` composes a deterministic operator brief from the KPI
  snapshot plus ``data/business_deals.json``. Replaces the council
  output until the council orchestrator lands; the council can drop in
  here without changing the surface contract.

``draft_email`` and ``log_deal`` stay structured stubs — they need a
mail provider / CRM integration to be useful and are out of scope for
the local-first cut.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...base import ActionSpec
from ..._http import post_json
from backend.core.vault import get_secret
from ....council import get_council

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_KPI_PATH = _REPO_ROOT / "data" / "business_kpi.json"
_DEFAULT_DEALS_PATH = _REPO_ROOT / "data" / "business_deals.json"


def _resolve(path_arg: str | None, env_var: str, default: Path) -> Path:
    if path_arg:
        return Path(path_arg).expanduser()
    env = os.getenv(env_var)
    if env:
        return Path(env).expanduser()
    return default


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


async def kpi_snapshot(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = _resolve(
        str(args.get("path") or "") or None,
        "BUSINESS_KPI_PATH",
        _DEFAULT_KPI_PATH,
    )
    if not path.exists():
        return {
            "ok": False,
            "error": "kpi_file_missing",
            "path": str(path),
            "hint": "drop a JSON snapshot at data/business_kpi.json or set BUSINESS_KPI_PATH",
        }
    try:
        data = _read_json(path)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": "kpi_parse_error", "detail": str(e)}

    metrics = data.get("metrics") or {}
    summary: list[dict[str, Any]] = []
    for key, value in metrics.items():
        if not isinstance(value, dict):
            continue
        summary.append(
            {
                "id": key,
                "value": value.get("value"),
                "delta_pct": value.get("delta_pct"),
                "trend": value.get("trend") or "flat",
            }
        )

    return {
        "ok": True,
        "as_of": data.get("as_of"),
        "sources": data.get("sources") or ["local"],
        "metrics": metrics,
        "summary": summary,
        "path": str(path),
    }


_DEFAULT_CAL_PATH = _REPO_ROOT / "data" / "calendar_events.json"


async def daily_brief(args: Mapping[str, Any]) -> Mapping[str, Any]:
    date = str(args.get("date") or datetime.now(timezone.utc).date().isoformat())

    kpi_path = _resolve(
        str(args.get("kpi_path") or "") or None,
        "BUSINESS_KPI_PATH",
        _DEFAULT_KPI_PATH,
    )
    deals_path = _resolve(
        str(args.get("deals_path") or "") or None,
        "BUSINESS_DEALS_PATH",
        _DEFAULT_DEALS_PATH,
    )
    cal_path = _resolve(
        str(args.get("calendar_path") or "") or None,
        "CALENDAR_PATH",
        _DEFAULT_CAL_PATH,
    )

    kpi_data: dict[str, Any] = {}
    if kpi_path.exists():
        try:
            kpi_data = _read_json(kpi_path)
        except json.JSONDecodeError:
            kpi_data = {}

    deals: list[dict[str, Any]] = []
    if deals_path.exists():
        try:
            raw = _read_json(deals_path)
            deals = [d for d in raw if isinstance(d, dict)]
        except json.JSONDecodeError:
            deals = []

    calendar_events: list[dict[str, Any]] = []
    if cal_path.exists():
        try:
            cal = _read_json(cal_path)
            calendar_events = [
                e for e in (cal.get("events") or []) if isinstance(e, dict)
            ]
        except json.JSONDecodeError:
            calendar_events = []
    today_iso = date
    today_events = [
        e for e in calendar_events if str(e.get("start", "")).startswith(today_iso)
    ]
    today_events.sort(key=lambda e: str(e.get("start") or ""))

    metrics = kpi_data.get("metrics") or {}
    deltas = []
    for key in ("mrr_usd", "pipeline_usd", "logo_churn_pct", "nps"):
        m = metrics.get(key) or {}
        if "delta_pct" not in m:
            continue
        deltas.append(
            {
                "id": key,
                "value": m.get("value"),
                "delta_pct": m.get("delta_pct"),
                "trend": m.get("trend") or "flat",
            }
        )

    deals_active = [d for d in deals if d.get("stage") not in {"won", "lost"}]
    deals_active.sort(
        key=lambda d: float(d.get("amount", 0) or 0), reverse=True
    )
    next_steps = [
        {
            "deal_id": d.get("id"),
            "name": d.get("name"),
            "stage": d.get("stage"),
            "amount": d.get("amount"),
            "due": d.get("due"),
            "next_step": d.get("next_step"),
        }
        for d in deals_active[:5]
    ]

    headline_metric = next(
        (
            d
            for d in deltas
            if isinstance(d.get("delta_pct"), (int, float))
        ),
        None,
    )
    if headline_metric:
        verb = "up" if (headline_metric["delta_pct"] or 0) >= 0 else "down"
        summary = (
            f"{headline_metric['id'].upper()} is {verb} "
            f"{abs(headline_metric['delta_pct']):.1f}% — focus on "
            f"{(next_steps[0]['name'] if next_steps else 'pipeline')}."
        )
    else:
        summary = "No KPI deltas available; review pipeline manually."

    cal_today_payload = [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "start": e.get("start"),
            "kind": e.get("kind"),
            "duration_min": e.get("duration_min"),
        }
        for e in today_events
    ]

    use_council = bool(args.get("council", True))
    deliberation = None
    headline_summary = summary
    if use_council:
        deliberation = await get_council().deliberate(
            "Compose the morning brief for the operator.",
            {
                "topic": "kpi",
                "deltas": deltas,
                "calendar_today": cal_today_payload,
                "deals_active": len(deals_active),
                "deals_total": len(deals),
            },
            mode=str(args.get("council_mode") or "dual_vote"),
        )
        headline_summary = deliberation.summary

    return {
        "ok": True,
        "date": date,
        "summary": headline_summary,
        "deltas": deltas,
        "actions": next_steps,
        "deals_total": len(deals),
        "deals_active": len(deals_active),
        "calendar_today": cal_today_payload,
        "sources": ["local-json", "calendar-local"]
        + (["council"] if deliberation else []),
        "council": deliberation.to_dict() if deliberation else None,
    }


async def _push_hubspot_deal(name: str, amount: float) -> dict[str, Any] | None:
    key = get_secret("HUBSPOT_API_KEY")
    if not key:
        return None
    props: dict[str, str] = {"dealname": name}
    if isinstance(amount, (int, float)) and amount > 0:
        props["amount"] = str(amount)
    status, data = await post_json(
        "https://api.hubapi.com/crm/v3/objects/deals",
        {"properties": props},
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        timeout=15.0,
    )
    if status in (200, 201) and isinstance(data, dict) and data.get("id"):
        return {
            "crm": "hubspot",
            "deal_id": str(data["id"]),
            "crm_pushed": True,
        }
    return None


async def _push_pipedrive_deal(name: str, amount: float) -> dict[str, Any] | None:
    token = get_secret("PIPEDRIVE_API_KEY")
    if not token:
        return None
    q = urllib.parse.urlencode({"api_token": token})
    url = f"https://api.pipedrive.com/v1/deals?{q}"
    payload: dict[str, Any] = {"title": name, "currency": "USD"}
    val = float(amount) if isinstance(amount, (int, float)) else 0.0
    if val > 0:
        payload["value"] = val
    status, data = await post_json(url, payload, timeout=15.0)
    if status not in (200, 201) or not isinstance(data, dict):
        return None
    inner = data.get("data")
    if isinstance(inner, dict) and inner.get("id"):
        return {
            "crm": "pipedrive",
            "deal_id": str(inner["id"]),
            "crm_pushed": True,
        }
    return None


async def draft_email(args: Mapping[str, Any]) -> Mapping[str, Any]:
    to = str(args.get("to", "")).strip()
    if not to:
        return {"ok": False, "error": "to_required"}
    subject = str(args.get("subject", "")).strip() or "Quick note"
    tone = str(args.get("tone", "concise"))

    body_by_tone = {
        "concise": "Quick one — could we sync briefly this week to align?",
        "warm": "Hope you're well! I'd love to grab time to align on next steps.",
        "formal": (
            "I would like to schedule a brief meeting at your convenience "
            "to discuss our next milestones."
        ),
        "blunt": "We need to align this week. What slot works?",
    }
    body = body_by_tone.get(tone, body_by_tone["concise"])

    return {
        "ok": True,
        "to": to,
        "subject": subject,
        "body": body,
        "tone": tone,
        "sent": False,
        "hint": "draft only; cockpit will require explicit confirmation to send",
    }


async def log_deal(args: Mapping[str, Any]) -> Mapping[str, Any]:
    name = str(args.get("name", "")).strip()
    if not name:
        return {"ok": False, "error": "name_required"}
    amount_f = float(args.get("amount", 0) or 0)
    stage = str(args.get("stage", "discovery"))

    pushed = await _push_hubspot_deal(name, amount_f)
    if pushed:
        return {
            "ok": True,
            "name": name,
            "amount": amount_f,
            "stage": stage,
            **pushed,
        }
    pushed = await _push_pipedrive_deal(name, amount_f)
    if pushed:
        return {
            "ok": True,
            "name": name,
            "amount": amount_f,
            "stage": stage,
            **pushed,
        }

    return {
        "ok": True,
        "deal_id": "stub-deal-0001",
        "name": name,
        "amount": amount_f,
        "stage": stage,
        "crm_pushed": False,
        "hint": (
            "set HUBSPOT_API_KEY or PIPEDRIVE_API_KEY — otherwise deal "
            "stays stub-local until a CRM vault entry is present."
        ),
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="daily_brief",
        name="Compose daily brief",
        description="Compose the morning brief from local KPI + deals snapshots.",
        handler=daily_brief,
        schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "kpi_path": {"type": "string"},
                "deals_path": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="draft_email",
        name="Draft email",
        description="Draft an outbound email; never sends without confirmation.",
        handler=draft_email,
        schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "tone": {
                    "type": "string",
                    "enum": ["concise", "warm", "formal", "blunt"],
                },
            },
            "required": ["to"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="kpi_snapshot",
        name="KPI snapshot",
        description="Read the local KPI snapshot (JSON) and return summary deltas.",
        handler=kpi_snapshot,
        schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    ),
    ActionSpec(
        id="log_deal",
        name="Log deal",
        description="Stage a new deal locally before pushing to CRM.",
        handler=log_deal,
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "amount": {"type": "number"},
                "stage": {"type": "string"},
            },
            "required": ["name"],
        },
        destructive=True,
    ),
)
