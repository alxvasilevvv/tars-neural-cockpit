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


_AUTO_ORDER: tuple[str, ...] = ("elevenlabs", "openai", "mac_say")
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
