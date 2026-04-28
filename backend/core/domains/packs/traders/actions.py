"""Action handlers for the traders pack.

All handlers are stubs that return well-typed responses but do not perform
network I/O yet. Real implementations will plug into exchange adapters and
the policy engine.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec


async def fetch_quote(args: Mapping[str, Any]) -> Mapping[str, Any]:
    ticker = str(args.get("ticker", "")).upper().strip()
    if not ticker:
        return {"ok": False, "error": "ticker_required"}
    return {
        "ok": True,
        "ticker": ticker,
        "price": None,
        "ts": None,
        "source": "stub",
    }


async def place_alert(args: Mapping[str, Any]) -> Mapping[str, Any]:
    required = {"ticker", "price", "direction"}
    missing = sorted(k for k in required if k not in args)
    if missing:
        return {"ok": False, "error": "missing_args", "missing": missing}
    return {
        "ok": True,
        "alert_id": "stub-0001",
        "ticker": str(args["ticker"]).upper(),
        "price": float(args["price"]),
        "direction": str(args["direction"]),
    }


async def summarize_market(args: Mapping[str, Any]) -> Mapping[str, Any]:
    horizon = str(args.get("horizon", "intraday"))
    return {
        "ok": True,
        "horizon": horizon,
        "summary": "Market summary stub. Replace with council output.",
        "signals": [],
        "contradictions": [],
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="fetch_quote",
        name="Fetch quote",
        description="Latest quote for a ticker.",
        handler=fetch_quote,
        schema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
    ActionSpec(
        id="place_alert",
        name="Place price alert",
        description="Create a price alert in the local policy engine.",
        handler=place_alert,
        schema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "price": {"type": "number"},
                "direction": {"type": "string", "enum": ["above", "below"]},
            },
            "required": ["ticker", "price", "direction"],
        },
    ),
    ActionSpec(
        id="summarize_market",
        name="Summarize market",
        description="Synthesize a market summary using the council.",
        handler=summarize_market,
        schema={
            "type": "object",
            "properties": {
                "horizon": {
                    "type": "string",
                    "enum": ["intraday", "swing", "position"],
                }
            },
        },
    ),
)
