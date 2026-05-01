"""Tests for the ``traders.local_alerts`` awareness source.

Covers the snapshot fetcher's filter defaults, envelope shape,
aggregation rollups, ticker normalisation, missing-store path, and the
pack's wiring (registered, live, defaulted to active-only).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.registry import get_pack
from backend.core.domains.packs.traders.actions import place_alert, cancel_alert
from backend.core.domains.packs.traders.awareness import _fetch_local_alerts
from backend.core.domains.packs.traders.local_alerts import (
    LOCAL_ALERTS_ENV_VAR,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    target = tmp_path / "traders_alerts.json"
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(target))
    return target


@pytest.fixture(autouse=True)
def _silence_meeet(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Spy:
        async def emit(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(
        "backend.core.domains.packs.traders.local_alerts.get_client",
        lambda: _Spy(),
    )


def _run(coro):
    return asyncio.run(coro)


def _seed(*specs: tuple[str, str]) -> None:
    for ticker, direction in specs:
        _run(place_alert({"ticker": ticker, "price": 1, "direction": direction}))


# ---------------------------------------------------------------- defaults

def test_fetch_local_alerts_defaults_active_only(_isolated_env: Path) -> None:
    _seed(("BTC", "above"), ("ETH", "below"))
    a = _run(place_alert({"ticker": "SOL", "price": 1, "direction": "cross_above"}))
    _run(cancel_alert({"alert_id": a["alert_id"]}))

    out = _run(_fetch_local_alerts({}))
    assert out["ok"] is True
    assert out["count"] == 2
    assert out["filters"]["active_only"] is True
    assert out["filters"]["limit"] == 50
    assert out["filters"]["ticker"] is None
    assert out["exists"] is True
    assert out["path"] == str(_isolated_env)
    tickers = {row["ticker"] for row in out["alerts"]}
    assert tickers == {"BTC", "ETH"}
    assert "as_of" in out


def test_fetch_local_alerts_can_include_inactive(_isolated_env: Path) -> None:
    a = _run(place_alert({"ticker": "BTC", "price": 1, "direction": "above"}))
    _run(cancel_alert({"alert_id": a["alert_id"]}))
    out = _run(_fetch_local_alerts({"active_only": False}))
    assert out["count"] == 1
    assert out["filters"]["active_only"] is False
    assert out["alerts"][0]["active"] is False


def test_fetch_local_alerts_missing_store_is_empty_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(tmp_path / "missing.json"))
    out = _run(_fetch_local_alerts({}))
    assert out["ok"] is True
    assert out["count"] == 0
    assert out["exists"] is False
    assert out["alerts"] == []
    assert out["by_direction"] == {}
    assert out["by_ticker"] == {}


def test_fetch_local_alerts_path_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(LOCAL_ALERTS_ENV_VAR, raising=False)
    target = tmp_path / "explicit.json"
    target.write_text(
        json.dumps(
            [
                {
                    "id": "local-alert-0001",
                    "ticker": "BTC",
                    "price": 1,
                    "direction": "above",
                    "active": True,
                    "source": "manual",
                    "created_at": "2030-01-01T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = _run(_fetch_local_alerts({"path": str(target)}))
    assert out["count"] == 1
    assert out["path"] == str(target)
    assert out["alerts"][0]["ticker"] == "BTC"


# ---------------------------------------------------------------- aggregations

def test_fetch_local_alerts_aggregates_by_direction_and_ticker(
    _isolated_env: Path,
) -> None:
    _seed(
        ("BTC", "above"),
        ("BTC", "below"),
        ("ETH", "above"),
        ("ETH", "above"),
    )
    out = _run(_fetch_local_alerts({}))
    assert out["count"] == 4
    assert out["by_direction"] == {"above": 3, "below": 1}
    assert out["by_ticker"] == {"BTC": 2, "ETH": 2}


def test_fetch_local_alerts_filters_by_ticker_and_normalises(
    _isolated_env: Path,
) -> None:
    _seed(("BTC", "above"), ("ETH", "below"))
    out = _run(_fetch_local_alerts({"ticker": "btc"}))
    assert out["count"] == 1
    assert out["alerts"][0]["ticker"] == "BTC"
    assert out["filters"]["ticker"] == "BTC"


def test_fetch_local_alerts_limit_clamps_to_200(_isolated_env: Path) -> None:
    _seed(("BTC", "above"))
    out = _run(_fetch_local_alerts({"limit": 9999}))
    assert out["filters"]["limit"] == 200


def test_fetch_local_alerts_limit_garbage_falls_back_to_default(
    _isolated_env: Path,
) -> None:
    _seed(("BTC", "above"))
    out = _run(_fetch_local_alerts({"limit": "many"}))
    assert out["filters"]["limit"] == 50


def test_fetch_local_alerts_limit_takes_recent_tail(_isolated_env: Path) -> None:
    for i in range(5):
        _seed((f"T{i}", "above"))
    out = _run(_fetch_local_alerts({"limit": 2}))
    assert out["count"] == 2
    assert [r["ticker"] for r in out["alerts"]] == ["T3", "T4"]


# ---------------------------------------------------------------- pack wiring

def test_traders_pack_registers_local_alerts_source() -> None:
    pack = get_pack("traders")
    assert pack is not None
    src = pack.find_awareness("local_alerts")
    assert src is not None
    assert src.kind == "local"
    assert src.fetcher is not None
    assert src.config["active_only"] is True
    assert src.config["path"].endswith("traders_alerts.json")


def test_to_dict_marks_local_alerts_live() -> None:
    pack = get_pack("traders")
    assert pack is not None
    by_id = {s["id"]: s for s in pack.to_dict()["awareness"]}
    assert by_id["local_alerts"]["live"] is True
    assert by_id["local_alerts"]["kind"] == "local"
