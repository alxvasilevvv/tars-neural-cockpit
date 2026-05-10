"""PaperAdapter — bar-driven simulated executor.

The paper adapter consumes the same ``Bar`` stream a backtest
does, but its time loop is driven by the runner (one bar at a
time, called from a background asyncio task in the FastAPI
worker or from a CLI loop). Every call to :meth:`on_bar`:

1. Marks open positions with the bar close.
2. Tries to fill any open limit orders whose price falls inside
   ``[bar.low, bar.high]``.
3. Returns the list of fills produced this bar so the runner
   can fan-out audit + cockpit events.

Market orders submitted between bars are filled at the *next*
bar's open with optional slippage and a deterministic commission.
That mirrors the W1a backtest harness so paper PnL ≈ backtest PnL
for the same strategy, modulo whatever the live data diverges.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .base import (
    AuditEvent,
    ExecAdapter,
    Fill,
    Order,
    OrderIntent,
    OrderStatus,
    OrderType,
    Side,
)


@dataclass
class PaperConfig:
    commission_bps: float = 1.0  # 1 bp = 0.01% per side
    slippage_bps: float = 2.0    # market orders cross by this much
    starting_cash: float = 100_000.0
    name: str = "paper"


@dataclass
class _Bar:
    instrument: str
    ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @classmethod
    def from_dict(cls, instrument: str, raw: dict) -> "_Bar":
        return cls(
            instrument=instrument,
            ts=float(raw.get("ts", raw.get("time", 0.0))),
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw.get("volume", 0.0)),
        )


class PaperAdapter(ExecAdapter):
    """Stateful paper executor. One instance per session."""

    def __init__(
        self,
        config: PaperConfig | None = None,
        *,
        on_fill: Callable[[Order, Fill], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config or PaperConfig()
        self.name = self.config.name
        self._orders: dict[str, Order] = {}
        self._intent_to_order: dict[str, str] = {}
        self._pending_market: list[str] = []
        self._open_limit: list[str] = []
        self._lock = asyncio.Lock()
        self._on_fill = on_fill

    # ----------------------------------------------------- adapter API

    async def submit(self, intent: OrderIntent) -> Order:
        async with self._lock:
            if intent.intent_id in self._intent_to_order:
                return self._orders[self._intent_to_order[intent.intent_id]]

            order = Order(
                order_id=f"ord_{uuid.uuid4().hex[:12]}",
                intent_id=intent.intent_id,
                strategy_fingerprint=intent.strategy_fingerprint,
                instrument=intent.instrument,
                side=intent.side,
                qty=float(intent.qty),
                type=intent.type,
                price=intent.price,
                status=OrderStatus.NEW,
                submitted_at=time.time(),
            )
            self._orders[order.order_id] = order
            self._intent_to_order[intent.intent_id] = order.order_id

            if order.type is OrderType.MARKET:
                self._pending_market.append(order.order_id)
            else:
                if order.price is None:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = "limit order requires price"
                    order.closed_at = time.time()
                    return order
                order.status = OrderStatus.OPEN
                self._open_limit.append(order.order_id)

            return order

    async def cancel(self, order_id: str) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise KeyError(order_id)
            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            ):
                return order
            order.status = OrderStatus.CANCELED
            order.closed_at = time.time()
            self._discard(order_id)
            return order

    async def status(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    # ----------------------------------------------------- bar engine

    async def on_bar(self, bar_dict: dict, *, instrument: str | None = None) -> list[Fill]:
        """Advance simulated time by one bar; emit any fills produced."""

        async with self._lock:
            instrument = instrument or bar_dict.get("instrument") or ""
            bar = _Bar.from_dict(instrument, bar_dict)
            fills: list[Fill] = []

            for order_id in list(self._pending_market):
                order = self._orders.get(order_id)
                if order is None or order.instrument != bar.instrument:
                    continue
                fill = self._fill_market(order, bar)
                if fill is not None:
                    fills.append(fill)
                self._pending_market.remove(order_id)

            for order_id in list(self._open_limit):
                order = self._orders.get(order_id)
                if order is None or order.instrument != bar.instrument:
                    continue
                fill = self._fill_limit(order, bar)
                if fill is not None:
                    fills.append(fill)
                    self._open_limit.remove(order_id)

        for order, fill in [(self._orders[f.order_id], f) for f in fills]:
            if self._on_fill is not None:
                await self._on_fill(order, fill)
        return fills

    # ----------------------------------------------------- internals

    def _fill_market(self, order: Order, bar: _Bar) -> Fill | None:
        slip = self.config.slippage_bps / 10_000.0
        price = bar.open * (1 + slip) if order.side is Side.BUY else bar.open * (1 - slip)
        fee = price * order.qty * (self.config.commission_bps / 10_000.0)
        fill = Fill(
            fill_id=f"fil_{uuid.uuid4().hex[:12]}",
            order_id=order.order_id,
            qty=order.qty,
            price=price,
            fee=fee,
            ts=bar.ts,
        )
        order.fills.append(fill)
        order.status = OrderStatus.FILLED
        order.closed_at = bar.ts
        return fill

    def _fill_limit(self, order: Order, bar: _Bar) -> Fill | None:
        if order.price is None:
            return None
        if order.side is Side.BUY:
            if bar.low <= order.price:
                fill_price = min(order.price, bar.open)
            else:
                return None
        else:
            if bar.high >= order.price:
                fill_price = max(order.price, bar.open)
            else:
                return None

        fee = fill_price * order.qty * (self.config.commission_bps / 10_000.0)
        fill = Fill(
            fill_id=f"fil_{uuid.uuid4().hex[:12]}",
            order_id=order.order_id,
            qty=order.qty,
            price=fill_price,
            fee=fee,
            ts=bar.ts,
        )
        order.fills.append(fill)
        order.status = OrderStatus.FILLED
        order.closed_at = bar.ts
        return fill

    def _discard(self, order_id: str) -> None:
        if order_id in self._pending_market:
            self._pending_market.remove(order_id)
        if order_id in self._open_limit:
            self._open_limit.remove(order_id)

    # ----------------------------------------------------- introspection

    def open_orders(self) -> list[Order]:
        return [
            self._orders[oid]
            for oid in (self._open_limit + self._pending_market)
            if oid in self._orders
        ]

    def all_orders(self) -> list[Order]:
        return list(self._orders.values())
