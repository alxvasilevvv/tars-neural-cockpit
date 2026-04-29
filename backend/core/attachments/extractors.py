"""Per-mime text extractors.

Goal: turn arbitrary bytes into a single UTF-8 text blob plus light
metadata (page count, row count, sheet names) that the chunker /
prompt-builder can consume.

Extractors return :class:`Extraction` (``text`` + ``meta``). Failures
return ``Extraction(text="", meta={"error": "..."})`` rather than
raising — the pipeline records the error in the attachment row but
still stores the bytes so the operator can re-trigger extraction
later.

Supported today:

- ``text/*``         — raw UTF-8 with safe fallback decoding.
- ``application/json`` — pretty-printed JSON.
- ``text/csv``       — first 50 rows as a markdown table preview +
                       full content as a separate text blob.
- ``text/markdown``  — passthrough.
- ``application/pdf``— ``pypdf`` page-by-page extraction (only new
                       dep, MIT, ~50 KB on disk).
- ``image/*``        — bytes-only stub. Vision routing through chat
                       voices lands in L4.
- everything else    — best-effort UTF-8 decode, otherwise empty.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
from dataclasses import dataclass, field
from typing import Any, Mapping


log = logging.getLogger("tars.attachments.extract")


@dataclass(frozen=True)
class Extraction:
    text: str
    mime: str
    meta: Mapping[str, Any] = field(default_factory=dict)


def sniff_mime(filename: str | None, declared: str | None) -> str:
    """Best-effort MIME type detection from filename + declared type."""

    if declared and declared != "application/octet-stream":
        return declared
    if filename:
        guess, _ = mimetypes.guess_type(filename)
        if guess:
            return guess
    return "application/octet-stream"


def extract(
    blob: bytes,
    *,
    filename: str | None = None,
    mime: str | None = None,
) -> Extraction:
    """Top-level extractor — picks the right strategy by MIME."""

    resolved = sniff_mime(filename, mime)
    try:
        if resolved == "application/pdf" or (filename or "").lower().endswith(
            ".pdf"
        ):
            return _extract_pdf(blob, resolved)
        if resolved == "application/json" or (filename or "").lower().endswith(
            ".json"
        ):
            return _extract_json(blob, resolved)
        if resolved == "text/csv" or (filename or "").lower().endswith(".csv"):
            return _extract_csv(blob, resolved)
        if resolved == "text/markdown" or (filename or "").lower().endswith(
            (".md", ".markdown")
        ):
            return _extract_text(blob, "text/markdown")
        if resolved.startswith("text/"):
            return _extract_text(blob, resolved)
        if resolved.startswith("image/"):
            return Extraction(
                text="",
                mime=resolved,
                meta={
                    "byte_count": len(blob),
                    "note": (
                        "image stored; vision routing happens through the"
                        " chat voice (L4 hookup)."
                    ),
                },
            )
        return _extract_text(blob, resolved)
    except Exception as exc:  # extractors are best-effort
        log.exception("extractor blew up for %s", resolved)
        return Extraction(
            text="",
            mime=resolved,
            meta={"error": f"extractor_error: {exc}"},
        )


# ---------------------------------------------------------------------
# Plaintext family
# ---------------------------------------------------------------------


def _extract_text(blob: bytes, mime: str) -> Extraction:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        text = blob.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return Extraction(
        text=text,
        mime=mime,
        meta={"chars": len(text), "lines": text.count("\n") + 1},
    )


# ---------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------


def _extract_json(blob: bytes, mime: str) -> Extraction:
    try:
        decoded = blob.decode("utf-8")
        parsed = json.loads(decoded)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False, sort_keys=False)
        return Extraction(
            text=pretty,
            mime=mime,
            meta={
                "chars": len(pretty),
                "kind": _json_shape(parsed),
            },
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Fall back to raw text.
        out = _extract_text(blob, mime)
        return Extraction(
            text=out.text,
            mime=mime,
            meta={**dict(out.meta), "error": f"json_parse: {exc}"},
        )


def _json_shape(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


# ---------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------


_CSV_PREVIEW_ROWS = 50
_CSV_PREVIEW_CHARS_PER_CELL = 80


def _extract_csv(blob: bytes, mime: str) -> Extraction:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        text = blob.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= _CSV_PREVIEW_ROWS * 4:  # cap memory
            break

    if not rows:
        return Extraction(text="", mime=mime, meta={"rows": 0})

    header = rows[0]
    body = rows[1:]
    preview_body = body[:_CSV_PREVIEW_ROWS]

    md = _csv_markdown(header, preview_body)
    full = "\n".join(",".join(_quote(cell) for cell in r) for r in rows)
    text_out = (
        f"{md}\n\n"
        f"# raw csv (first {len(rows)} rows)\n\n"
        f"{full}"
    )
    return Extraction(
        text=text_out,
        mime=mime,
        meta={
            "rows": len(body),
            "columns": len(header),
            "header": header,
            "preview_rows": len(preview_body),
        },
    )


def _csv_markdown(header: list[str], rows: list[list[str]]) -> str:
    if not header:
        return ""
    lines = ["| " + " | ".join(_clamp(c) for c in header) + " |"]
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for r in rows:
        padded = list(r) + [""] * max(0, len(header) - len(r))
        lines.append(
            "| " + " | ".join(_clamp(c) for c in padded[: len(header)]) + " |"
        )
    return "\n".join(lines)


def _clamp(s: str, *, n: int = _CSV_PREVIEW_CHARS_PER_CELL) -> str:
    cell = (s or "").replace("|", "\\|").replace("\n", " ")
    if len(cell) <= n:
        return cell
    return cell[: n - 1] + "…"


def _quote(s: str) -> str:
    if any(c in s for c in (",", '"', "\n")):
        return '"' + s.replace('"', '""') + '"'
    return s


# ---------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------


def _extract_pdf(blob: bytes, mime: str) -> Extraction:
    try:
        from pypdf import PdfReader  # lazy import — only loads when needed
    except ImportError:
        return Extraction(
            text="",
            mime=mime,
            meta={
                "error": (
                    "pypdf_unavailable — install pypdf or strip text"
                    " externally before uploading"
                )
            },
        )
    try:
        reader = PdfReader(io.BytesIO(blob))
    except Exception as exc:
        return Extraction(
            text="",
            mime=mime,
            meta={"error": f"pdf_open_failed: {exc}"},
        )
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    body = "\n\n".join(
        f"## page {i + 1}\n\n{p.strip()}" for i, p in enumerate(pages) if p.strip()
    )
    return Extraction(
        text=body,
        mime=mime,
        meta={
            "pages": len(pages),
            "non_empty_pages": sum(1 for p in pages if p.strip()),
        },
    )
