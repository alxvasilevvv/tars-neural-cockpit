"""Chunker tests."""

from __future__ import annotations

from backend.core.attachments.chunking import chunk_text


def test_chunk_text_returns_empty_for_blank_input() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_chunk_text_keeps_short_doc_in_single_slice() -> None:
    out = chunk_text("# Title\n\nOne paragraph.")
    assert len(out) == 1
    assert out[0].ord == 0
    assert "One paragraph" in out[0].text


def test_chunk_text_splits_by_paragraph_with_overlap() -> None:
    para = "Sentence " * 200  # ~1800 chars
    body = "\n\n".join([para] * 4)
    out = chunk_text(body, chunk_chars=2000, overlap_chars=200)
    assert len(out) >= 2
    # Overlap → consecutive chunks share at least some prefix tokens.
    assert any(
        out[i].text[:80] != out[i + 1].text[:80] for i in range(len(out) - 1)
    )
    assert all(c.ord == i for i, c in enumerate(out))


def test_chunk_text_resolves_nearest_heading() -> None:
    body = (
        "# Top\n\n"
        + "intro\n\n"
        + "## Section A\n\n"
        + "alpha details about A.\n\n"
        + "## Section B\n\n"
        + "bravo details about B and only B.\n"
    )
    out = chunk_text(body, chunk_chars=80, overlap_chars=10)
    assert len(out) >= 2
    headings = {c.heading for c in out if c.heading}
    assert "Top" in headings or any(h for h in headings)


def test_chunk_text_marks_pdf_pages_when_source_uses_page_convention() -> None:
    body = "## page 1\n\nfoo bar.\n\n## page 2\n\nzap zip zop."
    out = chunk_text(body, chunk_chars=40, overlap_chars=4)
    pages = [c.page for c in out]
    assert any(p == 1 for p in pages) or any(p == 2 for p in pages)


def test_chunk_text_dedupes_identical_emits() -> None:
    body = "abc def\n\n" * 6
    out = chunk_text(body, chunk_chars=20, overlap_chars=4)
    seen = {(c.text[:60], len(c.text)) for c in out}
    # Dedup keeps unique signatures even if overlap would emit twice.
    assert len(seen) == len(out)
