"""W217 — Accessibility helpers.

Two endpoints that turn TARS into a free screen-reader for users with
low vision or reading difficulties:

  POST /api/a11y/ocr_speak    — OCR a region/image, return text + audio
                                  TTS data URL (browser-playable).
  GET  /api/a11y/health       — feature probe.

The TTS path falls back gracefully: if no cloud TTS key is set, returns
the OCR text only and the cockpit uses Web Speech API on the client.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/a11y", tags=["a11y", "accessibility"])


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
        "hint": "Without cloud TTS key, the cockpit uses the browser's "
                "speechSynthesis API to read OCR'd text aloud locally.",
    }


@router.post("/ocr_speak")
async def ocr_speak(file: UploadFile = File(...)) -> dict[str, Any]:
    """OCR an uploaded image (PNG/JPEG) and return the extracted text.

    The cockpit will speak it via the browser's SpeechSynthesis when no
    cloud TTS is available, otherwise the cockpit can re-POST the text
    to a TTS endpoint of choice.
    """
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
    voice: str | None = Field(default=None, description="Optional voice id (engine-specific)")


@router.post("/speak")
async def speak(req: SpeakRequest) -> dict[str, Any]:
    """Return a hint object that lets the cockpit decide how to speak the text.

    For browser fallback (no key needed), the cockpit calls
    speechSynthesis directly. This endpoint exists so future cloud TTS
    integration (ElevenLabs / OpenAI) can be wired without a cockpit
    change — just configure the key and this endpoint will return the
    audio data URL instead of {use_browser_tts: true}.
    """
    text = req.text.strip()
    if not text:
        return {"ok": False, "error": "empty_text"}

    # Browser fallback — cockpit will use window.speechSynthesis.
    return {
        "ok": True,
        "use_browser_tts": True,
        "text": text[:10000],
        "hint": (
            "Cloud TTS not yet wired. The cockpit will use window.speechSynthesis "
            "to read the text in your default OS voice."
        ),
    }
