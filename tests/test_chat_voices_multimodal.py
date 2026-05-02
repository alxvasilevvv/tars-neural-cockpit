"""Voices ↔ multimodal integration.

Validates that ``_to_anthropic_messages`` and ``_to_openai_messages``
inject the multimodal content-block list into the **last user turn**
when ``image_blocks`` are provided, and stay text-only otherwise.

These tests don't hit the network — they assert against the message
list shape that gets serialised into the request body. The
``LocalChatVoice`` ``image_refs`` plumbing is also smoke-tested so
the abstract signature stays safe to widen.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.chat.models import Message, Thread
from backend.core.chat.voices import (
    LocalChatVoice,
    _to_anthropic_messages,
    _to_openai_messages,
)


_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63600000000200015e5cd5d70000000049454e44ae"
    "426082"
)


def _h(role: str, content: str, mid: str = "m") -> Message:
    return Message(
        id=mid,
        thread_id="t1",
        role=role,  # type: ignore[arg-type]
        content=content,
        created_at=0.0,
    )


# --- _to_anthropic_messages ----------------------------------------


class TestAnthropicShape:
    def test_no_image_blocks_keeps_string_content(self):
        msgs = _to_anthropic_messages([_h("operator", "hi")], "follow up")
        assert msgs[-1] == {"role": "user", "content": "follow up"}
        assert isinstance(msgs[-1]["content"], str)

    def test_image_blocks_widen_only_last_user_turn(self):
        history = [
            _h("operator", "first turn"),
            _h("tars", "got it"),
        ]
        blocks = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "AAAA",
                },
            }
        ]
        msgs = _to_anthropic_messages(
            history, "what's in the image?", image_blocks=blocks
        )
        # History entries stay strings.
        assert msgs[0]["content"] == "first turn"
        assert msgs[1]["content"] == "got it"
        last = msgs[-1]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        # First content-block is the image, last is the text.
        assert last["content"][0]["type"] == "image"
        assert last["content"][-1] == {
            "type": "text",
            "text": "what's in the image?",
        }

    def test_multiple_image_blocks_preserve_order(self):
        blocks = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A"}},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "B"}},
        ]
        msgs = _to_anthropic_messages([], "?", image_blocks=blocks)
        content = msgs[-1]["content"]
        assert [c["source"]["media_type"] for c in content if c["type"] == "image"] == [
            "image/png",
            "image/jpeg",
        ]


# --- _to_openai_messages -------------------------------------------


class TestOpenAIShape:
    def test_no_image_blocks_keeps_string_content(self):
        msgs = _to_openai_messages([], "ping")
        assert msgs == [{"role": "user", "content": "ping"}]

    def test_image_blocks_widen_only_last_user_turn(self):
        history = [
            _h("operator", "first turn"),
            _h("tars", "ack"),
        ]
        blocks = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
        ]
        msgs = _to_openai_messages(
            history, "describe", image_blocks=blocks
        )
        # History entries stay strings.
        assert msgs[0]["content"] == "first turn"
        assert msgs[1]["content"] == "ack"
        last = msgs[-1]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        # OpenAI convention: text first, images after (matches the
        # vendor's docs / examples).
        assert last["content"][0] == {"type": "text", "text": "describe"}
        assert last["content"][-1]["type"] == "image_url"

    def test_multiple_image_blocks_preserve_order(self):
        blocks = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,A"}},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,B"}},
        ]
        msgs = _to_openai_messages([], "?", image_blocks=blocks)
        urls = [
            c["image_url"]["url"]
            for c in msgs[-1]["content"]
            if c["type"] == "image_url"
        ]
        assert urls == [
            "data:image/png;base64,A",
            "data:image/jpeg;base64,B",
        ]


# --- LocalChatVoice ignores image_refs ------------------------------


class TestLocalIgnoresImages:
    def test_local_voice_accepts_image_refs_kwarg(self, tmp_path: Path):
        """The abstract signature now requires ``image_refs``;
        LocalChatVoice must accept (and ignore) it without raising."""

        p = tmp_path / "x.png"
        p.write_bytes(_PNG)
        voice = LocalChatVoice()
        thread = Thread(
            id="t1",
            title="t",
            pack_slug=None,
            project_id=None,
            created_at=0.0,
            updated_at=0.0,
        )

        async def collect():
            chunks = []
            async for c in voice.stream(
                thread,
                [],
                "hello",
                (),
                system_prompt=None,
                image_refs=[
                    {"attachment_id": "x", "mime": "image/png", "storage_path": str(p)}
                ],
            ):
                chunks.append(c)
            return chunks

        out = asyncio.run(collect())
        assert any(c.kind == "text" for c in out)
        assert any(c.kind == "done" for c in out)


# --- End-to-end body shape (Anthropic) ------------------------------


class TestAnthropicBodyAssembly:
    """Mirror what ``AnthropicChatVoice.stream`` builds, using only
    the public helpers + multimodal packer. No HTTP."""

    def test_full_body_includes_image_block(self, tmp_path: Path):
        from backend.core.chat.multimodal import pack_anthropic_image_blocks

        p = tmp_path / "shot.png"
        p.write_bytes(_PNG)
        refs = [
            {
                "attachment_id": "att-1",
                "mime": "image/png",
                "storage_path": str(p),
            }
        ]
        image_blocks = pack_anthropic_image_blocks(refs)
        msgs = _to_anthropic_messages(
            [_h("operator", "hi")],
            "what is this?",
            image_blocks=image_blocks,
        )
        assert isinstance(msgs[-1]["content"], list)
        kinds = [b["type"] for b in msgs[-1]["content"]]
        assert "image" in kinds
        assert kinds[-1] == "text"


class TestOpenAIBodyAssembly:
    def test_full_body_includes_image_url(self, tmp_path: Path):
        from backend.core.chat.multimodal import pack_openai_image_blocks

        p = tmp_path / "shot.png"
        p.write_bytes(_PNG)
        refs = [
            {
                "attachment_id": "att-1",
                "mime": "image/png",
                "storage_path": str(p),
            }
        ]
        image_blocks = pack_openai_image_blocks(refs)
        msgs = _to_openai_messages(
            [_h("operator", "hi")],
            "what is this?",
            image_blocks=image_blocks,
        )
        last = msgs[-1]
        assert isinstance(last["content"], list)
        urls = [
            c["image_url"]["url"]
            for c in last["content"]
            if c["type"] == "image_url"
        ]
        assert len(urls) == 1
        assert urls[0].startswith("data:image/png;base64,")
