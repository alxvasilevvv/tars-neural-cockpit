"""Tests for the awareness source fetchers introduced in Phase A.

Network-bound fetchers (`traders.binance_ws`, `traders.portfolio_local`,
`science.arxiv`) are exercised by the smoke harness in `serve.py`. Here
we cover the local-data fetchers and shape invariants.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.registry import get_pack
from backend.core.domains.packs.business.awareness import (
    _fetch_calendar,
    _fetch_gsheets_kpi,
    _fetch_hubspot,
)
from backend.core.domains.packs.science.awareness import (
    _fetch_datasets_dir,
    _fetch_local_papers,
)


def test_business_calendar_reads_sample() -> None:
    out = asyncio.run(_fetch_calendar({}))
    assert out["ok"] is True, out
    assert out["count"] >= 3
    assert all("title" in e for e in out["events"])


def test_business_kpi_via_awareness_matches_action_data() -> None:
    out = asyncio.run(_fetch_gsheets_kpi({}))
    assert out["ok"] is True
    assert "metrics" in out
    assert "mrr_usd" in out["metrics"]


def test_business_hubspot_aggregates_pipeline() -> None:
    out = asyncio.run(_fetch_hubspot({}))
    assert out["ok"] is True
    assert "by_stage" in out
    assert out["pipeline_usd"] > 0
    assert out["deals_total"] >= 5


def test_science_local_papers_handles_missing_dir(tmp_path) -> None:
    out = asyncio.run(_fetch_local_papers({"path": str(tmp_path / "nope")}))
    assert out["ok"] is True
    assert out["count"] == 0


def test_science_datasets_dir_handles_missing_dir(tmp_path) -> None:
    out = asyncio.run(_fetch_datasets_dir({"path": str(tmp_path / "nope")}))
    assert out["ok"] is True
    assert out["count"] == 0


def test_science_local_papers_lists_real_files(tmp_path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "b.md").write_text("# fake paper")
    (tmp_path / "ignore.bin").write_bytes(b"\x00\x01")
    out = asyncio.run(_fetch_local_papers({"path": str(tmp_path)}))
    assert out["ok"] is True
    assert out["count"] == 2
    names = {f["name"] for f in out["files"]}
    assert names == {"a.pdf", "b.md"}


@pytest.mark.parametrize(
    "slug,source_id",
    [
        ("business", "gcalendar"),
        ("business", "hubspot"),
        ("business", "gsheets_kpi"),
        ("traders", "news_feed"),
        ("mlm", "downline_db"),
    ],
)
def test_packs_advertise_live_fetchers(slug: str, source_id: str) -> None:
    pack = get_pack(slug)
    assert pack is not None
    src = pack.find_awareness(source_id)
    assert src is not None, f"{slug}/{source_id} missing"
    assert src.fetcher is not None, f"{slug}/{source_id} not live"


def test_to_dict_marks_live_flag() -> None:
    pack = get_pack("business")
    assert pack is not None
    sources = pack.to_dict()["awareness"]
    by_id = {s["id"]: s for s in sources}
    assert by_id["gcalendar"]["live"] is True
    assert by_id["gmail"]["live"] is True
