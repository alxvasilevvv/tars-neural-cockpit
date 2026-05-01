"""Tests for the ``business.local_deals`` awareness source.

Mirrors the traders alerts awareness wiring: a `kind="local"` source
that snapshots the local store via `read_local_deals` with sensible
defaults, structurally-stable envelope, and pre-computed rollups for
the cockpit ticker.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.registry import get_pack
from backend.core.domains.packs.business.actions import log_deal, update_deal
from backend.core.domains.packs.business.awareness import _fetch_local_deals
from backend.core.domains.packs.business.local_deals import (
    LOCAL_DEALS_ENV_VAR,
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
    base = {"name": name, "amount": 1000.0, "stage": "discovery", "council": False}
    base.update(overrides)
    out = _run(log_deal(base))
    assert out["ok"] is True
    return out["deal_id"]


# ---------------------------------------------------------------- defaults

def test_fetch_local_deals_defaults_active_only(_isolated_env: Path) -> None:
    a = _seed("A")
    _seed("B", stage="proposal")
    _seed("C")
    _run(update_deal({"deal_id": a, "stage": "won"}))

    out = _run(_fetch_local_deals({}))
    assert out["ok"] is True
    assert out["count"] == 2
    assert {d["name"] for d in out["deals"]} == {"B", "C"}
    assert out["filters"]["active_only"] is True
    assert out["filters"]["limit"] == 50
    assert out["filters"]["stage"] is None
    assert out["filters"]["owner"] is None
    assert out["exists"] is True
    assert out["path"] == str(_isolated_env)
    assert "as_of" in out


def test_fetch_local_deals_can_include_terminal(_isolated_env: Path) -> None:
    a = _seed("A")
    _run(update_deal({"deal_id": a, "stage": "won"}))
    out = _run(_fetch_local_deals({"active_only": False}))
    assert out["count"] == 1
    assert out["filters"]["active_only"] is False


def test_fetch_local_deals_missing_store_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LOCAL_DEALS_ENV_VAR, str(tmp_path / "missing.json"))
    out = _run(_fetch_local_deals({}))
    assert out["ok"] is True
    assert out["count"] == 0
    assert out["exists"] is False
    assert out["deals"] == []
    assert out["by_stage"] == {}
    assert out["by_owner"] == {}
    assert out["pipeline_usd"] == 0.0


def test_fetch_local_deals_path_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(LOCAL_DEALS_ENV_VAR, raising=False)
    target = tmp_path / "explicit.json"
    target.write_text(
        json.dumps(
            [
                {
                    "id": "local-0001",
                    "name": "Acme",
                    "amount": 5_000,
                    "stage": "proposal",
                    "owner": "Sam",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = _run(_fetch_local_deals({"path": str(target)}))
    assert out["count"] == 1
    assert out["path"] == str(target)
    assert out["pipeline_usd"] == 5_000.0
    assert out["by_owner"] == {"Sam": 1}


# ---------------------------------------------------------------- aggregations

def test_fetch_local_deals_aggregates_by_stage_owner(_isolated_env: Path) -> None:
    _seed("A", amount=100, stage="discovery", owner="Sam")
    _seed("B", amount=200, stage="proposal", owner="Sam")
    _seed("C", amount=300, stage="proposal", owner="Alex")
    out = _run(_fetch_local_deals({}))
    assert out["count"] == 3
    assert out["by_stage"] == {"discovery": 1, "proposal": 2}
    assert out["by_owner"] == {"Sam": 2, "Alex": 1}
    assert out["pipeline_usd"] == 600.0


def test_fetch_local_deals_pipeline_excludes_terminal(_isolated_env: Path) -> None:
    a = _seed("A", amount=100)
    _seed("B", amount=200)
    _run(update_deal({"deal_id": a, "stage": "won"}))
    out = _run(_fetch_local_deals({"active_only": False}))
    assert out["count"] == 2
    assert out["pipeline_usd"] == 200.0  # 'won' excluded from pipeline_usd


def test_fetch_local_deals_owner_filter_normalises(_isolated_env: Path) -> None:
    _seed("A", owner="Sam")
    _seed("B", owner="Alex")
    out = _run(_fetch_local_deals({"owner": "sam"}))
    assert out["count"] == 1
    assert out["filters"]["owner"] == "sam"


def test_fetch_local_deals_stage_filter_normalises(_isolated_env: Path) -> None:
    _seed("A", stage="proposal")
    _seed("B", stage="proposal")
    _seed("C")
    out = _run(_fetch_local_deals({"stage": "PROPOSAL"}))
    assert out["count"] == 2
    assert out["filters"]["stage"] == "proposal"


def test_fetch_local_deals_limit_clamps_to_200(_isolated_env: Path) -> None:
    _seed("A")
    out = _run(_fetch_local_deals({"limit": 9999}))
    assert out["filters"]["limit"] == 200


def test_fetch_local_deals_limit_garbage_falls_back_to_50(
    _isolated_env: Path,
) -> None:
    _seed("A")
    out = _run(_fetch_local_deals({"limit": "many"}))
    assert out["filters"]["limit"] == 50


def test_fetch_local_deals_limit_takes_recent_tail(_isolated_env: Path) -> None:
    for i in range(4):
        _seed(f"D{i}")
    out = _run(_fetch_local_deals({"limit": 2}))
    assert [d["name"] for d in out["deals"]] == ["D2", "D3"]


# ---------------------------------------------------------------- pack wiring

def test_business_pack_registers_local_deals_source() -> None:
    pack = get_pack("business")
    assert pack is not None
    src = pack.find_awareness("local_deals")
    assert src is not None
    assert src.kind == "local"
    assert src.fetcher is not None
    assert src.config["active_only"] is True
    assert src.config["path"].endswith("business_deals.json")


def test_to_dict_marks_local_deals_live() -> None:
    pack = get_pack("business")
    assert pack is not None
    by_id = {s["id"]: s for s in pack.to_dict()["awareness"]}
    assert by_id["local_deals"]["live"] is True
    assert by_id["local_deals"]["kind"] == "local"
