"""PnL attribution + slippage ledger + session metrics (W3-PR1).

The execution layer (W2-PR1) records every intent / verdict / order /
fill in an immutable per-session JSONL audit log. The analytics
module converts that raw stream into the numbers a quant fund's PM
actually wants to see at end-of-day:

- **PnL attribution** — realised vs unrealised PnL bucketed by
  instrument and strategy_fingerprint, plus a trade ledger of
  closed round-trips and a cumulative PnL curve.
- **Slippage ledger** — per-fill comparison of the strategy's
  *intended* execution price (bar's open for market orders, limit
  price for limit orders) against the actual fill price, in basis
  points and absolute slippage cost.
- **Session metrics** — the headline "show me one number per
  axis" summary the cockpit's session card renders: intents
  emitted, accepted / rejected, fills, open positions, PnL totals,
  slippage cost, bars consumed, wall-clock duration.

Stdlib-only. Reads the audit log via :class:`AuditLog.read_all` so
the analyser is fully decoupled from the in-memory wiring; the
same code can post-process a saved JSONL from a CI run, a
workshop replay, or a long-dead session that left only its file
on disk.

Design notes
------------

- **Trade matching**: the position store uses weighted-average
  entry pricing (long → reduce realises ``(exit - avg_entry) *
  qty``). The trade ledger here mirrors that: a "round trip" is
  the sequence ``open leg(s) → reduce / close leg(s)``. We
  rebuild the position state from fills (replaying the same logic
  as :class:`PositionStore.apply_fill`) and emit one
  :class:`RoundTrip` per closing leg, with the closing leg's
  realised PnL.
- **Strategy attribution**: each fill carries an ``order_id`` but
  not a ``strategy_fingerprint``. We index ``order_id →
  strategy_fingerprint`` from the audit's ``order`` events and
  join on that.
- **Slippage**: requires ``Fill.reference_price``. The paper
  adapter populates it (bar.open for market, limit price for
  limit). Fills without a reference are silently skipped from
  the slippage ledger but still counted in the totals' "missing"
  bucket so the cockpit can warn "live adapter without reference
  prices".
- **No look-ahead**: every metric is computed from data already
  in the audit log at the time the analyser is invoked. There is
  no peek at future bars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .base import AuditEvent


# ---------------------------------------------------------------------
# Trade ledger
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class RoundTrip:
    """One closed (or partially closed) trip through a position.

    A round trip is emitted every time a fill *closes* qty against
    an existing open position (long → reduce / flip, short →
    reduce / flip). Pure adds (long → long add, short → short add)
    do not emit a round trip; they update the running average
    entry instead.
    """

    instrument: str
    strategy_fingerprint: str | None
    side: str  # "long" or "short" — the side that was CLOSED
    qty: float
    entry_price: float
    exit_price: float
    fees: float
    pnl: float
    opened_at: float | None
    closed_at: float
    entry_order_id: str | None
    exit_order_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "strategy_fingerprint": self.strategy_fingerprint,
            "side": self.side,
            "qty": float(self.qty),
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price),
            "fees": float(self.fees),
            "pnl": float(self.pnl),
            "opened_at": (
                None if self.opened_at is None else float(self.opened_at)
            ),
            "closed_at": float(self.closed_at),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
        }


@dataclass(frozen=True)
class PnLAttribution:
    """Aggregate realised + unrealised PnL with breakdowns."""

    realized_total: float
    unrealized_total: float
    fees_total: float
    by_instrument: dict[str, dict[str, float]] = field(default_factory=dict)
    by_strategy: dict[str, dict[str, float]] = field(default_factory=dict)
    trades: tuple[RoundTrip, ...] = ()
    pnl_curve: tuple[tuple[float, float], ...] = ()
    """Cumulative realised PnL ``(ts, cumulative_realised_after_fees)``
    samples — one entry per closing leg, ordered by ``ts``."""

    @property
    def trades_count(self) -> int:
        return len(self.trades)

    def to_dict(self) -> dict[str, Any]:
        return {
            "realized_total": float(self.realized_total),
            "unrealized_total": float(self.unrealized_total),
            "fees_total": float(self.fees_total),
            "trades_count": self.trades_count,
            "by_instrument": {
                k: {kk: float(vv) for kk, vv in v.items()}
                for k, v in self.by_instrument.items()
            },
            "by_strategy": {
                k: {kk: float(vv) for kk, vv in v.items()}
                for k, v in self.by_strategy.items()
            },
            "trades": [t.to_dict() for t in self.trades],
            "pnl_curve": [
                {"ts": float(ts), "cum_realized": float(cum)}
                for ts, cum in self.pnl_curve
            ],
        }


# ---------------------------------------------------------------------
# Slippage ledger
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SlippageEntry:
    """Per-fill slippage record: actual vs reference, in bps + cost."""

    fill_id: str
    order_id: str
    instrument: str
    side: str  # "buy" / "sell"
    qty: float
    fill_price: float
    reference_price: float
    slippage_bps: float
    """Signed slippage in basis points. Positive = adverse to the
    trader (paid more on a buy, received less on a sell)."""
    slippage_cost: float
    """``abs(qty) * (fill - reference)`` for buys, ``abs(qty) *
    (reference - fill)`` for sells. Always signed: positive cost
    = money lost to slippage."""
    ts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "instrument": self.instrument,
            "side": self.side,
            "qty": float(self.qty),
            "fill_price": float(self.fill_price),
            "reference_price": float(self.reference_price),
            "slippage_bps": float(self.slippage_bps),
            "slippage_cost": float(self.slippage_cost),
            "ts": float(self.ts),
        }


@dataclass(frozen=True)
class SlippageReport:
    entries: tuple[SlippageEntry, ...]
    fills_total: int  # all fills seen, including those without reference
    fills_with_reference: int
    fills_missing_reference: int
    total_slippage_cost: float
    avg_slippage_bps: float
    p50_slippage_bps: float
    p95_slippage_bps: float
    worst_slippage_bps: float
    by_instrument: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fills_total": int(self.fills_total),
            "fills_with_reference": int(self.fills_with_reference),
            "fills_missing_reference": int(self.fills_missing_reference),
            "total_slippage_cost": float(self.total_slippage_cost),
            "avg_slippage_bps": float(self.avg_slippage_bps),
            "p50_slippage_bps": float(self.p50_slippage_bps),
            "p95_slippage_bps": float(self.p95_slippage_bps),
            "worst_slippage_bps": float(self.worst_slippage_bps),
            "by_instrument": {
                k: {kk: float(vv) for kk, vv in v.items()}
                for k, v in self.by_instrument.items()
            },
            "entries": [e.to_dict() for e in self.entries],
        }


# ---------------------------------------------------------------------
# Session metrics
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SessionMetrics:
    """Headline numbers for the cockpit's session card."""

    intents_total: int
    intents_accepted: int
    intents_rejected: int
    orders_total: int
    fills_total: int
    cancels_total: int
    bars_consumed: int
    realized_pnl: float
    unrealized_pnl: float
    fees_total: float
    total_slippage_cost: float
    avg_slippage_bps: float
    open_positions: int
    started_at: float | None
    last_event_at: float | None

    @property
    def acceptance_rate(self) -> float:
        if self.intents_total == 0:
            return 0.0
        return self.intents_accepted / self.intents_total

    @property
    def duration_seconds(self) -> float:
        if self.started_at is None or self.last_event_at is None:
            return 0.0
        return max(0.0, self.last_event_at - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intents_total": int(self.intents_total),
            "intents_accepted": int(self.intents_accepted),
            "intents_rejected": int(self.intents_rejected),
            "acceptance_rate": float(self.acceptance_rate),
            "orders_total": int(self.orders_total),
            "fills_total": int(self.fills_total),
            "cancels_total": int(self.cancels_total),
            "bars_consumed": int(self.bars_consumed),
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "fees_total": float(self.fees_total),
            "total_slippage_cost": float(self.total_slippage_cost),
            "avg_slippage_bps": float(self.avg_slippage_bps),
            "open_positions": int(self.open_positions),
            "started_at": (
                None if self.started_at is None else float(self.started_at)
            ),
            "last_event_at": (
                None
                if self.last_event_at is None
                else float(self.last_event_at)
            ),
            "duration_seconds": float(self.duration_seconds),
        }


# ---------------------------------------------------------------------
# Compute API
# ---------------------------------------------------------------------


def compute_attribution(
    events: Iterable[AuditEvent],
    *,
    mark_prices: Mapping[str, float] | None = None,
) -> PnLAttribution:
    """Replay the fill stream to build PnL attribution.

    ``mark_prices`` is an optional ``instrument → mark_price``
    snapshot (typically the last close from the bar feed). When
    present we include unrealised PnL for any still-open positions
    in the totals; otherwise unrealised stays at 0.0.
    """

    events = list(events)
    fills = _ordered_fills(events)
    order_to_strategy = _index_orders(events)
    order_to_side = _index_order_sides(events)
    order_to_instrument = _index_order_instruments(events)
    book: dict[str, _LegState] = {}
    trades: list[RoundTrip] = []
    fees_total = 0.0
    pnl_curve: list[tuple[float, float]] = []
    cum_realized = 0.0

    for ev in fills:
        order_id = ev.order_id or ""
        _, instrument_from_payload, fill = _extract_fill(ev)
        if fill is None:
            continue
        instrument = instrument_from_payload or order_to_instrument.get(order_id)
        if instrument is None:
            continue
        side = order_to_side.get(order_id)
        if side not in ("buy", "sell"):
            continue
        fees_total += float(fill.get("fee", 0.0))
        signed_qty = (
            float(fill["qty"]) if side == "buy" else -float(fill["qty"])
        )
        price = float(fill["price"])
        ts = float(fill.get("ts", ev.ts))
        fee = float(fill.get("fee", 0.0))
        strategy = order_to_strategy.get(order_id)

        leg = book.setdefault(instrument, _LegState())
        new_trades, realized_delta = leg.apply(
            instrument=instrument,
            strategy=strategy,
            order_id=order_id,
            signed_qty=signed_qty,
            price=price,
            fee=fee,
            ts=ts,
        )
        if new_trades:
            trades.extend(new_trades)
            cum_realized += realized_delta
            pnl_curve.append((ts, cum_realized))

    realized_total = sum(t.pnl for t in trades)
    unrealized_total = 0.0
    if mark_prices:
        for instrument, leg in book.items():
            if leg.qty == 0.0:
                continue
            mark = mark_prices.get(instrument)
            if mark is None:
                continue
            if leg.qty > 0:
                unrealized_total += (mark - leg.avg_price) * leg.qty
            else:
                unrealized_total += (leg.avg_price - mark) * abs(leg.qty)

    by_instrument: dict[str, dict[str, float]] = {}
    by_strategy: dict[str, dict[str, float]] = {}
    for t in trades:
        bi = by_instrument.setdefault(
            t.instrument, {"realized": 0.0, "fees": 0.0, "trades": 0.0}
        )
        bi["realized"] += t.pnl
        bi["fees"] += t.fees
        bi["trades"] += 1.0
        key = t.strategy_fingerprint or "<unknown>"
        bs = by_strategy.setdefault(
            key, {"realized": 0.0, "fees": 0.0, "trades": 0.0}
        )
        bs["realized"] += t.pnl
        bs["fees"] += t.fees
        bs["trades"] += 1.0

    return PnLAttribution(
        realized_total=realized_total,
        unrealized_total=unrealized_total,
        fees_total=fees_total,
        by_instrument=by_instrument,
        by_strategy=by_strategy,
        trades=tuple(trades),
        pnl_curve=tuple(pnl_curve),
    )


def compute_slippage(events: Iterable[AuditEvent]) -> SlippageReport:
    """Build the per-fill slippage ledger from audit events."""

    events = list(events)
    fills = _ordered_fills(events)
    side_index = _index_order_sides(events)
    instrument_index = _index_order_instruments(events)

    entries: list[SlippageEntry] = []
    fills_total = 0
    missing = 0

    for ev in fills:
        fills_total += 1
        order_id = ev.order_id or ""
        _, instrument_from_payload, fill = _extract_fill(ev)
        if fill is None:
            missing += 1
            continue
        instrument = instrument_from_payload or instrument_index.get(order_id) or ""
        side = side_index.get(order_id) or ""
        ref = fill.get("reference_price")
        if ref is None:
            missing += 1
            continue
        ref_price = float(ref)
        if ref_price <= 0:
            missing += 1
            continue
        fill_price = float(fill["price"])
        qty = float(fill["qty"])
        if side == "buy":
            slip_bps = (fill_price - ref_price) / ref_price * 10_000.0
            cost = (fill_price - ref_price) * qty
        elif side == "sell":
            slip_bps = (ref_price - fill_price) / ref_price * 10_000.0
            cost = (ref_price - fill_price) * qty
        else:
            missing += 1
            continue
        entries.append(
            SlippageEntry(
                fill_id=str(fill.get("fill_id", "")),
                order_id=order_id,
                instrument=instrument,
                side=side,
                qty=qty,
                fill_price=fill_price,
                reference_price=ref_price,
                slippage_bps=slip_bps,
                slippage_cost=cost,
                ts=float(fill.get("ts", ev.ts)),
            )
        )

    if entries:
        bps_sorted = sorted(e.slippage_bps for e in entries)
        avg_bps = sum(bps_sorted) / len(bps_sorted)
        p50 = bps_sorted[len(bps_sorted) // 2]
        idx95 = max(0, int(round(0.95 * (len(bps_sorted) - 1))))
        p95 = bps_sorted[idx95]
        worst = max(bps_sorted, key=lambda x: x)  # most positive = worst
        total_cost = sum(e.slippage_cost for e in entries)
    else:
        avg_bps = p50 = p95 = worst = 0.0
        total_cost = 0.0

    by_instrument: dict[str, dict[str, float]] = {}
    for e in entries:
        bucket = by_instrument.setdefault(
            e.instrument,
            {"count": 0.0, "total_cost": 0.0, "avg_bps_sum": 0.0},
        )
        bucket["count"] += 1.0
        bucket["total_cost"] += e.slippage_cost
        bucket["avg_bps_sum"] += e.slippage_bps
    for bucket in by_instrument.values():
        if bucket["count"]:
            bucket["avg_bps"] = bucket["avg_bps_sum"] / bucket["count"]
        bucket.pop("avg_bps_sum", None)

    return SlippageReport(
        entries=tuple(entries),
        fills_total=fills_total,
        fills_with_reference=len(entries),
        fills_missing_reference=missing,
        total_slippage_cost=total_cost,
        avg_slippage_bps=avg_bps,
        p50_slippage_bps=p50,
        p95_slippage_bps=p95,
        worst_slippage_bps=worst,
        by_instrument=by_instrument,
    )


def compute_session_metrics(
    events: Iterable[AuditEvent],
    *,
    open_positions: int = 0,
    realized_pnl: float | None = None,
    unrealized_pnl: float | None = None,
    bars_consumed: int | None = None,
    mark_prices: Mapping[str, float] | None = None,
) -> SessionMetrics:
    """Headline metrics for the cockpit session card.

    Pass live numbers (``open_positions``, ``realized_pnl``,
    ``unrealized_pnl``) from the in-memory wiring when available
    so they reflect the latest mark; otherwise we derive
    realised/unrealised from the audit replay (and honour
    ``mark_prices`` for unrealised).
    """

    events = list(events)
    intents = sum(1 for e in events if e.kind == "intent")
    accepted = 0
    rejected = 0
    for e in events:
        if e.kind != "verdict":
            continue
        if bool(e.payload.get("accepted")):
            accepted += 1
        else:
            rejected += 1
    orders_total = sum(1 for e in events if e.kind == "order")
    fills_total = sum(1 for e in events if e.kind == "fill")
    cancels_total = sum(1 for e in events if e.kind == "cancel")

    if bars_consumed is None:
        bars_consumed = sum(
            1
            for e in events
            if e.kind == "bar" or e.payload.get("kind") == "bar"
        )

    started_at = events[0].ts if events else None
    last_event_at = events[-1].ts if events else None

    fees_total = 0.0
    for e in events:
        if e.kind != "fill":
            continue
        fill = e.payload.get("fill") or {}
        fees_total += float(fill.get("fee", 0.0))

    if realized_pnl is None or unrealized_pnl is None:
        attribution = compute_attribution(events, mark_prices=mark_prices)
        if realized_pnl is None:
            realized_pnl = attribution.realized_total
        if unrealized_pnl is None:
            unrealized_pnl = attribution.unrealized_total

    slip = compute_slippage(events)

    return SessionMetrics(
        intents_total=intents,
        intents_accepted=accepted,
        intents_rejected=rejected,
        orders_total=orders_total,
        fills_total=fills_total,
        cancels_total=cancels_total,
        bars_consumed=int(bars_consumed),
        realized_pnl=float(realized_pnl),
        unrealized_pnl=float(unrealized_pnl),
        fees_total=fees_total,
        total_slippage_cost=slip.total_slippage_cost,
        avg_slippage_bps=slip.avg_slippage_bps,
        open_positions=int(open_positions),
        started_at=started_at,
        last_event_at=last_event_at,
    )


# ---------------------------------------------------------------------
# Internal: leg replay
# ---------------------------------------------------------------------


@dataclass
class _LegState:
    """Mirror of :class:`PositionStore.apply_fill` for replay-only use.

    Tracks running ``qty`` (signed), ``avg_price``, the order id
    that opened the current direction, and the open timestamp so
    emitted :class:`RoundTrip` rows have full provenance.
    """

    qty: float = 0.0
    avg_price: float = 0.0
    opened_at: float | None = None
    entry_order_id: str | None = None

    def apply(
        self,
        *,
        instrument: str,
        strategy: str | None,
        order_id: str,
        signed_qty: float,
        price: float,
        fee: float,
        ts: float,
    ) -> tuple[list[RoundTrip], float]:
        """Apply a fill leg; return any emitted round-trips +
        delta to cumulative realised PnL."""

        if abs(self.qty) < 1e-12:
            self.qty = signed_qty
            self.avg_price = price
            self.opened_at = ts
            self.entry_order_id = order_id
            return [], 0.0

        same_direction = (self.qty > 0) == (signed_qty > 0)
        if same_direction:
            new_qty = self.qty + signed_qty
            self.avg_price = (
                self.avg_price * abs(self.qty) + price * abs(signed_qty)
            ) / abs(new_qty)
            self.qty = new_qty
            return [], 0.0

        # Closing leg (or flip)
        closing_qty = min(abs(self.qty), abs(signed_qty))
        side_closed = "long" if self.qty > 0 else "short"
        if self.qty > 0:
            realised = (price - self.avg_price) * closing_qty
        else:
            realised = (self.avg_price - price) * closing_qty
        net = realised - fee
        trip = RoundTrip(
            instrument=instrument,
            strategy_fingerprint=strategy,
            side=side_closed,
            qty=closing_qty,
            entry_price=self.avg_price,
            exit_price=price,
            fees=fee,
            pnl=net,
            opened_at=self.opened_at,
            closed_at=ts,
            entry_order_id=self.entry_order_id,
            exit_order_id=order_id,
        )

        if abs(signed_qty) >= abs(self.qty):
            residual = abs(signed_qty) - abs(self.qty)
            if residual < 1e-12:
                self.qty = 0.0
                self.avg_price = 0.0
                self.opened_at = None
                self.entry_order_id = None
            else:
                self.qty = residual if signed_qty > 0 else -residual
                self.avg_price = price
                self.opened_at = ts
                self.entry_order_id = order_id
        else:
            self.qty = self.qty + signed_qty

        return [trip], net


# ---------------------------------------------------------------------
# Internal: audit indexers
# ---------------------------------------------------------------------


def _ordered_fills(events: Iterable[AuditEvent]) -> list[AuditEvent]:
    """Return only ``fill`` events, sorted by their fill ts (not the
    audit ts, which can drift slightly)."""

    fills = [e for e in events if e.kind == "fill"]
    return sorted(
        fills,
        key=lambda e: float(((e.payload.get("fill") or {}).get("ts") or e.ts)),
    )


def _extract_fill(ev: AuditEvent) -> tuple[str | None, str | None, dict | None]:
    """Pull side / instrument / fill payload out of a fill audit event.

    Side comes from the position payload's `qty` direction (the
    fill payload itself does not carry side; see
    :class:`OrderRouter._handle_fill`).
    """

    fill = ev.payload.get("fill")
    if not isinstance(fill, Mapping):
        return None, None, None
    fill = dict(fill)
    position = ev.payload.get("position") or {}
    instrument = position.get("instrument")
    # Side derivation: we don't have direct side on the fill, but
    # the order_id maps to a side via the order event; the fill
    # event records the position *after* the leg, so we can't read
    # side off it directly. Caller should join via the order event
    # when side matters; we leave side=None here.
    return None, instrument, fill


def _index_orders(events: Iterable[AuditEvent]) -> dict[str, str]:
    """``order_id → strategy_fingerprint`` from order events."""

    out: dict[str, str] = {}
    for ev in events:
        if ev.kind != "order":
            continue
        oid = ev.order_id or ev.payload.get("order_id")
        fp = ev.payload.get("strategy_fingerprint")
        if oid and fp:
            out[str(oid)] = str(fp)
    return out


def _index_order_sides(events: Iterable[AuditEvent]) -> dict[str, str]:
    """``order_id → 'buy'/'sell'`` from order events."""

    out: dict[str, str] = {}
    for ev in events:
        if ev.kind != "order":
            continue
        oid = ev.order_id or ev.payload.get("order_id")
        side = ev.payload.get("side")
        if oid and side:
            out[str(oid)] = str(side)
    return out


def _index_order_instruments(events: Iterable[AuditEvent]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ev in events:
        if ev.kind != "order":
            continue
        oid = ev.order_id or ev.payload.get("order_id")
        instrument = ev.payload.get("instrument")
        if oid and instrument:
            out[str(oid)] = str(instrument)
    return out
