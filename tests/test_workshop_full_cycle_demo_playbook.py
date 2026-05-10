"""Acceptance tests for the
``_workshop.quant.full_cycle_demo`` playbook (Wave M6 E2E).

The playbook is the opening exercise for workshop attendees:
list_recipes → load_recipe → synthetic_bars → backtest →
register_strategy → re-backtest by fingerprint →
list_strategies. It must run offline (no Binance, no CSV
file), produce the same fingerprint every time, and complete
in well under a second.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.domains.packs.algotrade import pack as _  # registers
from backend.core.playbooks.loader import discover, reset_loader_cache
from backend.core.playbooks.runner import PlaybookRunner
from backend.core.policy import PolicyMode

PLAYBOOK_ID = "_workshop.quant.full_cycle_demo"


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_HOME", str(tmp_path))
    monkeypatch.setenv("TARS_ALGOTRADE_HOME", str(tmp_path))
    reset_loader_cache()
    yield
    reset_loader_cache()


def _get_playbook():
    pbs = discover()
    pb = pbs.get(PLAYBOOK_ID)
    assert pb is not None, (
        f"playbook {PLAYBOOK_ID} not discovered; got "
        f"{sorted(p for p in pbs if p.startswith('_workshop.quant'))}"
    )
    return pb


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------
# Discoverability + structure
# ---------------------------------------------------------------------


def test_playbook_is_discovered() -> None:
    pb = _get_playbook()
    assert pb.id == PLAYBOOK_ID
    assert "demo" in pb.tags
    assert "offline" in pb.tags
    assert pb.pack == "workshop"


def test_playbook_step_ids_are_what_the_workshop_handbook_documents() -> None:
    pb = _get_playbook()
    expected = [
        "recipes", "recipe", "tape",
        "first_backtest", "registered",
        "second_backtest", "registry",
    ]
    assert [s.id for s in pb.steps] == expected


def test_playbook_only_uses_actions_present_on_main() -> None:
    """Guard against accidental dependency on Wave-W2+
    actions like algotrade.session.start that don't exist
    on main."""

    pb = _get_playbook()
    allowed = {
        "algotrade.list_recipes",
        "algotrade.load_recipe",
        "algotrade.synthetic_bars",
        "algotrade.backtest",
        "algotrade.register_strategy",
        "algotrade.list_strategies",
    }
    used = {s.action for s in pb.steps}
    extras = used - allowed
    assert not extras, (
        f"playbook references actions not on main: {extras}. "
        "Either widen the allowlist (with reason) or pick a "
        "main-only action."
    )


# ---------------------------------------------------------------------
# Execution — the real round trip
# ---------------------------------------------------------------------


def test_playbook_runs_end_to_end_in_autopilot_mode() -> None:
    pb = _get_playbook()
    res = _run(PlaybookRunner().run(pb, mode=PolicyMode.AUTOPILOT))
    assert res["ok"] is True
    assert len(res["steps"]) == 7
    for step in res["steps"]:
        assert step["ok"] is True, (
            f"step {step['id']} failed: {step.get('error')!r} "
            f"result={step.get('result')!r}"
        )
        assert not step["skipped"]
        assert not step["blocked"]


def test_playbook_round_trip_fingerprint_is_stable() -> None:
    pb = _get_playbook()
    res = _run(PlaybookRunner().run(pb, mode=PolicyMode.AUTOPILOT))
    fp_recipe = res["steps"][1]["result"]["fingerprint"]
    fp_register = res["steps"][4]["result"]["fingerprint"]
    fp_bt1 = res["steps"][3]["result"]["strategy_fingerprint"]
    fp_bt2 = res["steps"][5]["result"]["strategy_fingerprint"]
    assert fp_recipe == fp_register == fp_bt1 == fp_bt2


def test_playbook_round_trip_metrics_match_byte_for_byte() -> None:
    """If the fingerprint is the same and the bars are the
    same, the backtest must produce identical metrics. This
    is the entire promise of the demo."""

    pb = _get_playbook()
    res = _run(PlaybookRunner().run(pb, mode=PolicyMode.AUTOPILOT))
    metrics_1 = res["steps"][3]["result"]["metrics"]
    metrics_2 = res["steps"][5]["result"]["metrics"]
    assert metrics_1 == metrics_2


def test_playbook_registers_exactly_one_strategy_in_isolated_home() -> None:
    pb = _get_playbook()
    res = _run(PlaybookRunner().run(pb, mode=PolicyMode.AUTOPILOT))
    listed = res["steps"][6]["result"]
    assert listed["count"] == 1
    rows = listed["strategies"]
    assert rows[0]["author"] == "workshop_full_cycle_demo"


def test_playbook_completes_under_one_second() -> None:
    """Workshop demo budget — facilitator should not have to
    wait. Plenty of headroom on a slow CI runner; failures
    here usually mean a hidden network call snuck in."""

    pb = _get_playbook()
    res = _run(PlaybookRunner().run(pb, mode=PolicyMode.AUTOPILOT))
    total_ms = sum(s["took_ms"] for s in res["steps"])
    assert total_ms < 1000.0, f"too slow: {total_ms:.1f}ms"
