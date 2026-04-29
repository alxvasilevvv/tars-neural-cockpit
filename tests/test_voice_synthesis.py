"""Synthesis orchestrator tests — provider order, fallbacks, events.

Engines are stubbed via :class:`_FakeEngine` so the tests stay
deterministic and don't touch the network or the OS ``say`` binary.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from backend.core.meeet import get_store, reset_store
from backend.core.voice import SynthesisError, synthesize
from backend.core.voice.engines import SynthesisResult
from backend.core.voice.personas import get_persona
from backend.core.voice import synthesis as synth_module


class _FakeEngine:
    def __init__(
        self,
        name: str,
        *,
        available: bool = True,
        result: Optional[SynthesisResult] = None,
        explode: bool = False,
    ) -> None:
        self.name = name
        self._available = available
        self._result = result
        self._explode = explode
        self.calls = 0

    async def is_available(self) -> bool:
        return self._available

    async def synthesise(self, text, persona) -> SynthesisResult | None:
        self.calls += 1
        if self._explode:
            raise RuntimeError("boom")
        return self._result


def _ok_result(provider: str, voice_id: str = "v1") -> SynthesisResult:
    return SynthesisResult(
        audio=b"\x00\x01\x02",
        mime="audio/mpeg" if provider != "mac_say" else "audio/wav",
        provider=provider,
        voice_id=voice_id,
        duration_estimate_ms=100,
        bytes_total=3,
    )


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEEET_LOCAL_DB_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("TARS_VOICE_PROVIDER", raising=False)
    reset_store()
    synth_module.reset_engines()
    yield
    synth_module.reset_engines()
    reset_store()


def test_synthesize_picks_first_available_in_auto_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(
                "elevenlabs",
                available=True,
                result=_ok_result("elevenlabs", "ele_v"),
            ),
            "openai": _FakeEngine("openai", available=True, result=_ok_result("openai")),
            "mac_say": _FakeEngine("mac_say", available=True, result=_ok_result("mac_say")),
        },
    )

    res = asyncio.run(synthesize("Good evening, sir.", persona="jarvis"))
    assert res.provider == "elevenlabs"
    assert res.voice_id == "ele_v"


def test_synthesize_falls_through_to_next_provider_on_no_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = {
        "elevenlabs": _FakeEngine("elevenlabs", available=True, result=None),
        "openai": _FakeEngine(
            "openai", available=True, result=_ok_result("openai", "echo")
        ),
        "mac_say": _FakeEngine("mac_say", available=True, result=_ok_result("mac_say")),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)

    res = asyncio.run(synthesize("Run diagnostics.", persona="stark"))
    assert res.provider == "openai"
    assert fakes["mac_say"].calls == 0  # never reached


def test_synthesize_falls_through_to_next_provider_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = {
        "elevenlabs": _FakeEngine("elevenlabs", available=True, explode=True),
        "openai": _FakeEngine(
            "openai", available=True, result=_ok_result("openai")
        ),
        "mac_say": _FakeEngine("mac_say", available=True, result=_ok_result("mac_say")),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)

    res = asyncio.run(synthesize("Initialise.", persona="hal9000"))
    assert res.provider == "openai"


def test_pinned_provider_via_arg_skips_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = {
        "elevenlabs": _FakeEngine("elevenlabs", available=True, result=_ok_result("elevenlabs")),
        "openai": _FakeEngine("openai", available=False),
        "mac_say": _FakeEngine("mac_say", available=True, result=_ok_result("mac_say")),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)

    res = asyncio.run(
        synthesize("Local only please.", persona="operator", provider="mac_say")
    )
    assert res.provider == "mac_say"
    assert fakes["elevenlabs"].calls == 0


def test_pinned_provider_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_VOICE_PROVIDER", "openai")
    fakes = {
        "elevenlabs": _FakeEngine("elevenlabs", available=True, result=_ok_result("elevenlabs")),
        "openai": _FakeEngine("openai", available=True, result=_ok_result("openai")),
        "mac_say": _FakeEngine("mac_say", available=True, result=_ok_result("mac_say")),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)

    res = asyncio.run(synthesize("hi", persona="operator"))
    assert res.provider == "openai"
    assert fakes["elevenlabs"].calls == 0


def test_synthesize_raises_when_every_provider_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = {
        "elevenlabs": _FakeEngine("elevenlabs", available=True, result=None),
        "openai": _FakeEngine("openai", available=True, result=None),
        "mac_say": _FakeEngine("mac_say", available=False),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)

    with pytest.raises(SynthesisError):
        asyncio.run(synthesize("nope", persona="jarvis"))


def test_synthesize_emits_voice_tts_and_usage_tokens_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(
                "elevenlabs",
                available=True,
                result=_ok_result("elevenlabs", "ele_v"),
            ),
            "openai": _FakeEngine("openai", available=False),
            "mac_say": _FakeEngine("mac_say", available=False),
        },
    )

    asyncio.run(synthesize("Hello world", persona="jarvis", session_id="ses_v1"))
    store = get_store()
    voice_events = asyncio.run(store.list_events(limit=200, kind="voice.tts"))
    usage_events = asyncio.run(store.list_events(limit=500, kind="usage.tokens"))
    assert voice_events, "voice.tts event should have been emitted"
    assert usage_events, "usage.tokens event should have been emitted"
    events = voice_events + usage_events
    voice_event = next(
        ev for ev in voice_events if ev.payload.get("provider") == "elevenlabs"
    )
    assert voice_event.payload["persona"] == "jarvis"
    assert voice_event.payload["voice_id"] == "ele_v"
    assert voice_event.payload["chars"] == len("Hello world")
    assert voice_event.payload["cost_usd"] >= 0.0
    usage_event = next(
        ev
        for ev in usage_events
        if ev.payload.get("model") == "voice/elevenlabs"
        and ev.payload.get("topic") == "voice.tts"
    )
    assert usage_event is not None


def test_empty_text_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SynthesisError):
        asyncio.run(synthesize("   ", persona="jarvis"))
