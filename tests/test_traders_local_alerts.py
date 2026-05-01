"""Tests for ``traders.local_alerts`` and ``place_alert`` / ``list_alerts``.

Covers the local-first JSON store contract, validation, ID generation,
torn-write resilience, meeet event emission, and the action handler
fallbacks.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.packs.traders.actions import (
    list_alerts,
    place_alert,
)
from backend.core.domains.packs.traders.actions import ACTIONS as TRADERS_ACTIONS
from backend.core.domains.packs.traders.local_alerts import (
    DEFAULT_LOCAL_ALERTS_PATH,
    LOCAL_ALERTS_ENV_VAR,
    LOCAL_ID_PREFIX,
    VALID_DIRECTIONS,
    VALID_SOURCES,
    LocalAlertRecord,
    _atomic_write,
    _coerce_direction,
    _coerce_price,
    _coerce_source,
    _coerce_ticker,
    _next_local_id,
    _read_existing,
    append_local_alert,
    read_local_alerts,
    resolve_local_alerts_path,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the env var at a tmp file so tests never see ~/.tars."""

    target = tmp_path / "traders_alerts.json"
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(target))
    return target


@pytest.fixture(autouse=True)
def _spy_meeet(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture meeet events emitted during the test."""

    captured: list[tuple[str, dict[str, Any]]] = []

    class _Spy:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, dict(payload)))

    monkeypatch.setattr(
        "backend.core.domains.packs.traders.local_alerts.get_client",
        lambda: _Spy(),
    )
    return captured


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- path resolution

def test_resolve_local_alerts_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LOCAL_ALERTS_ENV_VAR, raising=False)
    assert resolve_local_alerts_path() == Path(
        os.path.expanduser(DEFAULT_LOCAL_ALERTS_PATH)
    )


def test_resolve_local_alerts_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "alt.json"
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(target))
    assert resolve_local_alerts_path() == target


def test_resolve_local_alerts_path_override_beats_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(tmp_path / "ignored.json"))
    target = tmp_path / "explicit.json"
    assert resolve_local_alerts_path(target) == target


def test_resolve_local_alerts_path_expands_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LOCAL_ALERTS_ENV_VAR, raising=False)
    out = resolve_local_alerts_path("~/foo/bar.json")
    assert "~" not in str(out)


# ---------------------------------------------------------------- _read_existing

def test_read_existing_missing(_isolated_env: Path) -> None:
    assert _read_existing(_isolated_env) == []


def test_read_existing_empty_file(_isolated_env: Path) -> None:
    _isolated_env.write_text("", encoding="utf-8")
    assert _read_existing(_isolated_env) == []


def test_read_existing_corrupt_json(_isolated_env: Path) -> None:
    _isolated_env.write_text("{not json", encoding="utf-8")
    assert _read_existing(_isolated_env) == []


def test_read_existing_not_a_list(_isolated_env: Path) -> None:
    _isolated_env.write_text(json.dumps({"id": "a"}), encoding="utf-8")
    assert _read_existing(_isolated_env) == []


def test_read_existing_filters_non_dicts(_isolated_env: Path) -> None:
    _isolated_env.write_text(
        json.dumps([{"id": "a"}, "not a dict", 7, {"id": "b"}]),
        encoding="utf-8",
    )
    rows = _read_existing(_isolated_env)
    assert [r["id"] for r in rows] == ["a", "b"]


# ---------------------------------------------------------------- atomic write

def test_atomic_write_creates_parents_and_appends_newline(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "store.json"
    _atomic_write(target, [{"id": "x"}])
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == [{"id": "x"}]


def test_atomic_write_replaces_existing(tmp_path: Path) -> None:
    target = tmp_path / "store.json"
    _atomic_write(target, [{"id": "a"}])
    _atomic_write(target, [{"id": "b"}])
    assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "b"}]


# ---------------------------------------------------------------- _next_local_id

def test_next_local_id_empty_starts_at_0001() -> None:
    assert _next_local_id([]) == "local-alert-0001"


def test_next_local_id_monotone_over_local_ids() -> None:
    rows = [
        {"id": "local-alert-0001"},
        {"id": "local-alert-0002"},
        {"id": "local-alert-0007"},
    ]
    assert _next_local_id(rows) == "local-alert-0008"


def test_next_local_id_ignores_foreign_ids() -> None:
    rows = [
        {"id": "venue-9001"},
        {"id": "tradingview-77"},
        {"id": None},
        {"id": "local-alert-0003"},
    ]
    assert _next_local_id(rows) == "local-alert-0004"


def test_next_local_id_handles_garbage_ids() -> None:
    rows = [
        {"id": "local-alert-not-a-number"},
        {"id": "local-alert-0005"},
    ]
    assert _next_local_id(rows) == "local-alert-0006"


# ---------------------------------------------------------------- coercion

@pytest.mark.parametrize("inp,exp", [("btc", "BTC"), ("  ETH ", "ETH"), ("Sol", "SOL")])
def test_coerce_ticker_normalises(inp: str, exp: str) -> None:
    assert _coerce_ticker(inp) == exp


@pytest.mark.parametrize("bad", ["", "   ", None, 7, []])
def test_coerce_ticker_rejects_garbage(bad: Any) -> None:
    with pytest.raises(ValueError, match="ticker_required"):
        _coerce_ticker(bad)


@pytest.mark.parametrize("inp,exp", [(1, 1.0), (1.5, 1.5), ("3.14", 3.14)])
def test_coerce_price_accepts_positive_finite(inp: Any, exp: float) -> None:
    assert _coerce_price(inp) == pytest.approx(exp)


@pytest.mark.parametrize("bad", [0, -1, "abc", None, float("nan"), [1]])
def test_coerce_price_rejects_garbage(bad: Any) -> None:
    with pytest.raises(ValueError, match="price_invalid"):
        _coerce_price(bad)


@pytest.mark.parametrize(
    "inp",
    sorted(VALID_DIRECTIONS) + ["ABOVE", "  Below ", "Cross_Above"],
)
def test_coerce_direction_accepts_known(inp: str) -> None:
    assert _coerce_direction(inp) in VALID_DIRECTIONS


@pytest.mark.parametrize("bad", ["sideways", "", None, 7, "across"])
def test_coerce_direction_rejects_unknown(bad: Any) -> None:
    with pytest.raises(ValueError, match="direction_invalid"):
        _coerce_direction(bad)


def test_coerce_source_falls_back_to_manual() -> None:
    assert _coerce_source(None) == "manual"
    assert _coerce_source("garbage") == "manual"
    assert _coerce_source("Playbook") == "playbook"


# ---------------------------------------------------------------- append_local_alert

def test_append_local_alert_happy_path(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    rec = _run(
        append_local_alert(
            ticker="btc",
            price=65000.0,
            direction="above",
            note="watch breakout",
            source="manual",
        )
    )
    assert isinstance(rec, LocalAlertRecord)
    assert rec.id == "local-alert-0001"
    assert rec.ticker == "BTC"
    assert rec.price == 65000.0
    assert rec.direction == "above"
    assert rec.source == "manual"
    assert rec.note == "watch breakout"
    assert rec.active is True
    assert rec.created_at  # non-empty ISO timestamp

    on_disk = json.loads(_isolated_env.read_text(encoding="utf-8"))
    assert isinstance(on_disk, list)
    assert on_disk[-1]["id"] == "local-alert-0001"

    assert _spy_meeet, "expected at least one meeet event"
    kind, payload = _spy_meeet[-1]
    assert kind == "traders.alert_placed"
    assert payload["id"] == "local-alert-0001"
    assert payload["ticker"] == "BTC"
    assert payload["store_path"] == str(_isolated_env)


def test_append_local_alert_assigns_monotonic_ids(_isolated_env: Path) -> None:
    rec1 = _run(append_local_alert(ticker="BTC", price=1, direction="above"))
    rec2 = _run(append_local_alert(ticker="ETH", price=2, direction="below"))
    rec3 = _run(append_local_alert(ticker="SOL", price=3, direction="cross_above"))
    assert (rec1.id, rec2.id, rec3.id) == (
        "local-alert-0001",
        "local-alert-0002",
        "local-alert-0003",
    )


def test_append_local_alert_blank_note_drops_to_none(_isolated_env: Path) -> None:
    rec = _run(append_local_alert(ticker="BTC", price=1, direction="above", note="   "))
    assert rec.note is None


def test_append_local_alert_now_override_used(_isolated_env: Path) -> None:
    rec = _run(
        append_local_alert(
            ticker="BTC",
            price=1,
            direction="above",
            now="2030-01-01T00:00:00Z",
        )
    )
    assert rec.created_at == "2030-01-01T00:00:00Z"


def test_append_local_alert_validation_error_no_event(
    _isolated_env: Path, _spy_meeet: list[tuple[str, dict[str, Any]]]
) -> None:
    with pytest.raises(ValueError, match="ticker_required"):
        _run(append_local_alert(ticker="", price=1, direction="above"))
    assert _spy_meeet == []
    assert not _isolated_env.exists()


def test_append_local_alert_recovers_from_corrupt_store(
    _isolated_env: Path,
) -> None:
    _isolated_env.write_text("{not json", encoding="utf-8")
    rec = _run(append_local_alert(ticker="BTC", price=1, direction="above"))
    assert rec.id == "local-alert-0001"
    on_disk = json.loads(_isolated_env.read_text(encoding="utf-8"))
    assert [r["id"] for r in on_disk] == ["local-alert-0001"]


# ---------------------------------------------------------------- read_local_alerts

def test_read_local_alerts_filters_by_ticker_and_active(
    _isolated_env: Path,
) -> None:
    _run(append_local_alert(ticker="BTC", price=1, direction="above"))
    _run(append_local_alert(ticker="ETH", price=2, direction="below"))
    rows = json.loads(_isolated_env.read_text(encoding="utf-8"))
    rows[0]["active"] = False
    _isolated_env.write_text(json.dumps(rows), encoding="utf-8")

    all_rows = read_local_alerts()
    assert {r["ticker"] for r in all_rows} == {"BTC", "ETH"}

    active = read_local_alerts(active_only=True)
    assert [r["ticker"] for r in active] == ["ETH"]

    btc_only = read_local_alerts(ticker="btc")
    assert [r["ticker"] for r in btc_only] == ["BTC"]


def test_read_local_alerts_limit_takes_tail(_isolated_env: Path) -> None:
    for i in range(5):
        _run(append_local_alert(ticker=f"T{i}", price=1, direction="above"))
    rows = read_local_alerts(limit=2)
    assert [r["ticker"] for r in rows] == ["T3", "T4"]


def test_read_local_alerts_missing_returns_empty(tmp_path: Path) -> None:
    assert read_local_alerts(path=tmp_path / "nope.json") == []


# ---------------------------------------------------------------- place_alert action

def test_place_alert_action_persists_and_returns_id(_isolated_env: Path) -> None:
    out = _run(
        place_alert({"ticker": "btc", "price": 100, "direction": "above"})
    )
    assert out["ok"] is True
    assert out["alert_id"] == "local-alert-0001"
    assert out["ticker"] == "BTC"
    assert out["store"] == "local"
    assert out["store_path"] == str(_isolated_env)
    assert out["active"] is True
    assert "hint" in out

    on_disk = json.loads(_isolated_env.read_text(encoding="utf-8"))
    assert on_disk[0]["id"] == "local-alert-0001"


def test_place_alert_action_missing_args() -> None:
    out = _run(place_alert({"ticker": "BTC"}))
    assert out == {
        "ok": False,
        "error": "missing_args",
        "missing": ["direction", "price"],
    }


def test_place_alert_action_invalid_direction(_isolated_env: Path) -> None:
    out = _run(
        place_alert({"ticker": "BTC", "price": 100, "direction": "sideways"})
    )
    assert out == {"ok": False, "error": "direction_invalid"}


def test_place_alert_action_invalid_price(_isolated_env: Path) -> None:
    out = _run(
        place_alert({"ticker": "BTC", "price": -1, "direction": "above"})
    )
    assert out == {"ok": False, "error": "price_invalid"}


def test_place_alert_action_blank_ticker(_isolated_env: Path) -> None:
    out = _run(place_alert({"ticker": "   ", "price": 1, "direction": "above"}))
    assert out == {"ok": False, "error": "ticker_required"}


def test_place_alert_action_path_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(LOCAL_ALERTS_ENV_VAR, raising=False)
    target = tmp_path / "explicit.json"
    out = _run(
        place_alert(
            {
                "ticker": "BTC",
                "price": 1,
                "direction": "above",
                "path": str(target),
            }
        )
    )
    assert out["ok"] is True
    assert out["store_path"] == str(target)
    assert target.exists()


def test_place_alert_action_local_store_unwritable(
    monkeypatch: pytest.MonkeyPatch, _isolated_env: Path
) -> None:
    def _boom(*args, **kwargs):
        raise OSError("read-only volume")

    monkeypatch.setattr(
        "backend.core.domains.packs.traders.local_alerts._atomic_write",
        _boom,
    )
    out = _run(
        place_alert({"ticker": "BTC", "price": 1, "direction": "above"})
    )
    assert out["ok"] is False
    assert out["error"] == "local_store_unwritable"
    assert "read-only" in out["detail"]


# ---------------------------------------------------------------- list_alerts action

def test_list_alerts_action_returns_envelope(_isolated_env: Path) -> None:
    _run(place_alert({"ticker": "BTC", "price": 1, "direction": "above"}))
    _run(place_alert({"ticker": "ETH", "price": 2, "direction": "below"}))

    out = _run(list_alerts({}))
    assert out["ok"] is True
    assert out["count"] == 2
    assert {r["ticker"] for r in out["alerts"]} == {"BTC", "ETH"}
    assert out["store"] == "local"
    assert out["store_path"] == str(_isolated_env)
    assert out["filters"] == {"ticker": None, "active_only": False, "limit": None}


def test_list_alerts_action_ticker_filter_uppercases(_isolated_env: Path) -> None:
    _run(place_alert({"ticker": "BTC", "price": 1, "direction": "above"}))
    _run(place_alert({"ticker": "ETH", "price": 2, "direction": "below"}))
    out = _run(list_alerts({"ticker": "eth"}))
    assert out["count"] == 1
    assert out["alerts"][0]["ticker"] == "ETH"
    assert out["filters"]["ticker"] == "ETH"


def test_list_alerts_action_limit_takes_recent_tail(_isolated_env: Path) -> None:
    for i in range(4):
        _run(
            place_alert({"ticker": f"T{i}", "price": 1, "direction": "above"})
        )
    out = _run(list_alerts({"limit": 2}))
    assert [r["ticker"] for r in out["alerts"]] == ["T2", "T3"]


def test_list_alerts_action_limit_ignores_garbage(_isolated_env: Path) -> None:
    _run(place_alert({"ticker": "BTC", "price": 1, "direction": "above"}))
    out = _run(list_alerts({"limit": "garbage"}))
    assert out["filters"]["limit"] is None
    assert out["count"] == 1


def test_list_alerts_action_active_only(_isolated_env: Path) -> None:
    _run(place_alert({"ticker": "BTC", "price": 1, "direction": "above"}))
    rows = json.loads(_isolated_env.read_text(encoding="utf-8"))
    rows[0]["active"] = False
    _isolated_env.write_text(json.dumps(rows), encoding="utf-8")
    out = _run(list_alerts({"active_only": True}))
    assert out["count"] == 0


def test_list_alerts_missing_store_is_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(LOCAL_ALERTS_ENV_VAR, str(tmp_path / "missing.json"))
    out = _run(list_alerts({}))
    assert out == {
        "ok": True,
        "count": 0,
        "alerts": [],
        "store": "local",
        "store_path": str(tmp_path / "missing.json"),
        "filters": {"ticker": None, "active_only": False, "limit": None},
    }


# ---------------------------------------------------------------- ActionSpec wiring

def _spec_by_id(action_id: str):
    return next(spec for spec in TRADERS_ACTIONS if spec.id == action_id)


def test_place_alert_spec_is_destructive_and_lists_directions() -> None:
    spec = _spec_by_id("place_alert")
    assert spec.destructive is True
    direction_enum = spec.schema["properties"]["direction"]["enum"]
    assert set(direction_enum) == set(VALID_DIRECTIONS)
    assert spec.schema["required"] == ["ticker", "price", "direction"]
    source_enum = spec.schema["properties"]["source"]["enum"]
    assert set(source_enum) == set(VALID_SOURCES)


def test_list_alerts_spec_is_present_and_safe() -> None:
    spec = _spec_by_id("list_alerts")
    assert spec.destructive is False
    assert "ticker" in spec.schema["properties"]
    assert "limit" in spec.schema["properties"]
    assert "active_only" in spec.schema["properties"]
