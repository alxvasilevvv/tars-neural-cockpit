"""OHLCV data sources.

v1 ships two:

- ``load_csv(path)`` — read a CSV with header row
  ``ts,open,high,low,close,volume``. The workshop ships sample
  files under ``backend/core/algotrade/recipes/data/``.
- ``load_binance_klines(symbol, interval, limit)`` — pulls from
  Binance's public spot endpoint; reuses the existing traders pack
  HTTP machinery. Network call, may be slow; caching is the
  caller's responsibility.

Both return ``list[Bar]`` so the harness can iterate cheaply. We
deliberately don't expose a streaming API yet — when paper trading
lands in W2 it will live in a sister module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .harness import Bar


class DataError(RuntimeError):
    """Raised when a data source can't produce a clean bar list."""


# --------------------------------------------------------- CSV


REQUIRED_COLS = ("ts", "open", "high", "low", "close", "volume")


def load_csv(path: str | Path) -> list[Bar]:
    """Load a CSV file into a list of :class:`Bar`."""
    p = Path(path)
    if not p.exists():
        raise DataError(f"csv not found: {p}")
    out: list[Bar] = []
    with p.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not set(REQUIRED_COLS) <= set(reader.fieldnames):
            raise DataError(
                f"csv must have columns {REQUIRED_COLS}, got "
                f"{reader.fieldnames}"
            )
        for i, row in enumerate(reader, start=1):
            try:
                out.append(
                    Bar(
                        ts=int(float(row["ts"])),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
            except (ValueError, KeyError) as exc:
                raise DataError(f"csv row {i} malformed: {exc}") from exc
    return out


# --------------------------------------------------------- Binance klines


# We piggy-back on the traders pack's HTTP layer to avoid a second
# dependency on httpx here. Local import to keep the algotrade
# module importable in environments without the traders pack.
async def load_binance_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
) -> list[Bar]:
    """Fetch the most recent ``limit`` klines from Binance spot.

    ``symbol`` example: ``BTCUSDT``. ``interval`` follows Binance
    notation (``1m`` / ``5m`` / ``15m`` / ``1h`` / ``4h`` / ``1d``).
    """

    from backend.core.domains._http import NetworkError, get_text

    if not symbol:
        raise DataError("symbol required")
    limit = max(1, min(int(limit), 1000))
    try:
        status, body = await get_text(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
            timeout=10.0,
        )
    except NetworkError as exc:
        raise DataError(f"binance unreachable: {exc}") from exc
    if status != 200:
        raise DataError(f"binance returned status {status}: {body[:200]}")
    try:
        rows = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DataError(f"binance returned non-JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise DataError("binance returned non-list payload")
    out: list[Bar] = []
    for row in rows:
        # Binance kline layout: open_time, open, high, low, close, volume,
        # close_time, quote_asset_volume, num_trades, taker_buy_base,
        # taker_buy_quote, ignore.
        try:
            close_time_ms = int(row[6])
            out.append(
                Bar(
                    ts=close_time_ms // 1000,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        except (IndexError, ValueError, TypeError) as exc:
            raise DataError(f"binance row malformed: {exc}") from exc
    return out


def chunked_bars(bars: Iterable[Bar], chunk: int) -> list[list[Bar]]:
    """Slice a bar iterable into evenly-sized chunks. Used by the
    workshop multi-pass benchmark cell."""
    out: list[list[Bar]] = []
    cur: list[Bar] = []
    for b in bars:
        cur.append(b)
        if len(cur) >= chunk:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out
