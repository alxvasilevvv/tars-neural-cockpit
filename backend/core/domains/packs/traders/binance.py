"""Binance public klines adapter (no key required).

Backs the ``traders.pull_klines`` action with a deterministic
read-only call to ``api.binance.com/api/v3/klines``. Returns a
normalised time-series shape so downstream actions / playbooks
can reason about OHLCV without re-parsing the raw array Binance
returns.

Reference: https://developers.binance.com/docs/binance-spot-api-docs/rest-api#klinecandlestick-data

The adapter is **stdlib-only** (uses :mod:`backend.core.domains._http`)
so it runs in any environment, with conservative timeouts. We
emit an ``integration.binance.klines`` event via the meeet
client per the IDEAS.md guideline so the cost ledger / observability
layer sees real-adapter calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..._http import NetworkError, get_json
from ....meeet import get_client


log = logging.getLogger("tars.traders.binance")


KLINES_URL = "https://api.binance.com/api/v3/klines"

ALLOWED_INTERVALS: tuple[str, ...] = (
    "1s", "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
)
DEFAULT_INTERVAL = "1h"
DEFAULT_LIMIT = 24
MAX_LIMIT = 1000  # Binance hard cap


@dataclass(frozen=True)
class Kline:
    """One candle row, normalised."""

    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_time_ms": self.open_time_ms,
            "close_time_ms": self.close_time_ms,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trades": self.trades,
        }


@dataclass(frozen=True)
class KlinesResult:
    ok: bool
    symbol: str
    interval: str
    candles: tuple[Kline, ...] = field(default_factory=tuple)
    error: str | None = None
    detail: str | None = None
    status: int | None = None
    source: str = "binance"

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ok": self.ok,
            "symbol": self.symbol,
            "interval": self.interval,
            "source": self.source,
            "count": len(self.candles),
            "candles": [c.to_dict() for c in self.candles],
        }
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        if self.status is not None:
            body["status"] = self.status
        if self.candles:
            close_first = self.candles[0].close
            close_last = self.candles[-1].close
            body["close_first"] = close_first
            body["close_last"] = close_last
            body["change_pct"] = (
                round(((close_last - close_first) / close_first) * 100.0, 4)
                if close_first
                else 0.0
            )
        return body


def _normalise_symbol(raw: Any) -> str | None:
    """Binance accepts plain symbols like ``BTCUSDT``; we strip
    common separators (``BTC/USDT``, ``BTC-USDT``, ``btc:usdt``)
    and uppercase. Return None for empty / non-string inputs.
    """

    if not isinstance(raw, str):
        return None
    s = raw.strip().upper()
    if not s:
        return None
    for sep in ("/", "-", ":", "_", " "):
        s = s.replace(sep, "")
    return s or None


def _parse_kline_row(row: Any) -> Kline | None:
    """Binance returns each kline as a list of 12 values. Be
    defensive about types — some upstream caches return numbers
    as strings."""

    if not isinstance(row, list) or len(row) < 9:
        return None
    try:
        return Kline(
            open_time_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time_ms=int(row[6]),
            quote_volume=float(row[7]),
            trades=int(row[8]),
        )
    except (TypeError, ValueError):
        return None


async def pull_klines(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Action handler: fetch klines for ``symbol`` / ``interval``.

    Args
    ----
    symbol : str (required)  e.g. ``"BTCUSDT"`` or ``"BTC/USDT"``.
    interval : str (default ``1h``) — must be in
        :data:`ALLOWED_INTERVALS`.
    limit : int (default 24, max 1000).

    Returns the :class:`KlinesResult` as a plain dict so the
    handler matches the action contract (``ok``, etc.).
    """

    raw_symbol = args.get("symbol") or args.get("ticker")
    symbol = _normalise_symbol(raw_symbol)
    if symbol is None:
        return KlinesResult(
            ok=False,
            symbol="",
            interval="",
            error="symbol_required",
        ).to_dict()

    interval = str(args.get("interval") or DEFAULT_INTERVAL).strip()
    if interval not in ALLOWED_INTERVALS:
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="invalid_interval",
            detail=(
                "interval must be one of "
                f"{list(ALLOWED_INTERVALS)}"
            ),
        ).to_dict()

    raw_limit = args.get("limit", DEFAULT_LIMIT)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="invalid_limit",
            detail=f"limit must be a positive int, got {raw_limit!r}",
        ).to_dict()
    if limit < 1 or limit > MAX_LIMIT:
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="invalid_limit",
            detail=f"limit must be 1..{MAX_LIMIT}, got {limit}",
        ).to_dict()

    params: dict[str, Any] = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    client = get_client()
    await client.emit(
        "integration.binance.klines",
        {
            "phase": "request",
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
    )

    try:
        status, payload = await get_json(KLINES_URL, params=params, timeout=6.0)
    except NetworkError as exc:
        await client.emit(
            "integration.binance.klines",
            {
                "phase": "error",
                "symbol": symbol,
                "interval": interval,
                "error": "network_error",
                "detail": str(exc),
            },
        )
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="network_error",
            detail=str(exc),
        ).to_dict()

    if status != 200:
        await client.emit(
            "integration.binance.klines",
            {
                "phase": "error",
                "symbol": symbol,
                "interval": interval,
                "error": "upstream_status",
                "status": status,
            },
        )
        # Binance returns {"code": -1121, "msg": "Invalid symbol"} on bad input.
        detail = None
        if isinstance(payload, dict):
            detail = str(payload.get("msg") or "")
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="upstream_status",
            status=status,
            detail=detail or None,
        ).to_dict()

    if not isinstance(payload, list):
        return KlinesResult(
            ok=False,
            symbol=symbol,
            interval=interval,
            error="upstream_payload_invalid",
            detail="expected JSON array of klines",
        ).to_dict()

    candles: list[Kline] = []
    for row in payload:
        parsed = _parse_kline_row(row)
        if parsed is not None:
            candles.append(parsed)
    if not candles:
        return KlinesResult(
            ok=True,
            symbol=symbol,
            interval=interval,
            candles=(),
        ).to_dict()

    await client.emit(
        "integration.binance.klines",
        {
            "phase": "completed",
            "symbol": symbol,
            "interval": interval,
            "count": len(candles),
        },
    )
    return KlinesResult(
        ok=True,
        symbol=symbol,
        interval=interval,
        candles=tuple(candles),
    ).to_dict()


__all__ = [
    "ALLOWED_INTERVALS",
    "DEFAULT_INTERVAL",
    "DEFAULT_LIMIT",
    "KLINES_URL",
    "Kline",
    "KlinesResult",
    "MAX_LIMIT",
    "pull_klines",
]
