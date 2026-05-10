"""Tests for the algotrade domain pack (Phase W1b).

Covers, end-to-end without network:

- Pack registration (slug + manifest + actions list).
- Every action handler produces a structured envelope (never
  raises for ordinary input).
- Backtest accepts inline bars / csv path / binance spec and
  routes to the W1a engine.
- Equity-curve down-sampling preserves first + last anchors.
- Awareness snapshot returns the registry inventory.
"""

from __future__ import annotations

import json
import math
import random
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend.core.algotrade.strategy.registry import reset_registry_for_tests


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Each test owns its own registry root."""
    monkeypatch.setenv("TARS_HOME", str(tmp_path))
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


@pytest.fixture
def pack():
    """Lazy-import the pack so the fixture-set TARS_HOME wins."""
    import backend.core.domains.packs  # noqa: F401  (registration)
    from backend.core.domains.registry import get_pack

    p = get_pack("algotrade")
    assert p is not None, "algotrade pack must be registered"
    return p


def _make_bars(n: int = 200, seed: int = 42) -> list[dict[str, Any]]:
    random.seed(seed)
    bars: list[dict[str, Any]] = []
    px = 100.0
    for i in range(n):
        px = 100 + 8 * math.sin(i / 15) + random.gauss(0, 1) + i * 0.05
        o = px + random.gauss(0, 0.2)
        h = max(o, px) + abs(random.gauss(0, 0.4))
        lo = min(o, px) - abs(random.gauss(0, 0.4))
        bars.append(
            {
                "ts": 1700000000 + i * 3600,
                "open": o,
                "high": h,
                "low": lo,
                "close": px,
                "volume": 1000.0,
            }
        )
    return bars


# --------------------------------------------------------- registration


def test_pack_is_registered(pack) -> None:
    assert pack.manifest.slug == "algotrade"
    action_ids = [a.id for a in pack.actions()]
    expected = {
        "list_recipes",
        "load_recipe",
        "parse_strategy",
        "register_strategy",
        "list_strategies",
        "get_strategy",
        "fork_strategy",
        "backtest",
    }
    assert expected <= set(action_ids)


def test_destructive_flags_are_set(pack) -> None:
    """Mutations must route through the policy gate."""
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["register_strategy"].destructive is True
    assert by_id["fork_strategy"].destructive is True
    # Reads stay non-destructive
    assert by_id["list_recipes"].destructive is False
    assert by_id["backtest"].destructive is False


def test_to_dict_includes_pack_memory_actions(pack) -> None:
    """all_actions appends the system-wide pack.memory.* layer."""
    d = pack.to_dict()
    ids = {a["id"] for a in d["actions"]}
    assert "pack.memory.set" in ids
    assert "pack.memory.get" in ids


# --------------------------------------------------------- recipe verbs


@pytest.mark.asyncio
async def test_list_recipes_returns_catalogue(pack) -> None:
    handler = pack.find_action("list_recipes").handler
    res = await handler({})
    assert res["ok"] is True
    assert "ma_cross" in res["recipes"]
    assert "bollinger_reversion" in res["recipes"]
    assert len(res["recipes"]) >= 3


@pytest.mark.asyncio
async def test_load_recipe_returns_full_ir(pack) -> None:
    handler = pack.find_action("load_recipe").handler
    res = await handler({"name": "ma_cross"})
    assert res["ok"] is True
    assert res["fingerprint"].startswith("sha256:")
    assert res["strategy"]["instrument"] == "BINANCE:BTCUSDT"
    assert res["strategy"]["timeframe"] == "1h"


@pytest.mark.asyncio
async def test_load_recipe_missing_name_returns_error(pack) -> None:
    res = await pack.find_action("load_recipe").handler({})
    assert res["ok"] is False
    assert res["error"] == "missing_name"


@pytest.mark.asyncio
async def test_load_recipe_unknown_returns_error(pack) -> None:
    res = await pack.find_action("load_recipe").handler({"name": "nope"})
    assert res["ok"] is False
    assert res["error"] == "recipe_not_found"


# --------------------------------------------------------- IR verbs


@pytest.mark.asyncio
async def test_parse_strategy_returns_canonical(pack) -> None:
    payload = {
        "name": "Manual",
        "description": "test",
        "instrument": "BINANCE:BTCUSDT",
        "timeframe": "1h",
        "side": "long",
        "entry": {
            "op": "lt",
            "args": [
                {"indicator": "close"},
                {"indicator": "sma", "params": {"period": 20}},
            ],
        },
        "exit": {
            "op": "gt",
            "args": [
                {"indicator": "close"},
                {"indicator": "sma", "params": {"period": 20}},
            ],
        },
        "sizing": {"kind": "fixed_qty", "qty": 1.0},
    }
    res = await pack.find_action("parse_strategy").handler({"ir": payload})
    assert res["ok"] is True
    assert res["fingerprint"].startswith("sha256:")
    assert res["strategy"]["instrument"] == "BINANCE:BTCUSDT"


@pytest.mark.asyncio
async def test_parse_strategy_invalid_returns_error(pack) -> None:
    bad = {"name": "x", "instrument": "no-colon"}
    res = await pack.find_action("parse_strategy").handler({"ir": bad})
    assert res["ok"] is False
    assert res["error"] == "invalid_ir"


# --------------------------------------------------------- registry verbs


@pytest.mark.asyncio
async def test_register_from_recipe_persists(pack) -> None:
    res = await pack.find_action("register_strategy").handler(
        {"recipe": "ma_cross", "author": "test"}
    )
    assert res["ok"] is True
    assert res["version"] == 1
    assert res["author"] == "test"


@pytest.mark.asyncio
async def test_register_idempotent_on_fingerprint(pack) -> None:
    h = pack.find_action("register_strategy").handler
    a = await h({"recipe": "ma_cross", "author": "test"})
    b = await h({"recipe": "ma_cross", "author": "test"})
    assert a["fingerprint"] == b["fingerprint"]
    assert a["version"] == b["version"]


@pytest.mark.asyncio
async def test_register_missing_source_returns_error(pack) -> None:
    res = await pack.find_action("register_strategy").handler({"author": "x"})
    assert res["ok"] is False
    assert res["error"] == "missing_strategy_source"


@pytest.mark.asyncio
async def test_list_strategies_inventory(pack) -> None:
    await pack.find_action("register_strategy").handler({"recipe": "ma_cross"})
    await pack.find_action("register_strategy").handler(
        {"recipe": "bollinger_reversion"}
    )
    res = await pack.find_action("list_strategies").handler({})
    assert res["ok"] is True
    assert res["count"] >= 2
    slugs = {s["slug"] for s in res["strategies"]}
    assert any("ma" in s for s in slugs)
    assert any("bollinger" in s for s in slugs)


@pytest.mark.asyncio
async def test_get_strategy_round_trip(pack) -> None:
    reg_h = pack.find_action("register_strategy").handler
    reg = await reg_h({"recipe": "ma_cross"})
    res = await pack.find_action("get_strategy").handler(
        {"fingerprint": reg["fingerprint"]}
    )
    assert res["ok"] is True
    assert res["fingerprint"] == reg["fingerprint"]
    assert res["strategy"]["name"]


@pytest.mark.asyncio
async def test_get_strategy_missing_returns_error(pack) -> None:
    res = await pack.find_action("get_strategy").handler(
        {"fingerprint": "sha256:00" * 16}
    )
    assert res["ok"] is False
    assert res["error"] == "strategy_not_found"


# --------------------------------------------------------- fork


@pytest.mark.asyncio
async def test_fork_strategy_records_parent(pack) -> None:
    reg = await pack.find_action("register_strategy").handler(
        {"recipe": "ma_cross"}
    )
    fork = await pack.find_action("fork_strategy").handler(
        {
            "fingerprint": reg["fingerprint"],
            "new_name": "ETH variant",
            "overrides": {"instrument": "BINANCE:ETHUSDT"},
        }
    )
    assert fork["ok"] is True
    assert fork["parent_fingerprint"] == reg["fingerprint"]
    assert fork["strategy"]["instrument"] == "BINANCE:ETHUSDT"
    assert fork["fingerprint"] != reg["fingerprint"]


@pytest.mark.asyncio
async def test_fork_invalid_overrides_returns_error(pack) -> None:
    reg = await pack.find_action("register_strategy").handler(
        {"recipe": "ma_cross"}
    )
    res = await pack.find_action("fork_strategy").handler(
        {
            "fingerprint": reg["fingerprint"],
            "overrides": {"instrument": "no-colon"},
        }
    )
    assert res["ok"] is False
    assert res["error"] == "fork_invalid"


# --------------------------------------------------------- backtest


@pytest.mark.asyncio
async def test_backtest_inline_bars_runs_clean(pack) -> None:
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "bars": _make_bars(200)}
    )
    assert res["ok"] is True
    assert res["bars"] == 200
    assert math.isfinite(res["metrics"]["sharpe"])
    assert isinstance(res["equity_curve"], list)
    assert isinstance(res["trades"], list)


@pytest.mark.asyncio
async def test_backtest_down_sample_anchors_endpoints(pack) -> None:
    bars = _make_bars(500)
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "bars": bars, "equity_down_sample": 50}
    )
    assert res["ok"] is True
    assert res.get("equity_curve_down_sampled") is True
    assert len(res["equity_curve"]) <= 50
    # First + last timestamps must equal the original endpoints
    assert res["equity_curve"][0]["ts"] == bars[0]["ts"]
    assert res["equity_curve"][-1]["ts"] == bars[-1]["ts"]


@pytest.mark.asyncio
async def test_backtest_csv_path_round_trip(pack, tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    lines = ["ts,open,high,low,close,volume"]
    for b in _make_bars(120):
        lines.append(
            f"{b['ts']},{b['open']},{b['high']},{b['low']},{b['close']},{b['volume']}"
        )
    csv_path.write_text("\n".join(lines))
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "csv_path": str(csv_path)}
    )
    assert res["ok"] is True
    assert res["bars"] == 120


@pytest.mark.asyncio
async def test_backtest_missing_data_source_returns_error(pack) -> None:
    res = await pack.find_action("backtest").handler({"recipe": "ma_cross"})
    assert res["ok"] is False
    assert res["error"] == "missing_data"


@pytest.mark.asyncio
async def test_backtest_ambiguous_data_source_returns_error(pack) -> None:
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "bars": [], "csv_path": "/no"}
    )
    assert res["ok"] is False
    assert res["error"] == "ambiguous_data"


@pytest.mark.asyncio
async def test_backtest_invalid_bar_returns_error(pack) -> None:
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "bars": [{"ts": "not-a-number"}]}
    )
    assert res["ok"] is False
    assert res["error"] == "invalid_bar"


@pytest.mark.asyncio
async def test_backtest_with_inline_ir(pack) -> None:
    bars = _make_bars(150)
    ir = {
        "name": "manual",
        "description": "test",
        "instrument": "SYNTH:T",
        "timeframe": "1h",
        "side": "long",
        "entry": {
            "op": "crosses_above",
            "args": [
                {"indicator": "sma", "params": {"period": 5}},
                {"indicator": "sma", "params": {"period": 20}},
            ],
        },
        "exit": {
            "op": "crosses_below",
            "args": [
                {"indicator": "sma", "params": {"period": 5}},
                {"indicator": "sma", "params": {"period": 20}},
            ],
        },
        "sizing": {"kind": "fixed_qty", "qty": 1.0},
    }
    res = await pack.find_action("backtest").handler({"ir": ir, "bars": bars})
    assert res["ok"] is True


@pytest.mark.asyncio
async def test_backtest_result_is_json_serialisable(pack) -> None:
    res = await pack.find_action("backtest").handler(
        {"recipe": "ma_cross", "bars": _make_bars(100)}
    )
    raw = json.dumps(res)
    assert json.loads(raw)["ok"] is True


# --------------------------------------------------------- awareness


@pytest.mark.asyncio
async def test_awareness_registry_snapshot(pack) -> None:
    await pack.find_action("register_strategy").handler({"recipe": "ma_cross"})
    src = pack.find_awareness("strategy_registry")
    snap = await src.fetcher({})
    assert snap["ok"] is True
    assert snap["count"] >= 1
    assert snap["strategies"][0]["fingerprint"].startswith("sha256:")
