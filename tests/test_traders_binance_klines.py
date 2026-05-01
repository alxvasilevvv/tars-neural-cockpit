"""Tests for the ``traders.pull_klines`` Binance adapter.

Covers symbol normalisation, argument validation, upstream-error
handling, payload parsing, derived fields (``change_pct``,
``close_first/last``), action wiring, and the
``integration.binance.klines`` meeet event emission.

The HTTP boundary is mocked so the suite is hermetic.
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _sample_kline_row(
    open_t: int,
    open_p: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
    quote_vol: float = 100_000.0,
    trades: int = 5,
) -> list[Any]:
    """Build a Binance-shaped 12-element kline row."""

    return [
        open_t,
        f"{open_p:.8f}",
        f"{high:.8f}",
        f"{low:.8f}",
        f"{close:.8f}",
        f"{volume:.8f}",
        open_t + 60_000 - 1,
        f"{quote_vol:.8f}",
        trades,
        "0",
        "0",
        "0",
    ]


def _sample_ok_payload() -> list[list[Any]]:
    return [
        _sample_kline_row(1_700_000_000_000, 30000, 30050, 29900, 29950),
        _sample_kline_row(1_700_000_060_000, 29950, 30100, 29940, 30080),
        _sample_kline_row(1_700_000_120_000, 30080, 30200, 30050, 30150),
    ]


@pytest.fixture
def patched_http(monkeypatch):
    """Replace ``binance.get_json`` with a controllable stub."""

    state: dict[str, Any] = {
        "calls": [],
        "status": 200,
        "payload": _sample_ok_payload(),
        "raise": None,
    }

    async def fake_get_json(url, *, params=None, headers=None, timeout=None):
        state["calls"].append({"url": url, "params": dict(params or {})})
        if state["raise"]:
            raise state["raise"]
        return state["status"], state["payload"]

    from backend.core.domains.packs.traders import binance as binance_mod

    monkeypatch.setattr(binance_mod, "get_json", fake_get_json)
    return state


# ---------------------------------------------------------------------
# Unit: argument validation
# ---------------------------------------------------------------------


def test_normalise_symbol_strips_separators_and_uppercases():
    from backend.core.domains.packs.traders.binance import _normalise_symbol

    assert _normalise_symbol("btcusdt") == "BTCUSDT"
    assert _normalise_symbol("BTC/USDT") == "BTCUSDT"
    assert _normalise_symbol("btc-usdt") == "BTCUSDT"
    assert _normalise_symbol("btc usdt") == "BTCUSDT"
    assert _normalise_symbol(" eth:usdt ") == "ETHUSDT"


def test_normalise_symbol_returns_none_for_empty_or_non_string():
    from backend.core.domains.packs.traders.binance import _normalise_symbol

    assert _normalise_symbol("") is None
    assert _normalise_symbol("   ") is None
    assert _normalise_symbol(None) is None
    assert _normalise_symbol(42) is None


def test_parse_kline_row_handles_string_and_int_types():
    from backend.core.domains.packs.traders.binance import _parse_kline_row

    row = _sample_kline_row(1_700_000_000_000, 30000, 30050, 29900, 29950)
    parsed = _parse_kline_row(row)
    assert parsed is not None
    assert parsed.open == 30000.0
    assert parsed.close == 29950.0
    assert parsed.open_time_ms == 1_700_000_000_000
    assert parsed.trades == 5


def test_parse_kline_row_returns_none_for_malformed_input():
    from backend.core.domains.packs.traders.binance import _parse_kline_row

    assert _parse_kline_row(None) is None
    assert _parse_kline_row([1, 2]) is None  # too short
    assert _parse_kline_row([1, "not-a-number"] * 6) is None


# ---------------------------------------------------------------------
# Unit: pull_klines validation paths
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_symbol_returns_validation_error():
    from backend.core.domains.packs.traders.binance import pull_klines

    res = await pull_klines({})
    assert res["ok"] is False
    assert res["error"] == "symbol_required"


@pytest.mark.asyncio
async def test_invalid_interval_returns_validation_error():
    from backend.core.domains.packs.traders.binance import pull_klines

    res = await pull_klines({"symbol": "BTCUSDT", "interval": "13m"})
    assert res["ok"] is False
    assert res["error"] == "invalid_interval"
    assert "1m" in res["detail"]


@pytest.mark.asyncio
async def test_default_interval_is_one_hour():
    from backend.core.domains.packs.traders import binance as binance_mod
    from backend.core.domains.packs.traders.binance import pull_klines

    captured: dict[str, Any] = {}

    async def fake(url, *, params=None, headers=None, timeout=None):
        captured.update(params or {})
        return 200, _sample_ok_payload()

    binance_mod.get_json = fake  # type: ignore[assignment]
    try:
        res = await pull_klines({"symbol": "BTCUSDT"})
        assert res["ok"] is True
        assert captured["interval"] == "1h"
    finally:
        # Reset import-time get_json — pytest will rebind in other tests.
        from backend.core.domains._http import get_json as real_get_json

        binance_mod.get_json = real_get_json  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_invalid_limit_string_returns_error():
    from backend.core.domains.packs.traders.binance import pull_klines

    res = await pull_klines({"symbol": "BTCUSDT", "limit": "many"})
    assert res["ok"] is False
    assert res["error"] == "invalid_limit"


@pytest.mark.asyncio
async def test_invalid_limit_out_of_range():
    from backend.core.domains.packs.traders.binance import pull_klines

    too_big = await pull_klines({"symbol": "BTCUSDT", "limit": 5000})
    assert too_big["ok"] is False
    assert too_big["error"] == "invalid_limit"

    too_small = await pull_klines({"symbol": "BTCUSDT", "limit": 0})
    assert too_small["ok"] is False
    assert too_small["error"] == "invalid_limit"


# ---------------------------------------------------------------------
# Unit: pull_klines happy / error paths against patched HTTP
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_normalised_candles(patched_http):
    from backend.core.domains.packs.traders.binance import pull_klines

    res = await pull_klines(
        {"symbol": "btc/usdt", "interval": "1m", "limit": 3}
    )
    assert res["ok"] is True
    assert res["symbol"] == "BTCUSDT"  # normalised
    assert res["interval"] == "1m"
    assert res["count"] == 3
    candles = res["candles"]
    assert candles[0]["open"] == 30000.0
    assert candles[-1]["close"] == 30150.0
    # Derived fields
    assert res["close_first"] == 29950.0
    assert res["close_last"] == 30150.0
    assert res["change_pct"] == pytest.approx(0.6677, rel=1e-3)
    # Outgoing call was correctly parameterised.
    assert len(patched_http["calls"]) == 1
    call = patched_http["calls"][0]
    assert call["params"]["symbol"] == "BTCUSDT"
    assert call["params"]["interval"] == "1m"
    assert call["params"]["limit"] == 3


@pytest.mark.asyncio
async def test_change_pct_handles_zero_first_close(patched_http):
    """When close_first is 0 we must not divide by zero."""

    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["payload"] = [
        _sample_kline_row(1_700_000_000_000, 0, 0, 0, 0),
        _sample_kline_row(1_700_000_060_000, 0, 100, 0, 50),
    ]
    res = await pull_klines({"symbol": "BTCUSDT"})
    assert res["ok"] is True
    assert res["change_pct"] == 0.0


@pytest.mark.asyncio
async def test_empty_payload_returns_ok_with_zero_candles(patched_http):
    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["payload"] = []
    res = await pull_klines({"symbol": "BTCUSDT"})
    assert res["ok"] is True
    assert res["count"] == 0
    assert "change_pct" not in res  # only set when candles exist


@pytest.mark.asyncio
async def test_upstream_invalid_symbol_returns_status_error(patched_http):
    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["status"] = 400
    patched_http["payload"] = {"code": -1121, "msg": "Invalid symbol."}
    res = await pull_klines({"symbol": "ZZZZZZ"})
    assert res["ok"] is False
    assert res["error"] == "upstream_status"
    assert res["status"] == 400
    assert "Invalid symbol" in res["detail"]


@pytest.mark.asyncio
async def test_upstream_returns_non_array_payload(patched_http):
    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["payload"] = {"unexpected": "shape"}
    res = await pull_klines({"symbol": "BTCUSDT"})
    assert res["ok"] is False
    assert res["error"] == "upstream_payload_invalid"


@pytest.mark.asyncio
async def test_network_error_surfaces_as_failure(patched_http):
    from backend.core.domains._http import NetworkError
    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["raise"] = NetworkError("connection refused")
    res = await pull_klines({"symbol": "BTCUSDT"})
    assert res["ok"] is False
    assert res["error"] == "network_error"
    assert "connection refused" in res["detail"]


@pytest.mark.asyncio
async def test_corrupt_rows_are_skipped(patched_http):
    from backend.core.domains.packs.traders.binance import pull_klines

    patched_http["payload"] = [
        _sample_kline_row(1_700_000_000_000, 30000, 30050, 29900, 29950),
        ["bad", "row"],  # too short
        _sample_kline_row(1_700_000_120_000, 30080, 30200, 30050, 30150),
    ]
    res = await pull_klines({"symbol": "BTCUSDT"})
    assert res["ok"] is True
    assert res["count"] == 2  # corrupt row dropped
    assert res["close_last"] == 30150.0


# ---------------------------------------------------------------------
# Action wiring
# ---------------------------------------------------------------------


def test_action_is_registered_on_traders_pack():
    from backend.core.domains.registry import get_pack

    pack = get_pack("traders")
    assert pack is not None
    actions = {a.id for a in pack.actions()}
    assert "pull_klines" in actions


def test_action_spec_carries_schema_with_intervals_enum():
    from backend.core.domains.packs.traders.actions import ACTIONS

    spec = next(a for a in ACTIONS if a.id == "pull_klines")
    assert spec.handler.__name__ == "pull_klines"
    schema = spec.schema or {}
    interval_schema = schema["properties"]["interval"]
    assert "1h" in interval_schema["enum"]
    assert "1m" in interval_schema["enum"]
    assert schema["required"] == ["symbol"]
    # Read-only adapters must not be policy-gated.
    assert spec.destructive is False


# ---------------------------------------------------------------------
# Meeet event emission
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emits_request_and_completed_events(monkeypatch, patched_http):
    """Successful klines pulls should fire request + completed
    integration events through the meeet bridge so the cost ledger
    sees real-adapter calls."""

    captured: list[dict[str, Any]] = []

    class _FakeClient:
        async def emit(self, kind, payload):
            captured.append({"kind": kind, "payload": dict(payload)})

    fake = _FakeClient()

    from backend.core.domains.packs.traders import binance as binance_mod

    monkeypatch.setattr(binance_mod, "get_client", lambda: fake)

    from backend.core.domains.packs.traders.binance import pull_klines

    await pull_klines({"symbol": "BTCUSDT", "interval": "1m"})
    kinds = [e["kind"] for e in captured]
    phases = [e["payload"]["phase"] for e in captured]
    assert all(k == "integration.binance.klines" for k in kinds)
    assert "request" in phases
    assert "completed" in phases


@pytest.mark.asyncio
async def test_emits_error_event_on_upstream_failure(monkeypatch, patched_http):
    captured: list[dict[str, Any]] = []

    class _FakeClient:
        async def emit(self, kind, payload):
            captured.append({"kind": kind, "payload": dict(payload)})

    fake = _FakeClient()
    from backend.core.domains.packs.traders import binance as binance_mod

    monkeypatch.setattr(binance_mod, "get_client", lambda: fake)
    patched_http["status"] = 503

    from backend.core.domains.packs.traders.binance import pull_klines

    await pull_klines({"symbol": "BTCUSDT"})
    phases = [e["payload"]["phase"] for e in captured]
    assert "request" in phases
    assert "error" in phases


@pytest.mark.asyncio
async def test_emits_error_event_on_network_failure(monkeypatch, patched_http):
    captured: list[dict[str, Any]] = []

    class _FakeClient:
        async def emit(self, kind, payload):
            captured.append({"kind": kind, "payload": dict(payload)})

    fake = _FakeClient()
    from backend.core.domains.packs.traders import binance as binance_mod
    from backend.core.domains._http import NetworkError

    monkeypatch.setattr(binance_mod, "get_client", lambda: fake)
    patched_http["raise"] = NetworkError("boom")

    from backend.core.domains.packs.traders.binance import pull_klines

    await pull_klines({"symbol": "BTCUSDT"})
    error_events = [
        e for e in captured if e["payload"].get("phase") == "error"
    ]
    assert error_events
    assert error_events[0]["payload"]["error"] == "network_error"
