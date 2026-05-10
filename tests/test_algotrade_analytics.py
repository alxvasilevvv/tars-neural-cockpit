"""Tests for the W3-PR1 analytics layer.

Three concerns, three pillars:

- :func:`compute_attribution` rebuilds PnL from a fill stream that
  matches the live :class:`PositionStore` byte-for-byte.
- :func:`compute_slippage` computes signed bps + cost from
  ``Fill.reference_price``; missing references roll into the
  ``fills_missing_reference`` bucket.
- :func:`compute_session_metrics` joins both into the cockpit's
  session card and is robust against an empty audit log.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from backend.core.algotrade.exec import (
    AuditEvent,
    AuditLog,
    OrderIntent,
    OrderRouter,
    OrderType,
    PaperAdapter,
    PaperConfig,
    PositionStore,
    RiskGate,
    RiskPolicy,
    Side,
    compute_attribution,
    compute_session_metrics,
    compute_slippage,
)


# ---------------------------------------------------------------- helpers


def _bar(ts: float, o: float, h: float, lo: float, c: float, instrument: str = "BINANCE:BTCUSDT") -> dict:
    return {
        "instrument": instrument,
        "ts": ts,
        "open": o,
        "high": h,
        "low": lo,
        "close": c,
        "volume": 1.0,
    }


def _intent(
    *,
    side: Side = Side.BUY,
    qty: float = 1.0,
    type: OrderType = OrderType.MARKET,
    price: float | None = None,
    instrument: str = "BINANCE:BTCUSDT",
    fingerprint: str = "fp_test",
) -> OrderIntent:
    return OrderIntent.make(
        strategy_fingerprint=fingerprint,
        instrument=instrument,
        side=side,
        qty=qty,
        type=type,
        price=price,
    )


def _wire(tmp_path: Path, *, slippage_bps: float = 0.0, commission_bps: float = 0.0):
    adapter = PaperAdapter(
        PaperConfig(slippage_bps=slippage_bps, commission_bps=commission_bps)
    )
    positions = PositionStore()
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = RiskGate(RiskPolicy())
    router = OrderRouter(
        adapter=adapter,
        gate=gate,
        positions=positions,
        audit=audit,
        session_id="sess_test",
    )
    return adapter, positions, audit, router


# ---------------------------------------------------------------- attribution


def test_attribution_long_round_trip(tmp_path: Path) -> None:
    """Long entry + same-instrument exit produces one round trip
    whose PnL matches the position store's realised PnL."""

    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        v1, _ = await router.submit(_intent(side=Side.BUY, qty=2.0))
        await adapter.on_bar(_bar(1, 100, 101, 99, 100))
        v2, _ = await router.submit(_intent(side=Side.SELL, qty=2.0))
        await adapter.on_bar(_bar(2, 110, 111, 109, 110))

    asyncio.run(run())

    events = audit.read_all()
    attr = compute_attribution(events)
    assert attr.trades_count == 1
    trip = attr.trades[0]
    assert trip.side == "long"
    assert trip.qty == 2.0
    assert trip.entry_price == pytest.approx(100.0)
    assert trip.exit_price == pytest.approx(110.0)
    assert trip.pnl == pytest.approx(20.0)
    assert attr.realized_total == pytest.approx(20.0)
    assert attr.fees_total == pytest.approx(0.0)
    assert positions.total_realized() == pytest.approx(attr.realized_total)


def test_attribution_short_round_trip(tmp_path: Path) -> None:
    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(1, 200, 200, 200, 200))
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(2, 180, 180, 180, 180))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert attr.trades_count == 1
    trip = attr.trades[0]
    assert trip.side == "short"
    assert trip.entry_price == pytest.approx(200.0)
    assert trip.exit_price == pytest.approx(180.0)
    assert trip.pnl == pytest.approx(20.0)


def test_attribution_pyramiding_then_close(tmp_path: Path) -> None:
    """Two adds at different prices → weighted-average entry, then
    a single close emits one round trip with the WA entry."""

    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(2, 120, 120, 120, 120))
        await router.submit(_intent(side=Side.SELL, qty=2.0))
        await adapter.on_bar(_bar(3, 130, 130, 130, 130))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert attr.trades_count == 1
    trip = attr.trades[0]
    assert trip.qty == 2.0
    assert trip.entry_price == pytest.approx(110.0)
    assert trip.exit_price == pytest.approx(130.0)
    assert trip.pnl == pytest.approx(40.0)


def test_attribution_partial_close_then_close(tmp_path: Path) -> None:
    """Half-close → second-half-close should emit two round trips,
    each with correct qty and PnL."""

    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=2.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(3, 120, 120, 120, 120))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert attr.trades_count == 2
    pnls = sorted(t.pnl for t in attr.trades)
    assert pnls == pytest.approx([10.0, 20.0])
    assert attr.realized_total == pytest.approx(30.0)


def test_attribution_flip_emits_round_trip_then_opens(tmp_path: Path) -> None:
    """Long 1 → sell 2 closes the long for PnL and opens a fresh
    short for residual qty=1."""

    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=2.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(3, 105, 105, 105, 105))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert attr.trades_count == 2
    long_trip = next(t for t in attr.trades if t.side == "long")
    short_trip = next(t for t in attr.trades if t.side == "short")
    assert long_trip.pnl == pytest.approx(10.0)
    assert short_trip.entry_price == pytest.approx(110.0)
    assert short_trip.exit_price == pytest.approx(105.0)
    assert short_trip.pnl == pytest.approx(5.0)
    assert attr.realized_total == pytest.approx(15.0)


def test_attribution_unrealized_with_mark(tmp_path: Path) -> None:
    """Open-only position picks up unrealised PnL from
    ``mark_prices``."""

    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=2.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))

    asyncio.run(run())

    attr = compute_attribution(
        audit.read_all(), mark_prices={"BINANCE:BTCUSDT": 130.0}
    )
    assert attr.trades_count == 0
    assert attr.realized_total == 0.0
    assert attr.unrealized_total == pytest.approx(60.0)


def test_attribution_buckets_by_strategy_and_instrument(tmp_path: Path) -> None:
    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        # Trade A on fp_alpha
        await router.submit(_intent(side=Side.BUY, qty=1.0, fingerprint="fp_alpha"))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0, fingerprint="fp_alpha"))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))
        # Trade B on fp_beta
        await router.submit(_intent(side=Side.BUY, qty=1.0, fingerprint="fp_beta"))
        await adapter.on_bar(_bar(3, 200, 200, 200, 200))
        await router.submit(_intent(side=Side.SELL, qty=1.0, fingerprint="fp_beta"))
        await adapter.on_bar(_bar(4, 250, 250, 250, 250))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert "fp_alpha" in attr.by_strategy
    assert "fp_beta" in attr.by_strategy
    assert attr.by_strategy["fp_alpha"]["realized"] == pytest.approx(10.0)
    assert attr.by_strategy["fp_beta"]["realized"] == pytest.approx(50.0)
    assert attr.by_instrument["BINANCE:BTCUSDT"]["realized"] == pytest.approx(60.0)
    assert attr.by_instrument["BINANCE:BTCUSDT"]["trades"] == 2.0


def test_attribution_pnl_curve_monotonic_in_time(tmp_path: Path) -> None:
    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=0)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(3, 105, 105, 105, 105))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(4, 100, 100, 100, 100))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    assert len(attr.pnl_curve) == 2
    timestamps = [ts for ts, _ in attr.pnl_curve]
    assert timestamps == sorted(timestamps)
    cumulatives = [cum for _, cum in attr.pnl_curve]
    assert cumulatives[0] == pytest.approx(10.0)
    assert cumulatives[1] == pytest.approx(5.0)


# ---------------------------------------------------------------- slippage


def test_slippage_market_buy_pays_slippage(tmp_path: Path) -> None:
    """Market buy with 5 bps slippage should record a +5 bps
    entry against the bar.open reference."""

    adapter, _positions, audit, router = _wire(tmp_path, slippage_bps=5)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 101, 99, 100))

    asyncio.run(run())

    report = compute_slippage(audit.read_all())
    assert report.fills_total == 1
    assert report.fills_with_reference == 1
    assert report.fills_missing_reference == 0
    assert len(report.entries) == 1
    e = report.entries[0]
    assert e.reference_price == pytest.approx(100.0)
    assert e.fill_price == pytest.approx(100.05)
    assert e.slippage_bps == pytest.approx(5.0)
    assert e.slippage_cost == pytest.approx(0.05)


def test_slippage_market_sell_signed_correctly(tmp_path: Path) -> None:
    """Sell @ slipped-down price should also report POSITIVE
    bps (cost to the trader), not negative."""

    adapter, _positions, audit, router = _wire(tmp_path, slippage_bps=10)

    async def run() -> None:
        await router.submit(_intent(side=Side.SELL, qty=2.0))
        await adapter.on_bar(_bar(1, 100, 101, 99, 100))

    asyncio.run(run())

    report = compute_slippage(audit.read_all())
    assert len(report.entries) == 1
    e = report.entries[0]
    assert e.side == "sell"
    assert e.reference_price == pytest.approx(100.0)
    assert e.fill_price == pytest.approx(99.9)
    assert e.slippage_bps == pytest.approx(10.0)
    assert e.slippage_cost == pytest.approx(0.2)


def test_slippage_aggregates_avg_p50_p95_and_worst(tmp_path: Path) -> None:
    adapter, _positions, audit, router = _wire(tmp_path, slippage_bps=10)

    async def run() -> None:
        for i, ts in enumerate([1, 2, 3, 4, 5], start=1):
            await router.submit(_intent(side=Side.BUY, qty=1.0))
            await adapter.on_bar(_bar(ts, 100 + i, 100 + i, 100 + i, 100 + i))

    asyncio.run(run())

    report = compute_slippage(audit.read_all())
    assert report.fills_with_reference == 5
    assert report.avg_slippage_bps == pytest.approx(10.0)
    assert report.p50_slippage_bps == pytest.approx(10.0)
    assert report.p95_slippage_bps == pytest.approx(10.0)
    assert report.worst_slippage_bps == pytest.approx(10.0)
    assert report.total_slippage_cost > 0
    bucket = report.by_instrument["BINANCE:BTCUSDT"]
    assert bucket["count"] == 5.0
    assert "avg_bps" in bucket


def test_slippage_skips_fills_without_reference() -> None:
    """A live-adapter fill without ``reference_price`` should be
    counted in ``fills_missing_reference`` but excluded from
    bps stats."""

    payload_with_ref = {
        "fill": {
            "fill_id": "fa",
            "order_id": "o1",
            "qty": 1.0,
            "price": 101.0,
            "fee": 0.0,
            "ts": 1.0,
            "reference_price": 100.0,
        },
        "order_status": "filled",
        "position": {"instrument": "INST"},
    }
    payload_no_ref = {
        "fill": {
            "fill_id": "fb",
            "order_id": "o2",
            "qty": 1.0,
            "price": 200.0,
            "fee": 0.0,
            "ts": 2.0,
            "reference_price": None,
        },
        "order_status": "filled",
        "position": {"instrument": "INST"},
    }
    order_a = {
        "order_id": "o1",
        "side": "buy",
        "instrument": "INST",
        "strategy_fingerprint": "fp",
    }
    order_b = {
        "order_id": "o2",
        "side": "sell",
        "instrument": "INST",
        "strategy_fingerprint": "fp",
    }
    events = [
        AuditEvent(ts=1.0, kind="order", intent_id="i1", order_id="o1", payload=order_a),
        AuditEvent(ts=1.0, kind="fill", intent_id="i1", order_id="o1", payload=payload_with_ref),
        AuditEvent(ts=2.0, kind="order", intent_id="i2", order_id="o2", payload=order_b),
        AuditEvent(ts=2.0, kind="fill", intent_id="i2", order_id="o2", payload=payload_no_ref),
    ]

    report = compute_slippage(events)
    assert report.fills_total == 2
    assert report.fills_with_reference == 1
    assert report.fills_missing_reference == 1
    assert len(report.entries) == 1
    assert report.entries[0].slippage_bps == pytest.approx(100.0)


# ---------------------------------------------------------------- session metrics


def test_session_metrics_basic_counts(tmp_path: Path) -> None:
    adapter, positions, audit, router = _wire(tmp_path, slippage_bps=2)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))

    asyncio.run(run())

    metrics = compute_session_metrics(
        audit.read_all(),
        open_positions=positions.open_count(),
        realized_pnl=positions.total_realized(),
        unrealized_pnl=positions.total_unrealized(),
    )
    assert metrics.intents_total == 2
    assert metrics.intents_accepted == 2
    assert metrics.intents_rejected == 0
    assert metrics.acceptance_rate == pytest.approx(1.0)
    assert metrics.orders_total == 2
    assert metrics.fills_total == 2
    assert metrics.cancels_total == 0
    assert metrics.open_positions == 0
    assert metrics.realized_pnl == pytest.approx(positions.total_realized())
    assert metrics.total_slippage_cost > 0
    assert metrics.duration_seconds >= 0.0


def test_session_metrics_handles_empty_audit() -> None:
    """An empty stream should not blow up; all numbers are 0."""

    metrics = compute_session_metrics([])
    assert metrics.intents_total == 0
    assert metrics.acceptance_rate == 0.0
    assert metrics.realized_pnl == 0.0
    assert metrics.duration_seconds == 0.0


def test_session_metrics_counts_rejected_verdicts(tmp_path: Path) -> None:
    """Rejected verdicts should land in ``intents_rejected`` and
    drop the acceptance rate accordingly."""

    adapter = PaperAdapter(PaperConfig(slippage_bps=0))
    positions = PositionStore()
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = RiskGate(RiskPolicy(kill_switch=True))
    router = OrderRouter(
        adapter=adapter,
        gate=gate,
        positions=positions,
        audit=audit,
        session_id="sess_killed",
    )

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))

    asyncio.run(run())

    metrics = compute_session_metrics(audit.read_all())
    assert metrics.intents_total == 1
    assert metrics.intents_accepted == 0
    assert metrics.intents_rejected == 1
    assert metrics.acceptance_rate == 0.0


# ---------------------------------------------------------------- to_dict round trips


def test_attribution_to_dict_is_json_serialisable(tmp_path: Path) -> None:
    import json

    adapter, _positions, audit, router = _wire(tmp_path, slippage_bps=2)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))

    asyncio.run(run())

    attr = compute_attribution(audit.read_all())
    blob = attr.to_dict()
    assert json.loads(json.dumps(blob)) == blob

    slip = compute_slippage(audit.read_all())
    blob2 = slip.to_dict()
    assert json.loads(json.dumps(blob2)) == blob2

    metrics = compute_session_metrics(audit.read_all())
    blob3 = metrics.to_dict()
    assert json.loads(json.dumps(blob3)) == blob3
