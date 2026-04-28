from __future__ import annotations

from ...base import AwarenessSource

SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="binance_ws",
        name="Binance WebSocket",
        description="Spot tickers via WebSocket.",
        kind="stream",
        config={
            "url": "wss://stream.binance.com:9443/ws",
            "tickers": ["btcusdt", "ethusdt", "solusdt"],
        },
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
    ),
    AwarenessSource(
        id="portfolio_local",
        name="Local portfolio file",
        description="Read positions from a local JSON file.",
        kind="local",
        config={"path": "~/.tars/portfolio.json"},
    ),
)
