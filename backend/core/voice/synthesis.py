"""Synthesis orchestrator.

Picks the best provider (or the operator-pinned one) and falls back
gracefully when the chosen engine is unavailable. Emits ``voice.tts``
events to the meeet bridge so the cost ledger sees voice usage.

Provider precedence (when ``provider="auto"``):
    elevenlabs  →  openai  →  mac_say
    (pin via ``TARS_VOICE_PROVIDER`` env or per-call ``provider`` arg)

The synthesis layer never raises on remote failures; it walks the
fallback chain and either returns a successful :class:`SynthesisResult`
or raises :class:`SynthesisError` after exhausting every option.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Iterable, Optional

from backend.core.meeet import current_route, get_client, set_route, trace_scope

from .engines import (
    ElevenLabsEngine,
    MacSayEngine,
    OpenAITTSEngine,
    SynthesisResult,
    TTSEngine,
)
from .personas import Persona, get_persona


# Public alias of the auto chain so external callers (e.g. the
# /api/voice/personas/effective endpoint) can advertise the same
# fallback order without duplicating the constant.
PROVIDER_CHAIN: tuple[str, ...] = ("elevenlabs", "openai", "mac_say")


log = logging.getLogger("tars.voice")


# USD per million characters (chars treated as 1 token in usage.tokens
# events for ledger compatibility). Override with
# ``TARS_VOICE_PRICE_<PROVIDER>`` env vars.
_DEFAULT_PRICE_PER_MCHAR: dict[str, float] = {
    "elevenlabs": 180.0,  # ~$0.18 / 1k chars on Multilingual v2 starter tier
    "openai": 12.0,       # gpt-4o-mini-tts ~$12 / 1M chars
    "mac_say": 0.0,
}


def _price_per_mchar(provider: str) -> float:
    raw = os.getenv(f"TARS_VOICE_PRICE_{provider.upper()}")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return _DEFAULT_PRICE_PER_MCHAR.get(provider, 0.0)


def _voice_cost_usd(provider: str, chars: int) -> float:
    if chars <= 0:
        return 0.0
    return round((chars / 1_000_000.0) * _price_per_mchar(provider), 6)


class SynthesisError(RuntimeError):
    """Raised when every provider fell through."""


_AUTO_ORDER: tuple[str, ...] = PROVIDER_CHAIN
_ENGINES: dict[str, TTSEngine] = {}


def _engines() -> dict[str, TTSEngine]:
    """Lazy singleton — engines are stateless but caching avoids work."""

    global _ENGINES
    if not _ENGINES:
        _ENGINES = {
            "elevenlabs": ElevenLabsEngine(),
            "openai": OpenAITTSEngine(),
            "mac_say": MacSayEngine(),
        }
    return _ENGINES


def reset_engines() -> None:
    """Clear cached engines — used in tests."""

    global _ENGINES
    _ENGINES = {}


async def available_engines() -> dict[str, bool]:
    out: dict[str, bool] = {}
    for name, eng in _engines().items():
        try:
            out[name] = await eng.is_available()
        except Exception:  # never explode a status probe
            out[name] = False
    return out


def _pinned_provider() -> Optional[str]:
    raw = (os.getenv("TARS_VOICE_PROVIDER") or "").strip().lower()
    if raw in _AUTO_ORDER:
        return raw
    return None


def _resolve_order(provider: str | None) -> list[str]:
    if provider and provider != "auto":
        if provider not in _AUTO_ORDER:
            return [provider]
        # Try the requested provider first, then fall back through the
        # auto chain (so a missing key never blocks playback).
        rest = [p for p in _AUTO_ORDER if p != provider]
        return [provider, *rest]
    pinned = _pinned_provider()
    if pinned:
        rest = [p for p in _AUTO_ORDER if p != pinned]
        return [pinned, *rest]
    return list(_AUTO_ORDER)


def _persona_voice_id_for(persona: Persona, provider: str) -> str | None:
    """Return the voice id ``persona`` advertises for ``provider``.

    Centralises the per-provider attribute lookup so both
    :func:`synthesize` and :func:`resolve_effective` agree on which
    field is the canonical voice handle (mac_say uses the ``say -v``
    voice name; elevenlabs uses the public voice id; openai uses the
    preset name).
    """

    if provider == "elevenlabs":
        return persona.provider.elevenlabs_voice_id
    if provider == "openai":
        return persona.provider.openai_voice
    if provider == "mac_say":
        return persona.provider.mac_say_voice
    return None


async def _effective_mac_say_voice(persona: Persona) -> str | None:
    """Resolve the ``mac_say`` voice the persona would actually fall
    to on this machine, applying :meth:`MacSayEngine._pick_fallback_voice`
    when the preferred voice is not installed.

    Returns ``None`` only when the mac_say engine itself isn't
    available (non-Darwin host or missing ``/usr/bin/say``).
    """

    eng = _engines().get("mac_say")
    if eng is None or not isinstance(eng, MacSayEngine):
        # Custom engine swap (tests). Fall back to the persona's
        # declared mac_say voice without further resolution.
        return persona.provider.mac_say_voice
    try:
        if not await eng.is_available():
            # mac_say still has a *declared* voice in the persona —
            # surface it so callers (the diagnostics endpoint) can
            # show what would be used on a Mac. Returning ``None``
            # here would falsely imply the persona is silent.
            return persona.provider.mac_say_voice
        installed = await eng.installed_voices()
    except Exception:  # never explode a status probe
        return persona.provider.mac_say_voice
    preferred = persona.provider.mac_say_voice or "Alex"
    if installed and preferred not in installed:
        return MacSayEngine._pick_fallback_voice(persona, installed)
    return preferred


async def resolve_effective(
    persona: Persona | str | None,
    *,
    provider: str | None = None,
) -> dict[str, object]:
    """Read-only mirror of :func:`synthesize`'s provider/voice picker.

    Walks the same provider chain as ``synthesize`` and reports the
    first provider that *would* be used (engine available + persona
    has a voice configured), plus the voice id that would be picked.

    Returns a dict with::

        effective_provider:        str | None
        effective_voice_id:        str | None
        effective_mac_say_voice:   str | None
        fallback_chain:            list[str]   # full theoretical order
        considered:                list[str]   # probed up to the chosen
        providers_available:       dict[str, bool]

    No audio is synthesised, no remote calls are made beyond the
    cheap ``is_available()`` probes that ``/api/voice/health``
    already runs.
    """

    target = persona if isinstance(persona, Persona) else get_persona(persona)
    order = _resolve_order(provider)
    engines = _engines()

    # Probe every engine once — this is what /health does too. Cheap.
    providers_available: dict[str, bool] = {}
    for name, engine in engines.items():
        try:
            providers_available[name] = await engine.is_available()
        except Exception:
            providers_available[name] = False

    effective_provider: str | None = None
    effective_voice_id: str | None = None
    considered: list[str] = []

    for name in order:
        engine = engines.get(name)
        if engine is None:
            continue
        considered.append(name)
        if not providers_available.get(name, False):
            continue
        vid = _persona_voice_id_for(target, name)
        if not vid:
            continue
        if name == "mac_say":
            # Apply the same install-aware fallback the engine does
            # at synthesis time so the reported voice matches reality.
            vid = await _effective_mac_say_voice(target) or vid
        effective_provider = name
        effective_voice_id = vid
        break

    # Always surface the mac_say voice the persona would fall to,
    # regardless of which provider was chosen — diagnostic clients
    # use this to show "if cloud goes away, you'd hear <voice>".
    effective_mac_say_voice = await _effective_mac_say_voice(target)

    return {
        "effective_provider": effective_provider,
        "effective_voice_id": effective_voice_id,
        "effective_mac_say_voice": effective_mac_say_voice,
        "fallback_chain": list(order),
        "considered": considered,
        "providers_available": providers_available,
    }


async def synthesize(
    text: str,
    persona: Persona | str | None = None,
    *,
    provider: str | None = None,
    session_id: str | None = None,
) -> SynthesisResult:
    """Synthesise ``text`` using ``persona``'s preferred voice.

    Parameters
    ----------
    text:
        UTF-8 prompt. Trimmed; empty input raises :class:`SynthesisError`.
    persona:
        Either a :class:`Persona` instance, a registered persona id,
        or ``None`` for the default operator voice.
    provider:
        ``"auto"`` (default), ``"elevenlabs"``, ``"openai"``, or
        ``"mac_say"``. Unknown values are tried as the only provider.
    session_id:
        Cockpit session id; threaded into the meeet trace so the
        cost ledger groups TTS calls with the originating chat turn.
    """

    if not text or not text.strip():
        raise SynthesisError("empty_text")
    text = text.strip()

    target = persona if isinstance(persona, Persona) else get_persona(persona)
    order = _resolve_order(provider)
    engines = _engines()

    client = get_client()
    started = time.perf_counter()
    last_attempt: dict[str, str] = {}

    with trace_scope(session=session_id, route="edge") as trace_id:
        for name in order:
            engine = engines.get(name)
            if engine is None:
                last_attempt[name] = "unknown_provider"
                continue
            try:
                if not await engine.is_available():
                    last_attempt[name] = "unavailable"
                    continue
                result = await engine.synthesise(text, target)
            except Exception as exc:  # never propagate engine bugs
                last_attempt[name] = f"exception: {exc}"
                log.exception("voice engine %s blew up", name)
                continue
            if result is None:
                last_attempt[name] = "no_audio"
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            # Cloud providers move us to the cloud route for the chat
            # turn the synthesis is nested in (if any).
            if name in ("elevenlabs", "openai"):
                set_route("cloud")
            cost_usd = _voice_cost_usd(result.provider, len(text))
            await client.emit(
                "voice.tts",
                {
                    "persona": target.id,
                    "provider": result.provider,
                    "voice_id": result.voice_id,
                    "mime": result.mime,
                    "bytes_total": result.bytes_total,
                    "chars": len(text),
                    "duration_estimate_ms": result.duration_estimate_ms,
                    "latency_ms": round(elapsed_ms, 3),
                    "route": current_route(),
                    "trace_id": trace_id,
                    "cost_usd": cost_usd,
                    "fallbacks_tried": [
                        n for n in last_attempt
                    ],
                    "fallback_reasons": last_attempt,
                },
            )
            # Also emit a `usage.tokens` event so the cost ledger picks
            # up TTS spend in the same /api/usage rollup as chat — the
            # model is "voice/<provider>" so the buckets stay distinct.
            await client.emit(
                "usage.tokens",
                {
                    "model": f"voice/{result.provider}",
                    "tokens_in": len(text),
                    "tokens_out": 0,
                    "latency_ms": round(elapsed_ms, 3),
                    "cost_usd": cost_usd,
                    "topic": "voice.tts",
                    "persona": target.id,
                    "voice_id": result.voice_id,
                },
            )
            return result

    raise SynthesisError(
        f"no_provider_succeeded order={order} attempts={last_attempt}"
    )
