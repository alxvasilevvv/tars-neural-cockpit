from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec


async def daily_brief(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "date": str(args.get("date", "")),
        "summary": "Daily brief stub. Replace with council output.",
        "deltas": [],
        "actions": [],
    }


async def draft_email(args: Mapping[str, Any]) -> Mapping[str, Any]:
    to = str(args.get("to", "")).strip()
    if not to:
        return {"ok": False, "error": "to_required"}
    return {
        "ok": True,
        "to": to,
        "subject": str(args.get("subject", "")),
        "body": "Draft email stub. Council will replace.",
        "tone": str(args.get("tone", "concise")),
    }


async def kpi_snapshot(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "metrics": {},
        "as_of": None,
        "sources": [],
    }


async def log_deal(args: Mapping[str, Any]) -> Mapping[str, Any]:
    name = str(args.get("name", "")).strip()
    if not name:
        return {"ok": False, "error": "name_required"}
    return {
        "ok": True,
        "deal_id": "stub-deal-0001",
        "name": name,
        "amount": float(args.get("amount", 0) or 0),
        "stage": str(args.get("stage", "discovery")),
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="daily_brief",
        name="Compose daily brief",
        description="Compose the morning brief from awareness sources.",
        handler=daily_brief,
        schema={
            "type": "object",
            "properties": {"date": {"type": "string", "format": "date"}},
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
    ),
    ActionSpec(
        id="kpi_snapshot",
        name="KPI snapshot",
        description="Snapshot KPI metrics from registered awareness sources.",
        handler=kpi_snapshot,
        schema={"type": "object", "properties": {}},
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
    ),
)
