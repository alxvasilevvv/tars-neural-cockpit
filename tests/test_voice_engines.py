"""Engine-level tests — focused on cross-platform / fallback logic.

Network providers (ElevenLabs / OpenAI) are exercised end-to-end via
``test_voice_synthesis.py`` with mocked engines; here we only cover
the macOS ``say`` voice fallback so a missing voice on the host
machine doesn't make Stark speak Spanish.
"""

from __future__ import annotations

import pytest

from backend.core.voice.engines import MacSayEngine, _rough_duration_ms
from backend.core.voice.personas import get_persona


def test_pick_fallback_prefers_british_for_jarvis() -> None:
    persona = get_persona("jarvis")
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Daniel", "Aaron", "Samantha"}
    )
    assert chosen == "Daniel"


def test_pick_fallback_prefers_american_for_stark() -> None:
    persona = get_persona("stark")
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Alex", "Daniel", "Luciana"}
    )
    assert chosen == "Alex"


def test_pick_fallback_walks_preference_list_in_order() -> None:
    persona = get_persona("stark")
    # Aaron not installed → prefer Tom (next in americal_preference).
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Tom", "Daniel", "Luciana"}
    )
    assert chosen == "Tom"


def test_pick_fallback_uses_alphabetical_when_no_preference_matches() -> None:
    persona = get_persona("operator")
    chosen = MacSayEngine._pick_fallback_voice(
        persona, installed={"Zarvox", "Carmit"}
    )
    # operator preference is ("Alex", "Daniel", "Samantha", "Tom") — none match,
    # so deterministic alphabetical first.
    assert chosen == "Carmit"


def test_pick_fallback_returns_persona_default_when_nothing_installed() -> None:
    persona = get_persona("jarvis")
    chosen = MacSayEngine._pick_fallback_voice(persona, installed=set())
    assert chosen == "Daniel"  # persona.provider.mac_say_voice


def test_rough_duration_ms_is_proportional_to_text() -> None:
    short = _rough_duration_ms("hi")
    long_ = _rough_duration_ms("hi " * 100)
    assert long_ > short
    assert _rough_duration_ms("") == 0
