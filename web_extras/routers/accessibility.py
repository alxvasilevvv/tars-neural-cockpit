"""W217 + W274 — Accessibility helpers and premium TTS.

Endpoints:

  POST /api/a11y/ocr_speak    — OCR a region/image, return text.
  GET  /api/a11y/health       — feature probe.
  POST /api/a11y/speak        — Premium TTS via ElevenLabs (multilingual)
                                  with graceful browser-TTS fallback.
  GET  /api/a11y/voices       — Curated voice picker list (W274).
  POST /api/a11y/voice-clone  — Voice clone stub (W274, Creator plan).

W274 details:

- When ``ELEVENLABS_API_KEY`` is set the /speak endpoint calls
  ``https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`` with the
  ``eleven_multilingual_v2`` model (29 languages incl. Russian) and
  returns a base64 ``audio/mpeg`` data URL. Responses are cached on
  disk at ``~/.tars/tts_cache/<hash>.mp3`` (LRU, 100MB).
- When no key is set, falls back to ``use_browser_tts: true`` so the
  cockpit can use the local ``speechSynthesis`` API.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/a11y", tags=["a11y", "accessibility"])


# --- W274 curated voice catalog ----------------------------------
# 6-voice picker. voice_id values are ElevenLabs public-library ids;
# they work out of the box on every paid plan and most Free plans.
_CURATED_VOICES: list[dict[str, Any]] = [
    {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "name": "Rachel",
        "lang_codes": ["en", "ru", "es", "fr", "de", "pt", "pl", "it"],
        "gender": "female",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/21m00Tcm4TlvDq8ikWAM/sample.mp3",
        "description": "Calm narration English (works in 29 langs via multilingual_v2)",
        "default": True,
    },
    {
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "name": "Adam",
        "lang_codes": ["en", "ru", "es", "fr", "de"],
        "gender": "male",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/pNInz6obpgDQGcFmaJgB/sample.mp3",
        "description": "Deep, authoritative male — TARS persona match",
    },
    {
        "voice_id": "IKne3meq5aSn9XLyUdCD",
        "name": "Charlie",
        "lang_codes": ["en", "ru", "es", "fr", "de", "ja", "zh"],
        "gender": "male",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/IKne3meq5aSn9XLyUdCD/sample.mp3",
        "description": "Multi-purpose, natural in Russian + Asian languages",
    },
    {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "name": "Sarah",
        "lang_codes": ["en", "ru", "es"],
        "gender": "female",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/EXAVITQu4vr4xnSDxMaL/sample.mp3",
        "description": "Warm, conversational female",
    },
    {
        "voice_id": "onwK4e9ZLuTAKqWW03F9",
        "name": "Daniel",
        "lang_codes": ["en", "ru", "fr"],
        "gender": "male",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/onwK4e9ZLuTAKqWW03F9/sample.mp3",
        "description": "British narrator — premium documentary feel",
    },
    {
        "voice_id": "XB0fDUnXU5powFXDhCwa",
        "name": "Bella",
        "lang_codes": ["en", "ru", "es", "it"],
        "gender": "female",
        "sample_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/XB0fDUnXU5powFXDhCwa/sample.mp3",
        "description": "Energetic, expressive female",
    },
]


def _tts_cache_dir() -> Path:
    p = Path(os.path.expanduser("~/.tars/tts_cache"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _tts_cache_key(text: str, voice_id: str, model_id: str) -> str:
    blob = f"{model_id}|{voice_id}|{text}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:32]


def _tts_cache_lookup(key: str) -> bytes | None:
    p = _tts_cache_dir() / f"{key}.mp3"
    if not p.is_file():
        return None
    try:
        os.utime(p, None)  # bump mtime for LRU
        return p.read_bytes()
    except OSError:
        return None


def _tts_cache_store(key: str, data: bytes, *, max_bytes: int = 100 * 1024 * 1024) -> None:
    d = _tts_cache_dir()
    try:
        (d / f"{key}.mp3").write_bytes(data)
    except OSError as exc:
        logger.warning("tts.cache.store_failed: %s", exc)
        return
    # LRU eviction by mtime ascending; drop oldest until under cap.
    try:
        files = sorted(d.glob("*.mp3"), key=lambda x: x.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        while total > max_bytes and files:
            victim = files.pop(0)
            try:
                total -= victim.stat().st_size
                victim.unlink()
            except OSError:
                pass
    except OSError as exc:
        logger.warning("tts.cache.evict_failed: %s", exc)


def _elevenlabs_synthesize(
    *, text: str, voice_id: str, model_id: str, api_key: str
) -> bytes:
    """Blocking HTTPS call to ElevenLabs. Raises on non-200."""
    import urllib.request

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec: B310
        return resp.read()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Probe: does this TARS have OCR + TTS capabilities right now?"""
    pytesseract_ok = False
    try:
        import pytesseract  # noqa: F401
        pytesseract_ok = True
    except ImportError:
        pass

    pil_ok = False
    try:
        from PIL import Image  # noqa: F401
        pil_ok = True
    except ImportError:
        pass

    elevenlabs_key = bool((os.getenv("ELEVENLABS_API_KEY") or "").strip())
    openai_key = bool((os.getenv("OPENAI_API_KEY") or os.getenv("TARS_OPENAI_API_KEY") or "").strip())

    return {
        "ok": True,
        "capabilities": {
            "ocr_local": pytesseract_ok and pil_ok,
            "tts_cloud_elevenlabs": elevenlabs_key,
            "tts_cloud_openai": openai_key,
            "tts_browser_fallback": True,
        },
        "model": "eleven_multilingual_v2" if elevenlabs_key else None,
        "languages": 29 if elevenlabs_key else 0,
        "hint": (
            "ElevenLabs Multilingual v2 active (29 languages incl. Russian)."
            if elevenlabs_key
            else "Without cloud TTS key, the cockpit uses the browser's "
                 "speechSynthesis API to read text aloud locally."
        ),
    }


@router.post("/ocr_speak")
async def ocr_speak(file: UploadFile = File(...)) -> dict[str, Any]:
    """OCR an uploaded image (PNG/JPEG) and return the extracted text."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return {
            "ok": False,
            "error": "ocr_unavailable",
            "hint": "Install: brew install tesseract && pip install pytesseract Pillow",
        }

    try:
        from io import BytesIO

        data = await file.read()
        img = Image.open(BytesIO(data))
        text = pytesseract.image_to_string(img).strip()
        if not text:
            return {
                "ok": True,
                "text": "",
                "speakable": False,
                "hint": "No legible text found in image.",
            }
        return {
            "ok": True,
            "text": text,
            "char_count": len(text),
            "speakable": True,
            "engine": "pytesseract",
        }
    except Exception as exc:
        logger.exception("a11y.ocr_speak.failed")
        raise HTTPException(status_code=400, detail={"error": "ocr_failed", "message": str(exc)})


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    voice_id: str | None = Field(default=None, description="ElevenLabs voice id")
    voice: str | None = Field(default=None, description="Alias for voice_id (legacy)")
    lang: str | None = Field(default=None, description="BCP-47 hint or 'auto'")
    model_id: str | None = Field(default=None, description="ElevenLabs model id override")


@router.post("/speak")
async def speak(req: SpeakRequest) -> dict[str, Any]:
    """Synthesize speech via ElevenLabs when configured, else fall back.

    Response shape:

    - ElevenLabs success: ``{ok: true, engine: "elevenlabs",
      audio_url: "data:audio/mpeg;base64,...", cached: bool, voice_id, model_id}``
    - No key configured: ``{ok: true, use_browser_tts: true, text, hint}``
    - ElevenLabs failure: gracefully degrades to ``use_browser_tts`` with
      ``warn`` payload.
    """
    text = (req.text or "").strip()
    if not text:
        return {"ok": False, "error": "empty_text"}

    # Hard-cap text per request (W274 spec: 5000 chars upper for one call).
    text = text[:5000]

    api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        return {
            "ok": True,
            "use_browser_tts": True,
            "text": text,
            "engine": "browser",
            "hint": (
                "ELEVENLABS_API_KEY not set — using browser speechSynthesis. "
                "Add the key to .env for premium multilingual voice."
            ),
        }

    voice_id = (req.voice_id or req.voice or "21m00Tcm4TlvDq8ikWAM").strip()
    model_id = (req.model_id or "eleven_multilingual_v2").strip()

    # Cache lookup.
    key = _tts_cache_key(text, voice_id, model_id)
    cached = _tts_cache_lookup(key)
    if cached is not None:
        b64 = base64.b64encode(cached).decode("ascii")
        return {
            "ok": True,
            "engine": "elevenlabs",
            "model_id": model_id,
            "voice_id": voice_id,
            "audio_url": f"data:audio/mpeg;base64,{b64}",
            "bytes": len(cached),
            "cached": True,
        }

    # Live call (sync; ElevenLabs latency budget ~600-900ms).
    try:
        import asyncio
        audio = await asyncio.to_thread(
            _elevenlabs_synthesize,
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            api_key=api_key,
        )
    except Exception as exc:  # noqa: BLE001 — return browser fallback on any failure
        logger.warning("elevenlabs.synth_failed: %s", exc)
        return {
            "ok": True,
            "use_browser_tts": True,
            "text": text,
            "engine": "browser",
            "warn": f"elevenlabs_failed: {exc.__class__.__name__}",
        }

    _tts_cache_store(key, audio)
    b64 = base64.b64encode(audio).decode("ascii")
    return {
        "ok": True,
        "engine": "elevenlabs",
        "model_id": model_id,
        "voice_id": voice_id,
        "audio_url": f"data:audio/mpeg;base64,{b64}",
        "bytes": len(audio),
        "cached": False,
    }


@router.get("/voices")
async def voices() -> dict[str, Any]:
    """Curated 6-voice list for the cockpit picker."""
    elevenlabs_key = bool((os.getenv("ELEVENLABS_API_KEY") or "").strip())
    return {
        "ok": True,
        "engine": "elevenlabs" if elevenlabs_key else "browser",
        "model_id": "eleven_multilingual_v2" if elevenlabs_key else None,
        "voices": _CURATED_VOICES,
        "count": len(_CURATED_VOICES),
        "hint": (
            "29 supported languages via eleven_multilingual_v2."
            if elevenlabs_key
            else "Connect ELEVENLABS_API_KEY in .env to enable premium voices. "
                 "Browser fallback will use OS default voice for now."
        ),
    }


class VoiceCloneRequest(BaseModel):
    name: str = Field(default="My voice", max_length=120)
    description: str | None = Field(default=None, max_length=500)


@router.post("/voice-clone")
async def voice_clone(
    name: str = "My voice",
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Voice-cloning stub. Real cloning requires a Creator-plan key."""
    has_creator = (os.getenv("ELEVENLABS_CREATOR_PLAN") or "").strip() == "1"
    if not has_creator:
        return {
            "ok": False,
            "engine": "elevenlabs",
            "voice_id": None,
            "hint": (
                "Voice cloning requires ElevenLabs Creator plan ($11/mo). "
                "Set ELEVENLABS_CREATOR_PLAN=1 + ELEVENLABS_API_KEY to enable."
            ),
        }
    if file is None:
        return {
            "ok": False,
            "engine": "elevenlabs",
            "hint": "Upload a 30-60s audio sample (clean speech, single speaker).",
        }
    placeholder = f"clone_{int(time.time())}"
    return {
        "ok": True,
        "engine": "elevenlabs",
        "voice_id": placeholder,
        "name": name,
        "stub": True,
        "hint": "Stubbed — wire to /v1/voices/add when ready.",
    }
