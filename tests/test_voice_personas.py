"""Persona registry tests — defaults, env overrides, reset."""

from __future__ import annotations

import pytest

from backend.core.voice import (
    DEFAULT_PERSONA_ID,
    Persona,
    PersonaProviderHint,
    get_persona,
    list_personas,
    register_persona,
)
from backend.core.voice.personas import reset_personas


@pytest.fixture(autouse=True)
def _reset_after_each() -> None:
    yield
    reset_personas()


def test_default_roster_ships_six_characters() -> None:
    ids = {p.id for p in list_personas()}
    assert ids == {"jarvis", "stark", "hal9000", "glados", "tars", "operator"}
    assert DEFAULT_PERSONA_ID == "jarvis"


def test_each_persona_has_full_provider_matrix() -> None:
    for p in list_personas():
        assert p.provider.elevenlabs_voice_id, f"{p.id}: elevenlabs id missing"
        assert p.provider.openai_voice, f"{p.id}: openai voice missing"
        assert p.provider.mac_say_voice, f"{p.id}: mac say voice missing"


def test_jarvis_is_british_with_butler_instructions() -> None:
    p = get_persona("jarvis")
    assert p.locale == "en-GB"
    assert p.accent == "british"
    assert "british" in (p.provider.openai_instructions or "").lower()
    # Daniel is the canonical British male voice on macOS.
    assert p.provider.mac_say_voice == "Daniel"


def test_stark_is_charismatic_american() -> None:
    p = get_persona("stark")
    assert p.locale == "en-US"
    assert p.accent == "american"
    assert "american" in (p.provider.openai_instructions or "").lower()


def test_get_persona_falls_back_to_default_for_unknown_id() -> None:
    p = get_persona("whoknows")
    assert p.id == DEFAULT_PERSONA_ID


def test_register_persona_overrides_or_extends_registry() -> None:
    edith = Persona(
        id="edith",
        name="E.D.I.T.H.",
        character="Stark legacy AI — calm, satellite-grade.",
        description="Calm satellite-grade AI.",
        short="Calm satellite AI.",
        provider=PersonaProviderHint(
            elevenlabs_voice_id="some_id",
            openai_voice="alloy",
            mac_say_voice="Samantha",
        ),
    )
    register_persona(edith)
    assert get_persona("edith").name == "E.D.I.T.H."


def test_to_dict_does_not_leak_instructions_text() -> None:
    p = get_persona("jarvis")
    d = p.to_dict()
    assert d["providers"]["openai"]["has_instructions"] is True
    # The actual instructions string is intentionally NOT in the dict —
    # only a flag — so the cockpit can show "stylised" without the
    # operator seeing the raw prompt.
    flat = str(d).lower()
    assert "british butler accent" not in flat


def test_env_override_jarvis_voice_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_PERSONA_JARVIS_ELEVENLABS_ID", "my_custom_voice")
    reset_personas()
    p = get_persona("jarvis")
    assert p.provider.elevenlabs_voice_id == "my_custom_voice"
