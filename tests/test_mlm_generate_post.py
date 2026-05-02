"""Tests for the upgraded ``mlm.generate_post`` drafter.

Two layers:

- Pure ``post_drafter`` module — template lookup, format
  overlays, hashtag composition, coercion.
- Action handler — validates channel, emits the
  ``mlm.post_drafted`` event, preserves backward compatibility
  with the original three-channel surface used by
  ``playbooks/mlm/retention_round.json``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.core.domains.packs.mlm import actions as mlm_actions
from backend.core.domains.packs.mlm import post_drafter as pd
from backend.core.domains.packs.mlm.actions import generate_post


# ---------------------------------------------------------------------
# Knob enums
# ---------------------------------------------------------------------


def test_known_enums_have_defaults():
    assert "ig" in pd.KNOWN_CHANNELS
    assert "post" in pd.KNOWN_FORMATS
    assert "warm" in pd.KNOWN_TONES
    assert "en" in pd.KNOWN_LANGUAGES


def test_template_registry_covers_full_matrix():
    for lang in pd.KNOWN_LANGUAGES:
        assert lang in pd._TEMPLATES, lang
        for channel in pd.KNOWN_CHANNELS:
            assert channel in pd._TEMPLATES[lang], (lang, channel)
            for tone in pd.KNOWN_TONES:
                assert tone in pd._TEMPLATES[lang][channel], (lang, channel, tone)


def test_template_strings_use_topic_placeholder():
    for lang in pd.KNOWN_LANGUAGES:
        for channel in pd.KNOWN_CHANNELS:
            for tone in pd.KNOWN_TONES:
                tpl = pd._TEMPLATES[lang][channel][tone]
                assert "{topic}" in tpl, (lang, channel, tone, tpl)


def test_default_ctas_cover_full_matrix():
    for lang in pd.KNOWN_LANGUAGES:
        for tone in pd.KNOWN_TONES:
            assert lang in pd._DEFAULT_CTAS
            assert tone in pd._DEFAULT_CTAS[lang]


# ---------------------------------------------------------------------
# draft_post — happy path
# ---------------------------------------------------------------------


def test_draft_post_default_topic_and_defaults():
    draft = pd.draft_post({})
    assert draft.channel == "ig"
    assert draft.format == "post"
    assert draft.tone == "warm"
    assert draft.language == "en"
    assert draft.topic == pd.DEFAULT_TOPIC
    assert draft.draft
    assert draft.cta
    assert draft.char_count == len(draft.draft)
    assert draft.word_count > 0


def test_draft_post_substitutes_topic():
    draft = pd.draft_post({"topic": "morning standup"})
    assert "morning standup" in draft.draft


def test_draft_post_is_deterministic():
    a = pd.draft_post({"channel": "tg", "tone": "urgent", "topic": "ABC"})
    b = pd.draft_post({"channel": "tg", "tone": "urgent", "topic": "ABC"})
    assert a.to_dict() == b.to_dict()


def test_draft_post_full_matrix_renders():
    """Every enum tuple should produce a non-empty draft."""

    for lang in pd.KNOWN_LANGUAGES:
        for channel in pd.KNOWN_CHANNELS:
            for tone in pd.KNOWN_TONES:
                for fmt in pd.KNOWN_FORMATS:
                    draft = pd.draft_post(
                        {
                            "channel": channel,
                            "tone": tone,
                            "language": lang,
                            "format": fmt,
                            "topic": "X",
                        }
                    )
                    assert draft.draft, (lang, channel, tone, fmt)
                    assert draft.char_count > 0


# ---------------------------------------------------------------------
# Coercion + fallbacks
# ---------------------------------------------------------------------


def test_unknown_tone_falls_back_to_warm():
    draft = pd.draft_post({"tone": "moonshot"})
    assert draft.tone == "warm"


def test_unknown_language_falls_back_to_en():
    draft = pd.draft_post({"language": "klingon"})
    assert draft.language == "en"


def test_unknown_format_falls_back_to_post():
    draft = pd.draft_post({"format": "newsletter"})
    assert draft.format == "post"


def test_unknown_channel_falls_back_to_ig_in_pure_helper():
    """The pure helper is forgiving; the action handler is not."""
    draft = pd.draft_post({"channel": "myspace"})
    assert draft.channel == "ig"


def test_blank_topic_yields_default():
    draft = pd.draft_post({"topic": "   "})
    assert draft.topic == pd.DEFAULT_TOPIC


def test_explicit_cta_wins_over_default():
    draft = pd.draft_post({"cta": "Reply with a 🔥"})
    assert draft.cta == "Reply with a 🔥"


def test_blank_cta_falls_back_to_default():
    draft = pd.draft_post({"cta": "   "})
    assert draft.cta == pd._DEFAULT_CTAS["en"]["warm"]


# ---------------------------------------------------------------------
# Format overlay
# ---------------------------------------------------------------------


def test_story_format_appends_swipe_up():
    draft = pd.draft_post({"format": "story"})
    assert draft.draft.endswith("Swipe up if you're in.")


def test_reel_format_collapses_to_short_punch():
    draft = pd.draft_post({"format": "reel"})
    # Reel collapses to first sentence + emoji close.
    assert draft.draft.endswith("👀")


def test_dm_format_strips_broadcast_close():
    """DM keeps only the first sentence."""

    full = pd.draft_post({"format": "post"})
    dm = pd.draft_post({"format": "dm"})
    assert len(dm.draft) <= len(full.draft)


# ---------------------------------------------------------------------
# Hashtags
# ---------------------------------------------------------------------


def test_hashtags_only_for_ig_and_linkedin():
    assert pd.draft_post({"channel": "tg"}).hashtags == ()
    assert pd.draft_post({"channel": "wa"}).hashtags == ()
    ig_tags = pd.draft_post({"channel": "ig"}).hashtags
    li_tags = pd.draft_post({"channel": "linkedin"}).hashtags
    assert ig_tags
    assert li_tags
    assert "#leadership" in li_tags  # linkedin-only extra


def test_hashtags_capped_at_eight():
    draft = pd.draft_post(
        {
            "channel": "linkedin",
            "topic": "growth",
        }
    )
    assert len(draft.hashtags) <= 8


def test_hashtags_strip_non_ascii():
    draft = pd.draft_post({"channel": "ig", "topic": "победа", "language": "ru"})
    # Only `momentum` + `team` survive ASCII slug; the topic stem is
    # cyrillic so it's dropped.
    assert all(t.startswith("#") for t in draft.hashtags)
    assert all(c.isascii() for tag in draft.hashtags for c in tag)


def test_hashtags_topic_stem_is_collapsed():
    draft = pd.draft_post({"channel": "ig", "topic": "Q3 launch plan"})
    # First word becomes the stem ('q3launchplan' after slug+strip).
    assert any("launch" in t for t in draft.hashtags) or any(
        "q3" in t for t in draft.hashtags
    )


# ---------------------------------------------------------------------
# Action handler — validation
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_post_default_args() -> None:
    out = await generate_post({"channel": "ig", "topic": "X"})
    assert out["ok"] is True
    assert out["channel"] == "ig"
    assert out["format"] == "post"
    assert out["tone"] == "warm"
    assert out["language"] == "en"
    assert "draft" in out
    assert "cta" in out
    assert out["char_count"] > 0


@pytest.mark.asyncio
async def test_generate_post_unsupported_channel() -> None:
    out = await generate_post({"channel": "telex"})
    assert out["ok"] is False
    assert out["error"] == "unsupported_channel"
    assert "telex" in out["channel"]
    assert "ig" in out["supported"]


@pytest.mark.asyncio
async def test_generate_post_omitted_channel_uses_ig() -> None:
    """Backward compat: existing playbooks may not set ``channel``
    explicitly. We accept missing/blank channel and fall back to ig.
    """
    out = await generate_post({"topic": "X"})
    assert out["ok"] is True
    assert out["channel"] == "ig"


@pytest.mark.asyncio
async def test_generate_post_blank_channel_uses_ig() -> None:
    out = await generate_post({"channel": "   ", "topic": "X"})
    assert out["ok"] is True
    assert out["channel"] == "ig"


@pytest.mark.asyncio
async def test_generate_post_includes_hashtags_for_ig() -> None:
    out = await generate_post({"channel": "ig", "topic": "kickoff"})
    assert isinstance(out["hashtags"], list)
    assert "#momentum" in out["hashtags"]


@pytest.mark.asyncio
async def test_generate_post_no_hashtags_for_tg() -> None:
    out = await generate_post({"channel": "tg", "topic": "kickoff"})
    assert out["hashtags"] == []


@pytest.mark.asyncio
async def test_generate_post_handles_full_dm_path() -> None:
    out = await generate_post(
        {
            "channel": "tg",
            "format": "dm",
            "tone": "urgent",
            "language": "ru",
            "topic": "контракт",
        }
    )
    assert out["ok"] is True
    assert out["language"] == "ru"
    assert out["format"] == "dm"
    assert "контракт" in out["draft"]


@pytest.mark.asyncio
async def test_generate_post_emits_meeet_event(monkeypatch) -> None:
    captured: list[tuple[str, dict[str, Any]]] = []

    class _Capture:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, payload))

    monkeypatch.setattr(mlm_actions, "get_client", lambda: _Capture())

    out = await generate_post({"channel": "ig", "topic": "Q3"})
    assert out["ok"] is True
    kinds = [k for k, _ in captured]
    assert "mlm.post_drafted" in kinds
    payload = next(p for k, p in captured if k == "mlm.post_drafted")
    assert payload["channel"] == "ig"
    assert payload["topic"] == "Q3"
    assert payload["char_count"] > 0


@pytest.mark.asyncio
async def test_generate_post_no_event_on_unsupported_channel(monkeypatch) -> None:
    """Validation errors must short-circuit before the meeet emit."""

    captured: list[tuple[str, dict[str, Any]]] = []

    class _Capture:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, payload))

    monkeypatch.setattr(mlm_actions, "get_client", lambda: _Capture())

    out = await generate_post({"channel": "telex"})
    assert out["ok"] is False
    assert captured == []


# ---------------------------------------------------------------------
# Backward compat — retention_round playbook
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retention_round_playbook_args_still_work() -> None:
    """``playbooks/mlm/retention_round.json`` calls generate_post
    with channel=tg, format=dm, topic=...; the new surface must
    keep that exact shape green."""

    out = await generate_post(
        {
            "channel": "tg",
            "format": "dm",
            "topic": "Reaching out to dormant downline (last contact > 21d)",
        }
    )
    assert out["ok"] is True
    assert out["channel"] == "tg"
    assert out["format"] == "dm"
    assert "dormant" in out["draft"] or "Reaching" in out["draft"]


# ---------------------------------------------------------------------
# Schema wiring
# ---------------------------------------------------------------------


def test_generate_post_schema_documents_new_knobs() -> None:
    spec = next(a for a in mlm_actions.ACTIONS if a.id == "generate_post")
    props = spec.schema["properties"]
    assert "tone" in props
    assert "language" in props
    assert "cta" in props
    assert spec.destructive is True
    assert "linkedin" in props["channel"]["enum"]
