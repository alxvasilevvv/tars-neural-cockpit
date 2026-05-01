"""Crossref fallback for OLD-style arXiv ids in ``science.summarize_paper``.

OpenAlex resolution depends on the ``10.48550/arXiv.<id>`` DOI, which arXiv
does **not** mint for legacy ids like ``cs/9901001`` or
``cs.AI/0301001``. The fallback consults Crossref's bibliographic search
using title + first-author surname pulled from the arXiv Atom record.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from backend.core.domains.packs.science import actions as science_actions
from backend.core.domains.packs.science import crossref as crossref_mod
from backend.core.domains.packs.science.actions import (
    _is_old_style_arxiv,
    summarize_paper,
)
from backend.core.domains.packs.science.crossref import (
    _first_surname,
    _publication_year,
    _title_overlap,
    enrich_via_crossref,
)


_OLD_ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/cs/9901001v1</id>
    <title>The Latent Semantics of Topic-Sensitive Web Search</title>
    <summary>We present a probabilistic model for ranking topic-relevant
documents from a categorised web crawl. The approach combines latent
factors with link-based authority signals to outperform purely textual
baselines on the WT2g and WT10g benchmarks.</summary>
    <published>1999-01-01T00:00:00Z</published>
    <author><name>Alice Researcher</name></author>
    <author><name>Bob Engineer</name></author>
    <category term="cs.IR" />
    <arxiv:primary_category term="cs.IR" />
  </entry>
</feed>
"""


def _make_text(body: str, status: int = 200):
    async def _fake(url, *, params=None, headers=None, timeout=8.0):
        return status, body

    return _fake


def _make_json(payload: Any, status: int = 200):
    async def _fake(url, *, params=None, headers=None, timeout=8.0):
        return status, payload

    return _fake


def _crossref_payload(*items: Mapping[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "message": {"items": list(items)}}


def test_is_old_style_recognises_legacy_ids() -> None:
    assert _is_old_style_arxiv("cs/9901001") is True
    assert _is_old_style_arxiv("cs.AI/0301001") is True
    assert _is_old_style_arxiv("math.AT/0701035") is True
    assert _is_old_style_arxiv("2305.13245") is False
    assert _is_old_style_arxiv("2305.13245v2") is False


def test_title_overlap_is_jaccard_like() -> None:
    a = "Latent Semantics of Topic-Sensitive Web Search"
    b = "The Latent Semantics of Topic-Sensitive Web Search"
    assert _title_overlap(a, b) > 0.7
    assert _title_overlap(a, "completely unrelated paper title") < 0.2
    assert _title_overlap("", "anything") == 0.0


def test_first_surname_handles_multi_word_last_names() -> None:
    assert _first_surname(["Alice de la Cruz", "Bob"]) == "Cruz"
    assert _first_surname(["", "Bob"]) == "Bob"
    assert _first_surname([]) is None


def test_publication_year_walks_known_keys() -> None:
    assert _publication_year({"issued": {"date-parts": [[2003, 4, 1]]}}) == 2003
    assert (
        _publication_year(
            {"published-print": {"date-parts": [[1999]]}}
        )
        == 1999
    )
    assert _publication_year({"created": {"date-parts": [[]]}}) is None
    assert _publication_year({}) is None


def test_crossref_fallback_returns_none_without_title() -> None:
    out = asyncio.run(enrich_via_crossref("cs/9901001", title=None))
    assert out is None


def test_crossref_fallback_picks_best_match(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _crossref_payload(
        {
            "DOI": "10.1145/9999",
            "title": ["Completely unrelated paper title"],
            "is-referenced-by-count": 1,
            "publisher": "ACM",
            "issued": {"date-parts": [[2024]]},
        },
        {
            "DOI": "10.1145/12345",
            "title": ["The Latent Semantics of Topic-Sensitive Web Search"],
            "is-referenced-by-count": 421,
            "publisher": "ACM",
            "issued": {"date-parts": [[2000, 6]]},
        },
    )
    monkeypatch.setattr(crossref_mod, "get_json", _make_json(payload))

    out = asyncio.run(
        enrich_via_crossref(
            "cs/9901001",
            title="Latent Semantics of Topic-Sensitive Web Search",
            authors=["Alice Researcher", "Bob Engineer"],
        )
    )
    assert out is not None
    assert out["doi"] == "10.1145/12345"
    assert out["url"] == "https://doi.org/10.1145/12345"
    assert out["publication_year"] == 2000
    assert out["cited_by_count"] == 421
    assert out["publisher"] == "ACM"
    assert out["source"] == "crossref"
    assert out["arxiv_id"] == "cs/9901001"
    assert out["title_match"] >= 0.4


def test_crossref_fallback_drops_unrelated_top_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _crossref_payload(
        {
            "DOI": "10.9999/zzz",
            "title": ["Quantum braiding in topological lattices"],
            "is-referenced-by-count": 7,
        }
    )
    monkeypatch.setattr(crossref_mod, "get_json", _make_json(payload))

    out = asyncio.run(
        enrich_via_crossref(
            "cs/9901001",
            title="Latent Semantics of Topic-Sensitive Web Search",
            authors=["Alice"],
        )
    )
    assert out is None


def test_crossref_fallback_swallows_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*_a, **_kw):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(crossref_mod, "get_json", _boom)

    out = asyncio.run(
        enrich_via_crossref(
            "cs/9901001",
            title="Anything",
            authors=["Alice"],
        )
    )
    assert out is None


def test_summarize_paper_falls_back_to_crossref_for_old_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        science_actions, "get_text", _make_text(_OLD_ARXIV_ATOM)
    )

    async def _no_openalex(_arxiv_id):
        return None

    monkeypatch.setattr(science_actions, "enrich_arxiv", _no_openalex)

    payload = _crossref_payload(
        {
            "DOI": "10.1145/12345",
            "title": ["Latent Semantics of Topic-Sensitive Web Search"],
            "is-referenced-by-count": 88,
            "publisher": "ACM",
            "issued": {"date-parts": [[2000]]},
        }
    )
    monkeypatch.setattr(crossref_mod, "get_json", _make_json(payload))

    out = asyncio.run(summarize_paper({"ref": "arXiv:cs/9901001"}))
    assert out["ok"] is True, out
    assert out["arxiv_id"] == "cs/9901001"
    assert "crossref" in out
    assert out["crossref"]["doi"] == "10.1145/12345"
    assert out["sources"] == ["arxiv", "crossref"]
    assert "openalex" not in out


def test_summarize_paper_skips_crossref_when_openalex_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New-style ids must not trigger Crossref calls — OpenAlex wins."""

    monkeypatch.setattr(
        science_actions,
        "get_text",
        _make_text(
            _OLD_ARXIV_ATOM.replace("cs/9901001v1", "2305.13245v1")
        ),
    )

    async def _ok_openalex(_arxiv_id):
        return {
            "openalex_id": "https://openalex.org/W123",
            "cited_by_count": 9,
            "publication_year": 2023,
            "is_open_access": True,
            "oa_url": "https://example.org/pdf",
        }

    monkeypatch.setattr(science_actions, "enrich_arxiv", _ok_openalex)

    async def _crossref_should_not_run(*_a, **_kw):
        raise AssertionError("crossref must not be queried for new-style ids")

    monkeypatch.setattr(crossref_mod, "get_json", _crossref_should_not_run)

    out = asyncio.run(summarize_paper({"ref": "arXiv:2305.13245"}))
    assert out["ok"] is True
    assert "openalex" in out
    assert "crossref" not in out
    assert out["sources"] == ["arxiv", "openalex"]


def test_summarize_paper_returns_arxiv_only_when_both_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        science_actions, "get_text", _make_text(_OLD_ARXIV_ATOM)
    )

    async def _no_openalex(_arxiv_id):
        return None

    monkeypatch.setattr(science_actions, "enrich_arxiv", _no_openalex)
    monkeypatch.setattr(
        crossref_mod, "get_json", _make_json({"message": {"items": []}})
    )

    out = asyncio.run(summarize_paper({"ref": "cs/9901001"}))
    assert out["ok"] is True
    assert out["sources"] == ["arxiv"]
    assert "openalex" not in out
    assert "crossref" not in out
