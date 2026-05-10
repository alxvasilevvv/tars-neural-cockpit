"""Backtest engine — stdlib-only event loop.

Submodules:

- :mod:`indicators` — incremental SMA / EMA / RSI / Bollinger / ATR.
- :mod:`harness` — bar-by-bar event loop that consumes :class:`Strategy`
  IR + an OHLCV iterable and emits :class:`BacktestResult`.
- :mod:`metrics` — Sharpe, Sortino, max drawdown, win rate, profit
  factor, exposure, CAGR.
- :mod:`data` — OHLCV fetchers (Binance via the existing traders
  pack adapter, plus a CSV loader).

The whole module is opt-in numpy-free. The reference loop is plain
Python iteration so workshop attendees can read every line in the
call stack and trust what it does.
"""

from .harness import (
    BacktestConfig,
    BacktestError,
    BacktestResult,
    Bar,
    Trade,
    run_backtest,
)
from .indicators import (
    INDICATORS,
    Bollinger,
    EMA,
    Indicator as RuntimeIndicator,
    RSI,
    SMA,
    eval_node,
)
from .metrics import compute_metrics

__all__ = [
    "BacktestConfig",
    "BacktestError",
    "BacktestResult",
    "Bar",
    "Bollinger",
    "EMA",
    "INDICATORS",
    "RSI",
    "RuntimeIndicator",
    "SMA",
    "Trade",
    "compute_metrics",
    "eval_node",
    "run_backtest",
]
