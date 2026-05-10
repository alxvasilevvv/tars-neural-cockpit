"""Strategy Intermediate Representation.

A `Strategy` is a JSON-serialisable, hash-stable description of an
algorithmic trading rule. The backtest engine, the live executor,
the risk gate, the council voices, and the cockpit visualiser all
operate on the **same** IR. There is no second source of truth.

Hard requirements:

- **Hashable**. ``Strategy.fingerprint()`` returns a stable
  ``sha256:…`` digest used to cache backtests, dedupe registry
  entries, and pin trace context.
- **Round-trippable**. ``Strategy.to_dict() → from_dict() → to_dict()``
  is bit-identical. JSON keys are sorted; nothing depends on
  insertion order.
- **Closed-world enums**. Indicator / operator / sizing names are
  enums — typos fail at IR parse time, not at backtest time.
- **No imperative escape hatch**. The IR is data. To extend the
  language you add an enum value + a handler, not a Python lambda
  inside a JSON file.

This file is stdlib-only on purpose. The backtest engine (sister
module) imports it without any third-party dependency.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class StrategyError(ValueError):
    """Raised when an IR fails validation."""


# --------------------------------------------------------- enums


class Timeframe(str, Enum):
    """Bar timeframe. Stored as the canonical short string so the
    JSON shape is human-friendly (``"4h"`` not ``"FOUR_HOURS"``)."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class Action(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    REBALANCE = "rebalance"  # reserved for future portfolio rules


class Operator(str, Enum):
    """Comparison / boolean operators valid inside :class:`Condition`."""

    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    EQ = "eq"
    AND = "and"
    OR = "or"
    NOT = "not"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


_BOOLEAN_OPS = {Operator.AND, Operator.OR, Operator.NOT}
_BINARY_COMPARE = {
    Operator.LT,
    Operator.LE,
    Operator.GT,
    Operator.GE,
    Operator.EQ,
    Operator.CROSSES_ABOVE,
    Operator.CROSSES_BELOW,
}


# --------------------------------------------------------- expression nodes


@dataclass(frozen=True)
class Constant:
    """Literal numeric value inside a condition."""

    value: float

    def to_dict(self) -> dict[str, Any]:
        return {"const": float(self.value)}


@dataclass(frozen=True)
class Indicator:
    """Reference to a series produced by a known indicator.

    Examples:
      ``Indicator(name="close")`` — the bar's close (no params).
      ``Indicator(name="sma", params={"period": 20})`` — 20-bar SMA.
      ``Indicator(name="bb_lower", params={"period": 20, "k": 2})``.

    Backtest indicators are resolved by name in
    ``backend/core/algotrade/backtest/indicators.py``.
    """

    name: str
    params: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"indicator": self.name}
        if self.params:
            out["params"] = {
                k: _coerce_param(v) for k, v in sorted(self.params.items())
            }
        return out


def _coerce_param(value: Any) -> float | int:
    if isinstance(value, bool):  # bool is an int subclass — guard explicitly
        return int(value)
    if isinstance(value, (int, float)):
        return value
    raise StrategyError(
        f"indicator param must be int/float, got {type(value).__name__}"
    )


# --------------------------------------------------------- condition tree


@dataclass(frozen=True)
class Condition:
    """A boolean expression over indicators / constants.

    Two shapes:
      - **Comparison**:
        ``op ∈ {lt,le,gt,ge,eq,crosses_above,crosses_below}`` and
        ``args = [Indicator|Constant, Indicator|Constant]``.
      - **Boolean**:
        ``op ∈ {and,or,not}``, ``args`` is a list of Conditions.
        ``not`` takes exactly one arg.
    """

    op: Operator
    args: Sequence["Condition | Indicator | Constant"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.value,
            "args": [
                a.to_dict() if hasattr(a, "to_dict") else a for a in self.args
            ],
        }

    def validate(self) -> None:
        if self.op in _BOOLEAN_OPS:
            if self.op is Operator.NOT:
                if len(self.args) != 1:
                    raise StrategyError("NOT requires exactly one operand")
                if not isinstance(self.args[0], Condition):
                    raise StrategyError("NOT operand must be a Condition")
            else:
                if len(self.args) < 2:
                    raise StrategyError(
                        f"{self.op.value} requires ≥ 2 operands"
                    )
                for a in self.args:
                    if not isinstance(a, Condition):
                        raise StrategyError(
                            f"{self.op.value} operands must be Conditions"
                        )
        elif self.op in _BINARY_COMPARE:
            if len(self.args) != 2:
                raise StrategyError(
                    f"{self.op.value} requires exactly 2 operands"
                )
            for a in self.args:
                if not isinstance(a, (Indicator, Constant)):
                    raise StrategyError(
                        f"{self.op.value} operand must be "
                        "Indicator or Constant"
                    )
        else:
            raise StrategyError(f"unknown operator {self.op!r}")


# --------------------------------------------------------- sizing


@dataclass(frozen=True)
class SizingRule:
    """How to size a fresh entry.

    Three shapes are supported in v1:

    - ``kind="fixed_qty"`` — always send ``qty`` units (e.g.
      ``0.01 BTC``).
    - ``kind="fixed_notional"`` — always send notional == ``notional``
      USD; backtest converts at fill price.
    - ``kind="risk_pct"`` — size so the implied loss to ``stop_loss``
      equals ``risk_pct`` of equity. Requires the strategy to declare
      a ``stop_loss`` exit; validation enforces this.
    """

    kind: str  # "fixed_qty" | "fixed_notional" | "risk_pct"
    qty: float | None = None
    notional: float | None = None
    risk_pct: float | None = None  # 0.01 = 1 %

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind}
        if self.qty is not None:
            out["qty"] = float(self.qty)
        if self.notional is not None:
            out["notional"] = float(self.notional)
        if self.risk_pct is not None:
            out["risk_pct"] = float(self.risk_pct)
        return out

    def validate(self) -> None:
        if self.kind == "fixed_qty":
            if self.qty is None or self.qty <= 0:
                raise StrategyError("fixed_qty requires qty > 0")
        elif self.kind == "fixed_notional":
            if self.notional is None or self.notional <= 0:
                raise StrategyError("fixed_notional requires notional > 0")
        elif self.kind == "risk_pct":
            if (
                self.risk_pct is None
                or self.risk_pct <= 0
                or self.risk_pct > 0.5
            ):
                raise StrategyError(
                    "risk_pct must be in (0, 0.5] (50% loss cap)"
                )
        else:
            raise StrategyError(f"unknown sizing kind {self.kind!r}")


# --------------------------------------------------------- strategy


@dataclass(frozen=True)
class Strategy:
    """Top-level strategy IR.

    Acceptance rules (enforced by :meth:`validate`):

    - ``name`` non-empty, ≤ 80 chars.
    - ``side`` one of ``long`` / ``short``.
    - ``timeframe`` one of the :class:`Timeframe` enum values.
    - At least one ``entry`` condition; ``exit`` may be empty
      *only* when ``stop_loss`` or ``take_profit`` is set.
    - ``risk_pct`` sizing requires either ``stop_loss`` or
      ``stop_loss_pct``.
    - ``max_positions`` ≥ 1.
    """

    name: str
    description: str
    instrument: str  # e.g. "BINANCE:BTCUSDT"
    timeframe: Timeframe
    side: Side
    entry: Condition
    exit: Condition | None = None
    sizing: SizingRule = field(
        default_factory=lambda: SizingRule(kind="fixed_qty", qty=1.0)
    )
    stop_loss_pct: float | None = None  # e.g. 0.02 = 2 % of entry
    take_profit_pct: float | None = None  # e.g. 0.04 = 4 % of entry
    trailing_stop_pct: float | None = None
    max_positions: int = 1
    cooldown_bars: int = 0  # bars to wait after a close before re-entering
    version: int = 1
    tags: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "instrument": self.instrument,
            "timeframe": self.timeframe.value,
            "side": self.side.value,
            "entry": self.entry.to_dict(),
            "sizing": self.sizing.to_dict(),
            "max_positions": int(self.max_positions),
            "cooldown_bars": int(self.cooldown_bars),
            "version": int(self.version),
            "tags": list(self.tags),
        }
        if self.exit is not None:
            out["exit"] = self.exit.to_dict()
        if self.stop_loss_pct is not None:
            out["stop_loss_pct"] = float(self.stop_loss_pct)
        if self.take_profit_pct is not None:
            out["take_profit_pct"] = float(self.take_profit_pct)
        if self.trailing_stop_pct is not None:
            out["trailing_stop_pct"] = float(self.trailing_stop_pct)
        return out

    def to_json(self) -> str:
        """Canonical JSON: sorted keys + no whitespace.

        Used as the input to :meth:`fingerprint`. Two strategies
        that differ only by IR field order produce the same hash.
        """
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        """sha256 of the canonical JSON; used as the registry key
        and the backtest cache key."""
        digest = hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise StrategyError("name is required")
        if len(self.name) > 80:
            raise StrategyError("name ≤ 80 chars")
        if not isinstance(self.instrument, str) or ":" not in self.instrument:
            raise StrategyError(
                "instrument must look like 'VENUE:SYMBOL' (e.g. BINANCE:BTCUSDT)"
            )
        if not isinstance(self.timeframe, Timeframe):
            raise StrategyError("timeframe must be a Timeframe enum")
        if not isinstance(self.side, Side):
            raise StrategyError("side must be Side enum")
        self.entry.validate()
        if self.exit is not None:
            self.exit.validate()
        elif (
            self.stop_loss_pct is None
            and self.take_profit_pct is None
            and self.trailing_stop_pct is None
        ):
            raise StrategyError(
                "exit condition required when no stop_loss / "
                "take_profit / trailing_stop is set"
            )
        self.sizing.validate()
        if self.sizing.kind == "risk_pct" and self.stop_loss_pct is None:
            raise StrategyError(
                "risk_pct sizing requires stop_loss_pct (so risk per "
                "trade is computable)"
            )
        if self.max_positions < 1:
            raise StrategyError("max_positions ≥ 1")
        if self.cooldown_bars < 0:
            raise StrategyError("cooldown_bars ≥ 0")
        for pct, name in (
            (self.stop_loss_pct, "stop_loss_pct"),
            (self.take_profit_pct, "take_profit_pct"),
            (self.trailing_stop_pct, "trailing_stop_pct"),
        ):
            if pct is not None and (pct <= 0 or pct >= 1):
                raise StrategyError(f"{name} must be in (0, 1)")

    # ------------------------------------------------------------------
    # parsing
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Strategy":
        try:
            timeframe = Timeframe(payload["timeframe"])
            side = Side(payload["side"])
        except (KeyError, ValueError) as exc:
            raise StrategyError(f"bad timeframe/side: {exc}") from exc

        entry_node = _parse_condition_node(payload.get("entry"))
        if not isinstance(entry_node, Condition):
            raise StrategyError("entry must be a Condition")

        exit_payload = payload.get("exit")
        exit_node: Condition | None = None
        if exit_payload is not None:
            parsed = _parse_condition_node(exit_payload)
            if not isinstance(parsed, Condition):
                raise StrategyError("exit must be a Condition")
            exit_node = parsed

        sizing_payload = payload.get("sizing") or {"kind": "fixed_qty", "qty": 1.0}
        sizing = SizingRule(
            kind=str(sizing_payload.get("kind") or "fixed_qty"),
            qty=_optional_float(sizing_payload.get("qty")),
            notional=_optional_float(sizing_payload.get("notional")),
            risk_pct=_optional_float(sizing_payload.get("risk_pct")),
        )

        tags_raw = payload.get("tags") or ()
        tags: tuple[str, ...] = tuple(str(t) for t in tags_raw if str(t).strip())

        s = cls(
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            instrument=str(payload.get("instrument") or ""),
            timeframe=timeframe,
            side=side,
            entry=entry_node,
            exit=exit_node,
            sizing=sizing,
            stop_loss_pct=_optional_float(payload.get("stop_loss_pct")),
            take_profit_pct=_optional_float(payload.get("take_profit_pct")),
            trailing_stop_pct=_optional_float(payload.get("trailing_stop_pct")),
            max_positions=int(payload.get("max_positions") or 1),
            cooldown_bars=int(payload.get("cooldown_bars") or 0),
            version=int(payload.get("version") or 1),
            tags=tags,
        )
        s.validate()
        return s


# --------------------------------------------------------- helpers


def _optional_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise StrategyError(f"expected number, got {v!r}") from exc


def _parse_condition_node(
    raw: Any,
) -> Condition | Indicator | Constant:
    if not isinstance(raw, Mapping):
        raise StrategyError("expression node must be a mapping")
    if "const" in raw:
        return Constant(value=float(raw["const"]))
    if "indicator" in raw:
        params_raw = raw.get("params") or {}
        if not isinstance(params_raw, Mapping):
            raise StrategyError("indicator params must be a mapping")
        return Indicator(
            name=str(raw["indicator"]),
            params={str(k): float(v) for k, v in params_raw.items()},
        )
    if "op" in raw:
        try:
            op = Operator(raw["op"])
        except ValueError as exc:
            raise StrategyError(f"unknown operator {raw['op']!r}") from exc
        args_raw = raw.get("args") or []
        if not isinstance(args_raw, Iterable):
            raise StrategyError("op.args must be a list")
        args = [_parse_condition_node(a) for a in args_raw]
        cond = Condition(op=op, args=args)
        cond.validate()
        return cond
    raise StrategyError(
        f"unrecognised node — expected one of {{const, indicator, op}}: "
        f"{sorted(raw.keys())!r}"
    )
