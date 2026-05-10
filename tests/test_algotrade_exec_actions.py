"""Tests for the W2-PR1 execution actions on the algotrade pack.

End-to-end without network; each test owns its TARS_HOME so the
session store + audit log + position book never bleed across.
"""

from __future__ import annotations

import asyncio
import math
import random
from typing import Any

import pytest

from backend.core.algotrade.exec import reset_runtime
from backend.core.algotrade.strategy.registry import reset_registry_for_tests


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_HOME", str(tmp_path))
    monkeypatch.setenv("TARS_ALGOTRADE_HOME", str(tmp_path))
    reset_registry_for_tests()
    reset_runtime()
    yield
    reset_registry_for_tests()
    reset_runtime()


@pytest.fixture
def pack():
    import backend.core.domains.packs  # noqa: F401  (registration)
    from backend.core.domains.registry import get_pack

    p = get_pack("algotrade")
    assert p is not None, "algotrade pack must be registered"
    return p


def _bar(ts: float, o: float, h: float, lo: float, c: float, *, instrument: str | None = None) -> dict:
    out = {"ts": ts, "open": o, "high": h, "low": lo, "close": c, "volume": 1.0}
    if instrument:
        out["instrument"] = instrument
    return out


async def _register_recipe(pack, recipe: str = "ma_cross") -> str:
    res = await pack.find_action("register_strategy").handler({"recipe": recipe})
    assert res["ok"], res
    return res["fingerprint"]


# --------------------------------------------------------- registration


def test_exec_actions_present(pack) -> None:
    ids = {a.id for a in pack.actions()}
    expected = {
        "start_paper_session",
        "stop_session",
        "list_sessions",
        "get_session",
        "submit_intent",
        "cancel_order",
        "feed_bar",
        "get_policy",
        "set_policy",
        "audit_tail",
    }
    assert expected <= ids


def test_destructive_flags_on_writes(pack) -> None:
    by_id = {a.id: a for a in pack.actions()}
    for write_id in (
        "start_paper_session",
        "stop_session",
        "submit_intent",
        "cancel_order",
        "set_policy",
    ):
        assert by_id[write_id].destructive is True, write_id
    for read_id in ("list_sessions", "get_session", "get_policy", "audit_tail", "feed_bar"):
        assert by_id[read_id].destructive is False, read_id


def test_pack_exposes_live_sessions_awareness(pack) -> None:
    ids = {a.id for a in pack.awareness()}
    assert {"strategy_registry", "live_sessions"} <= ids


# --------------------------------------------------------- start / stop


@pytest.mark.asyncio
async def test_start_paper_session_requires_fingerprint(pack) -> None:
    res = await pack.find_action("start_paper_session").handler({})
    assert res["ok"] is False
    assert res["error"] == "missing_fingerprint"


@pytest.mark.asyncio
async def test_start_paper_session_for_unknown_strategy(pack) -> None:
    res = await pack.find_action("start_paper_session").handler(
        {"fingerprint": "sha256:" + "00" * 32}
    )
    assert res["ok"] is False
    assert res["error"] == "strategy_not_found"


@pytest.mark.asyncio
async def test_start_paper_session_creates_running_session(pack) -> None:
    fp = await _register_recipe(pack)
    res = await pack.find_action("start_paper_session").handler(
        {
            "fingerprint": fp,
            "sandbox_id": "sb_demo",
            "policy": {"max_order_qty": 5.0, "kill_switch": False},
            "config": {"slippage_bps": 0.0, "commission_bps": 0.0},
        }
    )
    assert res["ok"], res
    sess = res["session"]
    assert sess["status"] == "running"
    assert sess["mode"] == "paper"
    assert sess["sandbox_id"] == "sb_demo"
    assert res["policy"]["max_order_qty"] == 5.0


@pytest.mark.asyncio
async def test_stop_session_marks_stopped(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler({"fingerprint": fp})
    sid = started["session"]["session_id"]
    res = await pack.find_action("stop_session").handler({"session_id": sid})
    assert res["ok"]
    assert res["session"]["status"] == "stopped"
    assert res["session"]["closed_at"] is not None


@pytest.mark.asyncio
async def test_stop_unknown_session_errors(pack) -> None:
    res = await pack.find_action("stop_session").handler({"session_id": "sess_doesnotexist"})
    assert res["ok"] is False
    assert res["error"] == "session_not_found"


# --------------------------------------------------------- listing


@pytest.mark.asyncio
async def test_list_sessions_filters_by_sandbox(pack) -> None:
    fp = await _register_recipe(pack)
    handler = pack.find_action("start_paper_session").handler
    await handler({"fingerprint": fp, "sandbox_id": "sb_a"})
    await handler({"fingerprint": fp, "sandbox_id": "sb_b"})
    res = await pack.find_action("list_sessions").handler({"sandbox_id": "sb_a"})
    assert res["ok"]
    assert res["count"] == 1
    assert res["sessions"][0]["sandbox_id"] == "sb_a"


# --------------------------------------------------------- intents / fills


@pytest.mark.asyncio
async def test_submit_intent_blocked_by_kill_switch(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {"fingerprint": fp, "policy": {"kill_switch": True}}
    )
    sid = started["session"]["session_id"]
    res = await pack.find_action("submit_intent").handler(
        {"session_id": sid, "side": "buy", "qty": 1.0}
    )
    assert res["ok"]  # envelope ok; verdict carries the rejection
    assert res["verdict"]["accepted"] is False
    assert "kill_switch" in res["verdict"]["triggered_rules"]
    assert res["order"] is None


@pytest.mark.asyncio
async def test_submit_market_intent_then_feed_bar_fills(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {
            "fingerprint": fp,
            "config": {"slippage_bps": 0.0, "commission_bps": 0.0},
        }
    )
    sid = started["session"]["session_id"]

    submit_res = await pack.find_action("submit_intent").handler(
        {
            "session_id": sid,
            "side": "buy",
            "qty": 1.0,
            "type": "market",
        }
    )
    assert submit_res["ok"]
    assert submit_res["verdict"]["accepted"] is True
    assert submit_res["order"]["status"] == "new"

    feed_res = await pack.find_action("feed_bar").handler(
        {
            "session_id": sid,
            "bar": _bar(1, 100.0, 101.0, 99.0, 100.5, instrument="BINANCE:BTCUSDT"),
        }
    )
    assert feed_res["ok"]
    assert len(feed_res["fills"]) == 1
    fill = feed_res["fills"][0]
    assert fill["price"] == pytest.approx(100.0)
    assert feed_res["positions"][0]["qty"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_submit_intent_validates_inputs(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler({"fingerprint": fp})
    sid = started["session"]["session_id"]
    h = pack.find_action("submit_intent").handler

    assert (await h({"session_id": sid}))["error"] == "invalid_side"
    assert (await h({"session_id": sid, "side": "buy", "qty": -1}))["error"] == "invalid_qty"
    assert (await h({"session_id": sid, "side": "buy", "qty": 1.0, "type": "limit"}))["error"] == "missing_price"
    assert (await h({"session_id": sid, "side": "weird", "qty": 1.0}))["error"] == "invalid_side"


# --------------------------------------------------------- cancel


@pytest.mark.asyncio
async def test_cancel_open_limit_order(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler({"fingerprint": fp})
    sid = started["session"]["session_id"]
    submit = await pack.find_action("submit_intent").handler(
        {
            "session_id": sid,
            "side": "buy",
            "qty": 1.0,
            "type": "limit",
            "price": 50.0,
        }
    )
    oid = submit["order"]["order_id"]
    res = await pack.find_action("cancel_order").handler({"session_id": sid, "order_id": oid})
    assert res["ok"]
    assert res["order"]["status"] == "canceled"


# --------------------------------------------------------- get_session


@pytest.mark.asyncio
async def test_get_session_snapshot_contains_everything(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {
            "fingerprint": fp,
            "config": {"slippage_bps": 0.0, "commission_bps": 0.0},
        }
    )
    sid = started["session"]["session_id"]
    await pack.find_action("submit_intent").handler(
        {"session_id": sid, "side": "buy", "qty": 1.0}
    )
    await pack.find_action("feed_bar").handler(
        {"session_id": sid, "bar": _bar(1, 100.0, 101.0, 99.0, 100.5, instrument="BINANCE:BTCUSDT")}
    )
    snap = await pack.find_action("get_session").handler({"session_id": sid})
    assert snap["ok"]
    assert snap["session"]["session_id"] == sid
    assert snap["positions"]
    assert snap["audit_tail"]
    assert any(e["kind"] == "fill" for e in snap["audit_tail"])
    assert snap["unrealized_pnl"] != 0  # marked at 100.5 vs entry 100.0


# --------------------------------------------------------- policy


@pytest.mark.asyncio
async def test_set_policy_updates_gate(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler({"fingerprint": fp})
    sid = started["session"]["session_id"]
    res = await pack.find_action("set_policy").handler(
        {"session_id": sid, "policy": {"max_order_qty": 0.1, "allow_short": False}}
    )
    assert res["ok"]
    blocked = await pack.find_action("submit_intent").handler(
        {"session_id": sid, "side": "buy", "qty": 1.0}
    )
    assert blocked["verdict"]["accepted"] is False
    assert "max_order_qty" in blocked["verdict"]["triggered_rules"]


@pytest.mark.asyncio
async def test_get_policy_round_trip(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {"fingerprint": fp, "policy": {"notes": "demo"}}
    )
    sid = started["session"]["session_id"]
    res = await pack.find_action("get_policy").handler({"session_id": sid})
    assert res["ok"]
    assert res["policy"]["notes"] == "demo"


# --------------------------------------------------------- audit


@pytest.mark.asyncio
async def test_audit_tail_returns_recent_events(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {
            "fingerprint": fp,
            "config": {"slippage_bps": 0.0, "commission_bps": 0.0},
        }
    )
    sid = started["session"]["session_id"]
    await pack.find_action("submit_intent").handler(
        {"session_id": sid, "side": "buy", "qty": 1.0}
    )
    res = await pack.find_action("audit_tail").handler({"session_id": sid, "limit": 10})
    assert res["ok"]
    kinds = [e["kind"] for e in res["events"]]
    assert "intent" in kinds and "verdict" in kinds and "order" in kinds


# --------------------------------------------------------- awareness


@pytest.mark.asyncio
async def test_live_sessions_awareness_lists_running_sessions(pack) -> None:
    fp = await _register_recipe(pack)
    started = await pack.find_action("start_paper_session").handler(
        {"fingerprint": fp, "sandbox_id": "sb_x"}
    )
    sid = started["session"]["session_id"]
    src = next(s for s in pack.awareness() if s.id == "live_sessions")
    snap = await src.fetcher({})
    assert snap["ok"]
    assert snap["count"] >= 1
    assert any(row["session_id"] == sid for row in snap["sessions"])
    filtered = await src.fetcher({"sandbox_id": "sb_other"})
    assert filtered["count"] == 0
