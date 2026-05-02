"""HTTP surface for the voice layer (Phase L4.1).

Endpoints:

- ``GET /api/voice/personas`` — character roster (Jarvis, Stark, HAL,
  GLaDOS, Interstellar TARS, Operator) with per-provider hints.
- ``GET /api/voice/health`` — which engines are usable right now
  (depends on env / vault keys / running OS).
- ``POST /api/voice/speak`` — synthesise an utterance. Returns
  ``audio/mpeg`` (cloud providers) or ``audio/wav`` (mac say) bytes.
  Optional query/body fields: ``persona``, ``provider``,
  ``thread_id`` (when set, the thread's pinned ``voice_persona_id``
  acts as a fallback persona), ``session_id`` (also honoured via
  ``x-tars-session-id`` header).

The endpoint is **not policy-gated** — TTS is non-destructive and the
cost rolls up automatically through the meeet bridge as a
``voice.tts`` event. **It is** entitlements-gated: TTS providers are
predominantly cloud-billed (ElevenLabs, OpenAI), so the entry point
calls :func:`require_cloud_budget` to surface a 402 before hitting
the synthesiser when the daily cap is exhausted (Bug #2 in
``docs/SYSTEM_AUDIT_2026-05-02.md``).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import Response

from backend.core.chat import get_chat_store
from backend.core.voice import (
    SynthesisError,
    available_engines,
    list_personas,
    synthesize,
)
from web_extras.entitlements_gate import require_cloud_budget


router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/personas")
async def personas_endpoint() -> dict[str, Any]:
    items = [p.to_dict() for p in list_personas()]
    return {
        "ok": True,
        "count": len(items),
        "default_persona_id": "jarvis",
        "personas": items,
    }


@router.get("/health")
async def health_endpoint() -> dict[str, Any]:
    engines = await available_engines()
    return {
        "ok": True,
        "engines": engines,
        "any_available": any(engines.values()),
        "preferred_order": ["elevenlabs", "openai", "mac_say"],
    }


@router.post("/speak")
async def speak_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
    x_tars_session_id: str | None = Header(default=None),
) -> Response:
    body = payload or {}
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text_required")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="text_too_long")
    persona = body.get("persona") or body.get("persona_id")
    provider = body.get("provider")
    session_id = (
        body.get("session_id") or x_tars_session_id or None
    )

    # Bug #2 fix — TTS providers are predominantly cloud-billed; gate
    # at the HTTP edge so a FREE-tier operator gets a clean 402
    # before any synthesis spend lands. ``mac say`` users (route =
    # edge) can opt out via ``TARS_CAP_ENFORCEMENT=off``; production
    # leaves enforcement on by default.
    await require_cloud_budget(kind="cloud", surface="voice.speak")

    # Thread-pinned persona fallback: if the caller didn't specify
    # an explicit ``persona`` but did pass ``thread_id``, look up
    # the thread's pinned ``voice_persona_id`` so coming back to a
    # thread keeps the same voice.
    persona_source = "request" if persona else None
    thread_id_arg = body.get("thread_id")
    if not persona and thread_id_arg:
        thread = await get_chat_store().get_thread(str(thread_id_arg))
        if thread and thread.voice_persona_id:
            persona = thread.voice_persona_id
            persona_source = "thread"

    try:
        result = await synthesize(
            text,
            persona=str(persona) if persona else None,
            provider=str(provider) if provider else None,
            session_id=str(session_id) if session_id else None,
        )
    except SynthesisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {
        "x-tars-voice-provider": result.provider,
        "x-tars-voice-voice-id": result.voice_id,
        "x-tars-voice-bytes": str(result.bytes_total),
        "x-tars-voice-duration-ms": str(result.duration_estimate_ms),
        "cache-control": "no-store",
    }
    if persona_source:
        headers["x-tars-voice-persona-source"] = persona_source
    return Response(content=result.audio, media_type=result.mime, headers=headers)
