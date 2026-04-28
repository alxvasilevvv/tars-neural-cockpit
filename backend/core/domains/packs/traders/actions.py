"""Action handlers for the traders pack.

``fetch_quote`` is a real adapter against the public DexScreener search
API (no key required). Other actions stay as typed stubs until they get
real ground.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec
from ..._http import get_json, NetworkError

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"


async def fetch_quote(args: Mapping[str, Any]) -> Mapping[str, Any]:
    ticker = str(args.get("ticker", "")).strip()
    if not ticker:
        return {"ok": False, "error": "ticker_required"}

    try:
        status, payload = await get_json(
            DEXSCREENER_SEARCH, params={"q": ticker}, timeout=6.0
        )
    except NetworkError as e:
        return {
            "ok": False,
            "error": "network_error",
            "hint": "dexscreener unreachable",
            "detail": str(e),
            "ticker": ticker,
        }

    if status != 200 or not isinstance(payload, dict):
        return {
            "ok": False,
            "error": "upstream_status",
            "status": status,
            "ticker": ticker,
        }

    pairs = payload.get("pairs") or []
    pairs = [p for p in pairs if isinstance(p, dict)]
    pairs.sort(
        key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0.0),
        reverse=True,
    )
    top = pairs[0] if pairs else None

    if not top:
        return {
            "ok": True,
            "ticker": ticker.upper(),
            "price": None,
            "source": "dexscreener",
            "matches": 0,
            "pairs": [],
        }

    base = top.get("baseToken") or {}
    quote = top.get("quoteToken") or {}
    return {
        "ok": True,
        "ticker": ticker.upper(),
        "price": _to_float(top.get("priceUsd")),
        "price_native": _to_float(top.get("priceNative")),
        "change_24h": _to_float(((top.get("priceChange") or {}).get("h24"))),
        "volume_24h": _to_float(((top.get("volume") or {}).get("h24"))),
        "liquidity_usd": _to_float(((top.get("liquidity") or {}).get("usd"))),
        "pair": f"{base.get('symbol', '?')}/{quote.get('symbol', '?')}",
        "chain": top.get("chainId"),
        "dex": top.get("dexId"),
        "url": top.get("url"),
        "source": "dexscreener",
        "matches": len(pairs),
    }


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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
        description="Live token quote via DexScreener public search.",
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
