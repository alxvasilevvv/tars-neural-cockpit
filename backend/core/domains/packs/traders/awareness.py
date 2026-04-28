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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree as ET

from ...base import AwarenessSource
from ..._http import NetworkError, get_text
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


_BAD_TONE = re.compile(
    r"\b(bear|crash|selloff|hack|regulat|war|inflation|panic)\b",
    re.I,
)
_GOOD_TONE = re.compile(r"\b(rally|surge|record|etf|adopt|etf inflow)\b", re.I)


def _tone_from_text(title: str, summary: str) -> str:
    blob = f"{title} {summary}"
    if _BAD_TONE.search(blob):
        return "bearish"
    if _GOOD_TONE.search(blob):
        return "bullish"
    return "neutral"


def _parse_rss_atom(xml: str, limit: int = 40) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom-ish XML into a lightweight item list."""

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []

    items: list[dict[str, Any]] = []
    local = root.tag.split("}")[-1]

    if local == "rss":
        channel = root.find("channel")
        if channel is None:
            return []
        for it in channel.findall("item")[:limit]:
            title_el = it.find("title")
            link_el = it.find("link")
            pub_el = it.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            href = ""
            if link_el is not None:
                txt = getattr(link_el, "text", None)
                href = (txt or "").strip() if txt else ""
            if not href:
                # RSS link can live in child's href attr in some feeds
                l2 = it.find("{http://www.w3.org/2005/Atom}link")
                if l2 is not None and l2.attrib.get("href"):
                    href = l2.attrib["href"]
            pub = (pub_el.text or "").strip() if pub_el is not None else ""
            items.append({"title": title, "href": href, "pub": pub, "tone": ""})
    else:
        # Atom feed
        atom_ns = "http://www.w3.org/2005/Atom"
        entries = root.findall(f"{{{atom_ns}}}entry")
        for entry in entries[:limit]:
            title_el = entry.find(f"{{{atom_ns}}}title")
            link_el = None
            for link in entry.findall(f"{{{atom_ns}}}link"):
                if link.attrib.get("rel") in (None, "alternate"):
                    link_el = link
                    break
            if link_el is None:
                link_el = entry.find(f"{{{atom_ns}}}link")
            updated = entry.find(f"{{{atom_ns}}}updated") or entry.find(
                f"{{{atom_ns}}}published"
            )
            title = (title_el.text or "").strip() if title_el is not None else ""
            href = (link_el.attrib.get("href") or "").strip() if link_el is not None else ""
            pub = (updated.text or "").strip() if updated is not None else ""
            items.append({"title": title, "href": href, "pub": pub, "tone": ""})

    for it in items:
        it["tone"] = _tone_from_text(it.get("title") or "", "")
    return items


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
    rss_env = os.getenv("TRADERS_NEWS_RSS_URL", "").strip()
    rss_url = str(args.get("rss_url") or "").strip() or rss_env
    if rss_url:
        try:
            status, body = await get_text(rss_url, timeout=10.0)
        except NetworkError:
            status, body = 0, ""
        if status == 200 and body:
            raw_items = _parse_rss_atom(body)
            if raw_items:
                items = []
                by_tone: dict[str, int] = {}
                for it in raw_items:
                    tone = it.get("tone") or "neutral"
                    by_tone[str(tone)] = by_tone.get(str(tone), 0) + 1
                    items.append(
                        {
                            "title": it.get("title"),
                            "href": it.get("href"),
                            "pub": it.get("pub"),
                            "tone": tone,
                        }
                    )
                return {
                    "ok": True,
                    "source": "rss",
                    "as_of": datetime.now(timezone.utc).isoformat(),
                    "rss_url": rss_url,
                    "count": len(items),
                    "by_tone": by_tone,
                    "items": items,
                }

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
        "source": "json",
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
