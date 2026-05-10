"""Tests for the algotrade Strategy IR.

Covers, end-to-end without network:

- IR construction + validation (all error paths in
  :class:`StrategyError`).
- Round-trip: ``Strategy → dict → from_dict → dict`` is
  bit-identical, and fingerprints match.
- Fingerprint stability against field ordering (sorted JSON keys).
- Condition tree shape rules (NOT requires 1 operand, AND/OR ≥ 2,
  binary compares require exactly 2 of indicator/constant).
- Sizing rule validation (fixed_qty / fixed_notional / risk_pct).
- Recipe catalogue: every shipped recipe loads + validates +
  fingerprints stably.
"""

from __future__ import annotations

import pytest

from backend.core.algotrade import (
    Condition,
    Constant,
    Indicator,
    Operator,
    Side,
    SizingRule,
    Strategy,
    StrategyError,
    Timeframe,
)
from backend.core.algotrade.recipes import list_recipes, load_recipe


def _basic_strategy(**overrides):
    base = dict(
        name="MA Cross 5/20",
        description="trend-following classic",
        instrument="BINANCE:BTCUSDT",
        timeframe=Timeframe.H1,
        side=Side.LONG,
        entry=Condition(
            op=Operator.CROSSES_ABOVE,
            args=[
                Indicator(name="sma", params={"period": 5.0}),
                Indicator(name="sma", params={"period": 20.0}),
            ],
        ),
        exit=Condition(
            op=Operator.CROSSES_BELOW,
            args=[
                Indicator(name="sma", params={"period": 5.0}),
                Indicator(name="sma", params={"period": 20.0}),
            ],
        ),
        sizing=SizingRule(kind="fixed_qty", qty=1.0),
    )
    base.update(overrides)
    return Strategy(**base)


# --------------------------------------------------------- happy path


def test_basic_strategy_validates_and_fingerprints() -> None:
    s = _basic_strategy()
    s.validate()  # must not raise
    fp = s.fingerprint()
    assert fp.startswith("sha256:")
    assert len(fp) == len("sha256:") + 64


def test_round_trip_preserves_fingerprint() -> None:
    s = _basic_strategy()
    payload = s.to_dict()
    s2 = Strategy.from_dict(payload)
    assert s2.fingerprint() == s.fingerprint()
    assert s2.to_dict() == payload


def test_fingerprint_is_field_order_independent() -> None:
    s = _basic_strategy()
    d1 = s.to_dict()
    # Reverse the top-level dict order
    d2 = {k: d1[k] for k in reversed(d1.keys())}
    assert Strategy.from_dict(d2).fingerprint() == s.fingerprint()


# --------------------------------------------------------- validation errors


def test_empty_name_rejected() -> None:
    with pytest.raises(StrategyError, match="name"):
        _basic_strategy(name="").validate()


def test_oversized_name_rejected() -> None:
    with pytest.raises(StrategyError, match="80 chars"):
        _basic_strategy(name="x" * 81).validate()


def test_instrument_must_have_venue_prefix() -> None:
    with pytest.raises(StrategyError, match="VENUE:SYMBOL"):
        _basic_strategy(instrument="BTCUSDT").validate()


def test_missing_exit_without_stops_rejected() -> None:
    with pytest.raises(StrategyError, match="exit condition required"):
        _basic_strategy(exit=None, stop_loss_pct=None).validate()


def test_risk_pct_sizing_requires_stop_loss() -> None:
    with pytest.raises(StrategyError, match="risk_pct sizing requires"):
        _basic_strategy(
            sizing=SizingRule(kind="risk_pct", risk_pct=0.01),
            stop_loss_pct=None,
        ).validate()


def test_invalid_stop_loss_pct_rejected() -> None:
    with pytest.raises(StrategyError, match="stop_loss_pct"):
        _basic_strategy(stop_loss_pct=1.5).validate()


def test_invalid_sizing_kind_rejected() -> None:
    s = _basic_strategy(sizing=SizingRule(kind="weird"))
    with pytest.raises(StrategyError, match="unknown sizing kind"):
        s.validate()


def test_max_positions_must_be_positive() -> None:
    with pytest.raises(StrategyError, match="max_positions"):
        _basic_strategy(max_positions=0).validate()


# --------------------------------------------------------- condition tree


def test_not_requires_exactly_one_operand() -> None:
    bad = Condition(op=Operator.NOT, args=[])
    with pytest.raises(StrategyError, match="exactly one operand"):
        bad.validate()


def test_and_requires_at_least_two_operands() -> None:
    inner = Condition(
        op=Operator.LT, args=[Indicator(name="close"), Constant(value=100.0)]
    )
    bad = Condition(op=Operator.AND, args=[inner])
    with pytest.raises(StrategyError, match="≥ 2"):
        bad.validate()


def test_binary_compare_requires_exactly_two_operands() -> None:
    bad = Condition(op=Operator.LT, args=[Indicator(name="close")])
    with pytest.raises(StrategyError, match="exactly 2 operands"):
        bad.validate()


def test_binary_compare_operand_must_be_indicator_or_constant() -> None:
    inner = Condition(
        op=Operator.GT,
        args=[Indicator(name="close"), Constant(value=10.0)],
    )
    bad = Condition(op=Operator.LT, args=[inner, Constant(value=5.0)])
    with pytest.raises(StrategyError, match="Indicator or Constant"):
        bad.validate()


def test_unknown_operator_in_payload_rejected() -> None:
    payload = {
        "name": "x",
        "description": "x",
        "instrument": "BINANCE:BTCUSDT",
        "timeframe": "1h",
        "side": "long",
        "entry": {"op": "weird_op", "args": []},
        "exit": {
            "op": "lt",
            "args": [
                {"indicator": "close"},
                {"const": 100},
            ],
        },
        "sizing": {"kind": "fixed_qty", "qty": 1.0},
    }
    with pytest.raises(StrategyError, match="unknown operator"):
        Strategy.from_dict(payload)


# --------------------------------------------------------- helpers


def test_indicator_param_must_be_numeric() -> None:
    with pytest.raises(StrategyError, match="param must be int/float"):
        Indicator(name="sma", params={"period": "thirty"}).to_dict()  # type: ignore[arg-type]


def test_constant_serialises_predictably() -> None:
    assert Constant(value=3.14).to_dict() == {"const": 3.14}


def test_indicator_serialises_with_sorted_params() -> None:
    d = Indicator(
        name="bb_lower", params={"k": 2.0, "period": 20.0}
    ).to_dict()
    # Keys should appear sorted (period < k alphabetically)
    assert list(d["params"].keys()) == ["k", "period"]


# --------------------------------------------------------- recipes


@pytest.mark.parametrize("name", list_recipes())
def test_recipe_loads_and_validates(name: str) -> None:
    s = load_recipe(name)
    s.validate()
    assert s.fingerprint().startswith("sha256:")


def test_recipe_round_trip_is_bit_identical() -> None:
    for name in list_recipes():
        s = load_recipe(name)
        s2 = Strategy.from_dict(s.to_dict())
        assert s2.fingerprint() == s.fingerprint(), name


def test_recipe_catalog_has_at_least_three_entries() -> None:
    # Lock the workshop catalogue size — accidental deletion will fail.
    assert len(list_recipes()) >= 3
