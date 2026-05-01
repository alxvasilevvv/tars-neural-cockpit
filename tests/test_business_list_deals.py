"""Tests for ``business.list_deals`` and ``read_local_deals``.

Mirrors ``traders.list_alerts`` for the business pack: a read-only
side door on the local deals store with optional filters and
pre-computed rollups so the cockpit can render a sidecar without a
second pass.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.packs.business.actions import (
    list_deals,
    log_deal,
    update_deal,
)
from backend.core.domains.packs.business.actions import ACTIONS as BUSINESS_ACTIONS
from backend.core.domains.packs.business.local_deals import (
    LOCAL_DEALS_ENV_VAR,
    read_local_deals,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    target = tmp_path / "business_deals.json"
    monkeypatch.setenv(LOCAL_DEALS_ENV_VAR, str(target))
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    return target


@pytest.fixture(autouse=True)
def _silence_meeet(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Spy:
        async def emit(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(
        "backend.core.domains.packs.business.local_deals.get_client",
        lambda: _Spy(),
    )


def _run(coro):
    return asyncio.run(coro)


def _seed(name: str, **overrides: Any) -> str:
    base = {
        "name": name,
        "amount": 1000.0,
        "stage": "discovery",
        "council": False,
    }
    base.update(overrides)
    out = _run(log_deal(base))
    assert out["ok"] is True
    return out["deal_id"]


# ---------------------------------------------------------------- read_local_deals

def test_read_local_deals_filters_active_only(_isolated_env: Path) -> None:
    a = _seed("A")
    b = _seed("B", stage="proposal")
    _seed("C")
    _run(update_deal({"deal_id": a, "stage": "won"}))
    _run(update_deal({"deal_id": b, "stage": "lost"}))

    rows = read_local_deals(active_only=True)
    assert {r["name"] for r in rows} == {"C"}


def test_read_local_deals_stage_filter_normalises(_isolated_env: Path) -> None:
    a = _seed("A")
    b = _seed("B")
    _run(update_deal({"deal_id": a, "stage": "won"}))
    _run(update_deal({"deal_id": b, "stage": "won"}))
    _seed("C")

    rows = read_local_deals(stage="WON")
    assert {r["name"] for r in rows} == {"A", "B"}


def test_read_local_deals_owner_filter(_isolated_env: Path) -> None:
    _seed("A", owner="Sam")
    _seed("B", owner="sam")
    _seed("C", owner="Alex")

    rows = read_local_deals(owner="SAM")
    assert {r["name"] for r in rows} == {"A", "B"}


def test_read_local_deals_limit_takes_tail(_isolated_env: Path) -> None:
    for i in range(5):
        _seed(f"D{i}")
    rows = read_local_deals(limit=2)
    assert [r["name"] for r in rows] == ["D3", "D4"]


def test_read_local_deals_missing_returns_empty(tmp_path: Path) -> None:
    assert read_local_deals(path=tmp_path / "nope.json") == []


def test_read_local_deals_owner_filter_skips_unset_rows(_isolated_env: Path) -> None:
    _seed("A", owner="Sam")
    _seed("B")  # no owner
    rows = read_local_deals(owner="sam")
    assert {r["name"] for r in rows} == {"A"}


def test_read_local_deals_unknown_stage_falls_back_to_discovery(
    _isolated_env: Path,
) -> None:
    _seed("A")  # discovery
    _seed("B", stage="proposal")
    rows = read_local_deals(stage="unknown_stage")
    assert {r["name"] for r in rows} == {"A"}


# ---------------------------------------------------------------- list_deals action

def test_list_deals_action_envelope_and_summary(_isolated_env: Path) -> None:
    _seed("A", amount=100, stage="discovery")
    _seed("B", amount=200, stage="proposal")
    _seed("C", amount=300, stage="proposal")

    out = _run(list_deals({}))
    assert out["ok"] is True
    assert out["count"] == 3
    assert {d["name"] for d in out["deals"]} == {"A", "B", "C"}
    assert out["store"] == "local"
    assert out["store_path"] == str(_isolated_env)
    assert out["filters"] == {
        "active_only": False,
        "stage": None,
        "owner": None,
        "limit": None,
    }
    assert out["summary"]["by_stage"] == {"discovery": 1, "proposal": 2}
    assert out["summary"]["total_amount"] == 600.0


def test_list_deals_action_active_only(_isolated_env: Path) -> None:
    a = _seed("A")
    _seed("B")
    _run(update_deal({"deal_id": a, "stage": "won"}))

    out = _run(list_deals({"active_only": True}))
    assert out["count"] == 1
    assert out["deals"][0]["name"] == "B"
    assert out["filters"]["active_only"] is True


def test_list_deals_action_stage_filter_normalises(_isolated_env: Path) -> None:
    a = _seed("A")
    _seed("B")
    _run(update_deal({"deal_id": a, "stage": "won"}))

    out = _run(list_deals({"stage": "WON"}))
    assert out["count"] == 1
    assert out["filters"]["stage"] == "won"
    assert out["deals"][0]["name"] == "A"


def test_list_deals_action_owner_filter(_isolated_env: Path) -> None:
    _seed("A", owner="Sam")
    _seed("B", owner="Alex")
    out = _run(list_deals({"owner": "sam"}))
    assert out["count"] == 1
    assert out["filters"]["owner"] == "sam"


def test_list_deals_action_limit_clamps_to_1000(_isolated_env: Path) -> None:
    _seed("A")
    out = _run(list_deals({"limit": 9999}))
    assert out["filters"]["limit"] == 1000


def test_list_deals_action_garbage_limit_is_none(_isolated_env: Path) -> None:
    _seed("A")
    out = _run(list_deals({"limit": "many"}))
    assert out["filters"]["limit"] is None


def test_list_deals_action_limit_takes_recent_tail(_isolated_env: Path) -> None:
    for i in range(4):
        _seed(f"D{i}")
    out = _run(list_deals({"limit": 2}))
    assert [d["name"] for d in out["deals"]] == ["D2", "D3"]


def test_list_deals_action_path_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(LOCAL_DEALS_ENV_VAR, raising=False)
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    target = tmp_path / "explicit.json"
    target.write_text(
        json.dumps(
            [
                {
                    "id": "local-0001",
                    "name": "Acme",
                    "amount": 99,
                    "stage": "won",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = _run(list_deals({"store_path": str(target)}))
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["store_path"] == str(target)
    assert out["summary"]["total_amount"] == 99.0


def test_list_deals_action_missing_store_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LOCAL_DEALS_ENV_VAR, str(tmp_path / "missing.json"))
    out = _run(list_deals({}))
    assert out == {
        "ok": True,
        "count": 0,
        "deals": [],
        "store": "local",
        "store_path": str(tmp_path / "missing.json"),
        "filters": {
            "active_only": False,
            "stage": None,
            "owner": None,
            "limit": None,
        },
        "summary": {"by_stage": {}, "total_amount": 0.0},
    }


def test_list_deals_action_total_amount_handles_garbage_amount(
    _isolated_env: Path,
) -> None:
    _seed("A", amount=100)
    _isolated_env.write_text(
        json.dumps(
            [
                {"id": "local-0001", "name": "A", "amount": 100, "stage": "discovery"},
                {"id": "local-0002", "name": "B", "amount": "xyz", "stage": "proposal"},
            ]
        ),
        encoding="utf-8",
    )
    out = _run(list_deals({}))
    assert out["summary"]["total_amount"] == 100.0
    assert out["summary"]["by_stage"] == {"discovery": 1, "proposal": 1}


# ---------------------------------------------------------------- ActionSpec wiring

def test_list_deals_spec_present_and_safe() -> None:
    spec = next(s for s in BUSINESS_ACTIONS if s.id == "list_deals")
    assert spec.destructive is False
    props = spec.schema["properties"]
    assert "active_only" in props
    assert "stage" in props
    assert "owner" in props
    assert "limit" in props
    assert "store_path" in props
    assert spec.schema.get("required") in (None, [])
    assert props["stage"]["enum"] == [
        "discovery",
        "qualification",
        "proposal",
        "negotiation",
        "won",
        "lost",
    ]
