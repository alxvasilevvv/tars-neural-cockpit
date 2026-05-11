"""Tests for per-thread voice-persona pinning.

Closes the "per-thread persona pinning" idea: persisting
``voice_persona_id`` on threads so coming back to a thread
keeps the same TARS voice. End-to-end coverage:

- store schema migration + dataclass round-trip
- POST /api/chat/threads accepts and validates the field
- PATCH /api/chat/threads/{id} accepts, validates, and clears it
- POST /api/voice/speak honours the thread-pinned persona when no
  explicit persona is supplied
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.chat import Thread, get_chat_store
from backend.core.chat import store as chat_store_mod
from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.voice.personas import iter_personas
from web_extras.app import app


KNOWN_PERSONA_IDS = sorted(p.id for p in iter_personas())


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture()
def chat_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv(
        "TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite")
    )
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)


@pytest.fixture()
def client(chat_env) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------
# Dataclass + store round-trip
# ---------------------------------------------------------------------


def test_thread_dataclass_defaults_to_none(chat_env) -> None:
    thread = Thread.fresh(title="t")
    assert thread.voice_persona_id is None
    assert thread.to_dict()["voice_persona_id"] is None


def test_thread_fresh_accepts_persona(chat_env) -> None:
    thread = Thread.fresh(title="t", voice_persona_id="jarvis")
    assert thread.voice_persona_id == "jarvis"
    assert thread.to_dict()["voice_persona_id"] == "jarvis"


def test_store_round_trips_voice_persona_id(chat_env) -> None:
    store = get_chat_store()
    thread = Thread.fresh(title="t", voice_persona_id="stark")
    asyncio.run(store.insert_thread(thread))
    rehydrated = asyncio.run(store.get_thread(thread.id))
    assert rehydrated is not None
    assert rehydrated.voice_persona_id == "stark"


def test_store_patch_sets_and_clears_persona(chat_env) -> None:
    store = get_chat_store()
    thread = Thread.fresh(title="t")
    asyncio.run(store.insert_thread(thread))

    patched = asyncio.run(
        store.patch_thread(thread.id, {"voice_persona_id": "jarvis"})
    )
    assert patched is not None
    assert patched.voice_persona_id == "jarvis"

    cleared = asyncio.run(
        store.patch_thread(thread.id, {"voice_persona_id": None})
    )
    assert cleared is not None
    assert cleared.voice_persona_id is None


# ---------------------------------------------------------------------
# POST /api/chat/threads
# ---------------------------------------------------------------------


def test_post_threads_accepts_voice_persona_id(client: TestClient) -> None:
    res = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "jarvis"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["thread"]["voice_persona_id"] == "jarvis"


def test_post_threads_rejects_unknown_persona(client: TestClient) -> None:
    res = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "skynet"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "voice_persona_id_unknown"


def test_post_threads_rejects_non_string_persona(
    client: TestClient,
) -> None:
    res = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": 7},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "voice_persona_id_invalid"


def test_post_threads_omits_persona_field_when_unset(
    client: TestClient,
) -> None:
    res = client.post("/api/chat/threads", json={"title": "t"})
    assert res.status_code == 200
    assert res.json()["thread"]["voice_persona_id"] is None


def test_post_threads_empty_persona_falls_to_none(
    client: TestClient,
) -> None:
    res = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "   "},
    )
    assert res.status_code == 200
    assert res.json()["thread"]["voice_persona_id"] is None


# ---------------------------------------------------------------------
# PATCH /api/chat/threads/{id}
# ---------------------------------------------------------------------


def test_patch_threads_pins_persona(client: TestClient) -> None:
    thread_id = client.post(
        "/api/chat/threads", json={"title": "t"}
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": "tars"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["thread"]["voice_persona_id"] == "tars"


def test_patch_threads_clears_persona_with_none(
    client: TestClient,
) -> None:
    thread_id = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "stark"},
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": None},
    )
    assert res.status_code == 200
    assert res.json()["thread"]["voice_persona_id"] is None


def test_patch_threads_clears_persona_with_blank_string(
    client: TestClient,
) -> None:
    thread_id = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "glados"},
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": "   "},
    )
    assert res.status_code == 200
    assert res.json()["thread"]["voice_persona_id"] is None


def test_patch_threads_rejects_unknown_persona(client: TestClient) -> None:
    thread_id = client.post(
        "/api/chat/threads", json={"title": "t"}
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": "skynet"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "voice_persona_id_unknown"


def test_patch_threads_rejects_non_string_persona(
    client: TestClient,
) -> None:
    thread_id = client.post(
        "/api/chat/threads", json={"title": "t"}
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": 1.0},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "voice_persona_id_invalid"


@pytest.mark.parametrize("persona_id", KNOWN_PERSONA_IDS)
def test_patch_threads_accepts_every_known_persona(
    client: TestClient, persona_id: str
) -> None:
    thread_id = client.post(
        "/api/chat/threads", json={"title": "t"}
    ).json()["thread"]["id"]
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"voice_persona_id": persona_id},
    )
    assert res.status_code == 200
    assert res.json()["thread"]["voice_persona_id"] == persona_id


def test_patch_threads_does_not_change_persona_when_field_absent(
    client: TestClient,
) -> None:
    thread_id = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "tars"},
    ).json()["thread"]["id"]
    # Patch a different field; persona should stick.
    res = client.patch(
        f"/api/chat/threads/{thread_id}",
        json={"title": "t2"},
    )
    assert res.status_code == 200
    body = res.json()["thread"]
    assert body["title"] == "t2"
    assert body["voice_persona_id"] == "tars"


# ---------------------------------------------------------------------
# Voice routing fallback
# ---------------------------------------------------------------------


def _patch_synthesize(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the voice synthesizer with a recording stub so the
    test can assert which persona was passed without needing the
    real engines."""

    captured: dict = {}

    async def _fake_synth(text, *, persona=None, provider=None, session_id=None):
        captured["text"] = text
        captured["persona"] = persona
        captured["provider"] = provider
        captured["session_id"] = session_id

        class _Result:
            audio = b"AUDIOBYTES"
            mime = "audio/mpeg"
            provider = "stub"
            voice_id = "stub-voice"
            bytes_total = 10
            duration_estimate_ms = 100
            # Phase L4.2 — router now reads requested_voice_id /
            # substituted off the result. Mirror the production
            # SynthesisResult contract so the trace emit + headers
            # path stays exercised under the persona-pinning tests.
            requested_voice_id = "stub-voice"
            substituted = False

        return _Result()

    import web_extras.routers.voice as voice_router

    monkeypatch.setattr(voice_router, "synthesize", _fake_synth)
    return captured


def test_voice_speak_uses_thread_persona_when_no_explicit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _patch_synthesize(monkeypatch)
    thread_id = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "stark"},
    ).json()["thread"]["id"]

    res = client.post(
        "/api/voice/speak",
        json={"text": "hello", "thread_id": thread_id},
    )
    assert res.status_code == 200, res.text
    assert captured["persona"] == "stark"
    assert (
        res.headers.get("x-tars-voice-persona-source") == "thread"
    )


def test_voice_speak_explicit_persona_overrides_thread(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _patch_synthesize(monkeypatch)
    thread_id = client.post(
        "/api/chat/threads",
        json={"title": "t", "voice_persona_id": "stark"},
    ).json()["thread"]["id"]

    res = client.post(
        "/api/voice/speak",
        json={
            "text": "hello",
            "thread_id": thread_id,
            "persona": "jarvis",
        },
    )
    assert res.status_code == 200
    assert captured["persona"] == "jarvis"
    assert (
        res.headers.get("x-tars-voice-persona-source") == "request"
    )


def test_voice_speak_no_persona_when_thread_has_none(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _patch_synthesize(monkeypatch)
    thread_id = client.post(
        "/api/chat/threads", json={"title": "t"}
    ).json()["thread"]["id"]

    res = client.post(
        "/api/voice/speak",
        json={"text": "hello", "thread_id": thread_id},
    )
    assert res.status_code == 200
    # Falls through with no persona — the synth layer picks default.
    assert captured["persona"] is None
    assert "x-tars-voice-persona-source" not in res.headers


def test_voice_speak_unknown_thread_does_not_set_source(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _patch_synthesize(monkeypatch)
    res = client.post(
        "/api/voice/speak",
        json={"text": "hello", "thread_id": "thr_does_not_exist"},
    )
    assert res.status_code == 200
    assert captured["persona"] is None
    assert "x-tars-voice-persona-source" not in res.headers


def test_voice_speak_persona_source_request_when_only_explicit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _patch_synthesize(monkeypatch)
    res = client.post(
        "/api/voice/speak",
        json={"text": "hello", "persona": "tars"},
    )
    assert res.status_code == 200
    assert captured["persona"] == "tars"
    assert (
        res.headers.get("x-tars-voice-persona-source") == "request"
    )
