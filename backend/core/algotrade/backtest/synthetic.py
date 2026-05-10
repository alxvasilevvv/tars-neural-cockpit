"""Deterministic OHLCV bar generator for workshop / demo / test use.

Wave M6 (E2E playbook). The W1 backtest harness accepts inline
bars, but workshop attendees usually want to see something
working *immediately*, before they have a CSV file or a
network connection to Binance. This module ships three
preset price regimes and a tiny generator function that
turns them into deterministic ``Bar``-shaped dicts.

Why hand-rolled instead of `random.gauss`:
- Deterministic across Python versions (no `random` state
  drift between 3.10 and 3.13).
- Pure stdlib `math` only — same constraint as the rest of
  the algotrade stack.
- Each preset reproduces a recognisable pattern so the
  facilitator can tell at a glance which regime is which.

Available presets:

- ``trending`` — gentle uptrend, suitable for `ma_cross` and
  `trailing_runner`. Backtests should produce positive Sharpe.
- ``mean_reverting`` — sinusoid around a flat baseline,
  suitable for `bollinger_reversion` and `rsi_oversold`.
- ``choppy`` — high-frequency noise around a slow drift,
  the kind of regime that breaks naïve trend systems.
"""

from __future__ import annotations

import math
from typing import Literal

Regime = Literal["trending", "mean_reverting", "choppy"]


_BASE_TS = 1_700_000_000  # 2023-11-14 22:13:20 UTC — fixed
_BAR_INTERVAL_S = 3600  # 1h bars


def generate_bars(
    *,
    regime: Regime = "trending",
    count: int = 200,
    start_price: float = 100.0,
) -> list[dict[str, float | int]]:
    """Return ``count`` deterministic OHLCV dicts for ``regime``.

    Same arguments → byte-identical output every time. Safe to
    cache, hash, replay. Each bar follows the
    ``{ts, open, high, low, close, volume}`` shape the
    backtest harness expects.
    """

    if count <= 0:
        return []
    if start_price <= 0:
        raise ValueError(f"start_price must be > 0, got {start_price}")
    if regime not in ("trending", "mean_reverting", "choppy"):
        raise ValueError(
            f"unknown regime {regime!r} — pick one of "
            "'trending' | 'mean_reverting' | 'choppy'"
        )

    bars: list[dict[str, float | int]] = []
    px = start_price
    for i in range(count):
        if regime == "trending":
            # Linear drift + sine + tiny deterministic wobble
            px = (
                start_price
                + 0.05 * i
                + 6.0 * math.sin(i / 18.0)
                + 0.4 * math.sin(i * 1.7)
            )
        elif regime == "mean_reverting":
            # Pure sinusoid around start_price, no drift
            px = (
                start_price
                + 8.0 * math.sin(i / 12.0)
                + 0.5 * math.sin(i * 0.9 + 1.7)
            )
        else:
            # Choppy: small drift + high-frequency noise
            px = (
                start_price
                + 0.02 * i
                + 1.5 * math.sin(i / 4.0)
                + 0.8 * math.sin(i * 2.3)
                + 0.6 * math.sin(i * 5.1 + 0.7)
            )

        # Build the OHLC band around the close. Deterministic —
        # use close + math-shaped offsets, never random.
        wick_high = abs(0.5 * math.sin(i * 1.3) + 0.3)
        wick_low = abs(0.5 * math.cos(i * 1.7) + 0.3)
        body_open = px - 0.4 * math.sin(i * 0.7)

        o = body_open
        h = max(o, px) + wick_high
        lo = min(o, px) - wick_low
        c = px
        bars.append(
            {
                "ts": _BASE_TS + i * _BAR_INTERVAL_S,
                "open": round(o, 4),
                "high": round(h, 4),
                "low": round(lo, 4),
                "close": round(c, 4),
                "volume": 1000.0 + 5.0 * (i % 7),
            }
        )
    return bars
