"""Action handlers for the traders pack.

``fetch_quote`` is a real adapter against the public DexScreener search
API (no key required). ``summarize_market`` aggregates a basket and asks
the council to interpret it. ``pull_klines`` is a read-only adapter
against Binance's public klines REST endpoint (no key required).
Other actions stay as typed stubs until they get real ground.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec
from ..._http import get_json, NetworkError
from ....council import get_council
from .binance import (
    ALLOWED_INTERVALS as BINANCE_INTERVALS,
    DEFAULT_INTERVAL as BINANCE_DEFAULT_INTERVAL,
    DEFAULT_LIMIT as BINANCE_DEFAULT_LIMIT,
    MAX_LIMIT as BINANCE_MAX_LIMIT,
    pull_klines as binance_pull_klines,
)

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
    # Prefer the highest-liquidity pair that has 24h change populated.
    # Some pairs surface high liquidity but no priceChange — falling back
    # to such a pair makes summarize_market noisy.
    top = next(
        (
            p
            for p in pairs
            if (p.get("priceChange") or {}).get("h24") is not None
        ),
        pairs[0] if pairs else None,
    )

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


DEFAULT_BASKET = ("BTC", "ETH", "SOL", "ARB")


async def summarize_market(args: Mapping[str, Any]) -> Mapping[str, Any]:
    horizon = str(args.get("horizon", "intraday"))
    basket_arg = args.get("basket")
    if isinstance(basket_arg, list) and basket_arg:
        basket = tuple(str(t).strip().upper() for t in basket_arg if t)
    else:
        basket = DEFAULT_BASKET

    quotes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for ticker in basket:
        q = await fetch_quote({"ticker": ticker})
        if q.get("ok") and q.get("price") is not None:
            quotes.append(dict(q))
        else:
            failures.append({"ticker": ticker, "error": q.get("error")})

    if not quotes:
        return {
            "ok": False,
            "error": "no_quotes",
            "horizon": horizon,
            "basket": list(basket),
            "failures": failures,
        }

    changes = [q.get("change_24h") for q in quotes if isinstance(q.get("change_24h"), (int, float))]
    avg_change = round(sum(changes) / len(changes), 3) if changes else None

    by_change = sorted(
        [q for q in quotes if isinstance(q.get("change_24h"), (int, float))],
        key=lambda q: q.get("change_24h", 0),
        reverse=True,
    )
    top_gainers = [
        {"ticker": q["ticker"], "change_24h": q["change_24h"], "price": q["price"]}
        for q in by_change[:2]
    ]
    top_losers = [
        {"ticker": q["ticker"], "change_24h": q["change_24h"], "price": q["price"]}
        for q in by_change[-2:][::-1]
        if q.get("change_24h", 0) < 0
    ]

    if avg_change is None:
        bias = "uncertain"
        verb = "no clear bias"
    elif avg_change > 0.5:
        bias = "risk_on"
        verb = f"basket up {avg_change:+.2f}% on 24h"
    elif avg_change < -0.5:
        bias = "risk_off"
        verb = f"basket down {avg_change:+.2f}% on 24h"
    else:
        bias = "neutral"
        verb = f"basket flat ({avg_change:+.2f}%)"

    signals = [
        {
            "kind": "trend",
            "horizon": horizon,
            "bias": bias,
            "evidence": verb,
        }
    ]

    contradictions: list[dict[str, Any]] = []
    if top_gainers and top_losers:
        contradictions.append(
            {
                "kind": "dispersion",
                "detail": (
                    f"{top_gainers[0]['ticker']} {top_gainers[0]['change_24h']:+.2f}% vs "
                    f"{top_losers[0]['ticker']} {top_losers[0]['change_24h']:+.2f}%"
                ),
            }
        )

    council_context: dict[str, Any] = {
        "topic": "market",
        "horizon": horizon,
        "avg_change_24h": avg_change,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "contradictions": contradictions,
        "basket": list(basket),
    }
    use_council = bool(args.get("council", True))
    deliberation = None
    council_summary = f"{bias.replace('_', '-').upper()} — {verb}."
    if use_council:
        deliberation = await get_council().deliberate(
            "Interpret this basket snapshot for an active trader.",
            council_context,
            mode=str(args.get("council_mode") or "dual_vote"),
        )
        council_summary = deliberation.summary
        # Surface council-recommended actions alongside aggregator signals.
        for act in deliberation.actions_recommended:
            signals.append(
                {
                    "kind": "council_action",
                    "horizon": horizon,
                    "action": act,
                    "evidence": f"voted by {deliberation.chosen}",
                }
            )

    return {
        "ok": True,
        "horizon": horizon,
        "basket": list(basket),
        "summary": council_summary,
        "avg_change_24h": avg_change,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "signals": signals,
        "contradictions": contradictions,
        "quotes": quotes,
        "failures": failures,
        "sources": ["dexscreener"]
        + (["council"] if deliberation else []),
        "council": deliberation.to_dict() if deliberation else None,
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
        destructive=True,
    ),
    ActionSpec(
        id="pull_klines",
        name="Pull klines",
        description=(
            "Fetch OHLCV klines for a symbol from Binance's public REST "
            "API. Read-only, no API key required."
        ),
        handler=binance_pull_klines,
        schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": (
                        "Binance pair symbol, e.g. 'BTCUSDT'. Common "
                        "separators (/, -, _, :, space) are stripped "
                        "automatically."
                    ),
                },
                "interval": {
                    "type": "string",
                    "enum": list(BINANCE_INTERVALS),
                    "default": BINANCE_DEFAULT_INTERVAL,
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": BINANCE_MAX_LIMIT,
                    "default": BINANCE_DEFAULT_LIMIT,
                },
            },
            "required": ["symbol"],
        },
    ),
    ActionSpec(
        id="summarize_market",
        name="Summarize market",
        description="Aggregate live quotes for a basket and surface bias + dispersion.",
        handler=summarize_market,
        schema={
            "type": "object",
            "properties": {
                "horizon": {
                    "type": "string",
                    "enum": ["intraday", "swing", "position"],
                },
                "basket": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 12,
                },
            },
        },
    ),
)
