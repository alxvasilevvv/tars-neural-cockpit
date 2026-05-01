"""Tests for per-persona system-prompt overlays.

Closes the "per-persona system-prompt overlay" idea from
`docs/IDEAS.md` (Voice section). When the operator pins a
voice persona on a thread, the orchestrator appends the
persona's tone overlay to the system prompt — without
overriding the operator role or pack guardrails.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.chat import Thread
from backend.core.chat.orchestrator import ChatOrchestrator
from backend.core.voice.personas import (
    DEFAULT_PERSONA_ID,
    Persona,
    PersonaProviderHint,
    compose_system_prompt,
    get_persona,
    get_system_prompt_overlay,
    iter_personas,
    register_persona,
    reset_personas,
)


# ---------------------------------------------------------------------
# get_system_prompt_overlay
# ---------------------------------------------------------------------


def test_overlay_for_unknown_persona_is_none() -> None:
    reset_personas()
    assert get_system_prompt_overlay(None) is None
    assert get_system_prompt_overlay("") is None
    assert get_system_prompt_overlay("nope") is None


def test_default_operator_persona_has_no_overlay() -> None:
    reset_personas()
    assert get_system_prompt_overlay("operator") is None


@pytest.mark.parametrize(
    "persona_id", ["jarvis", "stark", "hal9000", "glados", "tars"]
)
def test_named_persona_carries_overlay(persona_id: str) -> None:
    reset_personas()
    overlay = get_system_prompt_overlay(persona_id)
    assert overlay is not None
    assert overlay.strip()
    # Overlays should announce themselves so the cockpit can
    # detect / strip them later if needed.
    assert "Voice persona" in overlay


def test_overlay_includes_safety_footer() -> None:
    reset_personas()
    overlay = get_system_prompt_overlay("stark") or ""
    # Footer reminds the model not to bend pack guardrails.
    assert "guardrails" in overlay.lower()
    assert "destructive" in overlay.lower()


def test_overlay_returns_none_when_persona_overlay_is_blank() -> None:
    reset_personas()
    blank = Persona(
        id="blank",
        name="Blank",
        character="Just a stub.",
        description="No tone block.",
        short="Blank.",
        provider=PersonaProviderHint(),
        system_prompt_overlay="   ",
    )
    register_persona(blank)
    try:
        assert get_system_prompt_overlay("blank") is None
    finally:
        reset_personas()


# ---------------------------------------------------------------------
# compose_system_prompt
# ---------------------------------------------------------------------


def test_compose_returns_none_when_all_pieces_blank() -> None:
    assert compose_system_prompt() is None
    assert compose_system_prompt(role_overlay="") is None
    assert compose_system_prompt(persona_overlay="   ") is None


def test_compose_returns_single_piece_unwrapped() -> None:
    out = compose_system_prompt(pack_prompt="Use traders pack.")
    assert out == "Use traders pack."


def test_compose_orders_role_pack_persona() -> None:
    out = compose_system_prompt(
        role_overlay="ROLE",
        pack_prompt="PACK",
        persona_overlay="PERSONA",
    )
    assert out is not None
    parts = out.split("\n\n---\n\n")
    assert parts == ["ROLE", "PACK", "PERSONA"]


def test_compose_skips_blank_pieces_in_order() -> None:
    out = compose_system_prompt(
        role_overlay="ROLE", pack_prompt=None, persona_overlay="PERSONA"
    )
    assert out == "ROLE\n\n---\n\nPERSONA"


def test_compose_uses_custom_separator() -> None:
    out = compose_system_prompt(
        role_overlay="A", pack_prompt="B", separator=" | "
    )
    assert out == "A | B"


# ---------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------


def _thread(*, voice_persona_id: str | None = None, pack_slug: str | None = None):
    return Thread.fresh(
        title="t", pack_slug=pack_slug, voice_persona_id=voice_persona_id
    )


def test_orchestrator_returns_none_when_nothing_set() -> None:
    reset_personas()
    out = ChatOrchestrator._system_prompt_for(_thread())
    # The active operator role / pack may inject things; this case
    # is a thread with no pack and no persona, so any output is
    # purely the operator-role overlay if the test env happens to
    # have one. Assert we don't crash and the persona overlay isn't
    # present (since none was pinned).
    if out is not None:
        assert "Voice persona" not in out


def test_orchestrator_appends_persona_overlay_when_pinned() -> None:
    reset_personas()
    out = ChatOrchestrator._system_prompt_for(
        _thread(voice_persona_id="jarvis")
    )
    assert out is not None
    assert "Voice persona — J.A.R.V.I.S." in out


def test_orchestrator_omits_overlay_when_persona_is_operator() -> None:
    reset_personas()
    out = ChatOrchestrator._system_prompt_for(
        _thread(voice_persona_id="operator")
    )
    if out is not None:
        # The default operator persona declines the overlay.
        assert "Voice persona" not in out


def test_orchestrator_omits_overlay_when_persona_is_unknown() -> None:
    reset_personas()
    out = ChatOrchestrator._system_prompt_for(
        _thread(voice_persona_id="skynet")
    )
    if out is not None:
        assert "Voice persona" not in out


def test_orchestrator_pack_then_persona_when_both_set() -> None:
    reset_personas()
    # Use the science pack — it ships a system prompt and is in the
    # built-in registry.
    out = ChatOrchestrator._system_prompt_for(
        _thread(voice_persona_id="tars", pack_slug="science")
    )
    assert out is not None
    pack_marker = out.find("\n\n---\n\n")
    persona_marker = out.find("Voice persona — TARS")
    assert pack_marker != -1, out
    assert persona_marker != -1, out
    # Persona overlay must appear after at least one separator
    # (i.e. it's not first).
    assert persona_marker > pack_marker


def test_orchestrator_recovers_when_persona_lookup_throws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: if persona lookup raises (registry shenanigans
    in tests), the orchestrator must still produce a prompt for
    the pack / role and never crash the chat turn."""

    def _boom(_persona_id):
        raise RuntimeError("registry exploded")

    # The orchestrator does `from backend.core.voice import
    # get_system_prompt_overlay` inside the function, so patch the
    # symbol on the package (where the import lookup lands) rather
    # than the underlying submodule.
    monkeypatch.setattr(
        "backend.core.voice.get_system_prompt_overlay", _boom
    )
    out = ChatOrchestrator._system_prompt_for(
        _thread(voice_persona_id="stark", pack_slug="science")
    )
    # Must not raise — pack prompt still threads through.
    assert out is not None
    assert "Voice persona" not in out


def test_persona_to_dict_includes_has_overlay_flag() -> None:
    reset_personas()
    payload = get_persona("stark").to_dict()
    assert payload["has_system_prompt_overlay"] is True
    payload_op = get_persona("operator").to_dict()
    assert payload_op["has_system_prompt_overlay"] is False


def test_every_persona_has_complete_metadata() -> None:
    reset_personas()
    seen_ids = {p.id for p in iter_personas()}
    assert DEFAULT_PERSONA_ID in seen_ids
    for persona in iter_personas():
        d = persona.to_dict()
        assert d["id"]
        assert d["name"]
        assert "has_system_prompt_overlay" in d


# ---------------------------------------------------------------------
# Async runner pin (sanity check)
# ---------------------------------------------------------------------


def test_compose_smoke_async_roundtrip() -> None:
    """The orchestrator method is a staticmethod, but ensure the
    helper is asyncio-safe even when called from an event loop
    (some downstream callers do)."""

    async def _go() -> str | None:
        return ChatOrchestrator._system_prompt_for(
            _thread(voice_persona_id="hal9000")
        )

    out = asyncio.run(_go())
    assert out is not None
    assert "Voice persona — HAL 9000" in out
