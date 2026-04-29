"""HTTP tests for /api/voice/{personas,health,speak}."""

from __future__ import annotations

import asyncio
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_store
from backend.core.voice import synthesis as synth_module
from backend.core.voice.engines import SynthesisResult
from web_extras.app import app


class _FakeEngine:
    def __init__(self, *, name: str, available: bool, audio: bytes | None) -> None:
        self.name = name
        self._available = available
        self._audio = audio

    async def is_available(self) -> bool:
        return self._available

    async def synthesise(self, text, persona) -> SynthesisResult | None:
        if not self._audio:
            return None
        return SynthesisResult(
            audio=self._audio,
            mime="audio/mpeg",
            provider=self.name,
            voice_id="test_voice",
            duration_estimate_ms=42,
            bytes_total=len(self._audio),
        )


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("MEEET_LOCAL_DB_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("TARS_VOICE_PROVIDER", raising=False)
    reset_store()
    synth_module.reset_engines()
    yield TestClient(app)
    synth_module.reset_engines()
    reset_store()


def test_personas_endpoint_returns_full_roster(client: TestClient) -> None:
    res = client.get("/api/voice/personas")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["default_persona_id"] == "jarvis"
    ids = {p["id"] for p in body["personas"]}
    assert {"jarvis", "stark", "hal9000", "glados", "tars", "operator"} <= ids


def test_health_endpoint_reports_engines(client: TestClient) -> None:
    res = client.get("/api/voice/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "engines" in body
    assert set(body["engines"].keys()) == {"elevenlabs", "openai", "mac_say"}


def test_speak_endpoint_returns_audio(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(
                name="elevenlabs", available=True, audio=b"ID3audio"
            ),
            "openai": _FakeEngine(name="openai", available=False, audio=None),
            "mac_say": _FakeEngine(name="mac_say", available=False, audio=None),
        },
    )

    res = client.post(
        "/api/voice/speak",
        json={"text": "Good evening, sir.", "persona": "jarvis"},
        headers={"x-tars-session-id": "ses_v1"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.headers["x-tars-voice-provider"] == "elevenlabs"
    assert res.headers["x-tars-voice-voice-id"] == "test_voice"
    assert res.content == b"ID3audio"


def test_speak_endpoint_503_when_no_provider_succeeds(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(name="elevenlabs", available=False, audio=None),
            "openai": _FakeEngine(name="openai", available=False, audio=None),
            "mac_say": _FakeEngine(name="mac_say", available=False, audio=None),
        },
    )
    res = client.post(
        "/api/voice/speak",
        json={"text": "hi", "persona": "stark"},
    )
    assert res.status_code == 503
    assert "no_provider" in res.json()["detail"]


def test_speak_endpoint_400_when_text_missing(client: TestClient) -> None:
    res = client.post("/api/voice/speak", json={"text": "  "})
    assert res.status_code == 400


def test_speak_endpoint_400_when_text_too_long(client: TestClient) -> None:
    res = client.post(
        "/api/voice/speak", json={"text": "a" * 5001, "persona": "operator"}
    )
    assert res.status_code == 400
