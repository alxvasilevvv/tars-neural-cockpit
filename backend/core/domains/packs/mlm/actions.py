from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec


async def downline_snapshot(args: Mapping[str, Any]) -> Mapping[str, Any]:
    depth = int(args.get("depth", 5) or 5)
    return {
        "ok": True,
        "depth": depth,
        "active": 0,
        "dormant": 0,
        "ranks": {},
    }


async def score_recruit(args: Mapping[str, Any]) -> Mapping[str, Any]:
    handle = str(args.get("handle", "")).strip()
    if not handle:
        return {"ok": False, "error": "handle_required"}
    return {
        "ok": True,
        "handle": handle,
        "score": 0.0,
        "fit_signals": [],
        "risk_signals": [],
    }


async def generate_post(args: Mapping[str, Any]) -> Mapping[str, Any]:
    channel = str(args.get("channel", "ig")).lower()
    if channel not in {"ig", "tg", "wa"}:
        return {"ok": False, "error": "unsupported_channel", "channel": channel}
    return {
        "ok": True,
        "channel": channel,
        "format": str(args.get("format", "post")),
        "draft": "Content draft stub. Council will replace.",
        "hashtags": [],
    }


async def retention_alert(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "at_risk": [],
        "checked_at": None,
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="downline_snapshot",
        name="Downline snapshot",
        description="Snapshot of network depth, activity and ranks.",
        handler=downline_snapshot,
        schema={
            "type": "object",
            "properties": {"depth": {"type": "integer", "minimum": 1, "maximum": 12}},
        },
    ),
    ActionSpec(
        id="score_recruit",
        name="Score recruit",
        description="Score the fit of a candidate by public profile signals.",
        handler=score_recruit,
        schema={
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
    ),
    ActionSpec(
        id="generate_post",
        name="Generate post",
        description="Draft a channel-appropriate piece of content.",
        handler=generate_post,
        schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["ig", "tg", "wa"]},
                "format": {
                    "type": "string",
                    "enum": ["story", "post", "reel", "dm"],
                },
                "topic": {"type": "string"},
            },
            "required": ["channel"],
        },
    ),
    ActionSpec(
        id="retention_alert",
        name="Retention alert",
        description="Find members going quiet and explain why.",
        handler=retention_alert,
        schema={"type": "object", "properties": {}},
    ),
)
