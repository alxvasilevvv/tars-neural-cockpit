"""Tests for algotrade incremental indicators.

Each indicator is exercised against a known input series whose
expected output is computed in the test (or hand-verified) so a
regression in arithmetic shows up immediately.
"""

from __future__ import annotations

import math

import pytest

from backend.core.algotrade.backtest.harness import Bar
from backend.core.algotrade.backtest.indicators import (
    ATR,
    Bollinger,
    EMA,
    INDICATORS,
    RSI,
    SMA,
    build_indicator,
)
from backend.core.algotrade.strategy.ir import Indicator as IRIndicator
from backend.core.algotrade.strategy.ir import StrategyError


def _bars(*closes: float) -> list[Bar]:
    return [
        Bar(ts=1700000000 + i * 60, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


# --------------------------------------------------------- SMA


def test_sma_warms_up_then_emits_average() -> None:
    sma = SMA(period=3)
    out: list[float | None] = []
    for b in _bars(1, 2, 3, 4, 5):
        out.append(sma.update(b))
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(2.0)
    assert out[3] == pytest.approx(3.0)
    assert out[4] == pytest.approx(4.0)


def test_sma_period_must_be_positive() -> None:
    with pytest.raises(StrategyError):
        SMA(period=0)


# --------------------------------------------------------- EMA


def test_ema_seeds_with_sma_then_smooths() -> None:
    ema = EMA(period=3)
    closes = [10.0, 12.0, 14.0, 18.0]
    expected_seed = (10 + 12 + 14) / 3.0  # 12.0
    k = 2.0 / 4.0
    expected_after_18 = (18.0 - expected_seed) * k + expected_seed
    out = [ema.update(b) for b in _bars(*closes)]
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(expected_seed)
    assert out[3] == pytest.approx(expected_after_18)


# --------------------------------------------------------- RSI


def test_rsi_returns_100_when_only_gains() -> None:
    rsi = RSI(period=3)
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = [rsi.update(b) for b in _bars(*closes)]
    # warm-up bars: first one returns None (no prev), then we need
    # ``period`` more before RSI emits.
    assert out[0] is None
    last = [v for v in out if v is not None]
    assert last[-1] == pytest.approx(100.0)


def test_rsi_returns_zero_when_only_losses() -> None:
    rsi = RSI(period=3)
    closes = [5.0, 4.0, 3.0, 2.0, 1.0]
    out = [rsi.update(b) for b in _bars(*closes)]
    last = [v for v in out if v is not None]
    assert last[-1] == pytest.approx(0.0)


def test_rsi_oscillates_for_alternating_series() -> None:
    rsi = RSI(period=4)
    closes = [10.0, 11.0, 10.0, 11.0, 10.0, 11.0, 10.0, 11.0, 10.0]
    last = None
    for b in _bars(*closes):
        v = rsi.update(b)
        if v is not None:
            last = v
    assert last is not None
    assert 30.0 < last < 70.0  # oscillating, not extreme


# --------------------------------------------------------- ATR


def test_atr_warms_up_then_emits() -> None:
    atr = ATR(period=3)
    bars = [
        Bar(ts=0, open=10, high=12, low=9, close=11, volume=1),
        Bar(ts=1, open=11, high=13, low=10, close=12, volume=1),
        Bar(ts=2, open=12, high=14, low=11, close=13, volume=1),
        Bar(ts=3, open=13, high=15, low=12, close=14, volume=1),
    ]
    out = [atr.update(b) for b in bars]
    assert out[:2] == [None, None]
    assert out[2] is not None
    assert out[3] is not None
    # Each bar has TR=3 (high-low), so ATR converges to ~3.
    assert 2.5 < out[3] < 3.5


# --------------------------------------------------------- Bollinger


def test_bollinger_mid_equals_sma() -> None:
    closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    bb = Bollinger(period=5, k=2.0, band="mid")
    sma = SMA(period=5)
    out_bb: list[float | None] = []
    out_sma: list[float | None] = []
    for b in _bars(*closes):
        out_bb.append(bb.update(b))
        out_sma.append(sma.update(b))
    for x, y in zip(out_bb, out_sma):
        if x is None or y is None:
            assert x is None and y is None
        else:
            assert x == pytest.approx(y)


def test_bollinger_upper_above_lower() -> None:
    bb_up = Bollinger(period=4, k=2.0, band="upper")
    bb_lo = Bollinger(period=4, k=2.0, band="lower")
    closes = [10.0, 12.0, 8.0, 14.0, 6.0, 16.0, 4.0]
    last_u = last_l = None
    for b in _bars(*closes):
        u = bb_up.update(b)
        l = bb_lo.update(b)
        if u is not None:
            last_u = u
        if l is not None:
            last_l = l
    assert last_u is not None and last_l is not None
    assert last_u > last_l


def test_bollinger_rejects_unknown_band() -> None:
    with pytest.raises(StrategyError, match="bollinger"):
        Bollinger(period=20, k=2.0, band="centre")


# --------------------------------------------------------- registry


def test_indicator_registry_has_expected_names() -> None:
    expected = {
        "open", "high", "low", "close", "volume",
        "sma", "ema", "rsi", "atr",
        "bb_mid", "bb_upper", "bb_lower",
    }
    assert expected <= set(INDICATORS.keys())


def test_build_indicator_resolves_known_name() -> None:
    inst = build_indicator(IRIndicator(name="sma", params={"period": 14.0}))
    assert isinstance(inst, SMA)
    assert inst.period == 14


def test_build_indicator_raises_on_unknown_name() -> None:
    with pytest.raises(StrategyError, match="unknown indicator"):
        build_indicator(IRIndicator(name="nope"))


def test_build_indicator_raises_on_bad_params() -> None:
    with pytest.raises(StrategyError, match="rejected params"):
        build_indicator(IRIndicator(name="sma", params={"weird": 3.0}))
