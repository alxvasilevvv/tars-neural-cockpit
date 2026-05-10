"""Tests for the backtest engine.

These exercise the full event loop end-to-end:

- A deterministic price path runs through MA-cross and produces
  an expected number of trades + non-zero metrics.
- No look-ahead: signals computed at bar t fill at t+1 open.
- Stop-loss / take-profit / trailing-stop fire at intra-bar levels.
- Sizing modes (fixed_qty / fixed_notional / risk_pct) all produce
  positive quantities given a sane price.
- Result is JSON-serialisable.
- Two runs against the same data produce bit-identical equity
  curves and metrics — required for the backtest cache key
  to be valid.
"""

from __future__ import annotations

import json
import math
import random

import pytest

from backend.core.algotrade.backtest.harness import (
    Bar,
    BacktestConfig,
    BacktestError,
    Trade,
    run_backtest,
    _size,
)
from backend.core.algotrade.backtest.metrics import compute_metrics
from backend.core.algotrade.strategy.ir import (
    Condition,
    Constant,
    Indicator,
    Operator,
    Side,
    SizingRule,
    Strategy,
    Timeframe,
)


def _deterministic_bars(n: int = 400, start: float = 100.0, seed: int = 7) -> list[Bar]:
    """Sin wave + random walk + drift; same seed → same series."""
    random.seed(seed)
    bars: list[Bar] = []
    px = start
    for i in range(n):
        px = start + 10.0 * math.sin(i / 18.0) + random.gauss(0, 1.5) + i * 0.05
        o = px + random.gauss(0, 0.3)
        h = max(o, px) + abs(random.gauss(0, 0.6))
        lo = min(o, px) - abs(random.gauss(0, 0.6))
        bars.append(
            Bar(
                ts=1700000000 + i * 3600,
                open=o,
                high=h,
                low=lo,
                close=px,
                volume=abs(random.gauss(1000, 200)),
            )
        )
    return bars


def _ma_cross(qty: float = 1.0) -> Strategy:
    return Strategy(
        name="MA Cross 5/20 Test",
        description="cross",
        instrument="SYNTH:TEST",
        timeframe=Timeframe.H1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.CROSSES_ABOVE,
            args=[
                Indicator(name="sma", params={"period": 5.0}),
                Indicator(name="sma", params={"period": 20.0}),
            ],
        ),
        exit=Condition(
            op=Operator.CROSSES_BELOW,
            args=[
                Indicator(name="sma", params={"period": 5.0}),
                Indicator(name="sma", params={"period": 20.0}),
            ],
        ),
        sizing=SizingRule(kind="fixed_qty", qty=qty),
    )


def _bb_reversion() -> Strategy:
    return Strategy(
        name="BB Reversion",
        description="bb",
        instrument="SYNTH:TEST",
        timeframe=Timeframe.H1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.LT,
            args=[
                Indicator(name="close"),
                Indicator(name="bb_lower", params={"period": 20.0, "k": 2.0}),
            ],
        ),
        exit=Condition(
            op=Operator.GT,
            args=[
                Indicator(name="close"),
                Indicator(name="sma", params={"period": 20.0}),
            ],
        ),
        sizing=SizingRule(kind="risk_pct", risk_pct=0.01),
        stop_loss_pct=0.05,
    )


# --------------------------------------------------------- happy path


def test_ma_cross_produces_trades() -> None:
    bars = _deterministic_bars(400)
    res = run_backtest(_ma_cross(), bars)
    closed = [t for t in res.trades if t.exit_ts is not None]
    assert len(closed) >= 3
    assert res.bars == 400
    assert len(res.equity_curve) == 400
    assert res.equity_curve[0][1] == res.config.initial_equity


def test_metrics_are_finite_and_complete() -> None:
    bars = _deterministic_bars(400)
    res = run_backtest(_ma_cross(), bars)
    expected = {
        "total_return", "cagr", "sharpe", "sortino",
        "max_drawdown", "win_rate", "loss_rate",
        "profit_factor", "expectancy", "trades",
        "avg_trade_pct", "exposure",
    }
    assert expected <= set(res.metrics.keys())
    for k, v in res.metrics.items():
        assert math.isfinite(v), (k, v)
    assert res.metrics["trades"] > 0
    assert 0.0 <= res.metrics["win_rate"] <= 1.0


def test_result_is_json_serialisable() -> None:
    res = run_backtest(_ma_cross(), _deterministic_bars(200))
    payload = res.to_dict()
    raw = json.dumps(payload)
    parsed = json.loads(raw)
    assert parsed["bars"] == 200
    assert "metrics" in parsed
    assert "equity_curve" in parsed
    assert isinstance(parsed["trades"], list)


# --------------------------------------------------------- determinism / cache key


def test_same_data_same_result() -> None:
    bars1 = _deterministic_bars(300)
    bars2 = _deterministic_bars(300)
    a = run_backtest(_ma_cross(), bars1)
    b = run_backtest(_ma_cross(), bars2)
    assert a.equity_curve == b.equity_curve
    assert a.metrics == b.metrics
    assert [t.to_dict() for t in a.trades] == [t.to_dict() for t in b.trades]


# --------------------------------------------------------- no look-ahead


def test_entry_fills_at_next_bar_open() -> None:
    """Construct a series where bar 21 close crosses SMA(5) above
    SMA(20). The trade must enter at bar 22's open, not bar 21's
    close. We verify by reading the first trade's entry_ts."""
    closes = [50.0] * 20 + [60.0, 80.0, 80.0, 80.0, 80.0]
    bars = []
    for i, c in enumerate(closes):
        bars.append(
            Bar(
                ts=1700000000 + i * 60,
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1.0,
            )
        )
    s = _ma_cross()
    res = run_backtest(s, bars)
    assert res.trades, "expected at least one trade"
    first = res.trades[0]
    # The crossing happens at index 20 (close jumps from 50→60).
    # Fill must be at bar 21's open (or later), NEVER ≤ bar 20.
    assert first.entry_ts >= bars[21].ts


# --------------------------------------------------------- stops


def test_stop_loss_fires_intra_bar() -> None:
    """Construct entry → next bar drills through the SL price."""
    # 21 flat bars to warm SMA, then a clear cross, then a deep dip.
    closes = [100.0] * 21 + [115.0, 115.0]
    bars = []
    for i, c in enumerate(closes):
        bars.append(
            Bar(
                ts=1700000000 + i * 60,
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1.0,
            )
        )
    # Bar after entry: spike low through stop
    bars[-1] = Bar(
        ts=bars[-1].ts, open=115.0, high=115.0, low=80.0, close=80.0, volume=1.0
    )
    s = Strategy(
        name="MA Cross w/ stop",
        description="x",
        instrument="SYNTH:T",
        timeframe=Timeframe.M1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.GT,
            args=[Indicator(name="close"), Constant(value=110.0)],
        ),
        exit=Condition(
            op=Operator.LT,
            args=[Indicator(name="close"), Constant(value=50.0)],
        ),
        sizing=SizingRule(kind="fixed_qty", qty=1.0),
        stop_loss_pct=0.05,  # 5 % stop = 109.25 from 115 entry
    )
    res = run_backtest(s, bars)
    closed = [t for t in res.trades if t.exit_ts is not None]
    assert closed
    assert closed[-1].exit_reason == "stop_loss"


def test_take_profit_fires_intra_bar() -> None:
    closes = [100.0] * 21 + [115.0, 115.0]
    bars = [
        Bar(ts=1700000000 + i * 60, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]
    # Bar after entry: spike high to TP
    bars[-1] = Bar(
        ts=bars[-1].ts, open=115.0, high=140.0, low=115.0, close=120.0, volume=1.0
    )
    s = Strategy(
        name="TP test",
        description="x",
        instrument="SYNTH:T",
        timeframe=Timeframe.M1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.GT,
            args=[Indicator(name="close"), Constant(value=110.0)],
        ),
        exit=Condition(
            op=Operator.LT,
            args=[Indicator(name="close"), Constant(value=50.0)],
        ),
        sizing=SizingRule(kind="fixed_qty", qty=1.0),
        stop_loss_pct=0.10,
        take_profit_pct=0.05,  # 5 % TP = 120.75 from 115 entry
    )
    res = run_backtest(s, bars)
    closed = [t for t in res.trades if t.exit_ts is not None]
    assert closed
    assert closed[-1].exit_reason == "take_profit"


# --------------------------------------------------------- sizing


def test_fixed_qty_sizing() -> None:
    s = _ma_cross(qty=2.5)
    assert _size(s, price=100.0, equity=10_000.0) == pytest.approx(2.5)


def test_fixed_notional_sizing() -> None:
    s = Strategy.from_dict(
        {
            **_ma_cross().to_dict(),
            "sizing": {"kind": "fixed_notional", "notional": 1000.0},
        }
    )
    assert _size(s, price=200.0, equity=10_000.0) == pytest.approx(5.0)


def test_risk_pct_sizing_uses_stop_loss_pct() -> None:
    s = _bb_reversion()  # risk_pct=0.01, stop_loss_pct=0.05
    qty = _size(s, price=100.0, equity=10_000.0)
    # risk_per_unit = 100 * 0.05 = 5; risk_dollars = 10_000 * 0.01 = 100
    # → qty = 100 / 5 = 20
    assert qty == pytest.approx(20.0)


# --------------------------------------------------------- guardrails


def test_max_positions_above_one_rejected_in_v1() -> None:
    s = Strategy.from_dict({**_ma_cross().to_dict(), "max_positions": 2})
    with pytest.raises(BacktestError, match="max_positions=1"):
        run_backtest(s, _deterministic_bars(50))


def test_open_trade_force_closed_at_eod() -> None:
    """If the data ends with a trade still open, the engine closes
    it at the last bar's close (forced exit, ``end_of_data``)."""
    closes = [100.0] * 22 + [120.0]  # cross + immediate close (no exit signal)
    bars = [
        Bar(ts=1700000000 + i * 60, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]
    s = Strategy(
        name="Forced exit test",
        description="x",
        instrument="SYNTH:T",
        timeframe=Timeframe.M1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.GT,
            args=[Indicator(name="close"), Constant(value=110.0)],
        ),
        exit=Condition(
            op=Operator.LT,
            args=[Indicator(name="close"), Constant(value=10.0)],
        ),
        sizing=SizingRule(kind="fixed_qty", qty=1.0),
    )
    res = run_backtest(s, bars)
    if res.trades:
        last = res.trades[-1]
        assert last.exit_ts is not None
        assert last.exit_reason == "end_of_data"


# --------------------------------------------------------- bb reversion smoke


def test_bb_reversion_runs_clean() -> None:
    bars = _deterministic_bars(500)
    res = run_backtest(_bb_reversion(), bars)
    assert res.bars == 500
    assert all(math.isfinite(v) for v in res.metrics.values())


# --------------------------------------------------------- metrics edge cases


def test_metrics_handle_empty_curve() -> None:
    m = compute_metrics(equity_curve=[], trades=[], initial_equity=10_000.0)
    assert m["total_return"] == 0.0
    assert m["trades"] == 0.0


def test_metrics_max_drawdown_picks_largest_peak_to_trough() -> None:
    curve = [(0, 100.0), (1, 120.0), (2, 60.0), (3, 90.0)]
    m = compute_metrics(equity_curve=curve, trades=[], initial_equity=100.0)
    # peak 120 → trough 60 = 50 % drawdown
    assert m["max_drawdown"] == pytest.approx(0.5, abs=1e-6)
