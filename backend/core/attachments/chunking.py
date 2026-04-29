"""Token-aware chunker.

We intentionally avoid `tiktoken` (heavy dep) and approximate token
count via character heuristics — for retrieval the boundary doesn't
need to be exact, only consistent.

Rules:

- Split on paragraph boundaries first (``\\n\\n``), then on sentences
  inside oversized paragraphs.
- Target ``chunk_chars`` (default 3200, ~800 tokens at 4 chars/token).
- ``overlap_chars`` (default 320) so retrieval boundaries don't
  truncate context mid-claim.
- Empty / whitespace-only chunks are skipped.

Each yielded :class:`ChunkSlice` carries its ordinal index and a small
payload of context: a heading hint (the first ``#``/``##`` it found
above the chunk), and the start/end character offsets in the source
for "page N" stamping when the source is a PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


DEFAULT_CHUNK_CHARS = 3200
DEFAULT_OVERLAP_CHARS = 320

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ChunkSlice:
    ord: int
    text: str
    char_start: int
    char_end: int
    heading: str | None
    page: int | None = None


def chunk_text(
    source: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[ChunkSlice]:
    if not source.strip():
        return []
    paragraphs = _split_paragraphs(source)
    out: list[ChunkSlice] = []
    buffer = ""
    buffer_start = 0
    cursor = 0  # character offset into source

    for paragraph, p_start, p_end in paragraphs:
        # Oversized single paragraph — break by sentence then hard.
        if len(paragraph) > chunk_chars:
            if buffer:
                out.append(
                    _emit(
                        out,
                        buffer,
                        buffer_start,
                        buffer_start + len(buffer),
                        source,
                    )
                )
                buffer = ""
            for sub_text, sub_start, sub_end in _split_oversized(
                paragraph, p_start, chunk_chars
            ):
                out.append(
                    _emit(out, sub_text, sub_start, sub_end, source)
                )
            cursor = p_end
            continue

        # Fit into current buffer?
        candidate = (buffer + "\n\n" + paragraph).strip() if buffer else paragraph
        if len(candidate) <= chunk_chars:
            if not buffer:
                buffer_start = p_start
            buffer = candidate
            cursor = p_end
            continue

        # Buffer full — emit it, then start a new buffer with overlap.
        out.append(
            _emit(out, buffer, buffer_start, buffer_start + len(buffer), source)
        )
        if overlap_chars > 0:
            tail = buffer[-overlap_chars:]
            buffer = (tail + "\n\n" + paragraph).strip()
            buffer_start = max(0, buffer_start + len(buffer) - len(tail))
        else:
            buffer = paragraph
            buffer_start = p_start
        cursor = p_end

    if buffer.strip():
        out.append(
            _emit(out, buffer, buffer_start, buffer_start + len(buffer), source)
        )

    # Re-number and de-duplicate by hash to be safe.
    deduped: list[ChunkSlice] = []
    seen: set[str] = set()
    for i, c in enumerate(out):
        sig = f"{c.text[:120]}|{len(c.text)}"
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(
            ChunkSlice(
                ord=i,
                text=c.text,
                char_start=c.char_start,
                char_end=c.char_end,
                heading=c.heading,
                page=c.page,
            )
        )
    return deduped


# ---------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------


def _split_paragraphs(source: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    cursor = 0
    for match in _PARAGRAPH_RE.finditer(source):
        end = match.start()
        body = source[cursor:end]
        if body.strip():
            out.append((body.strip(), cursor, end))
        cursor = match.end()
    if cursor < len(source):
        body = source[cursor:]
        if body.strip():
            out.append((body.strip(), cursor, len(source)))
    return out


def _split_oversized(
    paragraph: str, p_start: int, chunk_chars: int
) -> Iterable[tuple[str, int, int]]:
    sentences = _SENTENCE_RE.split(paragraph)
    if len(sentences) == 1:
        # No sentence boundaries — hard slice.
        for i in range(0, len(paragraph), chunk_chars):
            piece = paragraph[i : i + chunk_chars]
            yield piece, p_start + i, p_start + i + len(piece)
        return
    cursor = 0
    buffer = ""
    buffer_start = 0
    for sentence in sentences:
        if not sentence:
            continue
        if not buffer:
            buffer_start = cursor
            buffer = sentence
        elif len(buffer) + len(sentence) + 1 <= chunk_chars:
            buffer += " " + sentence
        else:
            yield (
                buffer,
                p_start + buffer_start,
                p_start + buffer_start + len(buffer),
            )
            buffer = sentence
            buffer_start = cursor
        cursor += len(sentence) + 1
    if buffer:
        yield (
            buffer,
            p_start + buffer_start,
            p_start + buffer_start + len(buffer),
        )


def _emit(
    history: list[ChunkSlice],
    text: str,
    start: int,
    end: int,
    source: str,
) -> ChunkSlice:
    return ChunkSlice(
        ord=len(history),
        text=text.strip(),
        char_start=start,
        char_end=end,
        heading=_resolve_heading(source, start),
        page=_resolve_page(source, start),
    )


def _resolve_heading(source: str, offset: int) -> str | None:
    """Walk back from ``offset`` to find the nearest markdown heading."""

    if not source:
        return None
    last: str | None = None
    for m in _HEADING_RE.finditer(source[: max(offset, 0) + 1]):
        last = m.group(2).strip()
    return last


def _resolve_page(source: str, offset: int) -> int | None:
    """If the source uses our PDF ``## page N`` convention, surface it."""

    pattern = re.compile(r"^## page (\d+)$", re.MULTILINE)
    last: int | None = None
    for m in pattern.finditer(source[: max(offset, 0) + 1]):
        try:
            last = int(m.group(1))
        except (TypeError, ValueError):
            continue
    return last
