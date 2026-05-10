"""Backtest performance metrics — stdlib only.

We compute the canon a quant looks at first:

- ``total_return`` — final / initial - 1.
- ``cagr`` — annualised, derived from elapsed seconds in equity curve.
- ``sharpe`` / ``sortino`` — annualised; risk-free assumed 0 for the
  workshop (operators can plug a benchmark later).
- ``max_drawdown`` — largest peak-to-trough on the equity curve.
- ``win_rate`` / ``loss_rate`` — by trade count.
- ``profit_factor`` — gross gains / gross losses.
- ``expectancy`` — average PnL per trade.
- ``trades`` — count of closed trades.
- ``avg_trade_pct`` — mean ``pnl_pct`` per trade.
- ``exposure`` — fraction of bars holding a position.

Numbers are returned as plain floats (``-Infinity`` / ``NaN`` are
clamped to ``0.0`` so JSON serialisers don't trip).
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from .harness import Trade


SECONDS_PER_YEAR = 365 * 24 * 60 * 60


def compute_metrics(
    *,
    equity_curve: Sequence[tuple[int, float]],
    trades: Sequence[Trade],
    initial_equity: float,
) -> dict[str, float]:
    if not equity_curve:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "trades": 0.0,
            "avg_trade_pct": 0.0,
            "exposure": 0.0,
        }
    final_equity = equity_curve[-1][1]
    total_return = (
        (final_equity - initial_equity) / initial_equity
        if initial_equity > 0
        else 0.0
    )

    # Annualised return
    duration = max(equity_curve[-1][0] - equity_curve[0][0], 1)
    years = duration / SECONDS_PER_YEAR
    if years > 0 and final_equity > 0 and initial_equity > 0:
        cagr = (final_equity / initial_equity) ** (1.0 / max(years, 1e-9)) - 1.0
    else:
        cagr = 0.0

    # Period returns from the equity curve
    rets: list[float] = []
    prev_eq = equity_curve[0][1]
    for _, eq in equity_curve[1:]:
        if prev_eq > 0:
            rets.append((eq - prev_eq) / prev_eq)
        prev_eq = eq

    sharpe = _annualised_sharpe(rets, equity_curve)
    sortino = _annualised_sortino(rets, equity_curve)
    max_drawdown = _max_drawdown(equity_curve)

    # Trade stats — only closed trades count
    closed = [t for t in trades if t.exit_ts is not None]
    n = len(closed)
    wins = [t.pnl() for t in closed if t.pnl() > 0]
    losses = [t.pnl() for t in closed if t.pnl() < 0]
    win_rate = (len(wins) / n) if n else 0.0
    loss_rate = (len(losses) / n) if n else 0.0
    gross_gain = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_gain / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_gain > 0 else 0.0
    )
    expectancy = (sum(t.pnl() for t in closed) / n) if n else 0.0
    avg_pct = (sum(t.pnl_pct() for t in closed) / n) if n else 0.0

    # Exposure: fraction of curve points where a trade was open
    holding_bars = _count_holding_bars(equity_curve, trades)
    exposure = holding_bars / max(len(equity_curve), 1)

    return {
        "total_return": _safe(total_return),
        "cagr": _safe(cagr),
        "sharpe": _safe(sharpe),
        "sortino": _safe(sortino),
        "max_drawdown": _safe(max_drawdown),
        "win_rate": float(win_rate),
        "loss_rate": float(loss_rate),
        "profit_factor": _safe(profit_factor),
        "expectancy": _safe(expectancy),
        "trades": float(n),
        "avg_trade_pct": _safe(avg_pct),
        "exposure": float(exposure),
    }


def _safe(v: float) -> float:
    if v is None or math.isnan(v) or math.isinf(v):
        return 0.0
    return float(v)


def _max_drawdown(equity_curve: Sequence[tuple[int, float]]) -> float:
    peak = equity_curve[0][1]
    max_dd = 0.0
    for _, eq in equity_curve:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _annualised_sharpe(
    rets: Iterable[float], equity_curve: Sequence[tuple[int, float]]
) -> float:
    rets_list = list(rets)
    if len(rets_list) < 2:
        return 0.0
    mean = sum(rets_list) / len(rets_list)
    var = sum((r - mean) ** 2 for r in rets_list) / len(rets_list)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    bars_per_year = _bars_per_year(equity_curve)
    return (mean / sd) * math.sqrt(bars_per_year)


def _annualised_sortino(
    rets: Iterable[float], equity_curve: Sequence[tuple[int, float]]
) -> float:
    rets_list = list(rets)
    if len(rets_list) < 2:
        return 0.0
    mean = sum(rets_list) / len(rets_list)
    downside = [min(r, 0.0) for r in rets_list]
    dvar = sum(d * d for d in downside) / len(rets_list)
    dsd = math.sqrt(dvar)
    if dsd == 0:
        return 0.0
    bars_per_year = _bars_per_year(equity_curve)
    return (mean / dsd) * math.sqrt(bars_per_year)


def _bars_per_year(equity_curve: Sequence[tuple[int, float]]) -> float:
    if len(equity_curve) < 2:
        return 1.0
    span = equity_curve[-1][0] - equity_curve[0][0]
    if span <= 0:
        return 1.0
    avg_bar_seconds = span / max(len(equity_curve) - 1, 1)
    return SECONDS_PER_YEAR / avg_bar_seconds


def _count_holding_bars(
    equity_curve: Sequence[tuple[int, float]], trades: Sequence[Trade]
) -> int:
    if not equity_curve or not trades:
        return 0
    intervals = [
        (t.entry_ts, t.exit_ts if t.exit_ts is not None else equity_curve[-1][0])
        for t in trades
    ]
    held = 0
    for ts, _ in equity_curve:
        for start, end in intervals:
            if start <= ts <= end:
                held += 1
                break
    return held
