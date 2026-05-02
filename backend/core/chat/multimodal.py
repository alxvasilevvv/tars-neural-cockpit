"""Multimodal image packing for chat voices.

Closes the open follow-up of `docs/IDEAS.md` line 63 (image vision
routing). The vision agent already produces
``VisionPayload.image_refs`` — `(attachment_id, mime, storage_path,
filename)` tuples. The orchestrator passes those references through
to the chat voice; this module is the **pure-helper** layer that
turns them into the content-block shape each cloud LLM expects.

Two flavours ship in this batch:

- :func:`pack_anthropic_image_blocks` — Anthropic Messages API
  ``image`` blocks with ``source.type="base64"``.
- :func:`pack_openai_image_blocks` — OpenAI Chat Completions
  ``image_url`` blocks with ``data:<mime>;base64,<bytes>`` URL.

Both helpers are **side-effect-free** apart from a single
``Path.read_bytes`` per attachment. They are budget-aware:

- ``max_count`` — never pack more than N images per turn (default
  6 — enough for the cockpit's typical screenshot-per-turn flow,
  small enough that the request payload stays sane).
- ``max_bytes_per_image`` — drop any single attachment above the
  cap (default 5 MiB; both Anthropic and OpenAI hard-cap around
  20 MiB but the pre-encode size is what matters for our own RAM).
- ``max_total_bytes`` — running total across the turn so a 6 ×
  5 MiB explosion still gets bounded (default 18 MiB pre-encode).

Anything that fails (missing file, unreadable, oversize, unsupported
mime) is **silently dropped**; the caller already has a `vision`
text-block fallback so a multimodal turn never breaks.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

log = logging.getLogger("tars.chat.multimodal")

# --- Defaults -------------------------------------------------------

#: Hard cap on how many images one turn can carry into the cloud
#: payload. Six matches the cockpit's UX (screenshot strip is six
#: thumbnails before scrolling) and stays well under both vendors'
#: per-request maxima.
DEFAULT_MAX_COUNT = 6

#: Hard cap on a single image's pre-encode size. 5 MiB tolerates
#: typical 4K screenshots and DSLR JPEGs without packing huge
#: scanned PDFs that would balloon the payload.
DEFAULT_MAX_BYTES_PER_IMAGE = 5 * 1024 * 1024

#: Hard cap on the total pre-encode bytes per turn. 18 MiB is
#: deliberately ≤ Anthropic's ~20 MiB request budget so the
#: base64-encoded payload stays under their stricter post-encode
#: cap (~26 MiB).
DEFAULT_MAX_TOTAL_BYTES = 18 * 1024 * 1024

#: Allowed image mimes (intersection of Anthropic + OpenAI).
SUPPORTED_MIMES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }
)


# --- Public API -----------------------------------------------------


def is_supported_mime(mime: str | None) -> bool:
    """True iff ``mime`` is one of the four formats both Anthropic +
    OpenAI multimodal endpoints accept."""

    if not mime:
        return False
    return mime.lower() in SUPPORTED_MIMES


def normalise_mime(mime: str | None) -> str:
    """Return a canonical mime string (``image/jpeg`` not
    ``IMAGE/JPG``). Falls back to ``"application/octet-stream"`` so
    the caller never injects a literal ``None`` into the request
    payload.
    """

    if not mime:
        return "application/octet-stream"
    m = mime.strip().lower()
    if m == "image/jpg":
        return "image/jpeg"
    return m


def encode_image_b64(path: str | Path) -> str:
    """Read the file at ``path`` and return base64 (ascii) encoding.

    Raises ``OSError`` on any read failure — the caller decides
    whether to swallow.
    """

    raw = Path(path).read_bytes()
    return base64.b64encode(raw).decode("ascii")


def pack_anthropic_image_blocks(
    image_refs: Iterable[Mapping[str, Any]],
    *,
    max_count: int = DEFAULT_MAX_COUNT,
    max_bytes_per_image: int = DEFAULT_MAX_BYTES_PER_IMAGE,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> list[dict[str, Any]]:
    """Pack vision image_refs into Anthropic ``image`` content blocks.

    Returns ``[]`` when no usable images are found. The caller
    typically prepends these blocks to a final ``{"type": "text",
    "text": <operator_text>}`` block when assembling the user turn.
    """

    blocks: list[dict[str, Any]] = []
    total = 0
    for ref in _iter_capped(image_refs, max_count):
        rec = _validate_ref(ref)
        if rec is None:
            continue
        path, mime, size = rec
        if size > max_bytes_per_image:
            log.debug("multimodal: drop oversize image %s (%s bytes)", path, size)
            continue
        if total + size > max_total_bytes:
            log.debug(
                "multimodal: total budget exceeded — stop packing at %s bytes",
                total,
            )
            break
        try:
            data = encode_image_b64(path)
        except OSError as exc:
            log.debug("multimodal: read failed for %s: %s", path, exc)
            continue
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": data,
                },
            }
        )
        total += size
    return blocks


def pack_openai_image_blocks(
    image_refs: Iterable[Mapping[str, Any]],
    *,
    max_count: int = DEFAULT_MAX_COUNT,
    max_bytes_per_image: int = DEFAULT_MAX_BYTES_PER_IMAGE,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> list[dict[str, Any]]:
    """Pack vision image_refs into OpenAI ``image_url`` content blocks
    using inline ``data:`` URLs.

    Returns ``[]`` when no usable images are found.
    """

    blocks: list[dict[str, Any]] = []
    total = 0
    for ref in _iter_capped(image_refs, max_count):
        rec = _validate_ref(ref)
        if rec is None:
            continue
        path, mime, size = rec
        if size > max_bytes_per_image:
            log.debug("multimodal: drop oversize image %s (%s bytes)", path, size)
            continue
        if total + size > max_total_bytes:
            log.debug(
                "multimodal: total budget exceeded — stop packing at %s bytes",
                total,
            )
            break
        try:
            data = encode_image_b64(path)
        except OSError as exc:
            log.debug("multimodal: read failed for %s: %s", path, exc)
            continue
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            }
        )
        total += size
    return blocks


# --- Internals ------------------------------------------------------


def _iter_capped(
    refs: Iterable[Mapping[str, Any]],
    max_count: int,
) -> Iterable[Mapping[str, Any]]:
    if max_count <= 0:
        return
    for i, ref in enumerate(refs):
        if i >= max_count:
            return
        yield ref


def _validate_ref(
    ref: Mapping[str, Any],
) -> tuple[Path, str, int] | None:
    """Return ``(path, normalised_mime, size_bytes)`` when ``ref`` is
    a usable image attachment; ``None`` otherwise.

    The vision agent already filters by mime and emits image_refs
    only for attachments with a ``storage_path``; this is the
    second-line guard for tests / future callers that might
    construct refs by hand.
    """

    path_raw = ref.get("storage_path") or ref.get("path")
    if not path_raw:
        return None
    mime = normalise_mime(ref.get("mime"))
    if not is_supported_mime(mime):
        return None
    path = Path(str(path_raw))
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None
    return (path, mime, size)
