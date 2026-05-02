"""Tests for `science.extract_dataset` — named datasets + URL patterns.

Two layers:

- The pure-Python `extract_datasets_from_text` is the workhorse;
  most of the suite lives there because it's deterministic and
  doesn't touch the network.
- A handful of integration tests exercise the action handler
  through the standard arxiv Atom path (mocked at `get_text`).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.domains.packs.science import actions as science_actions
from backend.core.domains.packs.science.datasets import (
    KNOWN_DATASETS,
    URL_PATTERNS,
    DatasetMention,
    extract_datasets_from_text,
)


# ---------------------------------------------------------------------
# Sanity: registry shape
# ---------------------------------------------------------------------


def test_registry_aliases_are_unique_lowercase():
    seen: set[str] = set()
    for entry in KNOWN_DATASETS:
        for alias in entry.aliases:
            key = alias.lower()
            assert key not in seen, alias
            seen.add(key)


def test_registry_canonical_ids_unique():
    ids = [e.canonical_id for e in KNOWN_DATASETS]
    assert len(ids) == len(set(ids))


def test_url_patterns_have_canonical_template():
    for pattern in URL_PATTERNS:
        assert "{0}" in pattern.template


# ---------------------------------------------------------------------
# extract_datasets_from_text — named datasets
# ---------------------------------------------------------------------


def test_empty_text_returns_no_matches():
    assert extract_datasets_from_text("") == []
    assert extract_datasets_from_text("   ") == []


def test_imagenet_detected_with_homepage_and_domain():
    mentions = extract_datasets_from_text(
        "We train ResNet-50 on ImageNet for 90 epochs."
    )
    assert len(mentions) == 1
    m = mentions[0]
    assert m.canonical_id == "imagenet"
    assert m.source == "known_dataset"
    assert m.url == "https://www.image-net.org/"
    assert m.domain == "vision"
    assert "ImageNet" in m.evidence


def test_multiple_datasets_in_one_passage():
    text = (
        "Pretrained on The Pile, fine-tuned on SQuAD, evaluated on MMLU "
        "and HellaSwag."
    )
    mentions = extract_datasets_from_text(text)
    canonical = {m.canonical_id for m in mentions}
    assert {"the-pile", "squad", "mmlu", "hellaswag"} <= canonical


def test_alias_match_is_case_insensitive_but_preserves_match_casing():
    mentions = extract_datasets_from_text("Trained on cifar-10 only.")
    assert len(mentions) == 1
    assert mentions[0].canonical_id == "cifar-10"
    assert mentions[0].name == "cifar-10"


def test_word_boundary_prevents_false_positives():
    # "MNIST" inside "MNISTpaper" should NOT match.
    assert extract_datasets_from_text("MNISTpaper foobar") == []
    # But "(MNIST)" SHOULD match.
    mentions = extract_datasets_from_text("Tested on (MNIST), good.")
    assert {m.canonical_id for m in mentions} == {"mnist"}


def test_dedup_per_canonical_id_for_known_datasets():
    text = "ImageNet… ImageNet again… ImageNet-1K once more."
    mentions = extract_datasets_from_text(text)
    canonical = [m.canonical_id for m in mentions]
    assert canonical == ["imagenet"]


def test_aliases_collapse_to_canonical_id():
    text = "MS-COCO is great. MSCOCO too. Microsoft COCO is the same."
    mentions = extract_datasets_from_text(text)
    assert {m.canonical_id for m in mentions} == {"coco"}


# ---------------------------------------------------------------------
# extract_datasets_from_text — URL patterns
# ---------------------------------------------------------------------


def test_zenodo_record_url_detected():
    mentions = extract_datasets_from_text(
        "Data hosted at zenodo.org/record/1234567 (CC-BY)."
    )
    zenodo = [m for m in mentions if m.source == "zenodo"]
    assert len(zenodo) == 1
    assert zenodo[0].url == "https://zenodo.org/record/1234567"
    assert "1234567" in zenodo[0].name


def test_zenodo_doi_detected():
    mentions = extract_datasets_from_text("DOI 10.5281/zenodo.987654 archive.")
    z = [m for m in mentions if m.source == "zenodo"]
    assert len(z) == 1
    assert z[0].url == "https://doi.org/10.5281/zenodo.987654"


def test_huggingface_dataset_detected():
    mentions = extract_datasets_from_text(
        "We use https://huggingface.co/datasets/openai/gsm8k for evaluation."
    )
    hf = [m for m in mentions if m.source == "huggingface"]
    assert len(hf) == 1
    assert hf[0].url == "https://huggingface.co/datasets/openai/gsm8k"


def test_kaggle_dataset_detected():
    mentions = extract_datasets_from_text(
        "Released on kaggle.com/datasets/john/some-dataset."
    )
    k = [m for m in mentions if m.source == "kaggle"]
    assert len(k) == 1


def test_dryad_doi_detected():
    mentions = extract_datasets_from_text("Cite 10.5061/dryad.abc123 for raw data.")
    d = [m for m in mentions if m.source == "dryad"]
    assert len(d) == 1
    assert d[0].url == "https://doi.org/10.5061/dryad.abc123"


def test_named_and_url_both_emit_for_imagenet_subset_on_zenodo():
    text = (
        "We release an ImageNet subset on zenodo.org/record/444555 "
        "for reproducibility."
    )
    mentions = extract_datasets_from_text(text)
    sources = {m.source for m in mentions}
    assert sources == {"known_dataset", "zenodo"}
    canonical = {m.canonical_id for m in mentions}
    assert "imagenet" in canonical
    assert "zenodo:444555" in canonical


# ---------------------------------------------------------------------
# DatasetMention.to_dict — output shape
# ---------------------------------------------------------------------


def test_to_dict_drops_none_url_and_domain_and_extra():
    m = DatasetMention(
        canonical_id="x",
        name="x",
        source="known_dataset",
        evidence="snippet",
    )
    d = m.to_dict()
    assert "url" not in d
    assert "domain" not in d
    assert "extra" not in d


def test_to_dict_keeps_url_when_present():
    m = DatasetMention(
        canonical_id="imagenet",
        name="ImageNet",
        source="known_dataset",
        evidence="…",
        url="https://www.image-net.org/",
        domain="vision",
    )
    d = m.to_dict()
    assert d["url"] == "https://www.image-net.org/"
    assert d["domain"] == "vision"


# ---------------------------------------------------------------------
# Action handler — text-only path (no network)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_dataset_with_text_returns_inline_mentions():
    res: dict[str, Any] = dict(
        await science_actions.extract_dataset(
            {"text": "Trained on ImageNet, evaluated on COCO."}
        )
    )
    assert res["ok"] is True
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert canonical == {"imagenet", "coco"}
    assert res["count"] == 2
    assert "known_dataset" in res["sources"]


@pytest.mark.asyncio
async def test_extract_dataset_without_input_errors():
    res = await science_actions.extract_dataset({})
    assert res["ok"] is False
    assert res["error"] == "ref_or_text_or_attachment_required"


@pytest.mark.asyncio
async def test_extract_dataset_with_unrecognised_ref_errors():
    res = await science_actions.extract_dataset({"ref": "not-a-real-paper-id"})
    assert res["ok"] is False
    assert res["error"] == "ref_unrecognised"


@pytest.mark.asyncio
async def test_extract_dataset_text_overrides_ref():
    """When both inputs are provided, ``text`` wins — the handler
    must not call out to arXiv."""

    res = await science_actions.extract_dataset(
        {
            "ref": "2305.13245",
            "text": "We compare against Open Images and CIFAR-10.",
        }
    )
    assert res["ok"] is True
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert canonical == {"open-images", "cifar-10"}


# ---------------------------------------------------------------------
# Action handler — arxiv ref path (mocked)
# ---------------------------------------------------------------------


_FAKE_ARXIV_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2305.13245v1</id>
    <title>Speculative paper on ImageNet vs COCO</title>
    <summary>We benchmark on ImageNet and COCO using SQuAD-style metrics.</summary>
    <published>2026-01-01T00:00:00Z</published>
    <author><name>A. Researcher</name></author>
    <category term="cs.CL"/>
    <arxiv:primary_category term="cs.CL"/>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_extract_dataset_with_arxiv_ref_uses_abstract(monkeypatch):
    fake_get_text = AsyncMock(return_value=(200, _FAKE_ARXIV_BODY))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset({"ref": "arxiv:2305.13245"})

    assert res["ok"] is True
    assert res["arxiv_id"] == "2305.13245"
    canonical = {d["canonical_id"] for d in res["datasets"]}
    # Match should pick up at least imagenet and coco from the abstract.
    assert {"imagenet", "coco"} <= canonical


@pytest.mark.asyncio
async def test_extract_dataset_arxiv_network_error(monkeypatch):
    from backend.core.domains._http import NetworkError

    fake_get_text = AsyncMock(side_effect=NetworkError("boom"))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset({"ref": "2305.13245"})
    assert res["ok"] is False
    assert res["error"] == "network_error"


@pytest.mark.asyncio
async def test_extract_dataset_arxiv_upstream_status(monkeypatch):
    fake_get_text = AsyncMock(return_value=(503, ""))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset({"ref": "2305.13245"})
    assert res["ok"] is False
    assert res["error"] == "upstream_status"
    assert res["status"] == 503


@pytest.mark.asyncio
async def test_extract_dataset_arxiv_not_found(monkeypatch):
    empty_feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom"></feed>\n'
    )
    fake_get_text = AsyncMock(return_value=(200, empty_feed))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset({"ref": "2305.13245"})
    assert res["ok"] is False
    assert res["error"] == "not_found"


# ---------------------------------------------------------------------
# Wiring — action surface
# ---------------------------------------------------------------------


def test_extract_dataset_action_is_registered_with_schema():
    target = next(
        (a for a in science_actions.ACTIONS if a.id == "extract_dataset"), None
    )
    assert target is not None
    assert "ref" in target.schema["properties"]
    assert "text" in target.schema["properties"]
    assert "attachment_id" in target.schema["properties"]
    assert target.handler is science_actions.extract_dataset


# ---------------------------------------------------------------------
# Action handler — attachment_id path
# ---------------------------------------------------------------------


class _FakeAttachmentRecord:
    """Bare-minimum stand-in for `AttachmentRecord` covering the
    fields the extractor reads. Avoids spinning up the SQLite store
    just to feed a string of text through the detector."""

    def __init__(
        self,
        *,
        id: str,
        thread_id: str = "thr_test",
        filename: str = "paper.pdf",
        mime: str = "application/pdf",
        extracted_text: str | None = "",
    ) -> None:
        self.id = id
        self.thread_id = thread_id
        self.filename = filename
        self.mime = mime
        self.extracted_text = extracted_text


class _FakeAttachmentStore:
    """In-memory attachment store that mirrors the async API the
    handler actually calls (`get_attachment`)."""

    def __init__(self, records: dict[str, _FakeAttachmentRecord] | None = None) -> None:
        self._records = records or {}

    async def get_attachment(self, attachment_id: str):
        return self._records.get(attachment_id)


@pytest.fixture
def patch_attachment_store(monkeypatch):
    """Inject a fake attachment store via the lazy import the
    handler performs. Returns a setter so individual tests can
    seed the records they need."""

    import backend.core.attachments as attachments_pkg

    holder: dict[str, _FakeAttachmentStore] = {
        "store": _FakeAttachmentStore(),
    }

    def _factory():
        return holder["store"]

    monkeypatch.setattr(attachments_pkg, "get_attachment_store", _factory)

    def _set(records: dict[str, _FakeAttachmentRecord]) -> None:
        holder["store"] = _FakeAttachmentStore(records)

    return _set


@pytest.mark.asyncio
async def test_extract_dataset_with_attachment_id_uses_extracted_text(
    patch_attachment_store,
):
    patch_attachment_store(
        {
            "att_abc": _FakeAttachmentRecord(
                id="att_abc",
                filename="benchmarks.pdf",
                mime="application/pdf",
                extracted_text=(
                    "This paper benchmarks ResNet on ImageNet and SQuAD."
                ),
            )
        }
    )

    res: dict[str, Any] = dict(
        await science_actions.extract_dataset({"attachment_id": "att_abc"})
    )

    assert res["ok"] is True
    assert res["attachment_id"] == "att_abc"
    assert res["filename"] == "benchmarks.pdf"
    assert res["mime"] == "application/pdf"
    assert res["thread_id"] == "thr_test"
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert {"imagenet", "squad"} <= canonical
    assert "known_dataset" in res["sources"]


@pytest.mark.asyncio
async def test_extract_dataset_attachment_not_found(patch_attachment_store):
    patch_attachment_store({})
    res = await science_actions.extract_dataset({"attachment_id": "missing"})
    assert res["ok"] is False
    assert res["error"] == "attachment_not_found"
    assert res["attachment_id"] == "missing"


@pytest.mark.asyncio
async def test_extract_dataset_attachment_empty_text(patch_attachment_store):
    patch_attachment_store(
        {
            "att_blank": _FakeAttachmentRecord(
                id="att_blank",
                extracted_text="   \n  ",
            )
        }
    )
    res = await science_actions.extract_dataset({"attachment_id": "att_blank"})
    assert res["ok"] is False
    assert res["error"] == "attachment_empty"
    assert res["attachment_id"] == "att_blank"
    assert "hint" in res


@pytest.mark.asyncio
async def test_extract_dataset_attachment_none_text(patch_attachment_store):
    patch_attachment_store(
        {
            "att_none": _FakeAttachmentRecord(
                id="att_none",
                extracted_text=None,
            )
        }
    )
    res = await science_actions.extract_dataset({"attachment_id": "att_none"})
    assert res["ok"] is False
    assert res["error"] == "attachment_empty"


@pytest.mark.asyncio
async def test_extract_dataset_text_overrides_attachment_id(
    patch_attachment_store, monkeypatch
):
    """Explicit text always wins. The handler must not even consult
    the attachment store when ``text`` is provided."""

    called = {"hits": 0}

    class _BoomStore:
        async def get_attachment(self, attachment_id: str):  # pragma: no cover
            called["hits"] += 1
            raise AssertionError("attachment store should not be consulted")

    import backend.core.attachments as attachments_pkg

    monkeypatch.setattr(
        attachments_pkg, "get_attachment_store", lambda: _BoomStore()
    )

    res = await science_actions.extract_dataset(
        {
            "attachment_id": "att_should_be_ignored",
            "text": "We use CIFAR-10 in this excerpt.",
        }
    )
    assert res["ok"] is True
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert canonical == {"cifar-10"}
    assert called["hits"] == 0


@pytest.mark.asyncio
async def test_extract_dataset_attachment_id_overrides_ref(
    patch_attachment_store, monkeypatch
):
    """When both ``attachment_id`` and ``ref`` are supplied the
    attachment wins — arXiv must not be hit."""

    patch_attachment_store(
        {
            "att_priority": _FakeAttachmentRecord(
                id="att_priority",
                extracted_text="Trained on COCO.",
            )
        }
    )

    fake_get_text = AsyncMock(side_effect=AssertionError("arxiv not expected"))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset(
        {"attachment_id": "att_priority", "ref": "arxiv:2305.13245"}
    )
    assert res["ok"] is True
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert canonical == {"coco"}
    fake_get_text.assert_not_called()


@pytest.mark.asyncio
async def test_extract_dataset_attachment_id_blank_falls_back_to_ref(
    patch_attachment_store, monkeypatch
):
    """An empty / whitespace ``attachment_id`` should not short-circuit
    the handler — it should still try the ``ref`` path."""

    fake_get_text = AsyncMock(return_value=(200, _FAKE_ARXIV_BODY))
    monkeypatch.setattr(science_actions, "get_text", fake_get_text)

    res = await science_actions.extract_dataset(
        {"attachment_id": "   ", "ref": "arxiv:2305.13245"}
    )
    assert res["ok"] is True
    assert res["arxiv_id"] == "2305.13245"
    canonical = {d["canonical_id"] for d in res["datasets"]}
    assert {"imagenet", "coco"} <= canonical
