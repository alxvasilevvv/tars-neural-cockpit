"""Backtest event loop.

Reads OHLCV bars sequentially, evaluates the strategy IR against
incremental indicator state, opens / closes positions, and tracks
equity. Designed for honesty over speed:

- **No look-ahead.** The condition for bar *t* is evaluated on
  indicators built strictly from bars up to and including *t*'s
  close. Entries/exits triggered by bar *t* fill at *t+1* open.
- **Realistic costs.** Per-side commission and a configurable
  slippage model (none / fixed_bp / atr_pct) are applied to every
  fill. The defaults are conservative.
- **Single-position simplification (v1).** ``max_positions=1`` is
  the only supported value in this slice; the IR field exists so
  the v2 multi-position scheduler can be added without an IR change.

The :class:`BacktestResult` is JSON-serialisable in full
(``.to_dict()``) so the cockpit can render an equity curve, a
trade log table, and a metrics card without any server-side
post-processing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from ..strategy.ir import (
    Side,
    Strategy,
    StrategyError,
)


class BacktestError(RuntimeError):
    """Raised when the backtest fails for a reason worth surfacing."""


# --------------------------------------------------------- bar / trade


@dataclass(frozen=True)
class Bar:
    """One OHLCV row."""

    ts: int  # epoch seconds (close time)
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    """One round-trip position."""

    entry_ts: int
    entry_price: float
    qty: float
    side: Side
    exit_ts: int | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    fees: float = 0.0
    slippage_cost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_ts is None

    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        if self.side is Side.LONG:
            gross = (self.exit_price - self.entry_price) * self.qty
        else:
            gross = (self.entry_price - self.exit_price) * self.qty
        return gross - self.fees - self.slippage_cost

    def pnl_pct(self) -> float:
        notional = self.entry_price * self.qty
        if notional == 0:
            return 0.0
        return self.pnl() / notional

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_ts": int(self.entry_ts),
            "entry_price": float(self.entry_price),
            "qty": float(self.qty),
            "side": self.side.value,
            "exit_ts": None if self.exit_ts is None else int(self.exit_ts),
            "exit_price": (
                None if self.exit_price is None else float(self.exit_price)
            ),
            "exit_reason": self.exit_reason,
            "fees": float(self.fees),
            "slippage_cost": float(self.slippage_cost),
            "pnl": float(self.pnl()),
            "pnl_pct": float(self.pnl_pct()),
        }


# --------------------------------------------------------- config


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest knobs.

    Defaults match a midcap crypto venue: 10 bp commission per side,
    1 bp slippage. Override per workshop attendee.
    """

    initial_equity: float = 10_000.0
    commission_bp: float = 10.0  # one-side, in basis points (10 bp = 0.10 %)
    slippage_model: str = "fixed_bp"  # "none" | "fixed_bp" | "atr_pct"
    slippage_bp: float = 1.0
    slippage_atr_pct: float = 0.1
    seed: int = 42  # only matters once we add stochastic fills
    fill_at: str = "next_open"  # "next_open" | "close" — "close" is for
    # debugging; honest backtests fill at the next bar's open.


# --------------------------------------------------------- result


@dataclass
class BacktestResult:
    strategy_fingerprint: str
    config: BacktestConfig
    bars: int
    initial_equity: float
    final_equity: float
    trades: list[Trade]
    equity_curve: list[tuple[int, float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_fingerprint": self.strategy_fingerprint,
            "config": {
                "initial_equity": self.config.initial_equity,
                "commission_bp": self.config.commission_bp,
                "slippage_model": self.config.slippage_model,
                "slippage_bp": self.config.slippage_bp,
                "slippage_atr_pct": self.config.slippage_atr_pct,
                "seed": self.config.seed,
                "fill_at": self.config.fill_at,
            },
            "bars": int(self.bars),
            "initial_equity": float(self.initial_equity),
            "final_equity": float(self.final_equity),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [
                {"ts": int(ts), "equity": float(eq)}
                for ts, eq in self.equity_curve
            ],
            "metadata": dict(self.metadata),
            "metrics": dict(self.metrics),
        }


# --------------------------------------------------------- engine


def run_backtest(
    strategy: Strategy,
    bars: Iterable[Bar],
    *,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run ``strategy`` over ``bars`` and return a result.

    The bars iterable is consumed exactly once (so streaming sources
    work). Every indicator + condition is rebuilt fresh, so two
    invocations against the same data produce bit-identical results.
    """

    # Local imports — break a cycle (indicators imports Bar from this
    # module). At module import time we avoid the cycle by deferring.
    from .indicators import (
        collect_indicators,
        compile_node,
        eval_node,
    )

    strategy.validate()
    cfg = config or BacktestConfig()
    if strategy.max_positions != 1:
        raise BacktestError(
            "v1 backtest engine supports max_positions=1 only "
            "(IR field accepted for forward-compat)"
        )

    cache: dict[str, Any] = {}
    entry_node = compile_node(strategy.entry, cache)
    exit_node = (
        compile_node(strategy.exit, cache) if strategy.exit is not None else None
    )
    indicators = collect_indicators(entry_node) + (
        collect_indicators(exit_node) if exit_node is not None else []
    )
    seen_ids: set[int] = set()
    unique_indicators = []
    for ind in indicators:
        if id(ind) not in seen_ids:
            seen_ids.add(id(ind))
            unique_indicators.append(ind)

    equity = cfg.initial_equity
    cash = cfg.initial_equity
    trades: list[Trade] = []
    open_trade: Trade | None = None
    pending_action: str | None = None  # "open" | "close" — fills next open
    pending_exit_reason: str | None = None
    cooldown = 0
    high_water = 0.0  # for trailing stop

    equity_curve: list[tuple[int, float]] = []

    prev_indicator_values: dict[int, float | None] = {}
    bar_count = 0
    last_bar: Bar | None = None

    for bar in bars:
        bar_count += 1
        # Fill pending action at this bar's open BEFORE updating
        # indicators; this preserves no-look-ahead.
        if pending_action == "open" and open_trade is None:
            fill_price = _apply_slippage(
                base=bar.open,
                side=strategy.side,
                cfg=cfg,
                atr_value=_get_atr(unique_indicators),
                direction="entry",
            )
            qty = _size(strategy, fill_price, equity)
            if qty > 0:
                fees = fill_price * qty * (cfg.commission_bp / 10_000.0)
                slip_cost = abs(fill_price - bar.open) * qty
                trade = Trade(
                    entry_ts=bar.ts,
                    entry_price=fill_price,
                    qty=qty,
                    side=strategy.side,
                    fees=fees,
                    slippage_cost=slip_cost,
                )
                open_trade = trade
                trades.append(trade)
                cash -= fees + slip_cost
                high_water = fill_price
        elif pending_action == "close" and open_trade is not None:
            fill_price = _apply_slippage(
                base=bar.open,
                side=open_trade.side,
                cfg=cfg,
                atr_value=_get_atr(unique_indicators),
                direction="exit",
            )
            _close(open_trade, bar.ts, fill_price, pending_exit_reason or "signal", cfg)
            cash += open_trade.pnl()
            equity = cash
            open_trade = None
            cooldown = max(strategy.cooldown_bars, 0)
        pending_action = None
        pending_exit_reason = None

        # Update indicators with this bar
        for ind in unique_indicators:
            ind.update(bar)

        # Evaluate signals — entry/exit decisions schedule a next-bar fill
        if open_trade is None:
            if cooldown > 0:
                cooldown -= 1
            elif _all_warm(unique_indicators) and eval_node(
                entry_node, prev=prev_indicator_values
            ):
                pending_action = "open"
        else:
            # Update high-water for trailing stop
            if open_trade.side is Side.LONG:
                if bar.high > high_water:
                    high_water = bar.high
            else:
                if bar.low < high_water or high_water == 0:
                    high_water = bar.low

            # Intra-bar stop checks: if the low touches stop_loss or
            # trailing stop, exit *this* bar at the stop price (worst
            # case for the trader — honest).
            stop_hit = _stop_hit(strategy, open_trade, bar, high_water)
            if stop_hit is not None:
                fill_price, reason = stop_hit
                _close(open_trade, bar.ts, fill_price, reason, cfg)
                cash += open_trade.pnl()
                equity = cash
                open_trade = None
                cooldown = max(strategy.cooldown_bars, 0)
            else:
                # Take-profit check (price goal)
                tp_hit = _take_profit_hit(strategy, open_trade, bar)
                if tp_hit is not None:
                    fill_price, reason = tp_hit
                    _close(
                        open_trade, bar.ts, fill_price, reason, cfg
                    )
                    cash += open_trade.pnl()
                    equity = cash
                    open_trade = None
                    cooldown = max(strategy.cooldown_bars, 0)
                elif exit_node is not None and eval_node(
                    exit_node, prev=prev_indicator_values
                ):
                    pending_action = "close"
                    pending_exit_reason = "signal"

        # Mark equity at close (mark-to-market open trade)
        if open_trade is not None:
            mtm = _mtm(open_trade, bar.close)
            equity = cash + mtm
        else:
            equity = cash
        equity_curve.append((bar.ts, equity))

        # Snapshot indicator values for next bar's "crosses_above/below"
        prev_indicator_values = {id(i): i.last for i in unique_indicators}
        last_bar = bar

    # End of data: close any open trade at last close (forced exit, marked).
    if open_trade is not None and last_bar is not None:
        _close(
            open_trade,
            last_bar.ts,
            last_bar.close,
            "end_of_data",
            cfg,
        )
        cash += open_trade.pnl()
        equity = cash
        if equity_curve:
            equity_curve[-1] = (last_bar.ts, equity)

    from .metrics import compute_metrics  # local import — avoid cycle

    metrics = compute_metrics(
        equity_curve=equity_curve,
        trades=trades,
        initial_equity=cfg.initial_equity,
    )

    return BacktestResult(
        strategy_fingerprint=strategy.fingerprint(),
        config=cfg,
        bars=bar_count,
        initial_equity=cfg.initial_equity,
        final_equity=equity,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        metadata={
            "indicators": [_describe_ind(i) for i in unique_indicators],
        },
    )


# --------------------------------------------------------- helpers


def _all_warm(indicators: list[Any]) -> bool:
    """An indicator is 'warm' once it produces a non-None value."""
    return all(getattr(i, "last", None) is not None for i in indicators)


def _describe_ind(i: Any) -> str:
    cls = type(i).__name__
    if hasattr(i, "period"):
        suffix = f"({i.period})"
        if hasattr(i, "k"):
            suffix = f"({i.period},k={i.k})"
        return f"{cls}{suffix}"
    if hasattr(i, "field"):
        return f"_Field({i.field})"
    return cls


def _size(strategy: Strategy, price: float, equity: float) -> float:
    s = strategy.sizing
    if s.kind == "fixed_qty":
        return float(s.qty or 0.0)
    if s.kind == "fixed_notional":
        if price <= 0:
            return 0.0
        return float(s.notional or 0.0) / price
    if s.kind == "risk_pct":
        if price <= 0 or strategy.stop_loss_pct is None:
            return 0.0
        risk_per_unit = price * strategy.stop_loss_pct
        if risk_per_unit <= 0:
            return 0.0
        risk_dollars = equity * float(s.risk_pct or 0.0)
        return risk_dollars / risk_per_unit
    raise StrategyError(f"unknown sizing {s.kind!r}")


def _apply_slippage(
    *,
    base: float,
    side: Side,
    cfg: BacktestConfig,
    atr_value: float | None,
    direction: str,  # "entry" | "exit"
) -> float:
    if cfg.slippage_model == "none":
        return base
    if cfg.slippage_model == "fixed_bp":
        bps = cfg.slippage_bp / 10_000.0
        if (side is Side.LONG and direction == "entry") or (
            side is Side.SHORT and direction == "exit"
        ):
            return base * (1.0 + bps)
        return base * (1.0 - bps)
    if cfg.slippage_model == "atr_pct":
        if atr_value is None or atr_value == 0:
            return base
        offset = atr_value * cfg.slippage_atr_pct / 100.0
        if (side is Side.LONG and direction == "entry") or (
            side is Side.SHORT and direction == "exit"
        ):
            return base + offset
        return max(0.0, base - offset)
    raise BacktestError(f"unknown slippage_model {cfg.slippage_model!r}")


def _get_atr(indicators: list[Any]) -> float | None:
    for ind in indicators:
        if type(ind).__name__ == "ATR":
            return getattr(ind, "last", None)
    return None


def _close(
    trade: Trade,
    ts: int,
    fill_price: float,
    reason: str,
    cfg: BacktestConfig,
) -> None:
    fees = fill_price * trade.qty * (cfg.commission_bp / 10_000.0)
    trade.exit_ts = ts
    trade.exit_price = fill_price
    trade.exit_reason = reason
    trade.fees += fees


def _stop_hit(
    strategy: Strategy,
    trade: Trade,
    bar: Bar,
    high_water: float,
) -> tuple[float, str] | None:
    if trade.side is Side.LONG:
        if strategy.stop_loss_pct is not None:
            stop_px = trade.entry_price * (1.0 - strategy.stop_loss_pct)
            if bar.low <= stop_px:
                return stop_px, "stop_loss"
        if strategy.trailing_stop_pct is not None:
            trail_px = high_water * (1.0 - strategy.trailing_stop_pct)
            if bar.low <= trail_px:
                return trail_px, "trailing_stop"
    else:
        if strategy.stop_loss_pct is not None:
            stop_px = trade.entry_price * (1.0 + strategy.stop_loss_pct)
            if bar.high >= stop_px:
                return stop_px, "stop_loss"
        if strategy.trailing_stop_pct is not None:
            trail_px = high_water * (1.0 + strategy.trailing_stop_pct)
            if bar.high >= trail_px:
                return trail_px, "trailing_stop"
    return None


def _take_profit_hit(
    strategy: Strategy, trade: Trade, bar: Bar
) -> tuple[float, str] | None:
    if strategy.take_profit_pct is None:
        return None
    if trade.side is Side.LONG:
        tp_px = trade.entry_price * (1.0 + strategy.take_profit_pct)
        if bar.high >= tp_px:
            return tp_px, "take_profit"
    else:
        tp_px = trade.entry_price * (1.0 - strategy.take_profit_pct)
        if bar.low <= tp_px:
            return tp_px, "take_profit"
    return None


def _mtm(trade: Trade, mark_price: float) -> float:
    if trade.side is Side.LONG:
        return mark_price * trade.qty
    # short MtM: cash inflow at entry, payback at mark
    return (2 * trade.entry_price - mark_price) * trade.qty
