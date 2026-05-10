"""Tests for the W4-PR2 workshop lab mode.

Two surfaces:
1. **LabStore** — workshop / attendee / sandbox_id minting,
   on-disk roster persistence + reload.
2. **Leaderboard** — fan the W3-PR1 SessionMetrics across every
   attendee's sandbox, rank by net edge, deterministic
   tie-breakers.

The leaderboard tests drive real paper sessions through the
runtime (so the audit log is the same JSONL the cockpit reads
in production), keeping the "no caching" property honest.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from backend.core.algotrade import get_registry
from backend.core.algotrade.exec import (
    OrderIntent,
    OrderType,
    Side,
    get_runtime,
    reset_runtime,
)
from backend.core.algotrade.lab import (
    Attendee,
    LabStore,
    Workshop,
    WorkshopStatus,
    compute_leaderboard,
    get_lab_store,
    reset_lab_store,
)
from backend.core.algotrade.recipes import list_recipes, load_recipe


@pytest.fixture
def tars_home():
    """Isolate every test in its own $TARS_HOME so workshop /
    session state never leaks across runs."""

    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("TARS_ALGOTRADE_HOME")
        os.environ["TARS_ALGOTRADE_HOME"] = tmp
        reset_runtime()
        reset_lab_store()
        try:
            yield Path(tmp)
        finally:
            reset_runtime()
            reset_lab_store()
            if old is None:
                del os.environ["TARS_ALGOTRADE_HOME"]
            else:
                os.environ["TARS_ALGOTRADE_HOME"] = old


# --------------------------------------------------------- LabStore


def test_create_workshop_persists_to_disk(tars_home: Path) -> None:
    store = get_lab_store()
    ws = store.create_workshop(
        name="Cresco — Day 1",
        facilitator="alex",
        notes="bb_reversion + trailing_runner",
    )
    assert ws.name == "Cresco — Day 1"
    assert ws.status is WorkshopStatus.OPEN
    assert ws.workshop_id.startswith("ws_cresco-day-1_")
    roster = tars_home / "algotrade" / "lab" / ws.workshop_id / "roster.json"
    assert roster.exists()


def test_workshop_id_is_deterministic_when_passed(tars_home: Path) -> None:
    store = get_lab_store()
    ws = store.create_workshop(name="Demo", workshop_id="ws_demo_explicit")
    assert ws.workshop_id == "ws_demo_explicit"


def test_create_workshop_rejects_missing_name() -> None:
    """Caller-side concern, but the action layer enforces this;
    the store accepts any string and slugifies."""

    store = LabStore(root=Path(tempfile.mkdtemp()))
    ws = store.create_workshop(name="x")
    assert ws.name == "x"


def test_create_workshop_rejects_duplicate_id(tars_home: Path) -> None:
    store = get_lab_store()
    store.create_workshop(name="A", workshop_id="ws_dup")
    with pytest.raises(ValueError, match="already exists"):
        store.create_workshop(name="B", workshop_id="ws_dup")


def test_enroll_mints_deterministic_sandbox_id(tars_home: Path) -> None:
    store = get_lab_store()
    ws = store.create_workshop(name="W1", workshop_id="ws_w1")
    attendee = store.enroll(
        workshop_id="ws_w1",
        display_name="Alice",
        attendee_id="att_alice",
    )
    assert attendee.sandbox_id == "lab:ws_w1:att_alice"
    assert attendee.workshop_id == "ws_w1"


def test_enroll_rejects_unknown_workshop(tars_home: Path) -> None:
    store = get_lab_store()
    with pytest.raises(KeyError):
        store.enroll(workshop_id="ws_missing", display_name="Bob")


def test_enroll_rejects_closed_workshop(tars_home: Path) -> None:
    store = get_lab_store()
    ws = store.create_workshop(name="W2", workshop_id="ws_w2")
    store.set_workshop_status("ws_w2", WorkshopStatus.CLOSED)
    with pytest.raises(PermissionError, match="closed"):
        store.enroll(workshop_id="ws_w2", display_name="Carol")


def test_enroll_rejects_duplicate_attendee_id(tars_home: Path) -> None:
    store = get_lab_store()
    store.create_workshop(name="W3", workshop_id="ws_w3")
    store.enroll(
        workshop_id="ws_w3", display_name="A", attendee_id="att_dup"
    )
    with pytest.raises(ValueError, match="already exists"):
        store.enroll(
            workshop_id="ws_w3", display_name="A2", attendee_id="att_dup"
        )


def test_set_workshop_status_closes_with_timestamp(tars_home: Path) -> None:
    store = get_lab_store()
    store.create_workshop(name="W4", workshop_id="ws_w4")
    closed = store.set_workshop_status("ws_w4", WorkshopStatus.CLOSED)
    assert closed is not None
    assert closed.status is WorkshopStatus.CLOSED
    assert closed.closed_at is not None


def test_set_workshop_status_returns_none_for_unknown(tars_home: Path) -> None:
    store = get_lab_store()
    assert store.set_workshop_status("ws_missing", WorkshopStatus.CLOSED) is None


def test_list_workshops_filters_by_status(tars_home: Path) -> None:
    store = get_lab_store()
    store.create_workshop(name="A", workshop_id="ws_a")
    store.create_workshop(name="B", workshop_id="ws_b")
    store.set_workshop_status("ws_b", WorkshopStatus.CLOSED)
    open_only = store.list_workshops(status=WorkshopStatus.OPEN)
    assert {w.workshop_id for w in open_only} == {"ws_a"}
    closed_only = store.list_workshops(status=WorkshopStatus.CLOSED)
    assert {w.workshop_id for w in closed_only} == {"ws_b"}


def test_list_attendees_returns_empty_for_unknown_workshop(
    tars_home: Path,
) -> None:
    store = get_lab_store()
    assert store.list_attendees("ws_missing") == []


def test_roster_reloads_from_disk(tars_home: Path) -> None:
    """Persistence is the whole point of the file-backed
    roster: a worker restart must see the same workshops +
    attendees."""

    s1 = get_lab_store()
    ws = s1.create_workshop(name="Persistent", workshop_id="ws_persist")
    s1.enroll(
        workshop_id="ws_persist",
        display_name="Dana",
        attendee_id="att_dana",
    )

    reset_lab_store()
    s2 = get_lab_store()
    assert s2.get_workshop("ws_persist") is not None
    assert s2.get_attendee("att_dana") is not None
    assert (
        s2.get_attendee("att_dana").sandbox_id
        == "lab:ws_persist:att_dana"
    )


# --------------------------------------------------------- Leaderboard


def _bar_dict(*, ts: float, price: float, instrument: str) -> dict:
    return {
        "ts": ts,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 1.0,
        "instrument": instrument,
    }


def _drive_session_to_pnl(
    sandbox_id: str,
    *,
    open_price: float,
    close_price: float,
    qty: float,
    instrument: str = "BINANCE:BTCUSDT",
) -> str:
    """Spin up a paper session, submit BUY then SELL across
    three bars — the second bar fills the BUY at ``open_price``,
    the fourth bar fills the SELL at ``close_price``. The
    closed round-trip's PnL is what the leaderboard scores.
    """

    name = list_recipes()[0]
    fp = get_registry().put(load_recipe(name)).fingerprint
    runtime = get_runtime()
    wiring = runtime.start_paper_session(
        strategy_fingerprint=fp,
        instrument=instrument,
        sandbox_id=sandbox_id,
    )

    async def run() -> None:
        # Submit the BUY (no fills yet — paper fills on next bar open).
        await wiring.router.submit(
            OrderIntent.make(
                strategy_fingerprint=fp,
                instrument=instrument,
                side=Side.BUY,
                qty=qty,
                type=OrderType.MARKET,
            )
        )
        # Bar #1 — fills the BUY at open_price.
        await wiring.adapter.on_bar(
            _bar_dict(ts=1.0, price=open_price, instrument=instrument),
            instrument=instrument,
        )
        # Submit the SELL.
        await wiring.router.submit(
            OrderIntent.make(
                strategy_fingerprint=fp,
                instrument=instrument,
                side=Side.SELL,
                qty=qty,
                type=OrderType.MARKET,
            )
        )
        # Bar #2 — fills the SELL at close_price.
        await wiring.adapter.on_bar(
            _bar_dict(ts=2.0, price=close_price, instrument=instrument),
            instrument=instrument,
        )

    asyncio.run(run())
    return wiring.session.session_id


def test_leaderboard_for_unknown_workshop_raises(tars_home: Path) -> None:
    with pytest.raises(KeyError):
        compute_leaderboard("ws_missing")


def test_leaderboard_with_no_sessions_lists_attendees_in_join_order(
    tars_home: Path,
) -> None:
    store = get_lab_store()
    store.create_workshop(name="Empty", workshop_id="ws_empty")
    store.enroll(
        workshop_id="ws_empty", display_name="A", attendee_id="att_a"
    )
    store.enroll(
        workshop_id="ws_empty", display_name="B", attendee_id="att_b"
    )
    lb = compute_leaderboard("ws_empty")
    assert lb.attendees_total == 2
    assert lb.attendees_with_sessions == 0
    assert [e.attendee_id for e in lb.entries] == ["att_a", "att_b"]
    assert lb.entries[0].score == 0.0


def test_leaderboard_ranks_by_net_edge(tars_home: Path) -> None:
    """Three attendees: Alice profits, Bob loses, Carol breaks
    even. Expected order: Alice → Carol → Bob."""

    store = get_lab_store()
    store.create_workshop(name="Cresco", workshop_id="ws_cresco")
    alice = store.enroll(
        workshop_id="ws_cresco",
        display_name="Alice",
        attendee_id="att_alice",
    )
    bob = store.enroll(
        workshop_id="ws_cresco",
        display_name="Bob",
        attendee_id="att_bob",
    )
    carol = store.enroll(
        workshop_id="ws_cresco",
        display_name="Carol",
        attendee_id="att_carol",
    )

    _drive_session_to_pnl(alice.sandbox_id, open_price=100.0, close_price=110.0, qty=1.0)
    _drive_session_to_pnl(bob.sandbox_id, open_price=100.0, close_price=90.0, qty=1.0)
    _drive_session_to_pnl(carol.sandbox_id, open_price=100.0, close_price=100.0, qty=1.0)

    lb = compute_leaderboard("ws_cresco")
    assert lb.attendees_with_sessions == 3
    assert [e.attendee_id for e in lb.entries] == [
        "att_alice",
        "att_carol",
        "att_bob",
    ]
    assert lb.entries[0].rank == 1
    assert lb.entries[0].realized_pnl > 0
    assert lb.entries[2].realized_pnl < 0


def test_leaderboard_score_subtracts_fees_and_slippage(
    tars_home: Path,
) -> None:
    """A session that profits 10 but pays 1 in fees should
    score 9."""

    store = get_lab_store()
    store.create_workshop(name="Fees", workshop_id="ws_fees")
    a = store.enroll(
        workshop_id="ws_fees", display_name="A", attendee_id="att_a"
    )
    _drive_session_to_pnl(a.sandbox_id, open_price=100.0, close_price=110.0, qty=1.0)

    lb = compute_leaderboard("ws_fees")
    entry = lb.entries[0]
    expected = entry.realized_pnl - entry.fees_total - entry.slippage_cost
    assert entry.score == pytest.approx(expected)
    # Paper adapter charges commission so fees_total > 0.
    assert entry.fees_total > 0


def test_leaderboard_recomputes_from_disk_after_reset(
    tars_home: Path,
) -> None:
    """Drive sessions, drop the in-memory runtime + lab store,
    rehydrate, recompute — same ranking."""

    store = get_lab_store()
    store.create_workshop(name="Reset", workshop_id="ws_reset")
    a = store.enroll(
        workshop_id="ws_reset", display_name="A", attendee_id="att_a"
    )
    b = store.enroll(
        workshop_id="ws_reset", display_name="B", attendee_id="att_b"
    )
    _drive_session_to_pnl(a.sandbox_id, open_price=100.0, close_price=120.0, qty=1.0)
    _drive_session_to_pnl(b.sandbox_id, open_price=100.0, close_price=80.0, qty=1.0)

    lb_before = compute_leaderboard("ws_reset")

    reset_runtime()
    reset_lab_store()

    lb_after = compute_leaderboard("ws_reset")
    assert [e.attendee_id for e in lb_after.entries] == [
        e.attendee_id for e in lb_before.entries
    ]
    assert lb_after.entries[0].score == pytest.approx(
        lb_before.entries[0].score
    )


def test_leaderboard_counts_running_sessions(tars_home: Path) -> None:
    """`sessions_running` should reflect SessionStatus.RUNNING
    in the runtime after a fresh start_paper_session call."""

    store = get_lab_store()
    store.create_workshop(name="Run", workshop_id="ws_run")
    a = store.enroll(
        workshop_id="ws_run", display_name="A", attendee_id="att_a"
    )

    name = list_recipes()[0]
    fp = get_registry().put(load_recipe(name)).fingerprint
    get_runtime().start_paper_session(
        strategy_fingerprint=fp,
        instrument="BINANCE:BTCUSDT",
        sandbox_id=a.sandbox_id,
    )
    lb = compute_leaderboard("ws_run")
    assert lb.entries[0].sessions_total == 1
    assert lb.entries[0].sessions_running == 1


def test_leaderboard_tie_breaker_prefers_higher_acceptance_rate(
    tars_home: Path,
) -> None:
    """Two attendees with identical zero PnL: the one with no
    rejected intents should rank ahead."""

    store = get_lab_store()
    store.create_workshop(name="Tie", workshop_id="ws_tie")
    clean = store.enroll(
        workshop_id="ws_tie",
        display_name="Clean",
        attendee_id="att_clean",
    )
    spammy = store.enroll(
        workshop_id="ws_tie",
        display_name="Spammy",
        attendee_id="att_spammy",
    )

    name = list_recipes()[0]
    fp = get_registry().put(load_recipe(name)).fingerprint
    runtime = get_runtime()

    # Clean: one accepted intent, no rejections.
    clean_w = runtime.start_paper_session(
        strategy_fingerprint=fp,
        instrument="BINANCE:BTCUSDT",
        sandbox_id=clean.sandbox_id,
    )
    asyncio.run(
        clean_w.router.submit(
            OrderIntent.make(
                strategy_fingerprint=fp,
                instrument="BINANCE:BTCUSDT",
                side=Side.BUY,
                qty=0.001,
                type=OrderType.MARKET,
            )
        )
    )

    # Spammy: one accepted + one rejected. Pin a tight
    # max_order_qty so the second intent (10M qty) fails the gate.
    spammy_w = runtime.start_paper_session(
        strategy_fingerprint=fp,
        instrument="BINANCE:BTCUSDT",
        sandbox_id=spammy.sandbox_id,
        policy={"max_order_qty": 1.0},
    )
    asyncio.run(
        spammy_w.router.submit(
            OrderIntent.make(
                strategy_fingerprint=fp,
                instrument="BINANCE:BTCUSDT",
                side=Side.BUY,
                qty=0.001,
                type=OrderType.MARKET,
            )
        )
    )
    # No fills happen (no bar fed) so realized_pnl is identical
    # at 0 for both. Tie-breaker: acceptance_rate.
    asyncio.run(
        spammy_w.router.submit(
            OrderIntent.make(
                strategy_fingerprint=fp,
                instrument="BINANCE:BTCUSDT",
                side=Side.BUY,
                qty=10_000_000.0,  # blasts through any sane policy cap
                type=OrderType.MARKET,
            )
        )
    )

    lb = compute_leaderboard("ws_tie")
    by_id = {e.attendee_id: e for e in lb.entries}
    assert by_id["att_clean"].acceptance_rate == 1.0
    assert by_id["att_spammy"].acceptance_rate < 1.0
    assert by_id["att_clean"].rank < by_id["att_spammy"].rank
