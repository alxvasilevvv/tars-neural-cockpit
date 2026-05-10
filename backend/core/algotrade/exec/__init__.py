"""Execution layer — paper + live adapters, router, positions, audit.

The W1a backtest engine and the W2 paper / live executors share the
same building blocks (:class:`Bar`, :class:`Strategy` IR, indicators)
so the path from \"my backtest looks great\" → \"send a real order\" has
zero translation surface. The only thing that changes between
backtest, paper, and live is which :class:`ExecAdapter`
implementation the :class:`OrderRouter` is wired to.

W2-PR1 ships:

- :class:`OrderIntent`, :class:`Order`, :class:`Fill`,
  :class:`Position`, :class:`AuditEvent` dataclasses (the wire
  contract every adapter and the cockpit consume).
- :class:`PaperAdapter` — accepts intents, fills market orders at
  the next bar's open with configurable slippage, fills limit
  orders when the bar's range crosses the price.
- :class:`PositionStore` — single-process, instrument-keyed open
  position book with realised/unrealised PnL accounting.
- :class:`OrderRouter` — gate → adapter → audit pipeline.
- :class:`AuditLog` — append-only JSONL of every intent / verdict /
  order / fill, scoped per session for clean audit exports.
- :class:`SessionStore` — lightweight session metadata
  (id, mode, strategy fingerprint, started_at, status).

W2-PR2 will add the Binance live adapter behind a vault key.

W3-PR1 ships analytics on top of the audit log:

- :class:`PnLAttribution` — realised + unrealised PnL bucketed
  by instrument and strategy_fingerprint, plus a :class:`RoundTrip`
  ledger and a cumulative PnL curve.
- :class:`SlippageReport` — per-fill comparison of fill price vs
  the strategy's intended reference price (bar.open for market,
  limit price for limit), in basis points + cost.
- :class:`SessionMetrics` — headline counters for the cockpit
  session card.
"""

from .analytics import (
    PnLAttribution,
    RoundTrip,
    SessionMetrics,
    SlippageEntry,
    SlippageReport,
    compute_attribution,
    compute_session_metrics,
    compute_slippage,
)
from .base import (
    AuditEvent,
    ExecAdapter,
    Fill,
    Order,
    OrderIntent,
    OrderStatus,
    OrderType,
    Position,
    Side,
)
from .paper import PaperAdapter, PaperConfig
from .positions import PositionStore
from .risk import GateVerdict, RiskGate, RiskPolicy
from .router import AuditLog, OrderRouter
from .runtime import ExecRuntime, get_runtime, reset_runtime
from .sessions import Session, SessionStatus, SessionStore

__all__ = [
    "AuditEvent",
    "AuditLog",
    "ExecAdapter",
    "ExecRuntime",
    "Fill",
    "GateVerdict",
    "Order",
    "OrderIntent",
    "OrderRouter",
    "OrderStatus",
    "OrderType",
    "PaperAdapter",
    "PaperConfig",
    "PnLAttribution",
    "Position",
    "PositionStore",
    "RiskGate",
    "RiskPolicy",
    "RoundTrip",
    "Session",
    "SessionMetrics",
    "SessionStatus",
    "SessionStore",
    "Side",
    "SlippageEntry",
    "SlippageReport",
    "compute_attribution",
    "compute_session_metrics",
    "compute_slippage",
    "get_runtime",
    "reset_runtime",
]
