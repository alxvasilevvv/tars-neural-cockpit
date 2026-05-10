"""Tests for the recursive playbook loader (W4 prep).

Before W4 the loader walked one directory deep
(`playbooks/<pack>/foo.json`), which silently dropped every nested
workshop vertical (`playbooks/_workshop/<vertical>/foo.json`).
The recursive walk is what makes the workshop verticals
(``_workshop/algotrade/``, ``_workshop/quant/``,
``_workshop/saas/``, ``_workshop/fund/`` etc.) actually
discoverable to the runner + cockpit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.playbooks.loader import (
    discover,
    list_playbooks,
    reset_loader_cache,
)


@pytest.fixture
def tmp_playbooks(tmp_path: Path):
    return tmp_path


def _write(path: Path, blob: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob))


def test_recursive_walk_discovers_nested_verticals(tmp_playbooks: Path) -> None:
    _write(
        tmp_playbooks / "alpha" / "morning.json",
        {
            "id": "alpha.morning",
            "name": "Alpha morning",
            "description": "",
            "steps": [{"id": "s1", "action": "alpha.foo", "args": {}}],
        },
    )
    _write(
        tmp_playbooks / "_workshop" / "quant" / "lab.json",
        {
            "id": "_workshop.quant.lab",
            "name": "Quant lab",
            "description": "",
            "pack": "algotrade",
            "steps": [{"id": "s1", "action": "algotrade.backtest", "args": {}}],
        },
    )
    _write(
        tmp_playbooks / "_workshop" / "fund" / "morning.json",
        {
            "id": "_workshop.fund.morning",
            "name": "Fund morning",
            "description": "",
            "pack": "workshop",
            "steps": [{"id": "s1", "action": "business.morning", "args": {}}],
        },
    )

    out = discover(tmp_playbooks)
    ids = set(out.keys())
    assert ids == {
        "alpha.morning",
        "_workshop.quant.lab",
        "_workshop.fund.morning",
    }


def test_explicit_pack_field_wins_over_dir_name(tmp_playbooks: Path) -> None:
    _write(
        tmp_playbooks / "_workshop" / "quant" / "lab.json",
        {
            "id": "_workshop.quant.lab",
            "name": "Lab",
            "description": "",
            "pack": "algotrade",
            "steps": [{"id": "s1", "action": "algotrade.backtest", "args": {}}],
        },
    )
    out = discover(tmp_playbooks)
    pb = out["_workshop.quant.lab"]
    assert pb.pack == "algotrade"


def test_dir_chain_used_when_no_explicit_pack(tmp_playbooks: Path) -> None:
    _write(
        tmp_playbooks / "_workshop" / "quant" / "lab.json",
        {
            "id": "_workshop.quant.lab",
            "name": "Lab",
            "description": "",
            "steps": [{"id": "s1", "action": "alpha.foo", "args": {}}],
        },
    )
    out = discover(tmp_playbooks)
    pb = out["_workshop.quant.lab"]
    assert pb.pack == "_workshop.quant"


def test_top_level_files_skipped_without_pack_dir(tmp_playbooks: Path) -> None:
    _write(
        tmp_playbooks / "rogue.json",
        {
            "id": "rogue",
            "name": "rogue",
            "description": "",
            "steps": [{"id": "s1", "action": "alpha.foo", "args": {}}],
        },
    )
    out = discover(tmp_playbooks)
    assert "rogue" not in out


def test_duplicate_id_across_verticals_raises(tmp_playbooks: Path) -> None:
    _write(
        tmp_playbooks / "_workshop" / "quant" / "x.json",
        {
            "id": "dup",
            "name": "x",
            "description": "",
            "steps": [{"id": "s1", "action": "alpha.foo", "args": {}}],
        },
    )
    _write(
        tmp_playbooks / "_workshop" / "fund" / "x.json",
        {
            "id": "dup",
            "name": "x",
            "description": "",
            "steps": [{"id": "s1", "action": "alpha.foo", "args": {}}],
        },
    )
    with pytest.raises(ValueError, match="duplicate playbook id"):
        discover(tmp_playbooks)


def test_shipped_workshop_playbooks_load(monkeypatch) -> None:
    """Smoke test against the actual shipped playbooks tree."""

    reset_loader_cache()
    monkeypatch.delenv("TARS_PLAYBOOKS_DIR", raising=False)
    ids = {p.id for p in list_playbooks(refresh=True)}

    expected_quant = {
        "_workshop.quant.recipe_to_paper",
        "_workshop.quant.backtest_compare",
        "_workshop.quant.morning_pnl",
        "_workshop.quant.risk_review",
        "_workshop.quant.strategy_lab",
    }
    expected_algotrade = {
        "_workshop.algotrade.mean_reversion_strategy",
        "_workshop.algotrade.momentum_breakout_strategy",
        "_workshop.algotrade.live_paper_session",
        "_workshop.algotrade.backtest_to_live_pipeline",
        "_workshop.algotrade.risk_audit_weekly",
    }
    assert expected_quant <= ids, expected_quant - ids
    assert expected_algotrade <= ids, expected_algotrade - ids
