"""PositionStore — instrument-keyed open position book.

Single-process, in-memory. Mutated by the :class:`OrderRouter`
(or directly by the paper / live adapters during fill ingestion).
Persists to JSON on flush so a restart can reconstruct the book
without replaying the audit log.

PnL accounting:

- Long → Long add: weighted-average entry price.
- Long → reduce / close: realised PnL = ``(exit - entry) * qty``.
- Long → Short flip: realised PnL on the closing leg, then a fresh
  short opens for the residual qty.
- Symmetric for short legs.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterator

from .base import Fill, Order, Position, Side


class PositionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._book: dict[str, Position] = {}
        self._path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                self._load(path)

    # -------------------------------------------------------- read

    def get(self, instrument: str) -> Position | None:
        return self._book.get(instrument)

    def all(self) -> list[Position]:
        return list(self._book.values())

    def __iter__(self) -> Iterator[Position]:
        return iter(list(self._book.values()))

    def __len__(self) -> int:
        return sum(1 for p in self._book.values() if not p.is_flat())

    def open_count(self) -> int:
        return len(self)

    # -------------------------------------------------------- write

    def apply_fill(self, order: Order, fill: Fill) -> Position:
        """Mutate the book to reflect ``fill`` on ``order``. Returns
        the position row after mutation."""

        with self._lock:
            pos = self._book.setdefault(
                order.instrument, Position(instrument=order.instrument)
            )
            signed_qty = fill.qty if order.side is Side.BUY else -fill.qty

            if pos.is_flat():
                pos.qty = signed_qty
                pos.avg_price = fill.price
                pos.opened_at = fill.ts
            else:
                same_direction = (pos.qty > 0) == (signed_qty > 0)
                if same_direction:
                    new_qty = pos.qty + signed_qty
                    pos.avg_price = (
                        pos.avg_price * abs(pos.qty)
                        + fill.price * abs(signed_qty)
                    ) / abs(new_qty)
                    pos.qty = new_qty
                else:
                    closing_qty = min(abs(pos.qty), abs(signed_qty))
                    if pos.qty > 0:
                        realised = (fill.price - pos.avg_price) * closing_qty
                    else:
                        realised = (pos.avg_price - fill.price) * closing_qty
                    pos.realized_pnl += realised - fill.fee
                    if abs(signed_qty) >= abs(pos.qty):
                        residual = abs(signed_qty) - abs(pos.qty)
                        pos.qty = (
                            residual if signed_qty > 0 else -residual
                        )
                        if pos.is_flat():
                            pos.avg_price = 0.0
                            pos.opened_at = None
                        else:
                            pos.avg_price = fill.price
                            pos.opened_at = fill.ts
                    else:
                        new_qty = pos.qty + signed_qty
                        pos.qty = new_qty

            pos.last_update_ts = fill.ts
            pos.fills.append(fill)
            self._maybe_persist()
            return pos

    def mark(self, instrument: str, mark_price: float) -> Position | None:
        with self._lock:
            pos = self._book.get(instrument)
            if pos is None or pos.is_flat():
                return pos
            if pos.qty > 0:
                pos.unrealized_pnl = (mark_price - pos.avg_price) * pos.qty
            else:
                pos.unrealized_pnl = (pos.avg_price - mark_price) * abs(pos.qty)
            return pos

    def total_unrealized(self) -> float:
        return sum(p.unrealized_pnl for p in self._book.values())

    def total_realized(self) -> float:
        return sum(p.realized_pnl for p in self._book.values())

    # -------------------------------------------------------- io

    def _maybe_persist(self) -> None:
        if self._path is None:
            return
        payload = {
            ins: pos.to_dict() for ins, pos in self._book.items()
        }
        self._path.write_text(json.dumps(payload, indent=2))

    def _load(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for ins, raw in payload.items():
            self._book[ins] = Position(
                instrument=str(raw.get("instrument", ins)),
                qty=float(raw.get("qty", 0.0)),
                avg_price=float(raw.get("avg_price", 0.0)),
                realized_pnl=float(raw.get("realized_pnl", 0.0)),
                unrealized_pnl=float(raw.get("unrealized_pnl", 0.0)),
                opened_at=(
                    None
                    if raw.get("opened_at") is None
                    else float(raw["opened_at"])
                ),
                last_update_ts=float(raw.get("last_update_ts", 0.0)),
                fills=[
                    Fill(
                        fill_id=str(f["fill_id"]),
                        order_id=str(f["order_id"]),
                        qty=float(f["qty"]),
                        price=float(f["price"]),
                        fee=float(f.get("fee", 0.0)),
                        ts=float(f["ts"]),
                        reference_price=(
                            None
                            if f.get("reference_price") is None
                            else float(f["reference_price"])
                        ),
                    )
                    for f in raw.get("fills", [])
                ],
            )
