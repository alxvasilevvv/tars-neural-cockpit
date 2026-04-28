"""Local tests for the real-data adapters that don't need network.

The network-bound adapters (arXiv, DexScreener) are exercised by the
existing smoke harness in ``serve.py`` + curl. Here we cover the
deterministic, file-backed handlers and the input parsing of the
network-bound ones (so we still catch regressions without flakiness).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from backend.core.domains import packs as _packs  # noqa: F401 (registers)
from backend.core.domains.packs.business.actions import (
    daily_brief,
    kpi_snapshot,
)
from backend.core.domains.packs.mlm.actions import (
    downline_snapshot,
    retention_alert,
    score_recruit,
)
from backend.core.domains.packs.science.actions import (
    _normalize_arxiv_ref,
    summarize_paper,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_kpi_snapshot_reads_local_sample() -> None:
    result = asyncio.run(kpi_snapshot({}))
    assert result["ok"] is True, result
    assert "metrics" in result
    assert any(m["id"] == "mrr_usd" for m in result["summary"])
    assert "as_of" in result


def test_kpi_snapshot_missing_path_is_handled(tmp_path: Path) -> None:
    bogus = tmp_path / "nope.json"
    result = asyncio.run(kpi_snapshot({"path": str(bogus)}))
    assert result["ok"] is False
    assert result["error"] == "kpi_file_missing"


def test_daily_brief_composes_summary() -> None:
    result = asyncio.run(daily_brief({}))
    assert result["ok"] is True, result
    assert isinstance(result["deltas"], list)
    assert isinstance(result["actions"], list)
    assert "summary" in result
    assert result["summary"]


def test_daily_brief_handles_missing_files(tmp_path: Path) -> None:
    result = asyncio.run(
        daily_brief(
            {
                "kpi_path": str(tmp_path / "missing-kpi.json"),
                "deals_path": str(tmp_path / "missing-deals.json"),
            }
        )
    )
    assert result["ok"] is True
    assert result["deltas"] == []
    assert result["actions"] == []


def test_downline_snapshot_reads_csv() -> None:
    result = asyncio.run(downline_snapshot({}))
    assert result["ok"] is True, result
    assert result["total"] >= 10
    assert result["active"] + result["dormant"] == result["total"]
    assert any(m["depth"] == 0 for m in result["members"])  # at least one root
    assert "by_depth" in result


def test_retention_alert_finds_silent_members() -> None:
    result = asyncio.run(retention_alert({"threshold_days": 30}))
    assert result["ok"] is True
    for entry in result["at_risk"]:
        assert entry["days_silent"] >= 30


def test_score_recruit_is_deterministic_and_bounded() -> None:
    a = asyncio.run(score_recruit({"handle": "@nora"}))
    b = asyncio.run(score_recruit({"handle": "@nora"}))
    assert a["score"] == b["score"]
    assert 0.0 <= a["score"] <= 1.0


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2305.13245", "2305.13245"),
        ("arxiv:2305.13245", "2305.13245"),
        ("arXiv:2305.13245v2", "2305.13245v2"),
        ("https://arxiv.org/abs/2305.13245", "2305.13245"),
        ("not a paper", None),
        ("", None),
    ],
)
def test_normalize_arxiv_ref(raw: str, expected: str | None) -> None:
    assert _normalize_arxiv_ref(raw) == expected


def test_summarize_paper_rejects_empty() -> None:
    out = asyncio.run(summarize_paper({}))
    assert out["ok"] is False
    assert out["error"] == "ref_required"


def test_summarize_paper_rejects_garbage_ref() -> None:
    out = asyncio.run(summarize_paper({"ref": "not a ref"}))
    assert out["ok"] is False
    assert out["error"] == "ref_unrecognised"
