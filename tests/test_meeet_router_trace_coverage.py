"""Trace coverage smoke tests for the 2026-05-04 audit-2 pass.

The audit added ``trace_scope`` + meeet-event emission to three
hot operator-facing routers that were previously dark on the
trail:

- ``POST /api/chat/threads/{id}/messages`` —
  ``chat.message.{requested,completed,failed}``
- ``POST /api/voice/speak`` —
  ``voice.tts.{requested,completed,failed}``
- ``POST /api/speech/intents`` —
  ``speech.intent.{requested,completed,failed}``

These tests pin the contract: each successful call MUST land at
least one ``*.requested`` and one ``*.completed`` row in the
local meeet store, and the response MUST surface the ``trace_id``
either as a header or inline in the body so the cockpit can
correlate.

Run::

    .venv/bin/python -m pytest tests/test_meeet_router_trace_coverage.py -v
"""

from __future__ import annotations

import asyncio
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import StoredEvent, get_store, reset_store
from backend.core.voice import synthesis as synth_module
from backend.core.voice.engines import SynthesisResult
from web_extras.app import app


def _list_events(**kwargs) -> list[StoredEvent]:
    """Sync helper around the async ``MeeetStore.list_events`` API."""

    return asyncio.run(get_store().list_events(**kwargs))


class _FakeVoiceEngine:
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
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    reset_store()
    synth_module.reset_engines()
    yield TestClient(app)
    synth_module.reset_engines()
    reset_store()


def _kinds_in_store() -> set[str]:
    """Read every event kind currently in the local meeet store."""

    return {r.kind for r in _list_events(limit=200)}


def _events_for_trace(trace_id: str) -> list[StoredEvent]:
    """Return all events for a given trace_id from the local store."""

    return _list_events(limit=500, trace_id=trace_id)


# ----------------------------------------------------------------------
# voice.speak — TTS surface
# ----------------------------------------------------------------------


def test_voice_speak_emits_requested_and_completed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``POST /api/voice/speak`` must emit voice.tts.requested + completed."""

    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeVoiceEngine(
                name="elevenlabs", available=True, audio=b"ID3audio"
            ),
            "openai": _FakeVoiceEngine(name="openai", available=False, audio=None),
            "mac_say": _FakeVoiceEngine(name="mac_say", available=False, audio=None),
        },
    )

    res = client.post(
        "/api/voice/speak",
        json={"text": "Trace coverage test.", "persona": "jarvis"},
    )
    assert res.status_code == 200, res.text

    # The router promised an x-trace-id header so the cockpit can
    # correlate the audio response with the trail row.
    trace_id = res.headers.get("x-trace-id")
    assert trace_id, "x-trace-id header missing on /api/voice/speak"

    kinds = {r.kind for r in _events_for_trace(trace_id)}
    assert "voice.tts.requested" in kinds, kinds
    assert "voice.tts.completed" in kinds, kinds
    assert "voice.tts.failed" not in kinds


def test_voice_speak_emits_failed_when_no_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 503 from synthesis must still emit voice.tts.failed and
    explicitly NOT a completed event for the same trace."""

    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeVoiceEngine(name="elevenlabs", available=False, audio=None),
            "openai": _FakeVoiceEngine(name="openai", available=False, audio=None),
            "mac_say": _FakeVoiceEngine(name="mac_say", available=False, audio=None),
        },
    )

    parent_trace = "tr_test_failure_path"
    res = client.post(
        "/api/voice/speak",
        json={"text": "no provider should bomb us", "persona": "stark"},
        headers={"x-meeet-trace-id": parent_trace},
    )
    assert res.status_code == 503

    # Filter by the trace_id we explicitly handed in so other tests
    # in the same session can't pollute the assertion.
    rows = _events_for_trace(parent_trace)
    kinds_for_trace = {r.kind for r in rows}
    assert "voice.tts.requested" in kinds_for_trace
    assert "voice.tts.failed" in kinds_for_trace
    assert "voice.tts.completed" not in kinds_for_trace


def test_voice_speak_honours_parent_trace_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the cockpit hands an x-meeet-trace-id, the router must use it."""

    monkeypatch.setattr(
        synth_module,
        "_engines",
        lambda: {
            "elevenlabs": _FakeVoiceEngine(
                name="elevenlabs", available=True, audio=b"ID3"
            ),
            "openai": _FakeVoiceEngine(name="openai", available=False, audio=None),
            "mac_say": _FakeVoiceEngine(name="mac_say", available=False, audio=None),
        },
    )

    parent_trace = "tr_test_abcdef0123"
    res = client.post(
        "/api/voice/speak",
        json={"text": "with parent trace", "persona": "operator"},
        headers={"x-meeet-trace-id": parent_trace},
    )
    assert res.status_code == 200
    assert res.headers.get("x-trace-id") == parent_trace
    kinds = {r.kind for r in _events_for_trace(parent_trace)}
    assert "voice.tts.requested" in kinds
    assert "voice.tts.completed" in kinds


# ----------------------------------------------------------------------
# speech.parse_intent — dictation surface
# ----------------------------------------------------------------------


def test_speech_intents_emits_requested_and_completed(client: TestClient) -> None:
    res = client.post(
        "/api/speech/intents",
        json={"transcript": "/run morning_brief", "use_playbook_registry": False},
    )
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["ok"] is True
    trace_id = body.get("trace_id")
    assert trace_id, "trace_id missing in /api/speech/intents body"

    kinds = {r.kind for r in _events_for_trace(trace_id)}
    assert "speech.intent.requested" in kinds, kinds
    assert "speech.intent.completed" in kinds, kinds


def test_speech_intents_completed_carries_intent_kind(client: TestClient) -> None:
    """The completed event must carry the resolved intent kind so the
    operator dashboard can group dictated commands by what they did
    (chat / playbook / action / unknown)."""

    res = client.post(
        "/api/speech/intents",
        json={"transcript": "what is on my calendar today"},
    )
    assert res.status_code == 200
    trace_id = res.json()["trace_id"]

    rows = _events_for_trace(trace_id)
    completed = [r for r in rows if r.kind == "speech.intent.completed"]
    assert completed, "speech.intent.completed missing"
    payload = completed[0].payload
    assert "intent_kind" in payload


# ----------------------------------------------------------------------
# memory.upsert / memory.delete — pack memory partitions (audit-3)
# ----------------------------------------------------------------------


def test_memory_upsert_emits_requested_and_completed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``POST /api/packs/{slug}/memory`` emits memory.upsert.*."""

    res = client.post(
        "/api/packs/test_pack/memory",
        json={
            "key": "favourite_color",
            "value": "cyan",
            "kind": "fact",
            "source": "operator",
        },
    )
    # Memory store may be disabled in some test envs — skip then.
    if res.status_code == 503:
        pytest.skip("memory store disabled in this environment")
    assert res.status_code == 200, res.text
    body = res.json()
    trace_id = body.get("trace_id")
    assert trace_id, "trace_id missing in upsert response"

    kinds = {r.kind for r in _events_for_trace(trace_id)}
    assert "memory.upsert.requested" in kinds, kinds
    assert "memory.upsert.completed" in kinds, kinds


def test_memory_delete_emits_failed_on_missing_key(
    client: TestClient,
) -> None:
    """``DELETE`` on an unknown key must still emit memory.delete.failed."""

    parent_trace = "tr_test_memory_delete_404"
    res = client.delete(
        "/api/packs/test_pack/memory/this_key_definitely_does_not_exist",
        headers={"x-meeet-trace-id": parent_trace},
    )
    if res.status_code == 503:
        pytest.skip("memory store disabled in this environment")
    assert res.status_code == 404

    kinds = {r.kind for r in _events_for_trace(parent_trace)}
    assert "memory.delete.requested" in kinds, kinds
    assert "memory.delete.failed" in kinds, kinds


# ----------------------------------------------------------------------
# Bridge invariants the audit also implicitly relies on
# ----------------------------------------------------------------------


def test_meeet_store_persists_events_offline(client: TestClient) -> None:
    """``MEEET_INGEST_URL`` is unset in the fixture so emit() never
    leaves the box. The local SQLite store MUST still persist
    everything so ``POST /api/meeet/replay`` can later flush them.
    This pins the offline-buffer guarantee that the trace coverage
    work above relies on."""

    res = client.post(
        "/api/speech/intents",
        json={"transcript": "noop"},
    )
    assert res.status_code == 200

    rows = _list_events(limit=10)
    assert any(r.kind.startswith("speech.intent.") for r in rows)
    # Offline run: nothing has been pushed to remote ingest yet.
    assert all(not r.pushed for r in rows)
