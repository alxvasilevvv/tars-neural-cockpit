"""Tests for ``GET /api/voice/personas/effective`` (W295).

The endpoint is a pure read-only diagnostic that mirrors the
provider/voice picker used by :func:`backend.core.voice.synthesize`.
The W290 acceptance harness (``scripts/qa_w290_cockpit.sh`` Group 9)
consumes it to verify the four male personas (jarvis / stark /
hal9000 / tars) resolve to four *distinct* voices in both the
ElevenLabs-enabled and mac_say-only paths.

We stub the engines so the tests never touch the network or the OS
``say`` binary, and so the suite stays Linux-friendly (CI may run
where macOS' ``say`` doesn't exist at all).
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_store
from backend.core.voice import synthesis as synth_module
from backend.core.voice.engines import MacSayEngine
from web_extras.app import app


_MALE_IDS = {"jarvis", "stark", "hal9000", "tars"}


class _FakeEngine:
    """Tiny stand-in for a real TTS engine.

    Only ``is_available()`` is exercised by the effective-resolver —
    we never call ``synthesise`` here, so we leave it returning
    ``None`` to make accidental cloud spend impossible.
    """

    def __init__(self, *, name: str, available: bool) -> None:
        self.name = name
        self._available = available

    async def is_available(self) -> bool:
        return self._available

    async def synthesise(self, text, persona):  # pragma: no cover - unused
        return None


class _FakeMacSayEngine(MacSayEngine):
    """``mac_say`` impostor that pins ``is_available()`` /
    ``installed_voices()`` so the resolver's
    :meth:`MacSayEngine._pick_fallback_voice` path stays reachable —
    the real engine probes ``platform.system()`` and ``/usr/bin/say``,
    which we cannot rely on in CI.
    """

    def __init__(
        self,
        *,
        available: bool,
        installed: set[str],
    ) -> None:
        super().__init__()
        # Pre-fill the parent's caches so its native probes
        # (platform.system / shutil.which / subprocess) never run.
        self._available_cache = available
        self._installed_voices_cache = installed

    async def synthesise(self, text, persona):  # pragma: no cover - unused
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("MEEET_LOCAL_DB_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("TARS_VOICE_PROVIDER", raising=False)
    reset_store()
    synth_module.reset_engines()
    yield TestClient(app)
    synth_module.reset_engines()
    reset_store()


def _patch_engines(
    monkeypatch: pytest.MonkeyPatch,
    *,
    elevenlabs: bool,
    openai: bool,
    mac_say: bool,
    installed_voices: set[str] | None = None,
) -> None:
    """Swap the cached engine table for a deterministic stub set."""

    fakes = {
        "elevenlabs": _FakeEngine(name="elevenlabs", available=elevenlabs),
        "openai": _FakeEngine(name="openai", available=openai),
        "mac_say": _FakeMacSayEngine(
            available=mac_say,
            installed=installed_voices or set(),
        ),
    }
    monkeypatch.setattr(synth_module, "_engines", lambda: fakes)


def test_effective_endpoint_returns_full_envelope(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Samantha", "Alex"},
    )

    res = client.get("/api/voice/personas/effective")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["ok"] is True
    assert body["count"] == 6
    assert body["default_persona_id"] == "jarvis"
    assert body["provider_chain"] == ["elevenlabs", "openai", "mac_say"]
    assert isinstance(body["personas"], list)
    assert len(body["personas"]) == 6
    ids = {p["id"] for p in body["personas"]}
    assert {"jarvis", "stark", "hal9000", "glados", "tars", "operator"} <= ids
    for p in body["personas"]:
        # Every persona must carry the keys the harness consumes.
        assert "effective_provider" in p
        assert "effective_voice_id" in p
        assert "effective_mac_say_voice" in p
        assert p["fallback_chain"] == ["elevenlabs", "openai", "mac_say"]


def test_providers_available_mac_say_always_reported(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``providers_available.mac_say`` must always be present in the
    envelope — even on hosts where ``/usr/bin/say`` isn't installed,
    so callers can branch on availability rather than KeyErroring."""

    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Alex"},
    )
    body = client.get("/api/voice/personas/effective").json()
    assert "mac_say" in body["providers_available"]
    assert body["providers_available"]["mac_say"] is True


def test_with_elevenlabs_key_male_personas_have_4_distinct_voice_ids(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path #1 — operator runs with ELEVENLABS_API_KEY set.

    Each of the four male personas has a unique
    ``elevenlabs_voice_id`` baked into the registry, so the harness
    must see four distinct ``effective_voice_id`` values.
    """

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test_W295_fake_key")
    _patch_engines(
        monkeypatch,
        elevenlabs=True,
        openai=True,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Alex"},
    )

    body = client.get("/api/voice/personas/effective").json()
    male = [p for p in body["personas"] if p["id"] in _MALE_IDS]
    assert len(male) == 4, [p["id"] for p in male]
    voice_ids = [p["effective_voice_id"] for p in male]
    assert len(set(voice_ids)) == 4, voice_ids
    # All four should pick ElevenLabs as the effective provider when
    # the key is set.
    assert {p["effective_provider"] for p in male} == {"elevenlabs"}


def test_without_elevenlabs_key_male_personas_have_4_distinct_mac_say_voices(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path #2 — no cloud keys, mac_say-only.

    Each male persona has a unique default ``mac_say_voice``
    (Daniel / Aaron / Bruce / Tom). The endpoint must surface them
    so the harness can still assert distinctness in the offline
    path.
    """

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("TARS_ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TARS_OPENAI_API_KEY", raising=False)

    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Samantha", "Alex"},
    )

    body = client.get("/api/voice/personas/effective").json()
    male = [p for p in body["personas"] if p["id"] in _MALE_IDS]
    assert len(male) == 4, [p["id"] for p in male]

    # effective_voice_id falls back to the mac_say voice name when
    # mac_say is the chosen provider — should be 4 distinct names.
    voice_ids = [p["effective_voice_id"] for p in male]
    assert len(set(voice_ids)) == 4, voice_ids

    # And the dedicated effective_mac_say_voice key must also expose
    # 4 distinct voices regardless of which provider was chosen.
    say_voices = [p["effective_mac_say_voice"] for p in male]
    assert len(set(say_voices)) == 4, say_voices

    # All four resolve to mac_say when no cloud is available.
    assert {p["effective_provider"] for p in male} == {"mac_say"}


def test_endpoint_does_not_call_synthesize(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tripwire — the diagnostic endpoint must be pure read-only.

    If a future refactor accidentally pipes the request through
    :func:`synthesize`, every call would touch the cost ledger and
    rack up cloud spend. We blow up loudly here instead.
    """

    sentinel = {"called": False}

    async def _explode(*args, **kwargs):
        sentinel["called"] = True
        raise AssertionError("synthesize() must not be invoked by the diagnostic endpoint")

    monkeypatch.setattr(synth_module, "synthesize", _explode)
    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Alex"},
    )

    res = client.get("/api/voice/personas/effective")
    assert res.status_code == 200
    assert sentinel["called"] is False


def test_voice_id_alias_present_for_legacy_clients(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The harness reads ``effective_voice_id`` first and falls back to
    ``voice_id``. We expose both so older harnesses keep working."""

    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Daniel", "Aaron", "Bruce", "Tom", "Alex"},
    )
    body = client.get("/api/voice/personas/effective").json()
    for p in body["personas"]:
        if p["effective_voice_id"] is not None:
            assert p["voice_id"] == p["effective_voice_id"]


def test_mac_say_fallback_voice_picker_used_when_preferred_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the persona's preferred mac_say voice isn't installed, the
    resolver must call :meth:`MacSayEngine._pick_fallback_voice` — same
    logic the synthesis path uses — so the reported voice always
    matches what would actually be heard.

    W310-f: ``_pick_fallback_voice`` now walks ``persona.provider
    .mac_say_voice_alternatives`` BEFORE the global accent default.
    TARS's per-persona chain is ``("Tom", "Fred", "Junior", "Ralph",
    "Albert", "Daniel")`` so when Tom is missing it falls through to
    Fred (next installed) instead of jumping to Alex via the
    global accent default.
    """

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    # Tom (TARS' preferred voice) is *not* installed; the per-persona
    # alternatives chain walks Tom→Fred→Junior→Ralph→Albert→Daniel and
    # lands on Fred (the first installed voice in that chain).
    _patch_engines(
        monkeypatch,
        elevenlabs=False,
        openai=False,
        mac_say=True,
        installed_voices={"Alex", "Aaron", "Fred", "Daniel"},
    )

    body = client.get("/api/voice/personas/effective").json()
    tars = next(p for p in body["personas"] if p["id"] == "tars")

    # Per-persona alternates take precedence over the global accent
    # chain — Fred is the first installed entry in TARS's chain.
    assert tars["effective_mac_say_voice"] == "Fred"
    assert tars["effective_voice_id"] == "Fred"


def test_resolve_effective_returns_pure_dict_for_unit_callers() -> None:
    """The HTTP endpoint is a thin wrapper — make sure the underlying
    helper is also useful to non-HTTP callers (e.g. CLI ``tars
    voice doctor``)."""

    import asyncio

    from backend.core.voice import resolve_effective

    # No engine swap → use the real engines but with no cloud keys.
    # We don't assert on which provider was picked (depends on host),
    # only that the envelope keys are present and types are sane.
    try:
        eff = asyncio.run(resolve_effective("jarvis"))
    finally:
        synth_module.reset_engines()

    assert "effective_provider" in eff
    assert "effective_voice_id" in eff
    assert "effective_mac_say_voice" in eff
    assert eff["fallback_chain"] == ["elevenlabs", "openai", "mac_say"]
    assert isinstance(eff["providers_available"], dict)
