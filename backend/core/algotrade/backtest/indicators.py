"""Incremental indicators — stdlib only.

Each indicator exposes ``update(bar) -> float | None`` so the
backtest harness can call them once per bar and immediately get
the latest value (or ``None`` while warming up). Two-pass
batch indicators (anything that needs the whole series in
memory) are deliberately not supported here — they don't survive
the migration to live trading, and we want backtest ↔ live
parity.

Catalogue of names recognised by :func:`eval_node`:

- ``open`` / ``high`` / ``low`` / ``close`` / ``volume`` — raw bar
  fields. Take no params.
- ``sma`` — simple moving average, ``params={"period": N}``.
- ``ema`` — exponential moving average, ``params={"period": N}``.
- ``rsi`` — Wilder RSI, ``params={"period": N}``. Returns ``None``
  until N+1 bars have been seen.
- ``atr`` — Wilder ATR, ``params={"period": N}``. Same warm-up.
- ``bb_mid`` / ``bb_upper`` / ``bb_lower`` — Bollinger middle /
  upper / lower band, ``params={"period": N, "k": K}``.

Adding a new indicator is one line in ``INDICATORS`` plus a
class with ``update(bar) -> float | None``.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from ..strategy.ir import (
    Condition,
    Constant,
    Indicator as IRIndicator,
    Operator,
    StrategyError,
)
from .harness import Bar


class Indicator(Protocol):
    """Runtime indicator contract."""

    def update(self, bar: Bar) -> float | None:
        ...


# --------------------------------------------------------- raw bar fields


@dataclass
class _Field:
    field: str
    last: float | None = None

    def update(self, bar: Bar) -> float | None:
        v = getattr(bar, self.field)
        self.last = float(v)
        return self.last


def _open() -> Indicator:
    return _Field("open")


def _high() -> Indicator:
    return _Field("high")


def _low() -> Indicator:
    return _Field("low")


def _close() -> Indicator:
    return _Field("close")


def _volume() -> Indicator:
    return _Field("volume")


# --------------------------------------------------------- SMA / EMA


@dataclass
class SMA:
    period: int

    def __post_init__(self) -> None:
        if self.period < 1:
            raise StrategyError("SMA period ≥ 1")
        self._buf: deque[float] = deque(maxlen=self.period)
        self.last: float | None = None

    def update(self, bar: Bar) -> float | None:
        self._buf.append(bar.close)
        if len(self._buf) < self.period:
            self.last = None
            return None
        self.last = sum(self._buf) / self.period
        return self.last


@dataclass
class EMA:
    period: int

    def __post_init__(self) -> None:
        if self.period < 1:
            raise StrategyError("EMA period ≥ 1")
        self._k = 2.0 / (self.period + 1.0)
        self._seen = 0
        self._sum = 0.0
        self.last: float | None = None

    def update(self, bar: Bar) -> float | None:
        c = bar.close
        if self._seen < self.period:
            self._sum += c
            self._seen += 1
            if self._seen == self.period:
                self.last = self._sum / self.period
            else:
                self.last = None
        else:
            assert self.last is not None
            self.last = (c - self.last) * self._k + self.last
        return self.last


# --------------------------------------------------------- RSI (Wilder)


@dataclass
class RSI:
    period: int

    def __post_init__(self) -> None:
        if self.period < 2:
            raise StrategyError("RSI period ≥ 2")
        self._prev_close: float | None = None
        self._gains_seed: list[float] = []
        self._losses_seed: list[float] = []
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self.last: float | None = None

    def update(self, bar: Bar) -> float | None:
        c = bar.close
        if self._prev_close is None:
            self._prev_close = c
            return None
        diff = c - self._prev_close
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        self._prev_close = c

        if self._avg_gain is None:
            self._gains_seed.append(gain)
            self._losses_seed.append(loss)
            if len(self._gains_seed) == self.period:
                self._avg_gain = sum(self._gains_seed) / self.period
                self._avg_loss = sum(self._losses_seed) / self.period
            else:
                return None
        else:
            assert self._avg_loss is not None
            self._avg_gain = (
                self._avg_gain * (self.period - 1) + gain
            ) / self.period
            self._avg_loss = (
                self._avg_loss * (self.period - 1) + loss
            ) / self.period

        if self._avg_loss == 0:
            self.last = 100.0
            return self.last
        rs = self._avg_gain / self._avg_loss
        self.last = 100.0 - (100.0 / (1.0 + rs))
        return self.last


# --------------------------------------------------------- ATR (Wilder)


@dataclass
class ATR:
    period: int

    def __post_init__(self) -> None:
        if self.period < 1:
            raise StrategyError("ATR period ≥ 1")
        self._prev_close: float | None = None
        self._tr_seed: list[float] = []
        self._avg: float | None = None
        self.last: float | None = None

    def update(self, bar: Bar) -> float | None:
        if self._prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(
                bar.high - bar.low,
                abs(bar.high - self._prev_close),
                abs(bar.low - self._prev_close),
            )
        self._prev_close = bar.close

        if self._avg is None:
            self._tr_seed.append(tr)
            if len(self._tr_seed) == self.period:
                self._avg = sum(self._tr_seed) / self.period
            else:
                return None
        else:
            self._avg = (self._avg * (self.period - 1) + tr) / self.period
        self.last = self._avg
        return self.last


# --------------------------------------------------------- Bollinger Bands


@dataclass
class Bollinger:
    period: int
    k: float
    band: str  # "mid" | "upper" | "lower"

    def __post_init__(self) -> None:
        if self.period < 2:
            raise StrategyError("Bollinger period ≥ 2")
        if self.band not in {"mid", "upper", "lower"}:
            raise StrategyError(f"unknown bollinger band {self.band!r}")
        self._buf: deque[float] = deque(maxlen=self.period)
        self.last: float | None = None

    def update(self, bar: Bar) -> float | None:
        self._buf.append(bar.close)
        if len(self._buf) < self.period:
            self.last = None
            return None
        mid = sum(self._buf) / self.period
        var = sum((x - mid) ** 2 for x in self._buf) / self.period
        sigma = math.sqrt(var)
        if self.band == "mid":
            self.last = mid
        elif self.band == "upper":
            self.last = mid + self.k * sigma
        else:
            self.last = mid - self.k * sigma
        return self.last


# --------------------------------------------------------- registry


def _bb(band: str) -> Callable[..., Indicator]:
    def _factory(period: float, k: float = 2.0) -> Indicator:
        return Bollinger(period=int(period), k=float(k), band=band)

    return _factory


INDICATORS: dict[str, Callable[..., Indicator]] = {
    "open": lambda: _open(),
    "high": lambda: _high(),
    "low": lambda: _low(),
    "close": lambda: _close(),
    "volume": lambda: _volume(),
    "sma": lambda period: SMA(period=int(period)),
    "ema": lambda period: EMA(period=int(period)),
    "rsi": lambda period: RSI(period=int(period)),
    "atr": lambda period: ATR(period=int(period)),
    "bb_mid": _bb("mid"),
    "bb_upper": _bb("upper"),
    "bb_lower": _bb("lower"),
}


def build_indicator(node: IRIndicator) -> Indicator:
    """Resolve a name → runtime indicator instance."""
    factory = INDICATORS.get(node.name)
    if factory is None:
        raise StrategyError(f"unknown indicator {node.name!r}")
    try:
        return factory(**node.params)
    except TypeError as exc:
        raise StrategyError(
            f"indicator {node.name!r} rejected params {dict(node.params)}: {exc}"
        ) from exc


# --------------------------------------------------------- expression eval


CompiledNode = tuple[str, Any]
"""Internal compiled form of an IR node.

- ``("const", float)``
- ``("ind",   Indicator runtime instance)`` — caller polls ``.last``
  after :meth:`update` for the bar.
- ``("op",    op, list[CompiledNode])``
"""


def compile_node(
    node: Condition | IRIndicator | Constant,
    cache: dict[str, Indicator],
) -> CompiledNode:
    """Walk the IR tree, build runtime indicator instances.

    Indicator instances are de-duplicated by their canonical key so
    a strategy that references ``sma(20)`` twice in different
    branches still only computes it once per bar.
    """

    if isinstance(node, Constant):
        return ("const", float(node.value))
    if isinstance(node, IRIndicator):
        key = _indicator_key(node)
        inst = cache.get(key)
        if inst is None:
            inst = build_indicator(node)
            cache[key] = inst
        return ("ind", inst)
    if isinstance(node, Condition):
        node.validate()
        compiled_args = [compile_node(a, cache) for a in node.args]
        return ("op", node.op, compiled_args)
    raise StrategyError(f"cannot compile {type(node).__name__}")


def _indicator_key(node: IRIndicator) -> str:
    if not node.params:
        return node.name
    body = ",".join(f"{k}={v}" for k, v in sorted(node.params.items()))
    return f"{node.name}({body})"


def collect_indicators(compiled: CompiledNode) -> list[Indicator]:
    """Walk a compiled node, return every indicator instance once."""
    seen: list[Indicator] = []
    seen_ids: set[int] = set()

    def _walk(n: CompiledNode) -> None:
        kind = n[0]
        if kind == "ind":
            inst = n[1]
            if id(inst) not in seen_ids:
                seen_ids.add(id(inst))
                seen.append(inst)
        elif kind == "op":
            for child in n[2]:
                _walk(child)

    _walk(compiled)
    return seen


def eval_node(
    node: CompiledNode,
    *,
    prev: Mapping[int, float | None] | None = None,
) -> float | bool | None:
    """Evaluate a compiled node against current indicator values.

    ``prev`` is an optional mapping from indicator instance id to
    its **previous** value, used for ``crosses_above`` /
    ``crosses_below``. Without it those operators degrade to plain
    ``gt`` / ``lt``.
    """

    kind = node[0]
    if kind == "const":
        return node[1]
    if kind == "ind":
        inst = node[1]
        return inst.last  # may be None during warm-up
    if kind == "op":
        _, op, args = node
        if op is Operator.AND:
            for c in args:
                v = eval_node(c, prev=prev)
                if v is None or not v:
                    return False
            return True
        if op is Operator.OR:
            seen_none = False
            for c in args:
                v = eval_node(c, prev=prev)
                if v is None:
                    seen_none = True
                elif v:
                    return True
            return False if not seen_none else False
        if op is Operator.NOT:
            v = eval_node(args[0], prev=prev)
            if v is None:
                return False
            return not v
        # binary compare
        a = eval_node(args[0], prev=prev)
        b = eval_node(args[1], prev=prev)
        if a is None or b is None:
            return False
        a_f = float(a)
        b_f = float(b)
        if op is Operator.LT:
            return a_f < b_f
        if op is Operator.LE:
            return a_f <= b_f
        if op is Operator.GT:
            return a_f > b_f
        if op is Operator.GE:
            return a_f >= b_f
        if op is Operator.EQ:
            return a_f == b_f
        if op in (Operator.CROSSES_ABOVE, Operator.CROSSES_BELOW):
            inst_a = args[0][1] if args[0][0] == "ind" else None
            inst_b = args[1][1] if args[1][0] == "ind" else None
            if prev is None or inst_a is None or inst_b is None:
                return a_f > b_f if op is Operator.CROSSES_ABOVE else a_f < b_f
            pa = prev.get(id(inst_a))
            pb = prev.get(id(inst_b))
            if pa is None or pb is None:
                return False
            if op is Operator.CROSSES_ABOVE:
                return pa <= pb and a_f > b_f
            return pa >= pb and a_f < b_f
    return None
