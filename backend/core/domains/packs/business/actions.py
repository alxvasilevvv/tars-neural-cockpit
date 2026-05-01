"""Action handlers for the business pack.

Real adapters land here progressively. Two are implemented now:

- ``kpi_snapshot`` reads ``data/business_kpi.json`` (path overridable via
  ``BUSINESS_KPI_PATH`` env or the ``path`` arg).
- ``daily_brief`` composes a deterministic operator brief from the KPI
  snapshot plus ``data/business_deals.json``. Replaces the council
  output until the council orchestrator lands; the council can drop in
  here without changing the surface contract.

``log_deal`` is a real adapter:

- HubSpot ``HUBSPOT_API_KEY`` (vault) wins the routing.
- Pipedrive ``PIPEDRIVE_API_KEY`` (vault) is the second choice.
- When neither is configured the deal is appended to a local JSON
  store at ``~/.tars/business_deals.json`` (override via
  ``TARS_LOCAL_DEALS_PATH`` or the ``store_path`` arg). The brief
  reader (``daily_brief``) can union this store with the bundled
  sample so logged deals show up the next morning.

``draft_email`` is also a real adapter via SMTP outbound (XOAUTH2 +
refresh flow when configured), with policy gating for actual sends.
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
from .hubspot import pull_pipeline as hubspot_pull_pipeline
from .local_deals import (
    LOCAL_ID_PREFIX,
    append_local_deal,
    resolve_local_deals_path,
)
from .smtp import SmtpConfig, send_email

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
    local_deals_arg = args.get("local_deals_path")
    local_deals_path = resolve_local_deals_path(
        str(local_deals_arg) if local_deals_arg else None
    )
    include_local = bool(args.get("include_local_deals", True))
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

    # Union with the local store written by ``log_deal``.
    # Local rows whose id collides with a bundled row replace the
    # bundled one; brand-new local ids append. This keeps the brief
    # in sync with whatever the operator logged after the bundled
    # snapshot was taken.
    local_deals: list[dict[str, Any]] = []
    if include_local and local_deals_path.exists() and local_deals_path != deals_path:
        try:
            raw_local = _read_json(local_deals_path)
            local_deals = [d for d in raw_local if isinstance(d, dict)]
        except json.JSONDecodeError:
            local_deals = []
    if local_deals:
        by_id: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in deals + local_deals:
            rid = str(row.get("id") or "").strip()
            if not rid:
                rid = f"__anon_{len(order)}"
            if rid not in by_id:
                order.append(rid)
            by_id[rid] = row
        deals = [by_id[rid] for rid in order]

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

    locally_logged_count = sum(
        1
        for d in deals
        if str(d.get("id") or "").startswith(LOCAL_ID_PREFIX)
    )

    sources = ["local-json", "calendar-local"]
    if locally_logged_count > 0:
        sources.append("local-store")
    if deliberation:
        sources.append("council")

    return {
        "ok": True,
        "date": date,
        "summary": headline_summary,
        "deltas": deltas,
        "actions": next_steps,
        "deals_total": len(deals),
        "deals_active": len(deals_active),
        "deals_local_logged": locally_logged_count,
        "local_deals_path": str(local_deals_path),
        "calendar_today": cal_today_payload,
        "sources": sources,
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
    cc = str(args.get("cc", "")).strip() or None

    body_by_tone = {
        "concise": "Quick one — could we sync briefly this week to align?",
        "warm": "Hope you're well! I'd love to grab time to align on next steps.",
        "formal": (
            "I would like to schedule a brief meeting at your convenience "
            "to discuss our next milestones."
        ),
        "blunt": "We need to align this week. What slot works?",
    }
    raw_body = str(args.get("body") or "").strip()
    body = raw_body or body_by_tone.get(tone, body_by_tone["concise"])

    base = {
        "ok": True,
        "to": to,
        "subject": subject,
        "body": body,
        "tone": tone,
        "cc": cc,
    }

    # Caller must opt in: ``send`` is the explicit on-the-wire flag, and
    # the policy gate has already required confirmation by the time we're
    # here (action is destructive=True). Without ``send`` we always
    # return draft-only — same shape as before.
    want_send = bool(args.get("send", False))
    if not want_send:
        return {
            **base,
            "sent": False,
            "delivery": {"status": "draft", "via": "none"},
            "hint": (
                "set send=true to attempt real outbound (requires"
                " policy confirmation + SMTP vault config)."
            ),
        }

    cfg = SmtpConfig.load()
    if cfg is None:
        # Surface as a non-fatal degradation: handler succeeded, we just
        # couldn't reach a relay. The policy token is still consumed.
        return {
            **base,
            "sent": False,
            "delivery": {
                "status": "unavailable",
                "via": "none",
                "reason": "smtp_not_configured",
                "hint": (
                    "set SMTP_HOST + credentials (env or vault) to enable"
                    " real outbound mail."
                ),
            },
        }

    delivery = await send_email(
        to_addr=to,
        subject=subject,
        body=body,
        cc=cc,
        config=cfg,
    )
    sent = bool(delivery.get("sent"))
    return {
        **base,
        "sent": sent,
        "delivery": {
            "status": "sent" if sent else "send_failed",
            **delivery,
        },
    }


async def log_deal(args: Mapping[str, Any]) -> Mapping[str, Any]:
    name = str(args.get("name", "")).strip()
    if not name:
        return {"ok": False, "error": "name_required"}
    try:
        amount_f = float(args.get("amount", 0) or 0)
    except (TypeError, ValueError):
        amount_f = 0.0
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

    store_path_arg = args.get("store_path") or args.get("path")
    target = resolve_local_deals_path(
        str(store_path_arg) if store_path_arg else None
    )
    try:
        record = await append_local_deal(
            name=name,
            amount=amount_f,
            stage=stage,
            owner=str(args.get("owner") or "") or None,
            next_step=str(args.get("next_step") or "") or None,
            due=str(args.get("due") or "") or None,
            notes=str(args.get("notes") or "") or None,
            path=str(store_path_arg) if store_path_arg else None,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": "local_store_unwritable",
            "detail": str(exc),
            "store_path": str(target),
        }

    return {
        "ok": True,
        "deal_id": record.id,
        "name": record.name,
        "amount": record.amount,
        "stage": record.stage,
        "crm": "local",
        "crm_pushed": False,
        "store_path": str(target),
        "deal": record.to_dict(),
        "hint": (
            "deal saved to local JSON store; set HUBSPOT_API_KEY or "
            "PIPEDRIVE_API_KEY to push to a real CRM next time."
        ),
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="daily_brief",
        name="Compose daily brief",
        description=(
            "Compose the morning brief from local KPI + deals + "
            "calendar snapshots, optionally unioned with the local "
            "log_deal store at ~/.tars/business_deals.json (override "
            "via TARS_LOCAL_DEALS_PATH or local_deals_path arg). "
            "Local rows whose id starts with 'local-' are surfaced "
            "in 'deals_local_logged' so the cockpit can highlight "
            "operator-logged deals separately."
        ),
        handler=daily_brief,
        schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "kpi_path": {"type": "string"},
                "deals_path": {"type": "string"},
                "local_deals_path": {
                    "type": "string",
                    "description": (
                        "Override for the local log_deal store. "
                        "Defaults to ~/.tars/business_deals.json or "
                        "TARS_LOCAL_DEALS_PATH."
                    ),
                },
                "include_local_deals": {
                    "type": "boolean",
                    "description": (
                        "Set false to skip the local-store union; "
                        "useful in playbooks that want to look at "
                        "the bundled snapshot alone."
                    ),
                },
                "calendar_path": {"type": "string"},
                "council": {"type": "boolean"},
                "council_mode": {
                    "type": "string",
                    "enum": ["single", "dual_vote", "n_vote"],
                },
            },
        },
    ),
    ActionSpec(
        id="draft_email",
        name="Draft email",
        description=(
            "Draft an outbound email. Always returns the draft body; with"
            " send=true and SMTP configured, also attempts real delivery"
            " (after policy confirmation)."
        ),
        handler=draft_email,
        schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "cc": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "tone": {
                    "type": "string",
                    "enum": ["concise", "warm", "formal", "blunt"],
                },
                "send": {
                    "type": "boolean",
                    "description": (
                        "Opt-in to actual SMTP delivery; requires SMTP_*"
                        " vault config (otherwise returns draft + hint)."
                    ),
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
        description=(
            "Log a deal. Routes to HubSpot if HUBSPOT_API_KEY is set, "
            "Pipedrive if PIPEDRIVE_API_KEY is set, otherwise appends "
            "to the local JSON store at ~/.tars/business_deals.json "
            "(override via TARS_LOCAL_DEALS_PATH or store_path arg). "
            "Emits 'business.deal_logged' on the local-store path so "
            "the cost ledger and audit timeline see the row."
        ),
        handler=log_deal,
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "amount": {"type": "number"},
                "stage": {
                    "type": "string",
                    "enum": [
                        "discovery",
                        "qualification",
                        "proposal",
                        "negotiation",
                        "won",
                        "lost",
                    ],
                },
                "owner": {"type": "string"},
                "next_step": {"type": "string"},
                "due": {"type": "string"},
                "notes": {"type": "string"},
                "store_path": {
                    "type": "string",
                    "description": (
                        "Optional override for the local JSON store. "
                        "Useful for tests / multi-workspace setups."
                    ),
                },
            },
            "required": ["name"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="hubspot_pull_pipeline",
        name="Pull HubSpot pipeline",
        description=(
            "Read-only fetch of deals from HubSpot CRM "
            "(GET /crm/v3/objects/deals). Requires HUBSPOT_API_KEY "
            "in the vault. Supports pagination via 'after' cursor."
        ),
        handler=hubspot_pull_pipeline,
        schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Page size (1..100, default 25).",
                },
                "after": {
                    "type": "string",
                    "description": "Opaque cursor from a previous response.",
                },
                "properties": {
                    "type": ["array", "string"],
                    "description": (
                        "Property keys to request. Pass a list or a "
                        "comma-separated string. Defaults to a sane "
                        "set of HubSpot built-ins."
                    ),
                },
                "pipeline": {
                    "type": "string",
                    "description": (
                        "Optional pipeline id filter (applied "
                        "client-side; the public deals endpoint does "
                        "not accept a server-side pipeline filter)."
                    ),
                },
                "include_raw": {
                    "type": "boolean",
                    "description": (
                        "Attach each deal's raw HubSpot row under "
                        "'raw' for debugging."
                    ),
                },
            },
        },
    ),
)
