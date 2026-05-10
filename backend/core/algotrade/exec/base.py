"""Execution layer base types.

Stdlib-only. The dataclasses here are the contract every adapter
(paper / live Binance / live IBKR / live Coinbase) and every UI
surface (cockpit live order panel, PnL strip, audit viewer)
exchanges. There is exactly one source of truth.

Design principles:

- **Idempotency keys.** Every :class:`OrderIntent` carries a
  client-generated ``intent_id`` that the router de-dupes on. A
  retry submitting the same intent never produces a second
  order.
- **Frozen by default.** Mutability lives in :class:`Order` (fills
  arrive over time) and :class:`Position` (avg_price evolves);
  everything else is frozen so accidental mutation can't cause
  drift between cockpit and audit.
- **JSON-serialisable.** Every type ships ``to_dict()`` so
  ``/api/algotrade/sessions/<id>/stream`` SSE events serialise as
  one line of JSON. Re-hydration uses ``from_dict``.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELED = "canceled"
    REJECTED = "rejected"


# --------------------------------------------------------- intent / verdict


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class OrderIntent:
    """What the strategy / operator WANTS — pre-gate.

    The router is the only thing that constructs an :class:`Order`
    from an :class:`OrderIntent`. The intent is the audit anchor.
    """

    intent_id: str
    strategy_fingerprint: str
    instrument: str  # e.g. "BINANCE:BTCUSDT"
    side: Side
    qty: float
    type: OrderType = OrderType.MARKET
    price: float | None = None  # required for LIMIT
    time_in_force: str = "GTC"  # GTC / IOC / FOK — paper supports GTC + IOC
    requested_at: float = 0.0
    sandbox_id: str | None = None  # workshop multi-tenant key
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "strategy_fingerprint": self.strategy_fingerprint,
            "instrument": self.instrument,
            "side": self.side.value,
            "qty": float(self.qty),
            "type": self.type.value,
            "price": None if self.price is None else float(self.price),
            "time_in_force": self.time_in_force,
            "requested_at": float(self.requested_at),
            "sandbox_id": self.sandbox_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def make(
        cls,
        *,
        strategy_fingerprint: str,
        instrument: str,
        side: Side | str,
        qty: float,
        type: OrderType | str = OrderType.MARKET,
        price: float | None = None,
        sandbox_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OrderIntent":
        import time

        return cls(
            intent_id=_new_id("intent"),
            strategy_fingerprint=str(strategy_fingerprint),
            instrument=str(instrument),
            side=Side(side) if not isinstance(side, Side) else side,
            qty=float(qty),
            type=OrderType(type) if not isinstance(type, OrderType) else type,
            price=None if price is None else float(price),
            requested_at=time.time(),
            sandbox_id=sandbox_id,
            metadata=dict(metadata or {}),
        )


# --------------------------------------------------------- fill


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    qty: float
    price: float
    fee: float
    ts: float
    reference_price: float | None = None
    """The "ideal" price the strategy would have wanted at the moment
    the fill landed: the bar's open for market orders, the limit
    price for limit orders. Optional so live adapters that can't
    derive it leave it ``None``; the slippage ledger silently
    skips fills without a reference rather than fabricating one.
    """

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "qty": float(self.qty),
            "price": float(self.price),
            "fee": float(self.fee),
            "ts": float(self.ts),
            "reference_price": (
                None
                if self.reference_price is None
                else float(self.reference_price)
            ),
        }


# --------------------------------------------------------- order


@dataclass
class Order:
    """Lifecycle envelope: spans an intent's submission → fills → close.

    Fills arrive incrementally; the engine appends them and
    derives ``status`` from the cumulative filled qty:

    - ``filled`` when sum(fills.qty) == intent qty.
    - ``partial`` when sum(fills.qty) ∈ (0, intent qty).
    - ``open`` when 0 fills and not canceled / rejected.
    """

    order_id: str
    intent_id: str
    strategy_fingerprint: str
    instrument: str
    side: Side
    qty: float
    type: OrderType
    price: float | None
    status: OrderStatus
    submitted_at: float
    fills: list[Fill] = field(default_factory=list)
    closed_at: float | None = None
    rejection_reason: str | None = None

    def filled_qty(self) -> float:
        return sum(f.qty for f in self.fills)

    def avg_fill_price(self) -> float | None:
        total_qty = self.filled_qty()
        if total_qty == 0:
            return None
        return sum(f.qty * f.price for f in self.fills) / total_qty

    def total_fees(self) -> float:
        return sum(f.fee for f in self.fills)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "intent_id": self.intent_id,
            "strategy_fingerprint": self.strategy_fingerprint,
            "instrument": self.instrument,
            "side": self.side.value,
            "qty": float(self.qty),
            "type": self.type.value,
            "price": None if self.price is None else float(self.price),
            "status": self.status.value,
            "submitted_at": float(self.submitted_at),
            "fills": [f.to_dict() for f in self.fills],
            "closed_at": (
                None if self.closed_at is None else float(self.closed_at)
            ),
            "rejection_reason": self.rejection_reason,
            "filled_qty": self.filled_qty(),
            "avg_fill_price": self.avg_fill_price(),
            "total_fees": self.total_fees(),
        }


# --------------------------------------------------------- position


@dataclass
class Position:
    """Open position book entry, mutated as fills arrive.

    The store keeps one row per ``instrument``. Going from long to
    short (or vice versa) realises PnL on the closing leg first
    and then opens a new entry at the remaining qty.
    """

    instrument: str
    qty: float = 0.0  # signed: + long, - short
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: float | None = None
    last_update_ts: float = 0.0
    fills: list[Fill] = field(default_factory=list)

    def is_flat(self) -> bool:
        return abs(self.qty) < 1e-12

    def notional(self, mark_price: float) -> float:
        return abs(self.qty) * mark_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "qty": float(self.qty),
            "avg_price": float(self.avg_price),
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "opened_at": (
                None if self.opened_at is None else float(self.opened_at)
            ),
            "last_update_ts": float(self.last_update_ts),
            "fills": [f.to_dict() for f in self.fills],
        }


# --------------------------------------------------------- audit


@dataclass(frozen=True)
class AuditEvent:
    """One row in the per-session audit ledger."""

    ts: float
    kind: str  # "intent" | "verdict" | "order" | "fill" | "cancel" | "reject"
    intent_id: str | None
    order_id: str | None
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": float(self.ts),
            "kind": self.kind,
            "intent_id": self.intent_id,
            "order_id": self.order_id,
            "payload": dict(self.payload),
        }


# --------------------------------------------------------- adapter ABC


class ExecAdapter(ABC):
    """Contract every executor (paper / live Binance / IBKR / …) implements.

    Adapters are stateful — they accept intents, return :class:`Order`
    objects, and emit :class:`Fill` updates over a callback. Adapters
    do **not** call the risk gate; the :class:`OrderRouter` does that
    upstream.
    """

    name: str = "abstract"

    @abstractmethod
    async def submit(self, intent: OrderIntent) -> Order:
        """Translate an intent into an order, send it, return the
        initial :class:`Order` envelope. Fills may or may not be
        present in the return value (market orders typically fill
        synchronously in paper mode; limit orders almost never do)."""

    @abstractmethod
    async def cancel(self, order_id: str) -> Order:
        """Cancel an open order. Idempotent: cancelling a
        terminal-state order returns the existing envelope
        unchanged."""

    @abstractmethod
    async def status(self, order_id: str) -> Order | None:
        """Return the current envelope, or ``None`` if the adapter
        has no record of the order."""

    def on_fill(self, callback: Callable[[Order, Fill], Awaitable[None]]) -> None:
        """Register a callback invoked every time the adapter emits
        a fresh fill. Implementations override if they support
        async fill streams."""

        self._on_fill = callback  # type: ignore[attr-defined]
