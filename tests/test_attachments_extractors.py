"""Per-mime extractor tests."""

from __future__ import annotations

import json

from backend.core.attachments.extractors import extract, sniff_mime


def test_sniff_uses_filename_when_declared_is_octet_stream() -> None:
    assert sniff_mime("notes.md", "application/octet-stream") == "text/markdown"
    assert sniff_mime("data.json", None) == "application/json"
    assert sniff_mime(None, "text/plain") == "text/plain"
    assert sniff_mime(None, None) == "application/octet-stream"


def test_extract_text_normalises_line_endings() -> None:
    out = extract(b"hello\r\nworld\rfoo", filename="x.txt")
    assert out.text == "hello\nworld\nfoo"
    assert out.mime.startswith("text/")
    assert out.meta["chars"] == len(out.text)


def test_extract_json_pretty_prints_and_marks_shape() -> None:
    blob = json.dumps({"a": 1, "b": [1, 2]}).encode("utf-8")
    out = extract(blob, filename="config.json")
    assert "\"a\"" in out.text
    assert out.meta["kind"] == "object"


def test_extract_json_falls_back_to_text_for_invalid_payload() -> None:
    out = extract(b"{not really json,,}", filename="bad.json")
    assert out.text  # fall through to raw text
    assert "json_parse" in str(out.meta.get("error", ""))


def test_extract_csv_renders_markdown_preview_plus_raw() -> None:
    payload = b"name,score\nalice,42\nbob,17\n"
    out = extract(payload, filename="kpi.csv")
    assert "| name | score |" in out.text
    assert "alice" in out.text
    assert "raw csv" in out.text
    assert out.meta["columns"] == 2
    assert out.meta["rows"] == 2


def test_extract_image_keeps_bytes_only_with_note() -> None:
    out = extract(b"\x89PNG\r\n\x1a\n" + b"\x00" * 30, filename="logo.png")
    assert out.text == ""
    assert "image" in str(out.meta.get("note", ""))
    assert out.meta["byte_count"] > 0


def test_extract_unknown_mime_decodes_best_effort() -> None:
    out = extract(b"hi there", filename="weird.xyz")
    assert "hi there" in out.text


def test_extract_pdf_with_missing_pypdf_returns_clear_error() -> None:
    # Even if pypdf is installed, garbage bytes should surface as an
    # error rather than crash.
    out = extract(b"%PDF-not-really", filename="broken.pdf")
    assert out.text == ""
    assert "pdf_open_failed" in str(
        out.meta.get("error", "")
    ) or "pypdf_unavailable" in str(out.meta.get("error", ""))
