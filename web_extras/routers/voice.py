"""HTTP surface for the voice layer (Phase L4.1).

Endpoints:

- ``GET /api/voice/personas`` — character roster (Jarvis, Stark, HAL,
  GLaDOS, Interstellar TARS, Operator) with per-provider hints.
- ``GET /api/voice/health`` — which engines are usable right now
  (depends on env / vault keys / running OS) plus STT readiness.
- ``POST /api/voice/speak`` — synthesise an utterance. Returns
  ``audio/mpeg`` (cloud providers) or ``audio/wav`` (mac say) bytes.
  Optional query/body fields: ``persona``, ``provider``,
  ``thread_id`` (when set, the thread's pinned ``voice_persona_id``
  acts as a fallback persona), ``session_id`` (also honoured via
  ``x-tars-session-id`` header).
- ``POST /api/voice/transcribe`` — Wave 73 Feature 1. Multipart
  audio in (mp3/wav/webm/m4a/...), JSON ``{text, language,
  duration_ms, model, ...}`` out. Uses OpenAI Whisper API
  (``whisper-1``) when ``OPENAI_API_KEY`` is configured;
  otherwise returns 503 ``stt_not_configured``.

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

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response

from backend.core.chat import get_chat_store
from backend.core.meeet import get_client as get_meeet_client, new_trace_id, trace_scope
from backend.core.voice import (
    SynthesisError,
    available_engines,
    list_personas,
    synthesize,
)
from backend.core.voice.transcribe import (
    TranscribeError,
    is_configured as stt_is_configured,
    transcribe_bytes,
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
    stt = stt_is_configured()
    return {
        "ok": True,
        "engines": engines,
        "any_available": any(engines.values()),
        "preferred_order": ["elevenlabs", "openai", "mac_say"],
        "stt": stt,
    }


@router.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
    model: str | None = Form(default=None),
    x_tars_session_id: str | None = Header(default=None),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Wave 73 Feature 1 — Whisper-backed STT.

    Multipart file in (mp3/wav/webm/m4a/...), JSON out::

        {text, language, duration_ms, model, provider, ...}

    Returns 503 ``stt_not_configured`` when no key is set so the
    cockpit can flip the mic button to "configure" instead of
    silently failing.
    """

    config = stt_is_configured()
    if not config["configured"]:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "stt_not_configured",
                "hint": "set OPENAI_API_KEY (or WHISPER_LOCAL_PATH for local)",
            },
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="audio_empty")

    parent_trace = (x_meeet_trace_id or "").strip() or None
    trace_id = parent_trace or new_trace_id()
    meeet = get_meeet_client()
    base_payload = {
        "bytes_in": len(audio),
        "content_type": file.content_type,
        "filename": file.filename,
        "language_hint": language,
        "model_override": model,
        "session_id": x_tars_session_id,
    }
    with trace_scope(trace_id):
        await meeet.emit("voice.stt.requested", base_payload)
        try:
            result = await transcribe_bytes(
                audio,
                content_type=file.content_type,
                filename=file.filename,
                language=language,
                model=model,
            )
        except TranscribeError as exc:
            err_str = str(exc)
            await meeet.emit(
                "voice.stt.failed",
                {**base_payload, "error": err_str[:200]},
            )
            # 503 keeps the cockpit honest — the engine is missing /
            # transient. 400 only for empty body, handled above.
            raise HTTPException(status_code=503, detail=err_str) from exc

        await meeet.emit(
            "voice.stt.completed",
            {
                **base_payload,
                "text_len": len(result.get("text") or ""),
                "duration_ms": result.get("duration_ms"),
                "elapsed_ms": result.get("elapsed_ms"),
                "model": result.get("model"),
                "provider": result.get("provider"),
            },
        )
    result["trace_id"] = trace_id
    return result


@router.post("/speak")
async def speak_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
    x_tars_session_id: str | None = Header(default=None),
    x_meeet_trace_id: str | None = Header(default=None),
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

    # 2026-05-04 audit-2: voice.speak is one of the most-billed
    # operator surfaces (ElevenLabs/OpenAI tokens at ~$0.30/1k chars).
    # Wrap in trace_scope + emit voice.tts.{requested,completed,failed}
    # so every utterance is observable in the meeet trail with the
    # provider, persona, byte count and trace_id.
    parent_trace = (x_meeet_trace_id or "").strip() or None
    trace_id = parent_trace or new_trace_id()
    meeet = get_meeet_client()
    base_payload = {
        "text_len": len(text),
        "persona": persona,
        "persona_source": persona_source,
        "provider_hint": provider,
        "session_id": session_id,
        "thread_id": thread_id_arg,
    }

    with trace_scope(trace_id):
        await meeet.emit("voice.tts.requested", base_payload)
        try:
            result = await synthesize(
                text,
                persona=str(persona) if persona else None,
                provider=str(provider) if provider else None,
                session_id=str(session_id) if session_id else None,
            )
        except SynthesisError as exc:
            await meeet.emit(
                "voice.tts.failed",
                {**base_payload, "error": str(exc)[:200]},
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        await meeet.emit(
            "voice.tts.completed",
            {
                **base_payload,
                "provider": result.provider,
                "voice_id": result.voice_id,
                "bytes_total": result.bytes_total,
                "duration_estimate_ms": result.duration_estimate_ms,
            },
        )

    headers = {
        "x-tars-voice-provider": result.provider,
        "x-tars-voice-voice-id": result.voice_id,
        "x-tars-voice-bytes": str(result.bytes_total),
        "x-tars-voice-duration-ms": str(result.duration_estimate_ms),
        "x-trace-id": trace_id,
        "cache-control": "no-store",
    }
    if persona_source:
        headers["x-tars-voice-persona-source"] = persona_source
    return Response(content=result.audio, media_type=result.mime, headers=headers)
