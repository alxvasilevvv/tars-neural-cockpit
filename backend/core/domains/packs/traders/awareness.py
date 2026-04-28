"""Traders pack awareness sources with live fetchers.

- ``binance_ws`` → polls DexScreener for the configured tickers (we don't
  hold a websocket here; a single poll snapshot is enough for the council
  to reason about the basket).
- ``news_feed`` and ``portfolio_local`` are JSON-backed locally; the same
  shape will graduate to live RSS / Keychain-vaulted file paths.
- ``tradingview_alerts`` is webhook-only (no fetcher).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...base import AwarenessSource
from .actions import fetch_quote

_REPO_ROOT = Path(__file__).resolve().parents[5]
_NEWS_PATH = _REPO_ROOT / "data" / "traders_news.json"
_PORTFOLIO_PATH = _REPO_ROOT / "data" / "traders_portfolio.json"


def _read_json_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return None


def _resolve_path(arg_path: str, env_var: str, default: Path) -> Path:
    """Resolve a path with the priority env var > arg > default.

    Awareness source configs sometimes point at a future location
    (e.g. ``~/.tars/portfolio.json``) while the live data lives at
    ``data/`` for now. If the arg-provided path doesn't exist *and*
    no env override is set, fall through to the default sample.
    """

    env = os.getenv(env_var)
    if env:
        return Path(env).expanduser()
    if arg_path:
        candidate = Path(arg_path).expanduser()
        if candidate.exists():
            return candidate
    return default


async def _fetch_binance_ws(args: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_tickers = args.get("tickers")
    if isinstance(raw_tickers, list) and raw_tickers:
        tickers = [str(t).strip().upper() for t in raw_tickers if t]
    else:
        tickers = ["BTC", "ETH", "SOL"]

    quotes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for t in tickers:
        q = await fetch_quote({"ticker": t})
        if q.get("ok"):
            quotes.append(dict(q))
        else:
            failures.append({"ticker": t, "error": q.get("error")})

    return {
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers,
        "quotes": quotes,
        "failures": failures,
        "source": "dexscreener",
        "hint": "binance ws not connected; using dexscreener poll snapshot",
    }


async def _fetch_news_feed(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = _resolve_path(
        str(args.get("path") or ""), "TRADERS_NEWS_PATH", _NEWS_PATH
    )
    data = _read_json_or_none(path)
    if data is None:
        return {"ok": False, "error": "news_unavailable", "path": str(path)}
    items = data.get("items") or []
    by_tone: dict[str, int] = {}
    for it in items:
        by_tone[str(it.get("tone", "neutral"))] = (
            by_tone.get(str(it.get("tone", "neutral")), 0) + 1
        )
    return {
        "ok": True,
        "as_of": data.get("as_of"),
        "count": len(items),
        "by_tone": by_tone,
        "items": items,
        "path": str(path),
    }


async def _fetch_portfolio(args: Mapping[str, Any]) -> Mapping[str, Any]:
    path = _resolve_path(
        str(args.get("path") or ""), "TRADERS_PORTFOLIO_PATH", _PORTFOLIO_PATH
    )
    data = _read_json_or_none(path)
    if data is None:
        return {"ok": False, "error": "portfolio_unavailable", "path": str(path)}

    positions = data.get("positions") or []
    cash = float(data.get("cash_usd") or 0)

    enriched: list[dict[str, Any]] = []
    nav = cash
    for p in positions:
        if not isinstance(p, dict):
            continue
        ticker = str(p.get("ticker", "?")).upper()
        try:
            qty = float(p.get("qty") or 0)
            entry = float(p.get("entry") or 0)
        except (TypeError, ValueError):
            qty, entry = 0.0, 0.0
        q = await fetch_quote({"ticker": ticker})
        price = q.get("price") if isinstance(q, Mapping) and q.get("ok") else None
        if isinstance(price, (int, float)):
            mv = qty * price
            unrealised = mv - qty * entry
        else:
            mv = None
            unrealised = None
        if isinstance(mv, (int, float)):
            nav += mv
        enriched.append(
            {
                "ticker": ticker,
                "qty": qty,
                "entry": entry,
                "price": price,
                "market_value_usd": mv,
                "unrealised_usd": unrealised,
                "tags": list(p.get("tags") or []),
            }
        )
    return {
        "ok": True,
        "as_of": data.get("as_of"),
        "currency": data.get("currency") or "USD",
        "positions": enriched,
        "cash_usd": round(cash, 2),
        "nav_usd": round(nav, 2) if isinstance(nav, (int, float)) else None,
        "path": str(path),
    }


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="binance_ws",
        name="Binance WebSocket",
        description="Spot tickers via WebSocket (currently DexScreener poll fallback).",
        kind="stream",
        config={
            "url": "wss://stream.binance.com:9443/ws",
            "tickers": ["btcusdt", "ethusdt", "solusdt"],
        },
        fetcher=_fetch_binance_ws,
    ),
    AwarenessSource(
        id="tradingview_alerts",
        name="TradingView alerts",
        description="Inbound webhooks from TradingView strategies.",
        kind="webhook",
        config={"path": "/api/domains/traders/webhooks/tradingview"},
    ),
    AwarenessSource(
        id="news_feed",
        name="Finance news feed",
        description="Aggregated finance news (poll).",
        kind="poll",
        config={
            "interval_s": 120,
            "sources": ["coindesk", "ft", "bloomberg-rss"],
        },
        fetcher=_fetch_news_feed,
    ),
    AwarenessSource(
        id="portfolio_local",
        name="Local portfolio file",
        description="Read positions from a local JSON file (NAV-enriched).",
        kind="local",
        config={"path": "~/.tars/portfolio.json"},
        fetcher=_fetch_portfolio,
    ),
)
