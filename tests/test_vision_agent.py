"""Phase M / P8 — vision agent unit tests + orchestrator integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from backend.agents import (
    VisionAgent,
    VisionPayload,
    is_image_attachment,
)
from backend.agents.vision_agent import OCRRunner


# ─── helpers ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FakeAttachment:
    id: str
    filename: str | None
    mime: str
    bytes_total: int
    storage_path: str | None


class StubOCRRunner(OCRRunner):
    def __init__(self, response: tuple[str, str]) -> None:
        self.response = response
        self.calls: list[Any] = []

    async def run(self, path: Any) -> tuple[str, str]:
        self.calls.append(path)
        return self.response


# ─── is_image_attachment ──────────────────────────────────────────────


def test_image_mime_is_detected() -> None:
    assert is_image_attachment({"mime": "image/png", "filename": "x.png"})


def test_image_filename_extension_is_detected_when_mime_is_generic() -> None:
    assert is_image_attachment(
        {"mime": "application/octet-stream", "filename": "shot.JPG"}
    )


def test_non_image_attachment_rejected() -> None:
    assert not is_image_attachment({"mime": "text/plain", "filename": "a.txt"})


# ─── VisionAgent.inspect ──────────────────────────────────────────────


def test_inspect_with_no_attachments_returns_empty_payload() -> None:
    agent = VisionAgent()
    payload = asyncio.run(agent.inspect([]))
    assert payload.has_images is False
    assert payload.text_block == ""
    assert payload.image_refs == ()


def test_inspect_skips_non_image_attachments() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("", "unavailable")))
    payload = asyncio.run(
        agent.inspect(
            [
                FakeAttachment(
                    id="a1",
                    filename="notes.txt",
                    mime="text/plain",
                    bytes_total=10,
                    storage_path=None,
                )
            ]
        )
    )
    assert payload.has_images is False


def test_inspect_with_image_renders_text_block() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("hello world", "ok")))
    att = FakeAttachment(
        id="att-1",
        filename="screenshot.png",
        mime="image/png",
        bytes_total=4096,
        storage_path="/tmp/screenshot.png",
    )
    payload = asyncio.run(agent.inspect([att]))
    assert payload.has_images is True
    assert "screenshot.png" in payload.text_block
    assert "hello world" in payload.text_block
    assert payload.image_refs[0]["attachment_id"] == "att-1"
    assert payload.image_refs[0]["mime"] == "image/png"
    assert payload.image_refs[0]["storage_path"] == "/tmp/screenshot.png"


def test_inspect_marks_ocr_unavailable() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("", "unavailable")))
    att = FakeAttachment(
        id="att-2",
        filename="img.png",
        mime="image/png",
        bytes_total=2048,
        storage_path="/tmp/x.png",
    )
    payload = asyncio.run(agent.inspect([att]))
    assert "OCR unavailable" in payload.text_block


def test_inspect_handles_empty_ocr_text() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("", "empty")))
    att = FakeAttachment(
        id="att-3",
        filename="blank.png",
        mime="image/png",
        bytes_total=2048,
        storage_path="/tmp/x.png",
    )
    payload = asyncio.run(agent.inspect([att]))
    assert "OCR ran but found no text" in payload.text_block


def test_inspect_truncates_long_ocr() -> None:
    long_text = "lorem ipsum " * 500
    agent = VisionAgent(
        ocr_runner=StubOCRRunner((long_text, "ok")),
        max_ocr_chars_per_image=100,
    )
    att = FakeAttachment(
        id="att-4",
        filename="big.png",
        mime="image/png",
        bytes_total=10_000,
        storage_path="/tmp/big.png",
    )
    payload = asyncio.run(agent.inspect([att]))
    summary = payload.summaries[0]
    assert summary.ocr_text is not None
    assert len(summary.ocr_text) <= 110  # 100 + ellipsis padding


def test_inspect_emits_image_refs_for_storage_paths() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("", "unavailable")))
    images = [
        FakeAttachment(
            id=f"a{i}",
            filename=f"img{i}.png",
            mime="image/png",
            bytes_total=1024,
            storage_path=f"/tmp/img{i}.png",
        )
        for i in range(3)
    ]
    payload = asyncio.run(agent.inspect(images))
    assert len(payload.image_refs) == 3
    ids = {ref["attachment_id"] for ref in payload.image_refs}
    assert ids == {"a0", "a1", "a2"}


def test_inspect_drops_image_refs_without_storage_path() -> None:
    agent = VisionAgent(ocr_runner=StubOCRRunner(("", "unavailable")))
    att = FakeAttachment(
        id="att-x",
        filename="ghost.png",
        mime="image/png",
        bytes_total=0,
        storage_path=None,
    )
    payload = asyncio.run(agent.inspect([att]))
    assert payload.has_images is True
    assert payload.image_refs == ()


# ─── orchestrator hook ────────────────────────────────────────────────


def test_compose_system_prompt_folds_vision_block() -> None:
    """When vision_payload has images, the block must appear in the prompt."""

    from backend.core.chat.models import Thread
    from backend.core.chat.orchestrator import ChatOrchestrator

    payload = VisionPayload(
        summaries=tuple(),
        text_block="## Image attachments\n1. shot.png (image/png · 800×600px)\n",
        image_refs=tuple(),
    )
    # has_images is False because summaries is empty — but the
    # composer also checks text_block. Build a fake payload with
    # has_images True.

    class _P:
        text_block = payload.text_block
        has_images = True

    thread = Thread(
        id="t",
        title=None,
        pack_slug=None,
        project_id=None,
        created_at=0.0,
        updated_at=0.0,
    )
    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    composed = ChatOrchestrator._compose_system_prompt(
        orch,
        thread,
        retrieved=[],
        vision_payload=_P(),
    )
    assert composed is not None
    assert "Image attachments" in composed


def test_chat_voice_supports_multimodal_flag() -> None:
    """Anthropic + OpenAI voices declare supports_multimodal=True."""

    from backend.core.chat.voices import (
        AnthropicChatVoice,
        LocalChatVoice,
        OpenAIChatVoice,
    )

    assert AnthropicChatVoice.supports_multimodal is True
    assert OpenAIChatVoice.supports_multimodal is True
    # Local voice is text-only.
    assert LocalChatVoice.supports_multimodal is False
