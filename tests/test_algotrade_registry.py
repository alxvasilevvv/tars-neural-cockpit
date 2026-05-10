"""Tests for the file-backed StrategyRegistry."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.algotrade import (
    Condition,
    Indicator,
    Operator,
    Side,
    SizingRule,
    Strategy,
    StrategyRegistry,
    Timeframe,
)


def _strat(name="MA Cross 5/20", description="x") -> Strategy:
    return Strategy(
        name=name,
        description=description,
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


def test_put_and_get_round_trip(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    s = _strat()
    row = reg.put(s, author="op")
    assert row.fingerprint == s.fingerprint()
    assert row.version == 1
    fetched = reg.get(s.fingerprint())
    assert fetched is not None
    assert fetched.strategy.fingerprint() == s.fingerprint()


def test_put_is_idempotent_on_fingerprint(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    s = _strat()
    a = reg.put(s, author="op")
    b = reg.put(s, author="op-again")
    assert a.version == b.version == 1
    # Author of the original entry sticks; we don't overwrite.
    assert b.author == "op"


def test_put_bumps_version_on_changed_strategy(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    s1 = _strat(description="v1")
    s2 = _strat(description="v2")
    reg.put(s1, author="op")
    row = reg.put(s2, author="op", parent_fingerprint=s1.fingerprint())
    assert row.version == 2
    assert row.parent_fingerprint == s1.fingerprint()


def test_versions_orders_by_creation(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    reg.put(_strat(description="a"), author="op")
    reg.put(_strat(description="b"), author="op")
    reg.put(_strat(description="c"), author="op")
    versions = reg.versions("MA Cross 5/20")
    assert [v.version for v in versions] == [1, 2, 3]


def test_latest_returns_top_version(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    reg.put(_strat(description="v1"), author="op")
    reg.put(_strat(description="v2"), author="op")
    latest = reg.latest("MA Cross 5/20")
    assert latest is not None
    assert latest.version == 2
    assert latest.strategy.description == "v2"


def test_search_by_tag_filters_correctly(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    s = _strat()
    s_with_tag = Strategy.from_dict(
        {**s.to_dict(), "tags": ["trend_following"]}
    )
    reg.put(s_with_tag, author="op")
    other = Strategy.from_dict(
        {**s.to_dict(), "name": "Other", "description": "y", "tags": ["mean_reversion"]}
    )
    reg.put(other, author="op")
    rows = reg.search(tag="trend_following")
    assert {r.strategy.name for r in rows} == {"MA Cross 5/20"}


def test_search_by_instrument(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    reg.put(_strat(), author="op")
    other = Strategy.from_dict(
        {
            **_strat().to_dict(),
            "name": "ETH variant",
            "description": "y",
            "instrument": "BINANCE:ETHUSDT",
        }
    )
    reg.put(other, author="op")
    rows = reg.search(instrument="BINANCE:ETHUSDT")
    assert len(rows) == 1
    assert rows[0].strategy.instrument == "BINANCE:ETHUSDT"


def test_list_slugs_returns_unique_sorted(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    reg.put(_strat(name="Alpha"), author="op")
    reg.put(_strat(name="Beta", description="z"), author="op")
    slugs = reg.list_slugs()
    assert slugs == sorted(slugs)
    assert "alpha" in slugs and "beta" in slugs


def test_iter_yields_all_versions(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    reg.put(_strat(description="v1"), author="op")
    reg.put(_strat(description="v2"), author="op")
    rows = list(reg)
    assert len(rows) == 2


def test_bad_fingerprint_raises(tmp_path: Path) -> None:
    reg = StrategyRegistry(root=tmp_path)
    with pytest.raises(Exception):
        reg.get("md5:something")
