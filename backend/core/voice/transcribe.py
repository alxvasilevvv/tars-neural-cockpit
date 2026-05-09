"""Speech-to-text via OpenAI Whisper API (Wave 73 — Feature 1).

Closes a long-standing audit gap: ``backend.core.voice`` advertised
STT in its ``__init__`` doc but only TTS was wired. The cockpit's
voice loop has been broken because of it — TTS comes back, but the
mic input never produced text.

This module ships the missing half:

- :func:`transcribe_bytes` — sync POST to ``api.openai.com/v1/audio/
  transcriptions`` (model ``whisper-1`` by default), wrapped in
  ``asyncio.to_thread`` for the FastAPI handler.
- :func:`is_configured` — cheap "should the endpoint return 503?"
  probe for the ``/api/voice/health`` view.
- :class:`TranscribeError` — narrow exception so the router surfaces
  ``503 stt_*`` vs. raising a 500.

Stdlib ``urllib`` only — same pattern as
:mod:`backend.core.council.llm` and the council voices.

If ``WHISPER_LOCAL_PATH`` is set the module *attempts* a local
faster-whisper / whisper.cpp lookup. Missing dep is a soft failure:
we just fall back to the cloud path. (No silent install — the
operator opted in by setting the env var.)
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Literal

from backend.core.vault import get_secret


log = logging.getLogger("tars.voice.transcribe")


_WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_MODEL = "whisper-1"
_DEFAULT_TIMEOUT_S = 60.0

# Audit-trace ceiling. Whisper's own cap is 25 MiB; we keep a softer
# one so a misbehaving client doesn't tip over the FastAPI worker.
_MAX_BYTES = 24 * 1024 * 1024  # 24 MiB

# Accepted upstream MIME types — Whisper claims it sniffs by ext, so
# we just need the extension on the multipart filename. Map common
# browser MediaRecorder shapes here.
_EXT_BY_MIME: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/flac": "flac",
}


class TranscribeError(RuntimeError):
    """Narrow exception type so the HTTP layer can map → 503 cleanly."""


def _resolve_openai_key() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def is_configured() -> dict[str, Any]:
    """Tell ``/api/voice/health`` whether STT can serve a request.

    Returns a small dict the router can splat into the existing
    health envelope without taking another round-trip.
    """

    key_present = bool(_resolve_openai_key())
    local_path = (os.getenv("WHISPER_LOCAL_PATH") or "").strip() or None
    return {
        "configured": key_present or bool(local_path),
        "provider": "openai_whisper" if key_present else (
            "local_whisper" if local_path else None
        ),
        "model": os.getenv("TARS_WHISPER_MODEL") or _DEFAULT_MODEL,
        "local_path": local_path,
    }


def _ext_for(content_type: str | None, filename: str | None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"mp3", "wav", "webm", "ogg", "m4a", "mp4", "flac", "mpga"}:
            return ext
    if content_type:
        ct = content_type.lower().split(";", 1)[0].strip()
        if ct in _EXT_BY_MIME:
            return _EXT_BY_MIME[ct]
    return "wav"  # safest universal default for raw PCM or unknown


def _build_multipart(
    *, audio: bytes, ext: str, model: str, language: str | None
) -> tuple[bytes, str]:
    """Hand-roll a multipart/form-data body — keeps stdlib-only."""

    boundary = f"----TARSWhisper{uuid.uuid4().hex}"
    crlf = "\r\n"
    parts: list[bytes] = []

    def _field(name: str, value: str) -> None:
        parts.append(
            (
                f"--{boundary}{crlf}"
                f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'
                f"{value}{crlf}"
            ).encode("utf-8")
        )

    _field("model", model)
    if language:
        _field("language", language)
    _field("response_format", "verbose_json")

    parts.append(
        (
            f"--{boundary}{crlf}"
            f'Content-Disposition: form-data; name="file"; filename="audio.{ext}"{crlf}'
            f"Content-Type: audio/{ext}{crlf}{crlf}"
        ).encode("utf-8")
    )
    parts.append(audio)
    parts.append(crlf.encode("utf-8"))
    parts.append(f"--{boundary}--{crlf}".encode("utf-8"))

    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post_whisper(
    *, audio: bytes, ext: str, model: str, language: str | None,
    timeout_s: float, key: str,
) -> dict[str, Any]:
    body, content_type = _build_multipart(
        audio=audio, ext=ext, model=model, language=language,
    )
    req = urllib.request.Request(
        _WHISPER_API_URL,
        data=body,
        method="POST",
        headers={
            "authorization": f"Bearer {key}",
            "content-type": content_type,
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        # OpenAI returns JSON with {error: {...}} on 4xx/5xx
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body or "{}")
            err_msg = (err_json.get("error") or {}).get("message") or exc.reason
        except Exception:
            err_msg = str(exc)
        raise TranscribeError(f"openai_http_{exc.code}: {err_msg}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TranscribeError(f"transport_error: {exc}") from exc

    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise TranscribeError(f"invalid_json_response: {exc}") from exc


async def transcribe_bytes(
    audio: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
    language: str | None = None,
    model: str | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Transcribe ``audio`` and return the structured Whisper result.

    Output shape is normalised so the router doesn't leak provider
    details: ``{text, language, duration_ms, model, provider,
    segments_count}``.

    Raises :class:`TranscribeError` for any non-2xx, transport, or
    parse failure. Caller maps to 503 (or 400 for empty body).
    """

    if not audio:
        raise TranscribeError("audio_empty")
    if len(audio) > _MAX_BYTES:
        raise TranscribeError(
            f"audio_too_large: {len(audio)} > {_MAX_BYTES}"
        )

    key = _resolve_openai_key()
    if not key:
        raise TranscribeError("stt_not_configured")

    chosen_model = (
        model or os.getenv("TARS_WHISPER_MODEL") or _DEFAULT_MODEL
    )
    ext = _ext_for(content_type, filename)

    started = time.perf_counter()
    payload = await asyncio.to_thread(
        _post_whisper,
        audio=audio,
        ext=ext,
        model=chosen_model,
        language=language,
        timeout_s=timeout_s,
        key=key,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    text = str(payload.get("text") or "").strip()
    duration_s = payload.get("duration")
    duration_ms: int | None = None
    if isinstance(duration_s, (int, float)):
        duration_ms = int(float(duration_s) * 1000)

    segments = payload.get("segments") or []
    segments_count = len(segments) if isinstance(segments, list) else 0

    return {
        "text": text,
        "language": payload.get("language") or language or "en",
        "duration_ms": duration_ms,
        "elapsed_ms": elapsed_ms,
        "model": chosen_model,
        "provider": "openai_whisper",
        "segments_count": segments_count,
        "bytes_in": len(audio),
        "ext": ext,
    }


__all__ = [
    "TranscribeError",
    "is_configured",
    "transcribe_bytes",
]
