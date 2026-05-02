"""Pytest contract for `backend.core.chat.multimodal`.

Pure helpers; no network. The Anthropic / OpenAI integration tests
in ``tests/test_chat_voices_multimodal.py`` cover the wire-level
shape end-to-end.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Mapping

import pytest

from backend.core.chat.multimodal import (
    DEFAULT_MAX_BYTES_PER_IMAGE,
    DEFAULT_MAX_COUNT,
    SUPPORTED_MIMES,
    encode_image_b64,
    is_supported_mime,
    normalise_mime,
    pack_anthropic_image_blocks,
    pack_openai_image_blocks,
)

_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63600000000200015e5cd5d70000000049454e44ae"
    "426082"
)
_JPG_BYTES = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605"
    "08070707090908090a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a"
    "0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0affc000110800010001030122000211"
    "01031101ffd9"
)


def _ref(path: Path, mime: str = "image/png", **over) -> dict:
    base = {
        "attachment_id": "att-1",
        "mime": mime,
        "storage_path": str(path),
        "filename": path.name,
    }
    base.update(over)
    return base


@pytest.fixture
def png_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.png"
    p.write_bytes(_PNG_BYTES)
    return p


@pytest.fixture
def jpg_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.jpg"
    p.write_bytes(_JPG_BYTES)
    return p


# --- mime helpers ---------------------------------------------------


class TestMime:
    def test_supported_set_is_intersection_of_anthropic_openai(self):
        assert SUPPORTED_MIMES == frozenset(
            {"image/png", "image/jpeg", "image/webp", "image/gif"}
        )

    @pytest.mark.parametrize(
        "mime,expected",
        [
            ("image/png", True),
            ("image/PNG", True),
            ("image/JPEG", True),
            ("image/jpg", False),  # raw form not supported; normalise first
            ("image/heic", False),
            ("application/pdf", False),
            ("", False),
            (None, False),
        ],
    )
    def test_is_supported_mime(self, mime, expected):
        assert is_supported_mime(mime) is expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("image/png", "image/png"),
            ("IMAGE/PNG", "image/png"),
            ("image/jpg", "image/jpeg"),  # JPG → JPEG canonical
            ("image/JPG", "image/jpeg"),
            ("  image/webp  ", "image/webp"),
            (None, "application/octet-stream"),
            ("", "application/octet-stream"),
        ],
    )
    def test_normalise_mime(self, raw, expected):
        assert normalise_mime(raw) == expected


# --- encode_image_b64 ----------------------------------------------


class TestEncode:
    def test_round_trips(self, png_path: Path):
        b64 = encode_image_b64(png_path)
        assert base64.b64decode(b64) == _PNG_BYTES

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(OSError):
            encode_image_b64(tmp_path / "ghost.png")


# --- pack_anthropic_image_blocks -----------------------------------


class TestPackAnthropic:
    def test_happy_path_single_image(self, png_path: Path):
        blocks = pack_anthropic_image_blocks([_ref(png_path)])
        assert len(blocks) == 1
        b = blocks[0]
        assert b["type"] == "image"
        assert b["source"]["type"] == "base64"
        assert b["source"]["media_type"] == "image/png"
        assert base64.b64decode(b["source"]["data"]) == _PNG_BYTES

    def test_normalises_jpg_to_jpeg(self, jpg_path: Path):
        blocks = pack_anthropic_image_blocks([_ref(jpg_path, mime="image/jpg")])
        assert len(blocks) == 1
        assert blocks[0]["source"]["media_type"] == "image/jpeg"

    def test_drops_unsupported_mime(self, tmp_path: Path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4 minimal")
        assert pack_anthropic_image_blocks([_ref(p, mime="application/pdf")]) == []

    def test_drops_missing_storage_path(self):
        assert pack_anthropic_image_blocks(
            [{"attachment_id": "x", "mime": "image/png"}]
        ) == []

    def test_drops_zero_byte_file(self, tmp_path: Path):
        p = tmp_path / "empty.png"
        p.write_bytes(b"")
        assert pack_anthropic_image_blocks([_ref(p)]) == []

    def test_drops_missing_file(self, tmp_path: Path):
        ref = _ref(tmp_path / "ghost.png")
        assert pack_anthropic_image_blocks([ref]) == []

    def test_count_cap(self, png_path: Path):
        refs = [_ref(png_path) for _ in range(DEFAULT_MAX_COUNT + 3)]
        blocks = pack_anthropic_image_blocks(refs)
        assert len(blocks) == DEFAULT_MAX_COUNT

    def test_max_count_kwarg_overrides_default(self, png_path: Path):
        refs = [_ref(png_path) for _ in range(5)]
        blocks = pack_anthropic_image_blocks(refs, max_count=2)
        assert len(blocks) == 2

    def test_per_image_byte_cap(self, png_path: Path):
        # PNG fixture is ~85 bytes; cap at 10 forces drop.
        blocks = pack_anthropic_image_blocks(
            [_ref(png_path)], max_bytes_per_image=10
        )
        assert blocks == []

    def test_total_byte_cap_stops_packing_partway(self, png_path: Path):
        refs = [_ref(png_path) for _ in range(4)]
        size = png_path.stat().st_size
        # Only allow exactly 2 images worth of bytes.
        blocks = pack_anthropic_image_blocks(
            refs, max_total_bytes=size * 2 + 1
        )
        assert len(blocks) == 2

    def test_max_count_zero_returns_empty(self, png_path: Path):
        assert pack_anthropic_image_blocks([_ref(png_path)], max_count=0) == []

    def test_empty_input(self):
        assert pack_anthropic_image_blocks([]) == []


# --- pack_openai_image_blocks --------------------------------------


class TestPackOpenAI:
    def test_happy_path_returns_data_url(self, png_path: Path):
        blocks = pack_openai_image_blocks([_ref(png_path)])
        assert len(blocks) == 1
        b = blocks[0]
        assert b["type"] == "image_url"
        url = b["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        b64 = url.split("base64,", 1)[1]
        assert base64.b64decode(b64) == _PNG_BYTES

    def test_normalises_jpg_to_jpeg_in_url(self, jpg_path: Path):
        blocks = pack_openai_image_blocks([_ref(jpg_path, mime="image/jpg")])
        assert blocks[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    def test_drops_unsupported_mime(self, tmp_path: Path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4 minimal")
        assert pack_openai_image_blocks([_ref(p, mime="application/pdf")]) == []

    def test_count_cap_matches_default(self, png_path: Path):
        refs = [_ref(png_path) for _ in range(DEFAULT_MAX_COUNT + 3)]
        blocks = pack_openai_image_blocks(refs)
        assert len(blocks) == DEFAULT_MAX_COUNT

    def test_per_image_byte_cap(self, png_path: Path):
        # Cap at 1 byte → drop.
        blocks = pack_openai_image_blocks(
            [_ref(png_path)], max_bytes_per_image=1
        )
        assert blocks == []

    def test_total_byte_cap(self, png_path: Path):
        refs = [_ref(png_path) for _ in range(5)]
        size = png_path.stat().st_size
        blocks = pack_openai_image_blocks(
            refs, max_total_bytes=size * 3 + 1
        )
        assert len(blocks) == 3

    def test_path_field_alias(self, png_path: Path):
        # Allow refs that use `path` instead of `storage_path` for
        # forward compat with future callers.
        blocks = pack_openai_image_blocks(
            [
                {
                    "attachment_id": "x",
                    "mime": "image/png",
                    "path": str(png_path),
                }
            ]
        )
        assert len(blocks) == 1


# --- Integration with default budget --------------------------------


class TestBudgetDefaults:
    def test_default_per_image_cap_is_5_mib(self):
        assert DEFAULT_MAX_BYTES_PER_IMAGE == 5 * 1024 * 1024

    def test_default_count_is_six(self):
        assert DEFAULT_MAX_COUNT == 6
