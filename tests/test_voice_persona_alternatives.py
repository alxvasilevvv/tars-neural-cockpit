"""Phase L4.2 — per-persona mac_say fallback chains.

The default ``personas.py`` registry asks for ``Aaron``/``Tom``/
``Bruce``/``Alex`` — *premium* macOS voices that are **not** shipped
on a stock macOS 13+ install. Without per-persona alternatives, three
of the four male personas (Stark / HAL / TARS) all collapse to the
single global accent default and end up using the same ``Fred`` voice,
so an operator switching personas would hear no difference at all.

These tests pin the design contract that on a "lowest common denominator"
mac install (Daniel + Samantha + Fred + Albert + Ralph + Junior + Karen
+ Tessa — all of which ship by default on macOS 13/14/15), the four male
personas resolve to **four distinct voices**, and ``SynthesisResult``
exposes ``requested_voice_id`` / ``substituted`` so the cockpit can
surface "voice swapped" diagnostics.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.voice.engines import (
    MacSayEngine,
    SynthesisResult,
)
from backend.core.voice.personas import get_persona, list_personas


# Voices guaranteed to ship by default on macOS 13+.
_STOCK_MACOS_VOICES = {
    "Daniel",     # UK male butler
    "Samantha",   # US female default
    "Fred",       # US male, classic
    "Albert",     # US male, slightly synthetic
    "Ralph",      # US male, deeper
    "Junior",     # US male, younger
    "Karen",      # AU female
    "Tessa",      # ZA female
    "Moira",      # IE female
}


def test_default_male_personas_land_on_distinct_voices() -> None:
    """The four male personas must NOT collapse to one voice on
    a stock macOS install. This is the regression that the per-
    persona fallback chains are designed to prevent."""

    male_personas = ["jarvis", "stark", "hal9000", "tars"]
    chosen = {
        pid: MacSayEngine._pick_fallback_voice(
            get_persona(pid), installed=_STOCK_MACOS_VOICES
        )
        for pid in male_personas
    }
    distinct = set(chosen.values())
    assert len(distinct) == len(male_personas), (
        f"male personas collapsed to {chosen!r} — operators "
        "would hear identical voices when switching personas"
    )


def test_persona_alternatives_walked_in_order_before_accent_default() -> None:
    """Stark's accent default would pick ``Alex`` if it were
    installed; the per-persona alternatives list claims ``Ralph``
    first to keep Stark distinct from HAL on a default mac."""

    persona = get_persona("stark")
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Alex", "Ralph", "Daniel"}
    )
    # Ralph is in stark's alternatives at position 3 (after Aaron,
    # Tom). Alex is in the *global* accent default. Per-persona
    # alternatives win, so we land on Ralph, not Alex.
    assert chosen == "Ralph"


def test_persona_alternatives_skip_unavailable_then_resume_chain() -> None:
    """When the top persona alternative is missing, we walk down
    the persona's own list before falling back to global rules."""

    persona = get_persona("hal9000")
    # HAL alternatives: (Bruce, Albert, Fred, Ralph, Daniel)
    # Bruce missing → Albert wins.
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Albert", "Fred", "Ralph"}
    )
    assert chosen == "Albert"


def test_persona_alternatives_exhausted_falls_through_to_accent_default() -> None:
    """When every persona-level alternative is missing, the engine
    must still find a sensible voice via the global accent rules."""

    persona = get_persona("jarvis")
    # jarvis alternatives are British-leaning. Strip them all,
    # leave only Karen (AU female) and Samantha (US female).
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Karen", "Samantha"}
    )
    # accent="british" preference is (Daniel, Oliver, Serena, Kate, Alex)
    # — none of them are installed either, so we land on
    # alphabetical: Karen.
    assert chosen == "Karen"


def test_persona_alternatives_are_exposed_in_to_dict() -> None:
    """The cockpit picker reads ``mac_say.voice_alternatives`` to
    show "if Aaron is missing we'll try Tom, Ralph, Junior, Daniel"
    in the persona drawer. Stable contract."""

    payload = get_persona("stark").to_dict()
    mac = payload["providers"]["mac_say"]  # type: ignore[index]
    assert mac["voice_alternatives"] == ["Aaron", "Tom", "Ralph", "Junior", "Daniel"]


def test_every_default_persona_carries_alternatives() -> None:
    """Regression guard — every persona in the default registry
    must declare a non-empty mac_say_voice_alternatives list, or
    the substitution chain silently regresses to single-voice."""

    for persona in list_personas():
        alts = persona.provider.mac_say_voice_alternatives
        assert isinstance(alts, tuple), f"{persona.id} alternatives not a tuple"
        assert len(alts) >= 3, (
            f"persona {persona.id!r} ships only {len(alts)} mac_say "
            "alternatives — need at least 3 for graceful degradation"
        )


# ---------------------------------------------------------------------
# SynthesisResult diagnostic surface
# ---------------------------------------------------------------------


def test_synthesis_result_substituted_is_false_when_voice_unchanged() -> None:
    res = SynthesisResult(
        audio=b"\x00",
        mime="audio/wav",
        provider="mac_say",
        voice_id="Daniel",
        duration_estimate_ms=100,
        bytes_total=1,
        requested_voice_id="Daniel",
    )
    assert res.substituted is False


def test_synthesis_result_substituted_is_true_when_engine_swapped() -> None:
    res = SynthesisResult(
        audio=b"\x00",
        mime="audio/wav",
        provider="mac_say",
        voice_id="Fred",
        duration_estimate_ms=100,
        bytes_total=1,
        requested_voice_id="Aaron",
    )
    assert res.substituted is True


def test_synthesis_result_substituted_is_false_for_legacy_callers() -> None:
    """Backward compatibility: callers that didn't record a
    ``requested_voice_id`` continue to look "non-substituted"."""

    res = SynthesisResult(
        audio=b"\x00",
        mime="audio/wav",
        provider="elevenlabs",
        voice_id="onwK4e9ZLuTAKqWW03F9",
        duration_estimate_ms=100,
        bytes_total=1,
    )
    assert res.requested_voice_id is None
    assert res.substituted is False


def test_synthesis_result_to_dict_carries_diagnostic_fields() -> None:
    res = SynthesisResult(
        audio=b"\x00",
        mime="audio/wav",
        provider="mac_say",
        voice_id="Daniel",
        duration_estimate_ms=100,
        bytes_total=1,
        requested_voice_id="Alex",
    )
    payload = res.to_dict()
    assert payload["requested_voice_id"] == "Alex"
    assert payload["substituted"] is True


# ---------------------------------------------------------------------
# Live engine integration
# ---------------------------------------------------------------------


def test_mac_say_engine_records_requested_voice_id() -> None:
    """Live integration on macOS: the engine must record what
    the persona asked for so the substitution flag is meaningful.
    Skipped automatically on non-Darwin CI."""

    import platform

    if platform.system() != "Darwin":
        pytest.skip("mac_say is macOS-only")

    async def _go() -> SynthesisResult | None:
        engine = MacSayEngine()
        if not await engine.is_available():
            return None
        return await engine.synthesise("hello", get_persona("operator"))

    result = asyncio.run(_go())
    if result is None:
        pytest.skip("mac say binary unavailable on this host")
    assert result.requested_voice_id == "Alex"
    # On stock macOS Alex is missing → engine substituted.
    # On hosts with the premium voices installed, the equality
    # holds. Both branches are valid; only assert the contract.
    if result.voice_id != "Alex":
        assert result.substituted is True
    else:
        assert result.substituted is False
