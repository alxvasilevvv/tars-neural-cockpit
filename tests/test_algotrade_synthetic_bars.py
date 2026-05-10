"""Tests for the deterministic OHLCV bar generator and the
``algotrade.synthetic_bars`` action wrapper (Wave M6 E2E)."""

from __future__ import annotations

import asyncio

import pytest

from backend.core.algotrade.backtest.synthetic import generate_bars
from backend.core.domains.packs.algotrade import pack as _  # registers
from backend.core.domains.registry import get_pack


def _action(name: str):
    return get_pack("algotrade").find_action(name)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------
# Generator basics
# ---------------------------------------------------------------------


def test_generate_bars_count_zero_returns_empty() -> None:
    assert generate_bars(count=0) == []


def test_generate_bars_default_count_is_200() -> None:
    bars = generate_bars()
    assert len(bars) == 200


def test_generate_bars_each_bar_has_required_fields() -> None:
    for bar in generate_bars(count=5):
        assert set(bar.keys()) == {
            "ts", "open", "high", "low", "close", "volume",
        }
        assert bar["high"] >= max(bar["open"], bar["close"]) - 1e-9
        assert bar["low"] <= min(bar["open"], bar["close"]) + 1e-9
        assert bar["volume"] >= 1000.0


def test_generate_bars_timestamps_are_monotone_hourly() -> None:
    bars = generate_bars(count=10)
    diffs = [bars[i + 1]["ts"] - bars[i]["ts"] for i in range(len(bars) - 1)]
    assert all(d == 3600 for d in diffs)


# ---------------------------------------------------------------------
# Determinism — same args, byte-identical output
# ---------------------------------------------------------------------


def test_generate_bars_is_deterministic() -> None:
    a = generate_bars(regime="trending", count=50, start_price=100.0)
    b = generate_bars(regime="trending", count=50, start_price=100.0)
    assert a == b


def test_generate_bars_different_regimes_produce_different_output() -> None:
    trending = generate_bars(regime="trending", count=20)
    mean_rev = generate_bars(regime="mean_reverting", count=20)
    choppy = generate_bars(regime="choppy", count=20)
    assert trending != mean_rev != choppy


def test_generate_bars_trending_drifts_up_overall() -> None:
    bars = generate_bars(regime="trending", count=200, start_price=100.0)
    avg_first = sum(b["close"] for b in bars[:20]) / 20
    avg_last = sum(b["close"] for b in bars[-20:]) / 20
    # Linear drift dominates the embedded sine over 200 bars
    # so the last window must average meaningfully above the
    # first one. The exact magnitude depends on where the sine
    # cycle lands; >0.5 leaves headroom while still proving
    # the regime is "up not flat".
    assert avg_last - avg_first > 0.5


def test_generate_bars_mean_reverting_stays_around_baseline() -> None:
    bars = generate_bars(regime="mean_reverting", count=200, start_price=100.0)
    avg = sum(b["close"] for b in bars) / len(bars)
    # Pure sine around baseline → average close to start_price.
    assert abs(avg - 100.0) < 1.0


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def test_generate_bars_rejects_unknown_regime() -> None:
    with pytest.raises(ValueError, match="unknown regime"):
        generate_bars(regime="moonshot", count=5)  # type: ignore[arg-type]


def test_generate_bars_rejects_negative_start_price() -> None:
    with pytest.raises(ValueError, match="start_price"):
        generate_bars(start_price=-1.0)


# ---------------------------------------------------------------------
# Action wrapper
# ---------------------------------------------------------------------


def test_synthetic_bars_action_default_args() -> None:
    res = _run(_action("synthetic_bars").handler({}))
    assert res["ok"] is True
    assert res["regime"] == "trending"
    assert res["count"] == 200
    assert len(res["bars"]) == 200


def test_synthetic_bars_action_custom_count_and_regime() -> None:
    res = _run(_action("synthetic_bars").handler({
        "regime": "mean_reverting", "count": 50, "start_price": 50,
    }))
    assert res["ok"] is True
    assert res["regime"] == "mean_reverting"
    assert res["count"] == 50
    assert len(res["bars"]) == 50


def test_synthetic_bars_action_rejects_zero_count() -> None:
    res = _run(_action("synthetic_bars").handler({"count": 0}))
    assert res["ok"] is False
    assert res["error"] == "invalid_count"


def test_synthetic_bars_action_rejects_huge_count() -> None:
    res = _run(_action("synthetic_bars").handler({"count": 10_000}))
    assert res["ok"] is False
    assert res["error"] == "invalid_count"


def test_synthetic_bars_action_rejects_unknown_regime() -> None:
    res = _run(_action("synthetic_bars").handler({"regime": "moonshot"}))
    assert res["ok"] is False
    assert res["error"] == "invalid_args"


def test_synthetic_bars_action_is_registered() -> None:
    pack = get_pack("algotrade")
    assert any(a.id == "synthetic_bars" for a in pack.actions())
    spec = pack.find_action("synthetic_bars")
    assert spec.destructive is False
    schema = spec.schema
    assert schema["type"] == "object"
    assert "regime" in schema["properties"]


# ---------------------------------------------------------------------
# Chaining smoke — synthetic_bars feeds backtest
# ---------------------------------------------------------------------


def test_synthetic_bars_output_feeds_backtest_directly() -> None:
    async def go():
        gen = await _action("synthetic_bars").handler({"count": 100})
        bt = await _action("backtest").handler({
            "recipe": "ma_cross",
            "bars": gen["bars"],
            "config": {"initial_equity": 10_000, "seed": 42},
        })
        return bt

    bt = _run(go())
    assert bt["ok"] is True
    assert "metrics" in bt
    assert "sharpe" in bt["metrics"]
    assert "strategy_fingerprint" in bt
    # Determinism: same inputs → same fingerprint
    bt2 = _run(go())
    assert bt2["strategy_fingerprint"] == bt["strategy_fingerprint"]
    assert bt2["metrics"]["sharpe"] == bt["metrics"]["sharpe"]
