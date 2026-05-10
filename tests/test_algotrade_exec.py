"""Tests for the W2 execution layer (paper + risk gate + router + sessions).

These exercise the contract every cockpit + adapter consumes:

- :class:`OrderIntent` is JSON round-trippable; ``make`` mints
  unique idempotent ids.
- :class:`PaperAdapter` fills market orders at next bar's open
  with the configured slippage + commission.
- :class:`PaperAdapter` only fills limit orders when the bar's
  range crosses the price.
- :class:`PositionStore` realises PnL on closing legs and rolls
  over on flips with the right residual sign.
- :class:`RiskGate` blocks: kill switch, allowlist, per-order
  qty cap, no-short policy, position notional cap, max open
  positions, and daily loss kill switch.
- :class:`OrderRouter` audits intent → verdict → order → fill,
  is idempotent on duplicate intent ids, and replays callbacks
  to subscribers.
- :class:`SessionStore` persists across instances via JSONL.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from backend.core.algotrade.exec import (
    AuditLog,
    Fill,
    GateVerdict,
    Order,
    OrderIntent,
    OrderRouter,
    OrderStatus,
    OrderType,
    PaperAdapter,
    PaperConfig,
    Position,
    PositionStore,
    RiskGate,
    RiskPolicy,
    Session,
    SessionStatus,
    SessionStore,
    Side,
)


# -------------------------------------------------------- helpers


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
    sandbox_id: str | None = None,
) -> OrderIntent:
    return OrderIntent.make(
        strategy_fingerprint=fingerprint,
        instrument=instrument,
        side=side,
        qty=qty,
        type=type,
        price=price,
        sandbox_id=sandbox_id,
    )


def _await(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# -------------------------------------------------------- intent


class TestOrderIntent:
    def test_make_assigns_unique_intent_id(self) -> None:
        a = _intent()
        b = _intent()
        assert a.intent_id != b.intent_id
        assert a.intent_id.startswith("intent_")

    def test_to_dict_roundtrip(self) -> None:
        intent = _intent(side=Side.SELL, qty=2.5, type=OrderType.LIMIT, price=100.5)
        payload = intent.to_dict()
        assert payload["side"] == "sell"
        assert payload["type"] == "limit"
        assert payload["price"] == 100.5
        assert payload["qty"] == 2.5
        assert json.dumps(payload)

    def test_make_normalises_side_and_type(self) -> None:
        intent = OrderIntent.make(
            strategy_fingerprint="fp",
            instrument="X",
            side="buy",
            qty=1,
            type="limit",
            price=10,
        )
        assert intent.side is Side.BUY
        assert intent.type is OrderType.LIMIT


# -------------------------------------------------------- paper adapter


class TestPaperAdapter:
    @pytest.mark.asyncio
    async def test_market_order_fills_at_next_bar_open_with_slippage(self) -> None:
        adapter = PaperAdapter(PaperConfig(commission_bps=1.0, slippage_bps=10.0))
        intent = _intent(side=Side.BUY, qty=1.0)
        order = await adapter.submit(intent)
        assert order.status is OrderStatus.NEW
        assert order.fills == []

        fills = await adapter.on_bar(_bar(1, 100.0, 105.0, 99.0, 102.0))
        assert len(fills) == 1
        fill = fills[0]
        assert fill.qty == pytest.approx(1.0)
        assert fill.price == pytest.approx(100.0 * (1 + 10.0 / 10_000))
        assert fill.fee > 0
        order_after = await adapter.status(order.order_id)
        assert order_after.status is OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_market_sell_uses_negative_slippage(self) -> None:
        adapter = PaperAdapter(PaperConfig(slippage_bps=20.0))
        intent = _intent(side=Side.SELL, qty=1.0)
        await adapter.submit(intent)
        fills = await adapter.on_bar(_bar(1, 100.0, 101.0, 99.0, 100.0))
        assert fills[0].price == pytest.approx(100.0 * (1 - 20.0 / 10_000))

    @pytest.mark.asyncio
    async def test_limit_buy_fills_only_when_bar_low_touches_price(self) -> None:
        adapter = PaperAdapter(PaperConfig(slippage_bps=0.0, commission_bps=0.0))
        intent = _intent(type=OrderType.LIMIT, price=99.0, side=Side.BUY)
        order = await adapter.submit(intent)
        assert order.status is OrderStatus.OPEN

        fills = await adapter.on_bar(_bar(1, 100.0, 101.0, 99.5, 100.5))
        assert fills == []
        fills = await adapter.on_bar(_bar(2, 100.0, 100.5, 98.0, 99.5))
        assert len(fills) == 1
        assert fills[0].price <= 99.0

    @pytest.mark.asyncio
    async def test_limit_sell_fills_only_when_bar_high_crosses(self) -> None:
        adapter = PaperAdapter(PaperConfig(slippage_bps=0.0, commission_bps=0.0))
        intent = _intent(type=OrderType.LIMIT, price=110.0, side=Side.SELL)
        await adapter.submit(intent)
        fills = await adapter.on_bar(_bar(1, 100.0, 105.0, 99.0, 102.0))
        assert fills == []
        fills = await adapter.on_bar(_bar(2, 105.0, 112.0, 105.0, 111.0))
        assert len(fills) == 1
        assert fills[0].price >= 110.0

    @pytest.mark.asyncio
    async def test_idempotent_submit_returns_same_order(self) -> None:
        adapter = PaperAdapter()
        intent = _intent()
        a = await adapter.submit(intent)
        b = await adapter.submit(intent)
        assert a.order_id == b.order_id

    @pytest.mark.asyncio
    async def test_cancel_open_limit(self) -> None:
        adapter = PaperAdapter()
        intent = _intent(type=OrderType.LIMIT, price=50.0)
        order = await adapter.submit(intent)
        cancelled = await adapter.cancel(order.order_id)
        assert cancelled.status is OrderStatus.CANCELED
        fills = await adapter.on_bar(_bar(1, 50.0, 51.0, 49.0, 50.0))
        assert fills == []

    @pytest.mark.asyncio
    async def test_limit_without_price_is_rejected(self) -> None:
        adapter = PaperAdapter()
        intent = OrderIntent.make(
            strategy_fingerprint="fp",
            instrument="BINANCE:BTCUSDT",
            side=Side.BUY,
            qty=1.0,
            type=OrderType.LIMIT,
            price=None,
        )
        order = await adapter.submit(intent)
        assert order.status is OrderStatus.REJECTED
        assert "price" in (order.rejection_reason or "")


# -------------------------------------------------------- positions


class TestPositionStore:
    def test_open_long_then_close_realises_pnl(self) -> None:
        store = PositionStore()
        order_open = Order(
            order_id="o1", intent_id="i1", strategy_fingerprint="fp",
            instrument="X", side=Side.BUY, qty=2.0, type=OrderType.MARKET,
            price=None, status=OrderStatus.FILLED, submitted_at=0.0,
        )
        f_open = Fill(fill_id="fa", order_id="o1", qty=2.0, price=100.0, fee=0.0, ts=1)
        store.apply_fill(order_open, f_open)
        pos = store.get("X")
        assert pos.qty == 2.0
        assert pos.avg_price == 100.0

        order_close = Order(
            order_id="o2", intent_id="i2", strategy_fingerprint="fp",
            instrument="X", side=Side.SELL, qty=2.0, type=OrderType.MARKET,
            price=None, status=OrderStatus.FILLED, submitted_at=0.0,
        )
        f_close = Fill(fill_id="fb", order_id="o2", qty=2.0, price=110.0, fee=0.5, ts=2)
        store.apply_fill(order_close, f_close)
        pos = store.get("X")
        assert pos.is_flat()
        assert pos.realized_pnl == pytest.approx(2.0 * 10.0 - 0.5)

    def test_long_to_short_flip_realises_and_opens_residual(self) -> None:
        store = PositionStore()
        store.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="X", side=Side.BUY, qty=1.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=1.0, price=100.0, fee=0.0, ts=1),
        )
        store.apply_fill(
            Order(order_id="o2", intent_id="i2", strategy_fingerprint="fp",
                  instrument="X", side=Side.SELL, qty=3.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fb", order_id="o2", qty=3.0, price=120.0, fee=0.0, ts=2),
        )
        pos = store.get("X")
        assert pos.qty == pytest.approx(-2.0)
        assert pos.avg_price == pytest.approx(120.0)
        assert pos.realized_pnl == pytest.approx(20.0)

    def test_average_price_on_pyramid(self) -> None:
        store = PositionStore()
        store.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="X", side=Side.BUY, qty=1.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=1.0, price=100.0, fee=0.0, ts=1),
        )
        store.apply_fill(
            Order(order_id="o2", intent_id="i2", strategy_fingerprint="fp",
                  instrument="X", side=Side.BUY, qty=1.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fb", order_id="o2", qty=1.0, price=110.0, fee=0.0, ts=2),
        )
        pos = store.get("X")
        assert pos.qty == pytest.approx(2.0)
        assert pos.avg_price == pytest.approx(105.0)

    def test_persistence_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "positions.json"
        store = PositionStore(path=path)
        store.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="X", side=Side.BUY, qty=1.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=1.0, price=100.0, fee=0.0, ts=1),
        )
        assert path.exists()
        reborn = PositionStore(path=path)
        pos = reborn.get("X")
        assert pos is not None
        assert pos.qty == 1.0
        assert pos.avg_price == 100.0

    def test_mark_unrealised_long(self) -> None:
        store = PositionStore()
        store.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="X", side=Side.BUY, qty=2.0, type=OrderType.MARKET,
                  price=None, status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=2.0, price=100.0, fee=0.0, ts=1),
        )
        store.mark("X", 105.0)
        assert store.get("X").unrealized_pnl == pytest.approx(10.0)


# -------------------------------------------------------- risk gate


class TestRiskGate:
    def test_kill_switch_blocks_everything(self) -> None:
        gate = RiskGate(RiskPolicy(kill_switch=True))
        verdict = gate.evaluate(_intent())
        assert not verdict.accepted
        assert "kill_switch" in verdict.triggered_rules

    def test_allowed_instruments_blocks_others(self) -> None:
        gate = RiskGate(RiskPolicy(allowed_instruments=("BINANCE:ETHUSDT",)))
        verdict = gate.evaluate(_intent(instrument="BINANCE:BTCUSDT"))
        assert not verdict.accepted
        assert "allowed_instruments" in verdict.triggered_rules

    def test_max_order_qty_blocks_oversized(self) -> None:
        gate = RiskGate(RiskPolicy(max_order_qty=1.0))
        assert gate.evaluate(_intent(qty=0.5)).accepted
        verdict = gate.evaluate(_intent(qty=2.0))
        assert not verdict.accepted
        assert "max_order_qty" in verdict.triggered_rules

    def test_no_short_blocks_naked_sell(self) -> None:
        gate = RiskGate(RiskPolicy(allow_short=False), positions=PositionStore())
        verdict = gate.evaluate(_intent(side=Side.SELL, qty=1.0))
        assert not verdict.accepted
        assert "allow_short" in verdict.triggered_rules

    def test_no_short_allows_closing_long(self) -> None:
        positions = PositionStore()
        positions.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="BINANCE:BTCUSDT", side=Side.BUY, qty=2.0,
                  type=OrderType.MARKET, price=None,
                  status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=2.0, price=100.0, fee=0.0, ts=1),
        )
        gate = RiskGate(RiskPolicy(allow_short=False), positions=positions)
        assert gate.evaluate(_intent(side=Side.SELL, qty=1.5)).accepted

    def test_max_position_notional(self) -> None:
        gate = RiskGate(
            RiskPolicy(max_position_notional=200.0),
            positions=PositionStore(),
            mark_prices={"BINANCE:BTCUSDT": 110.0},
        )
        ok = gate.evaluate(_intent(qty=1.0))
        assert ok.accepted
        nope = gate.evaluate(_intent(qty=5.0))
        assert not nope.accepted
        assert "max_position_notional" in nope.triggered_rules

    def test_max_open_positions(self) -> None:
        positions = PositionStore()
        positions.apply_fill(
            Order(order_id="o1", intent_id="i1", strategy_fingerprint="fp",
                  instrument="A", side=Side.BUY, qty=1.0,
                  type=OrderType.MARKET, price=None,
                  status=OrderStatus.FILLED, submitted_at=0.0),
            Fill(fill_id="fa", order_id="o1", qty=1.0, price=100.0, fee=0.0, ts=1),
        )
        gate = RiskGate(RiskPolicy(max_open_positions=1), positions=positions)
        verdict = gate.evaluate(_intent(instrument="B"))
        assert not verdict.accepted
        assert "max_open_positions" in verdict.triggered_rules
        assert gate.evaluate(_intent(instrument="A")).accepted

    def test_max_daily_loss_kill(self) -> None:
        positions = PositionStore()
        positions._book["X"] = Position(
            instrument="X", qty=0.0, avg_price=0.0, realized_pnl=-150.0
        )
        gate = RiskGate(RiskPolicy(max_daily_loss=100.0), positions=positions)
        verdict = gate.evaluate(_intent())
        assert not verdict.accepted
        assert "max_daily_loss" in verdict.triggered_rules

    def test_policy_roundtrip(self) -> None:
        original = RiskPolicy(
            max_position_notional=1000.0,
            max_order_qty=5.0,
            max_open_positions=3,
            max_daily_loss=200.0,
            allow_short=False,
            allowed_instruments=("X", "Y"),
            kill_switch=False,
            notes="workshop default",
        )
        roundtripped = RiskPolicy.from_dict(original.to_dict())
        assert roundtripped == original


# -------------------------------------------------------- router


class TestOrderRouter:
    def _wire(self, tmp_path: Path, policy: RiskPolicy | None = None):
        positions = PositionStore(path=tmp_path / "positions.json")
        adapter = PaperAdapter(PaperConfig(slippage_bps=0.0, commission_bps=0.0))
        gate = RiskGate(policy=policy or RiskPolicy(), positions=positions)
        audit = AuditLog(tmp_path / "audit.jsonl")
        router = OrderRouter(
            adapter=adapter,
            gate=gate,
            positions=positions,
            audit=audit,
            session_id="sess_test",
        )
        return router, adapter, positions, audit

    @pytest.mark.asyncio
    async def test_blocked_intent_records_verdict_no_order(self, tmp_path: Path) -> None:
        router, _, _, audit = self._wire(tmp_path, RiskPolicy(kill_switch=True))
        verdict, order = await router.submit(_intent())
        assert order is None
        assert not verdict.accepted
        kinds = [e.kind for e in audit.read_all()]
        assert "intent" in kinds and "verdict" in kinds and "order" not in kinds

    @pytest.mark.asyncio
    async def test_full_flow_audits_intent_verdict_order_fill(self, tmp_path: Path) -> None:
        router, adapter, positions, audit = self._wire(tmp_path)
        verdict, order = await router.submit(_intent())
        assert verdict.accepted
        assert order is not None
        await adapter.on_bar(_bar(1, 100.0, 101.0, 99.0, 100.5))
        events = audit.read_all()
        kinds = [e.kind for e in events]
        assert kinds[:3] == ["intent", "verdict", "order"]
        assert "fill" in kinds
        # the position store sees the fill
        assert positions.get(order.instrument).qty == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_idempotent_submit_returns_same_order(self, tmp_path: Path) -> None:
        router, _, _, audit = self._wire(tmp_path)
        intent = _intent()
        verdict_a, order_a = await router.submit(intent)
        verdict_b, order_b = await router.submit(intent)
        assert order_a.order_id == order_b.order_id
        # second submit logs a replay intent without re-running gate
        kinds = [e.kind for e in audit.read_all()]
        assert kinds.count("verdict") == 1
        assert any(
            e.kind == "intent" and e.payload.get("replay") for e in audit.read_all()
        )

    @pytest.mark.asyncio
    async def test_subscribers_receive_events(self, tmp_path: Path) -> None:
        router, adapter, _, _ = self._wire(tmp_path)
        events: list[str] = []

        async def listener(event):
            events.append(event.kind)

        unsub = router.subscribe(listener)
        await router.submit(_intent())
        await adapter.on_bar(_bar(1, 100.0, 101.0, 99.0, 100.5))
        unsub()
        assert "intent" in events and "fill" in events


# -------------------------------------------------------- sessions


class TestSessionStore:
    def test_create_and_persist(self, tmp_path: Path) -> None:
        path = tmp_path / "sessions.jsonl"
        store = SessionStore(path)
        s = store.create(
            mode="paper",
            strategy_fingerprint="fp_x",
            instrument="X",
            adapter="paper",
            sandbox_id="sb_demo",
        )
        assert s.session_id.startswith("sess_")
        assert s.status is SessionStatus.PENDING
        reborn = SessionStore(path)
        again = reborn.get(s.session_id)
        assert again is not None
        assert again.strategy_fingerprint == "fp_x"
        assert again.sandbox_id == "sb_demo"

    def test_filter_by_mode_and_sandbox(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "s.jsonl")
        store.create(mode="paper", strategy_fingerprint="a", instrument="X",
                     adapter="paper", sandbox_id="sb_a")
        store.create(mode="live", strategy_fingerprint="b", instrument="X",
                     adapter="binance", sandbox_id="sb_b")
        assert len(store.filter(mode="paper")) == 1
        assert len(store.filter(sandbox_id="sb_b")) == 1
        assert len(store.filter()) == 2

    def test_update_status_records_close_time(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "s.jsonl")
        s = store.create(mode="paper", strategy_fingerprint="a",
                         instrument="X", adapter="paper")
        updated = store.update_status(s.session_id, SessionStatus.STOPPED, notes="manual")
        assert updated.status is SessionStatus.STOPPED
        assert updated.closed_at is not None
        assert updated.notes == "manual"


# -------------------------------------------------------- audit log


class TestAuditLog:
    def test_append_and_read(self, tmp_path: Path) -> None:
        log = AuditLog(tmp_path / "audit.jsonl")
        from backend.core.algotrade.exec import AuditEvent
        log.append(AuditEvent(ts=1.0, kind="intent", intent_id="i1",
                              order_id=None, payload={"hello": "world"}))
        log.append(AuditEvent(ts=2.0, kind="verdict", intent_id="i1",
                              order_id=None, payload={"accepted": True}))
        events = log.read_all()
        assert [e.kind for e in events] == ["intent", "verdict"]
        assert log.tail(1)[0].kind == "verdict"
