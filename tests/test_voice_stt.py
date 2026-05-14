"""W229 — pytest for the /api/voice/transcribe endpoint.

Env-isolated: each test runs with no OpenAI/Whisper credentials in
the process env, then opts into the credentials it needs via
``monkeypatch.setenv``. We patch ``transcribe_bytes`` so we don't
actually hit the OpenAI network.
"""

from __future__ import annotations

import io
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_store
from backend.core.voice import transcribe as transcribe_mod
from web_extras.app import app


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Hard-clear any STT credentials so tests start from "no backend".
    for var in (
        "OPENAI_API_KEY",
        "TARS_OPENAI_API_KEY",
        "WHISPER_CPP_BIN",
        "WHISPER_CPP_MODEL",
        "WHISPER_LOCAL_PATH",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MEEET_LOCAL_DB_PATH", str(tmp_path / "meeet.sqlite"))
    reset_store()
    # Bust the faster-whisper import cache between tests.
    if hasattr(transcribe_mod._faster_whisper_available, "_cached"):
        delattr(transcribe_mod._faster_whisper_available, "_cached")
    yield
    reset_store()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_no_audio_field_returns_422(client: TestClient) -> None:
    # No file part at all → FastAPI validation kicks in (422).
    r = client.post("/api/voice/transcribe")
    assert r.status_code == 422, r.text


def test_empty_audio_returns_200_with_empty_text(
    client: TestClient,
) -> None:
    # Empty bytes are NOT a configuration error — the endpoint returns
    # 200 with text="" so the cockpit can decide whether to retry.
    files = {"audio": ("voice.webm", b"", "audio/webm")}
    r = client.post("/api/voice/transcribe", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["text"] == ""


def test_mock_openai_returns_200_with_text(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")

    async def _fake_transcribe(audio, **kwargs):  # noqa: ANN001
        assert audio == b"FAKEOPUSBYTES"
        return {
            "text": "hello tars",
            "language": "en",
            "duration_ms": 1200,
            "elapsed_ms": 45,
            "model": "whisper-1",
            "provider": "openai_whisper",
            "segments_count": 1,
            "bytes_in": len(audio),
            "ext": "webm",
        }

    # Patch the symbol imported into the router module — that's the
    # one the endpoint actually calls.
    from web_extras.routers import voice as voice_router_mod
    monkeypatch.setattr(voice_router_mod, "transcribe_bytes", _fake_transcribe)

    files = {"audio": ("voice.webm", b"FAKEOPUSBYTES", "audio/webm")}
    r = client.post("/api/voice/transcribe", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["text"] == "hello tars"
    assert body["engine"] == "openai_whisper"
    assert body["lang"] == "en"


def test_oversized_audio_returns_413(client: TestClient) -> None:
    # 25 MiB + 1 byte → rejected before any work happens.
    too_big = b"\x00" * (25 * 1024 * 1024 + 1)
    files = {"audio": ("big.webm", too_big, "audio/webm")}
    r = client.post("/api/voice/transcribe", files=files)
    assert r.status_code == 413, r.status_code


def test_no_backend_returns_503_with_hint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No env at all + something resembling real audio bytes — should
    # fall through to NoSTTBackend → 503 with the structured hint.
    async def _raise_no_backend(audio, **kwargs):  # noqa: ANN001
        raise transcribe_mod.NoSTTBackend("no_stt_backend")

    from web_extras.routers import voice as voice_router_mod
    monkeypatch.setattr(voice_router_mod, "transcribe_bytes", _raise_no_backend)

    files = {"audio": ("voice.webm", b"realbytes", "audio/webm")}
    r = client.post("/api/voice/transcribe", files=files)
    assert r.status_code == 503, r.text
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail["ok"] is False
    assert detail["error"] == "no_stt_backend"
    assert "hint" in detail and detail["hint"]
