"""Speech-to-text via OpenAI Whisper API + local fallbacks.

Originally Wave 73 — Feature 1; extended in W229 to add local
fallbacks so voice input works on Tauri WKWebView (which lacks
``webkitSpeechRecognition``).

Pipeline order, first match wins:

  1. whisper.cpp binary at ``WHISPER_CPP_BIN`` (offline, no key).
  2. OpenAI Whisper API (``whisper-1``) when ``OPENAI_API_KEY``
     (or ``TARS_OPENAI_API_KEY``) is set.
  3. faster-whisper Python package if importable + model path via
     ``WHISPER_LOCAL_PATH``.
  4. Graceful 503 ``no_stt_backend`` with hint.

Stdlib-only for OpenAI path (urllib). Local engines use subprocess
(whisper.cpp) or an optional import (faster-whisper).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from backend.core.vault import get_secret


log = logging.getLogger("tars.voice.transcribe")


_WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_MODEL = "whisper-1"
_DEFAULT_TIMEOUT_S = 60.0
# W229 — frontend caps requests at 25 MiB; align here.
_MAX_BYTES = 25 * 1024 * 1024

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


class NoSTTBackend(TranscribeError):
    """Raised when no engine is configured — separate type so the
    router can return a structured ``{ok:false, error:'no_stt_backend'}``
    envelope with a hint."""


# ─── Engine resolution helpers ───────────────────────────────────


def _resolve_openai_key() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def _whisper_cpp_bin() -> str | None:
    """Path to a working whisper.cpp ``main`` binary, or None."""
    raw = (os.getenv("WHISPER_CPP_BIN") or "").strip()
    if not raw:
        return None
    # Accept either an absolute path or a name on $PATH.
    if "/" in raw and os.path.isfile(raw) and os.access(raw, os.X_OK):
        return raw
    resolved = shutil.which(raw)
    return resolved


def _whisper_cpp_model() -> str | None:
    return (os.getenv("WHISPER_CPP_MODEL") or "").strip() or None


def _faster_whisper_model_path() -> str | None:
    return (os.getenv("WHISPER_LOCAL_PATH") or "").strip() or None


def _faster_whisper_available() -> bool:
    """Cheap import probe — does NOT import the heavy module at
    request time; cached after first call."""
    cache = getattr(_faster_whisper_available, "_cached", None)
    if cache is not None:
        return cache
    try:  # pragma: no cover — exercised via env-isolated tests
        import importlib

        importlib.import_module("faster_whisper")
        result = True
    except Exception:  # pragma: no cover
        result = False
    _faster_whisper_available._cached = result  # type: ignore[attr-defined]
    return result


def is_configured() -> dict[str, Any]:
    """Tell ``/api/voice/health`` whether STT can serve a request.

    Returns a small dict the router can splat into the existing
    health envelope without taking another round-trip.
    """

    cpp = _whisper_cpp_bin()
    key_present = bool(_resolve_openai_key())
    local_path = _faster_whisper_model_path()
    fw = _faster_whisper_available() and bool(local_path)
    provider: str | None = None
    if cpp:
        provider = "whisper_cpp"
    elif key_present:
        provider = "openai_whisper"
    elif fw:
        provider = "faster_whisper"
    return {
        "configured": bool(cpp or key_present or fw),
        "provider": provider,
        "model": os.getenv("TARS_WHISPER_MODEL") or _DEFAULT_MODEL,
        "local_path": local_path,
        "whisper_cpp_bin": cpp,
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
    return "wav"


# ─── Engine: OpenAI Whisper ──────────────────────────────────────


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


# ─── Engine: whisper.cpp ────────────────────────────────────────


def _run_whisper_cpp(
    *, audio: bytes, ext: str, language: str | None, timeout_s: float,
    binary: str, model: str | None,
) -> dict[str, Any]:
    """Run a whisper.cpp invocation and parse its JSON output.

    whisper.cpp's ``main`` accepts ``-f <audio> -m <model> -oj`` and
    writes ``<audio>.json`` alongside the input. We use a temp dir
    so we can read it back deterministically.
    """

    with tempfile.TemporaryDirectory(prefix="tars-whispercpp-") as tmpdir:
        audio_path = os.path.join(tmpdir, f"in.{ext}")
        with open(audio_path, "wb") as f:
            f.write(audio)
        cmd: list[str] = [binary, "-f", audio_path, "-oj", "-of", audio_path]
        if model:
            cmd.extend(["-m", model])
        if language:
            cmd.extend(["-l", language])
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise TranscribeError(f"whisper_cpp_timeout: {exc}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:500]
            raise TranscribeError(
                f"whisper_cpp_failed_rc{exc.returncode}: {stderr}"
            ) from exc
        except FileNotFoundError as exc:
            raise TranscribeError(f"whisper_cpp_missing: {exc}") from exc

        out_path = audio_path + ".json"
        if not os.path.isfile(out_path):
            raise TranscribeError("whisper_cpp_no_output")
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise TranscribeError(f"whisper_cpp_parse: {exc}") from exc

    # whisper.cpp's -oj shape: {transcription: [{text, offsets:{from,to}, ...}, ...]}
    segments = payload.get("transcription") or []
    text = "".join(seg.get("text", "") for seg in segments).strip()
    duration_ms: int | None = None
    if segments:
        last = segments[-1]
        try:
            duration_ms = int(last.get("offsets", {}).get("to") or 0) or None
        except Exception:
            duration_ms = None
    return {
        "text": text,
        "duration_ms": duration_ms,
        "segments_count": len(segments),
        "language": (payload.get("result") or {}).get("language") or language or "en",
    }


# ─── Engine: faster-whisper ─────────────────────────────────────


def _run_faster_whisper(
    *, audio: bytes, ext: str, language: str | None, model_path: str,
) -> dict[str, Any]:  # pragma: no cover — depends on optional dep
    from faster_whisper import WhisperModel  # type: ignore

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(audio)
        tmp_path = tmp.name
    try:
        wm = WhisperModel(model_path, device="auto", compute_type="auto")
        segments_iter, info = wm.transcribe(tmp_path, language=language)
        segments = list(segments_iter)
        text = "".join(s.text for s in segments).strip()
        duration_ms = int(float(info.duration or 0) * 1000) if info else None
        return {
            "text": text,
            "duration_ms": duration_ms,
            "segments_count": len(segments),
            "language": getattr(info, "language", None) or language or "en",
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─── Orchestrator ────────────────────────────────────────────────


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

    Tries engines in priority order: whisper.cpp → OpenAI → faster-whisper.
    Raises :class:`NoSTTBackend` if none is configured; the router
    maps that to a 503 with the configuration hint.
    """

    if not audio:
        return {
            "text": "",
            "language": language or "en",
            "duration_ms": 0,
            "elapsed_ms": 0,
            "model": _DEFAULT_MODEL,
            "provider": "noop",
            "segments_count": 0,
            "bytes_in": 0,
            "ext": _ext_for(content_type, filename),
        }
    if len(audio) > _MAX_BYTES:
        raise TranscribeError(
            f"audio_too_large: {len(audio)} > {_MAX_BYTES}"
        )

    ext = _ext_for(content_type, filename)
    chosen_model = (
        model or os.getenv("TARS_WHISPER_MODEL") or _DEFAULT_MODEL
    )
    started = time.perf_counter()

    # 1) whisper.cpp
    cpp_bin = _whisper_cpp_bin()
    if cpp_bin:
        payload = await asyncio.to_thread(
            _run_whisper_cpp,
            audio=audio, ext=ext, language=language,
            timeout_s=timeout_s, binary=cpp_bin,
            model=_whisper_cpp_model(),
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            **payload,
            "elapsed_ms": elapsed_ms,
            "model": _whisper_cpp_model() or "whisper_cpp",
            "provider": "whisper_cpp",
            "bytes_in": len(audio),
            "ext": ext,
        }

    # 2) OpenAI Whisper
    key = _resolve_openai_key()
    if key:
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
        return {
            "text": text,
            "language": payload.get("language") or language or "en",
            "duration_ms": duration_ms,
            "elapsed_ms": elapsed_ms,
            "model": chosen_model,
            "provider": "openai_whisper",
            "segments_count": len(segments) if isinstance(segments, list) else 0,
            "bytes_in": len(audio),
            "ext": ext,
        }

    # 3) faster-whisper
    fw_path = _faster_whisper_model_path()
    if fw_path and _faster_whisper_available():
        payload = await asyncio.to_thread(
            _run_faster_whisper,
            audio=audio, ext=ext, language=language,
            model_path=fw_path,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            **payload,
            "elapsed_ms": elapsed_ms,
            "model": fw_path,
            "provider": "faster_whisper",
            "bytes_in": len(audio),
            "ext": ext,
        }

    raise NoSTTBackend("no_stt_backend")


__all__ = [
    "TranscribeError",
    "NoSTTBackend",
    "is_configured",
    "transcribe_bytes",
]
