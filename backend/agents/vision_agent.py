"""Vision agent — Phase M / P8.

Goal: when a thread carries image attachments, give the orchestrator
*something* useful to feed into both multimodal-capable voices and
text-only fallbacks. The agent does **not** call out to a remote
vision API on its own — that crosses the cloud-budget gate, and
the orchestrator already owns that decision. Instead:

1. **For multimodal voices**: return ``VisionPayload.image_refs`` —
   a list of ``(attachment_id, mime, storage_path)`` triples the
   voice can attach as native ``image`` content blocks (Anthropic
   ``image`` block, OpenAI ``image_url`` block, etc.).

2. **For text-only voices**: return ``VisionPayload.text`` — a
   short structured description (filename, mime, dimensions, OCR
   text if available). This lets the assistant *acknowledge*
   the image even without a vision-capable voice in the loop.

OCR is opt-in. If ``pytesseract`` and the system ``tesseract`` binary
are present, we run a best-effort pass and surface the text. If not,
the agent reports ``ocr_status="unavailable"`` and we keep going.

The agent is stateless: every call rebuilds the payload from the
attachment metadata + bytes on disk. No cache — the underlying
attachments table is already content-hashed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


log = logging.getLogger("tars.agents.vision")


_IMAGE_MIME_PREFIX = "image/"


def is_image_attachment(att: Mapping[str, Any] | Any) -> bool:
    """Best-effort MIME check that works on dicts AND dataclasses."""

    mime = _attr(att, "mime") or ""
    if mime.startswith(_IMAGE_MIME_PREFIX):
        return True
    fname = (_attr(att, "filename") or "").lower()
    if any(fname.endswith(ext) for ext in (
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"
    )):
        return True
    return False


def _attr(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


@dataclass(frozen=True)
class VisionAttachmentSummary:
    """Per-image summary the orchestrator can feed into prompts."""

    attachment_id: str
    filename: str | None
    mime: str
    bytes_total: int
    storage_path: str | None
    width: int | None
    height: int | None
    ocr_text: str | None
    ocr_status: str  # "ok" | "empty" | "unavailable" | "error"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "filename": self.filename,
            "mime": self.mime,
            "bytes_total": self.bytes_total,
            "storage_path": self.storage_path,
            "width": self.width,
            "height": self.height,
            "ocr_text": self.ocr_text,
            "ocr_status": self.ocr_status,
            "note": self.note,
        }


@dataclass(frozen=True)
class VisionPayload:
    """Aggregate of vision context for one orchestrator turn."""

    summaries: tuple[VisionAttachmentSummary, ...] = ()
    text_block: str = ""
    image_refs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @property
    def has_images(self) -> bool:
        return bool(self.summaries)


class VisionAgent:
    """Inspects image attachments and produces a :class:`VisionPayload`.

    Construct once per request — the agent caches nothing; it just
    walks the attachments and assembles the payload. Pluggable OCR
    backends can be injected via ``ocr_runner`` for tests.
    """

    def __init__(
        self,
        *,
        ocr_runner: "OCRRunner | None" = None,
        max_ocr_chars_per_image: int = 2000,
    ) -> None:
        self.ocr_runner = ocr_runner or DefaultOCRRunner()
        self.max_ocr_chars_per_image = max_ocr_chars_per_image

    async def inspect(
        self,
        attachments: Sequence[Any],
    ) -> VisionPayload:
        images = [a for a in attachments if is_image_attachment(a)]
        if not images:
            return VisionPayload()
        summaries = await asyncio.gather(*(
            self._inspect_one(a) for a in images
        ))
        text_block = self._compose_text_block(summaries)
        image_refs = tuple(
            {
                "attachment_id": s.attachment_id,
                "mime": s.mime,
                "storage_path": s.storage_path,
                "filename": s.filename,
            }
            for s in summaries
            if s.storage_path
        )
        return VisionPayload(
            summaries=tuple(summaries),
            text_block=text_block,
            image_refs=image_refs,
        )

    # -- internals ----------------------------------------------------

    async def _inspect_one(self, att: Any) -> VisionAttachmentSummary:
        attachment_id = str(_attr(att, "id") or "")
        filename = _attr(att, "filename")
        mime = _attr(att, "mime") or "application/octet-stream"
        bytes_total = int(_attr(att, "bytes_total") or 0)
        storage_path = _attr(att, "storage_path")

        width, height = await asyncio.to_thread(_image_dimensions, storage_path)
        ocr_text, ocr_status = await self.ocr_runner.run(storage_path)
        if ocr_text and len(ocr_text) > self.max_ocr_chars_per_image:
            ocr_text = ocr_text[: self.max_ocr_chars_per_image] + "…"

        return VisionAttachmentSummary(
            attachment_id=attachment_id,
            filename=filename,
            mime=mime,
            bytes_total=bytes_total,
            storage_path=str(storage_path) if storage_path else None,
            width=width,
            height=height,
            ocr_text=ocr_text or None,
            ocr_status=ocr_status,
            note=None,
        )

    @staticmethod
    def _compose_text_block(
        summaries: Iterable[VisionAttachmentSummary],
    ) -> str:
        lines: list[str] = ["## Image attachments"]
        for i, s in enumerate(summaries, start=1):
            label = s.filename or s.attachment_id
            dims = (
                f" · {s.width}×{s.height}px"
                if (s.width and s.height)
                else ""
            )
            head = f"{i}. {label} ({s.mime}{dims})"
            lines.append(head)
            if s.ocr_status == "ok" and s.ocr_text:
                lines.append("   - extracted text (OCR):")
                # Indent each OCR line by 4 spaces so markdown renders
                # the snippet as a code-ish block in cockpit previews.
                for ocr_line in s.ocr_text.splitlines():
                    lines.append(f"     {ocr_line}")
            elif s.ocr_status == "empty":
                lines.append("   - OCR ran but found no text")
            elif s.ocr_status == "unavailable":
                lines.append(
                    "   - OCR unavailable on this host (install pytesseract"
                    " + tesseract binary to extract text from images)"
                )
            elif s.ocr_status == "error":
                lines.append("   - OCR failed; image kept for vision-capable voice")
        return "\n".join(lines).rstrip() + "\n"


# ─── OCR runner abstraction ────────────────────────────────────────────


class OCRRunner:
    """Pluggable OCR backend. Tests inject a deterministic stub."""

    async def run(self, path: Any) -> tuple[str, str]:  # pragma: no cover
        raise NotImplementedError


class DefaultOCRRunner(OCRRunner):
    """pytesseract-backed OCR, falling back gracefully when missing."""

    async def run(self, path: Any) -> tuple[str, str]:
        if not path:
            return ("", "unavailable")
        return await asyncio.to_thread(self._run_blocking, str(path))

    @staticmethod
    def _run_blocking(path: str) -> tuple[str, str]:
        try:
            import pytesseract  # type: ignore[import-not-found]
            from PIL import Image  # type: ignore[import-not-found]
        except ImportError:
            return ("", "unavailable")
        try:
            with Image.open(path) as img:
                text = pytesseract.image_to_string(img)
        except FileNotFoundError:
            # tesseract binary missing on the host even if the python
            # wrapper imported successfully. Treat as unavailable.
            return ("", "unavailable")
        except Exception as exc:
            log.warning("OCR failed for %s: %s", path, exc)
            return ("", "error")
        text = (text or "").strip()
        if not text:
            return ("", "empty")
        return (text, "ok")


def _image_dimensions(path: Any) -> tuple[int | None, int | None]:
    """Best-effort PIL probe for image dimensions."""

    if not path:
        return (None, None)
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        return (None, None)
    try:
        with Image.open(str(path)) as img:
            return (int(img.width), int(img.height))
    except Exception:
        return (None, None)
