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


# ---------------------------------------------------------------------
# Phase L4.2 — substitution diagnostic surface
# ---------------------------------------------------------------------


class _DiagnosticEngine:
    """Test engine that returns a SynthesisResult with a known
    requested-vs-effective mismatch so we can pin the response
    headers and the meeet trace contract."""

    def __init__(self, *, requested: str, effective: str) -> None:
        self.name = "mac_say"
        self._requested = requested
        self._effective = effective

    async def is_available(self) -> bool:
        return True

    async def synthesise(self, text, persona) -> SynthesisResult:
        return SynthesisResult(
            audio=b"\x00\x01wav",
            mime="audio/wav",
            provider=self.name,
            voice_id=self._effective,
            duration_estimate_ms=10,
            bytes_total=5,
            requested_voice_id=self._requested,
        )


def test_speak_endpoint_surfaces_substitution_headers(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the engine swapped voices (Aaron → Fred), the cockpit
    must be able to read both ids + a substitution flag."""

    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(
                name="elevenlabs", available=False, audio=None
            ),
            "openai": _FakeEngine(name="openai", available=False, audio=None),
            "mac_say": _DiagnosticEngine(requested="Aaron", effective="Fred"),
        },
    )

    res = client.post(
        "/api/voice/speak",
        json={"text": "hi from stark", "persona": "stark"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["x-tars-voice-requested-id"] == "Aaron"
    assert res.headers["x-tars-voice-voice-id"] == "Fred"
    assert res.headers["x-tars-voice-substituted"] == "true"


def test_speak_endpoint_marks_non_substituted_when_voice_matches(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeEngine(
                name="elevenlabs", available=False, audio=None
            ),
            "openai": _FakeEngine(name="openai", available=False, audio=None),
            "mac_say": _DiagnosticEngine(requested="Daniel", effective="Daniel"),
        },
    )

    res = client.post(
        "/api/voice/speak",
        json={"text": "calm and precise", "persona": "jarvis"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["x-tars-voice-requested-id"] == "Daniel"
    assert res.headers["x-tars-voice-substituted"] == "false"


# ---------------------------------------------------------------------
# Phase L4.2 — /api/voice/personas/effective
# ---------------------------------------------------------------------


def test_personas_effective_endpoint_lists_all_personas(
    client: TestClient,
) -> None:
    res = client.get("/api/voice/personas/effective")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    ids = {row["id"] for row in body["personas"]}
    assert {"jarvis", "stark", "hal9000", "glados", "tars", "operator"} <= ids
    # Every row must carry the per-provider effective/requested map.
    sample = body["personas"][0]
    for provider in ("elevenlabs", "openai", "mac_say"):
        assert provider in sample["providers"]
        assert "requested" in sample["providers"][provider]
        assert "effective" in sample["providers"][provider]
        assert "substituted" in sample["providers"][provider]


def test_personas_effective_endpoint_marks_substitution_when_premium_voice_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the mac_say engine to report a "stock macOS 13" voice
    set (no Aaron / Tom / Bruce / Alex) and confirm the endpoint
    flags Stark/HAL/TARS as substituted, while jarvis (Daniel) and
    glados (Samantha) are not."""

    from backend.core.voice import engines as engines_module

    async def _fake_installed(self):
        return {"Daniel", "Samantha", "Fred", "Albert", "Ralph", "Junior"}

    monkeypatch.setattr(
        engines_module.MacSayEngine,
        "installed_voices",
        _fake_installed,
    )

    res = client.get("/api/voice/personas/effective")
    assert res.status_code == 200
    body = res.json()
    by_id = {row["id"]: row for row in body["personas"]}

    # jarvis asks for Daniel, which is installed → no substitution.
    assert by_id["jarvis"]["providers"]["mac_say"]["requested"] == "Daniel"
    assert by_id["jarvis"]["providers"]["mac_say"]["substituted"] is False

    # stark asks for Aaron — missing on stock mac → substituted.
    assert by_id["stark"]["providers"]["mac_say"]["requested"] == "Aaron"
    assert by_id["stark"]["providers"]["mac_say"]["substituted"] is True
    # The effective voice must be a different, distinct voice.
    assert by_id["stark"]["providers"]["mac_say"]["effective"] != "Aaron"

    # hal9000 asks for Bruce → substituted, lands on Albert
    # (its first installed alternative).
    assert by_id["hal9000"]["providers"]["mac_say"]["effective"] == "Albert"
    assert by_id["hal9000"]["providers"]["mac_say"]["substituted"] is True

    # All four male personas must end up on different voices.
    male = ["jarvis", "stark", "hal9000", "tars"]
    distinct = {by_id[p]["providers"]["mac_say"]["effective"] for p in male}
    assert len(distinct) == 4, (
        f"male personas collapsed to {distinct!r} — fallback chain "
        "failed to keep them distinct on a stock macOS install"
    )
