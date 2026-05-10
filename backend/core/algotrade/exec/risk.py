"""Risk Gate — pre-trade policy enforcement.

Every :class:`OrderIntent` flows through ``RiskGate.evaluate``
before it's handed to an :class:`ExecAdapter`. The gate produces
a :class:`GateVerdict` with a verdict and human-readable reason,
which the router both audits and surfaces to the cockpit.

Workshop policies (intentionally explicit so attendees can audit):

- ``max_position_notional`` — abs notional per instrument cap.
- ``max_order_qty`` — single-order qty ceiling.
- ``max_open_positions`` — global open position count.
- ``max_daily_loss`` — kill switch on cumulative realised PnL.
- ``allow_short`` — disables sells that would open / extend a short.
- ``allowed_instruments`` — whitelist (None = wide open).
- ``kill_switch`` — operator-controlled hard stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .base import OrderIntent, Side
from .positions import PositionStore


@dataclass
class RiskPolicy:
    max_position_notional: float | None = None
    max_order_qty: float | None = None
    max_open_positions: int | None = None
    max_daily_loss: float | None = None
    allow_short: bool = True
    allowed_instruments: tuple[str, ...] | None = None
    kill_switch: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "max_position_notional": self.max_position_notional,
            "max_order_qty": self.max_order_qty,
            "max_open_positions": self.max_open_positions,
            "max_daily_loss": self.max_daily_loss,
            "allow_short": self.allow_short,
            "allowed_instruments": (
                None
                if self.allowed_instruments is None
                else list(self.allowed_instruments)
            ),
            "kill_switch": self.kill_switch,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "RiskPolicy":
        if not data:
            return cls()
        instruments = data.get("allowed_instruments")
        return cls(
            max_position_notional=data.get("max_position_notional"),
            max_order_qty=data.get("max_order_qty"),
            max_open_positions=data.get("max_open_positions"),
            max_daily_loss=data.get("max_daily_loss"),
            allow_short=bool(data.get("allow_short", True)),
            allowed_instruments=(
                None if instruments is None else tuple(str(i) for i in instruments)
            ),
            kill_switch=bool(data.get("kill_switch", False)),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class GateVerdict:
    accepted: bool
    reason: str
    policy_snapshot: dict = field(default_factory=dict)
    triggered_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "policy_snapshot": dict(self.policy_snapshot),
            "triggered_rules": list(self.triggered_rules),
        }


class RiskGate:
    """Stateless evaluator (modulo the policy + position book it
    references). Safe to share across sessions; not thread-safe
    against concurrent policy mutation, so :class:`OrderRouter`
    serialises updates."""

    def __init__(
        self,
        policy: RiskPolicy | None = None,
        positions: PositionStore | None = None,
        mark_prices: dict[str, float] | None = None,
    ) -> None:
        self.policy = policy or RiskPolicy()
        self.positions = positions
        self.mark_prices = dict(mark_prices or {})

    def update_mark(self, instrument: str, price: float) -> None:
        self.mark_prices[instrument] = float(price)

    def update_marks(self, marks: dict[str, float]) -> None:
        for inst, px in marks.items():
            self.mark_prices[inst] = float(px)

    def set_policy(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def evaluate(self, intent: OrderIntent) -> GateVerdict:
        triggered: list[str] = []
        reasons: list[str] = []
        snap = self.policy.to_dict()

        if self.policy.kill_switch:
            triggered.append("kill_switch")
            reasons.append("kill switch is engaged")

        if (
            self.policy.allowed_instruments is not None
            and intent.instrument not in self.policy.allowed_instruments
        ):
            triggered.append("allowed_instruments")
            reasons.append(
                f"instrument {intent.instrument!r} not in allowlist"
            )

        if (
            self.policy.max_order_qty is not None
            and intent.qty > self.policy.max_order_qty
        ):
            triggered.append("max_order_qty")
            reasons.append(
                f"qty {intent.qty} exceeds per-order cap "
                f"{self.policy.max_order_qty}"
            )

        if not self.policy.allow_short and intent.side is Side.SELL:
            current_qty = 0.0
            if self.positions is not None:
                pos = self.positions.get(intent.instrument)
                if pos is not None:
                    current_qty = pos.qty
            if intent.qty > max(current_qty, 0.0):
                triggered.append("allow_short")
                reasons.append(
                    "policy disallows opening / extending shorts"
                )

        if (
            self.policy.max_position_notional is not None
            and self.positions is not None
        ):
            pos = self.positions.get(intent.instrument)
            current_qty = 0.0 if pos is None else pos.qty
            delta = intent.qty if intent.side is Side.BUY else -intent.qty
            projected_qty = abs(current_qty + delta)
            mark = self.mark_prices.get(intent.instrument) or intent.price
            if mark is not None:
                projected_notional = projected_qty * mark
                if projected_notional > self.policy.max_position_notional:
                    triggered.append("max_position_notional")
                    reasons.append(
                        f"projected notional {projected_notional:.2f} "
                        f"exceeds cap {self.policy.max_position_notional}"
                    )

        if (
            self.policy.max_open_positions is not None
            and self.positions is not None
        ):
            existing = sum(
                1 for p in self.positions.all() if not p.is_flat()
            )
            pos = self.positions.get(intent.instrument)
            opens_new = pos is None or pos.is_flat()
            if opens_new and existing >= self.policy.max_open_positions:
                triggered.append("max_open_positions")
                reasons.append(
                    f"open positions {existing} ≥ cap "
                    f"{self.policy.max_open_positions}"
                )

        if (
            self.policy.max_daily_loss is not None
            and self.positions is not None
        ):
            realised = sum(p.realized_pnl for p in self.positions.all())
            if realised <= -abs(self.policy.max_daily_loss):
                triggered.append("max_daily_loss")
                reasons.append(
                    f"daily loss {realised:.2f} ≤ "
                    f"-{self.policy.max_daily_loss}"
                )

        accepted = not triggered
        reason = "ok" if accepted else "; ".join(reasons)
        return GateVerdict(
            accepted=accepted,
            reason=reason,
            policy_snapshot=snap,
            triggered_rules=tuple(triggered),
        )

    @staticmethod
    def reject_reasons(verdicts: Iterable[GateVerdict]) -> list[str]:
        return [v.reason for v in verdicts if not v.accepted]
