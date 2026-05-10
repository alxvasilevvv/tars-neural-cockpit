"""Tests for the W3-PR3 trading council voices.

The voices are pure functions over the W3-PR1 dataclasses
(`PnLAttribution`, `SlippageReport`, `SessionMetrics`,
`RiskPolicy`). Every test feeds a hand-crafted dataclass and
asserts the right severity + a recognisable bullet, so we
preserve the workshop guarantee that "same numbers always
produce the same verdict".
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from backend.core.algotrade.exec import (
    PnLAttribution,
    RiskPolicy,
    RoundTrip,
    SessionMetrics,
    SlippageEntry,
    SlippageReport,
    Voice,
    execution_trader_voice,
    pnl_auditor_voice,
    risk_analyst_voice,
    run_council,
)


# --------------------------------------------------------- helpers


def _metrics(
    *,
    intents_total: int = 4,
    intents_accepted: int = 4,
    intents_rejected: int = 0,
    orders_total: int = 4,
    fills_total: int = 4,
    cancels_total: int = 0,
    realized_pnl: float = 100.0,
    unrealized_pnl: float = 0.0,
    fees_total: float = 1.0,
    total_slippage_cost: float = 0.5,
    avg_slippage_bps: float = 2.0,
    open_positions: int = 0,
) -> SessionMetrics:
    return SessionMetrics(
        intents_total=intents_total,
        intents_accepted=intents_accepted,
        intents_rejected=intents_rejected,
        orders_total=orders_total,
        fills_total=fills_total,
        cancels_total=cancels_total,
        bars_consumed=10,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        fees_total=fees_total,
        total_slippage_cost=total_slippage_cost,
        avg_slippage_bps=avg_slippage_bps,
        open_positions=open_positions,
        started_at=1700000000.0,
        last_event_at=1700000060.0,
    )


def _slippage(
    *,
    fills_total: int = 4,
    fills_with_reference: int = 4,
    fills_missing_reference: int = 0,
    avg_bps: float = 2.0,
    worst_bps: float = 5.0,
    total_cost: float = 0.5,
) -> SlippageReport:
    return SlippageReport(
        entries=tuple(
            SlippageEntry(
                fill_id=f"f{i}",
                order_id=f"o{i}",
                instrument="BINANCE:BTCUSDT",
                side="buy" if i % 2 == 0 else "sell",
                qty=1.0,
                fill_price=100.0,
                reference_price=100.0,
                slippage_bps=avg_bps,
                slippage_cost=0.0,
                ts=float(i),
            )
            for i in range(fills_with_reference)
        ),
        fills_total=fills_total,
        fills_with_reference=fills_with_reference,
        fills_missing_reference=fills_missing_reference,
        total_slippage_cost=total_cost,
        avg_slippage_bps=avg_bps,
        p50_slippage_bps=avg_bps,
        p95_slippage_bps=worst_bps,
        worst_slippage_bps=worst_bps,
    )


def _trip(*, side: str = "long", pnl: float = 10.0, qty: float = 1.0, fees: float = 0.05, instrument: str = "BINANCE:BTCUSDT") -> RoundTrip:
    entry = 100.0
    exit_price = entry + (pnl / qty) if side == "long" else entry - (pnl / qty)
    return RoundTrip(
        instrument=instrument,
        strategy_fingerprint="fp_test",
        side=side,
        qty=qty,
        entry_price=entry,
        exit_price=exit_price,
        fees=fees,
        pnl=pnl,
        opened_at=1.0,
        closed_at=2.0,
        entry_order_id="o_entry",
        exit_order_id="o_exit",
    )


def _attribution(
    *,
    trades=None,
    realized_total: float | None = None,
    fees_total: float = 0.5,
    by_instrument: dict | None = None,
    by_strategy: dict | None = None,
) -> PnLAttribution:
    if trades is None:
        trades = (_trip(),)
    if realized_total is None:
        realized_total = sum(t.pnl for t in trades)
    return PnLAttribution(
        realized_total=realized_total,
        unrealized_total=0.0,
        fees_total=fees_total,
        by_instrument=by_instrument or {"BINANCE:BTCUSDT": {"realized": realized_total, "fees": fees_total, "trades": float(len(trades))}},
        by_strategy=by_strategy or {"fp_test": {"realized": realized_total, "fees": fees_total, "trades": float(len(trades))}},
        trades=tuple(trades),
        pnl_curve=tuple((float(i + 1), sum(t.pnl for t in trades[: i + 1])) for i in range(len(trades))),
    )


# --------------------------------------------------------- risk analyst


def test_risk_analyst_healthy_session_is_info() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(),
        metrics=_metrics(),
        slippage=_slippage(),
    )
    assert voice.severity == "info"
    assert voice.headline.lower().startswith("risk policy is healthy")


def test_risk_analyst_kill_switch_is_alert() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(kill_switch=True),
        metrics=_metrics(),
        slippage=_slippage(),
    )
    assert voice.severity == "alert"
    assert any("kill" in b.lower() for b in voice.bullets)


def test_risk_analyst_high_rejection_rate_alerts() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(),
        metrics=_metrics(intents_total=10, intents_accepted=3, intents_rejected=7),
        slippage=_slippage(),
    )
    assert voice.severity == "alert"
    assert any("rejection" in b.lower() for b in voice.bullets)


def test_risk_analyst_warn_rejection_rate_warns() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(),
        metrics=_metrics(intents_total=10, intents_accepted=7, intents_rejected=3),
        slippage=_slippage(),
    )
    assert voice.severity == "warn"


def test_risk_analyst_daily_loss_breach_is_alert() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(max_daily_loss=50.0),
        metrics=_metrics(realized_pnl=-60.0),
        slippage=_slippage(),
    )
    assert voice.severity == "alert"
    assert any("daily-loss" in b.lower() for b in voice.bullets)


def test_risk_analyst_daily_loss_thin_cushion_warns() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(max_daily_loss=100.0),
        metrics=_metrics(realized_pnl=-80.0),
        slippage=_slippage(),
    )
    assert voice.severity == "warn"


def test_risk_analyst_slippage_eats_pnl_warns() -> None:
    voice = risk_analyst_voice(
        policy=RiskPolicy(),
        metrics=_metrics(realized_pnl=10.0, total_slippage_cost=8.0),
        slippage=_slippage(total_cost=8.0),
    )
    assert voice.severity == "warn"
    assert any("slippage" in b.lower() for b in voice.bullets)


# --------------------------------------------------------- execution trader


def test_execution_trader_no_fills_returns_info() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(fills_total=0),
        slippage=_slippage(fills_total=0, fills_with_reference=0),
    )
    assert voice.severity == "info"
    assert "no fills" in voice.headline.lower()


def test_execution_trader_clean_fills_is_info() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(),
        slippage=_slippage(avg_bps=2.0, worst_bps=4.0),
    )
    assert voice.severity == "info"


def test_execution_trader_high_avg_slippage_warns() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(),
        slippage=_slippage(avg_bps=15.0, worst_bps=20.0),
    )
    assert voice.severity == "warn"


def test_execution_trader_worst_fill_30bps_is_alert() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(),
        slippage=_slippage(avg_bps=5.0, worst_bps=35.0),
    )
    assert voice.severity == "alert"


def test_execution_trader_low_acceptance_rate_warns() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(intents_total=10, intents_accepted=5, intents_rejected=5),
        slippage=_slippage(),
    )
    assert voice.severity == "warn"


def test_execution_trader_zero_reference_coverage_warns() -> None:
    voice = execution_trader_voice(
        metrics=_metrics(),
        slippage=_slippage(fills_total=4, fills_with_reference=0, fills_missing_reference=4),
    )
    assert voice.severity == "warn"
    assert any("reference" in b.lower() for b in voice.bullets)


# --------------------------------------------------------- pnl auditor


def test_pnl_auditor_no_trades_is_info() -> None:
    voice = pnl_auditor_voice(
        attribution=_attribution(trades=()),
        metrics=_metrics(),
    )
    assert voice.severity == "info"


def test_pnl_auditor_healthy_pnl_is_info() -> None:
    trades = (_trip(pnl=10.0), _trip(pnl=20.0), _trip(pnl=15.0))
    voice = pnl_auditor_voice(
        attribution=_attribution(trades=trades),
        metrics=_metrics(realized_pnl=45.0),
    )
    assert voice.severity == "info"


def test_pnl_auditor_low_winrate_low_ratio_alerts() -> None:
    """1 winner of 4 trips (25% win rate) with avg_win/avg_loss < 2x → alert."""

    trades = (
        _trip(pnl=2.0),
        _trip(pnl=-3.0),
        _trip(pnl=-2.5),
        _trip(pnl=-3.5),
    )
    voice = pnl_auditor_voice(
        attribution=_attribution(trades=trades, realized_total=sum(t.pnl for t in trades)),
        metrics=_metrics(realized_pnl=sum(t.pnl for t in trades)),
    )
    assert voice.severity == "alert"
    assert any("fragile" in b.lower() or "edge" in b.lower() for b in voice.bullets)


def test_pnl_auditor_concentration_risk_warns() -> None:
    """One trade contributes >50% of total realised PnL → warn."""

    trades = (
        _trip(pnl=100.0),
        _trip(pnl=10.0),
        _trip(pnl=5.0),
    )
    voice = pnl_auditor_voice(
        attribution=_attribution(trades=trades, realized_total=115.0),
        metrics=_metrics(realized_pnl=115.0),
    )
    assert voice.severity == "warn"
    assert any("concentration" in b.lower() for b in voice.bullets)


def test_pnl_auditor_fee_heavy_warns() -> None:
    """Fees swallow >30% of realised PnL → warn."""

    trades = (_trip(pnl=10.0),)
    voice = pnl_auditor_voice(
        attribution=_attribution(trades=trades, realized_total=10.0, fees_total=4.0),
        metrics=_metrics(realized_pnl=10.0, fees_total=4.0),
    )
    assert voice.severity == "warn"
    assert any("fee" in b.lower() for b in voice.bullets)


# --------------------------------------------------------- council aggregator


def test_council_consensus_picks_worst_severity() -> None:
    review = run_council(
        policy=RiskPolicy(kill_switch=True),
        metrics=_metrics(),
        attribution=_attribution(),
        slippage=_slippage(),
    )
    assert review.consensus == "alert"
    assert len(review.voices) == 3
    assert any(v.severity == "alert" for v in review.voices)


def test_council_all_info_consensus_is_info() -> None:
    """Three even-ish wins → no concentration risk, no fee
    issues, no slippage flags → all voices info → consensus info."""

    trades = (
        _trip(pnl=15.0, fees=0.05),
        _trip(pnl=18.0, fees=0.05),
        _trip(pnl=20.0, fees=0.05),
    )
    review = run_council(
        policy=RiskPolicy(),
        metrics=_metrics(realized_pnl=53.0),
        attribution=_attribution(
            trades=trades,
            realized_total=53.0,
            fees_total=0.15,
        ),
        slippage=_slippage(avg_bps=2.0, worst_bps=4.0),
    )
    assert review.consensus == "info"
    assert all(v.severity == "info" for v in review.voices)


def test_council_voice_dataclasses_are_json_serialisable() -> None:
    import json

    review = run_council(
        policy=RiskPolicy(),
        metrics=_metrics(),
        attribution=_attribution(),
        slippage=_slippage(),
    )
    blob = review.to_dict()
    assert json.loads(json.dumps(blob)) == blob
    for v in review.voices:
        assert isinstance(v, Voice)


# --------------------------------------------------------- end-to-end action


def test_council_review_action_returns_voices_and_consensus() -> None:
    """End-to-end through the action so the cockpit's contract
    stays honest."""

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        from backend.core.algotrade.exec import reset_runtime
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.domains.packs.algotrade.exec_actions import (
            council_review_action,
            feed_bar_action,
            start_paper_session_action,
            submit_intent_action,
        )

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint

        async def run():
            s = await start_paper_session_action({
                "fingerprint": fp,
                "instrument": "BINANCE:BTCUSDT",
                "config": {"slippage_bps": 2.0, "commission_bps": 0.5},
            })
            sid = s["session"]["session_id"]
            await submit_intent_action({"session_id": sid, "side": "buy", "qty": 1.0})
            await feed_bar_action({
                "session_id": sid,
                "bar": {"ts": 1, "open": 100, "high": 100, "low": 100, "close": 100, "instrument": "BINANCE:BTCUSDT"},
            })
            await submit_intent_action({"session_id": sid, "side": "sell", "qty": 1.0})
            await feed_bar_action({
                "session_id": sid,
                "bar": {"ts": 2, "open": 110, "high": 110, "low": 110, "close": 110, "instrument": "BINANCE:BTCUSDT"},
            })
            return await council_review_action({"session_id": sid})

        result = asyncio.run(run())
        assert result["ok"] is True
        assert result["consensus"] in {"info", "warn", "alert"}
        assert len(result["voices"]) == 3
        names = {v["name"] for v in result["voices"]}
        assert names == {"risk_analyst", "execution_trader", "pnl_auditor"}
        for v in result["voices"]:
            assert v["severity"] in {"info", "warn", "alert"}
            assert v["headline"]
            assert isinstance(v["bullets"], list)
            assert isinstance(v["metrics_consulted"], list)
