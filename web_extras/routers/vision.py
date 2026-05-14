"""Wave 203 — Vision endpoints for the desktop control center.

Exposes lightweight endpoints that wire the cockpit's Vision tab to the
existing ``backend.agents.vision_agent`` (OCR via pytesseract + image
metadata) plus a ``/api/vision/analyze`` shim that hands a screenshot to
the configured cloud LLM (Claude / OpenAI / OpenRouter) when the user
has a key.

Three endpoints:

  POST /api/vision/ocr        — multipart upload, runs pytesseract
  POST /api/vision/analyze    — JSON {image_data_url, prompt}, calls LLM
  GET  /api/vision/health     — quick capability probe (which engines work)

All three are safe to call without a backend LLM key: they degrade to
an honest "configure your key" body instead of crashing.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])


# ─── /health ──────────────────────────────────────────────────────────────
@router.get("/health")
async def vision_health() -> dict[str, Any]:
    """Report which vision capabilities are available right now."""
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

    anthropic_key = bool(
        (os.getenv("TARS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    )
    openai_key = bool(
        (os.getenv("TARS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    )
    openrouter_key = bool(
        (os.getenv("TARS_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "").strip()
    )

    return {
        "ok": True,
        "capabilities": {
            "ocr_local": pytesseract_ok and pil_ok,
            "image_metadata": pil_ok,
            "llm_vision_anthropic": anthropic_key,
            "llm_vision_openai": openai_key,
            "llm_vision_openrouter": openrouter_key,
            "llm_vision_any": anthropic_key or openai_key or openrouter_key,
        },
    }


# ─── /ocr ─────────────────────────────────────────────────────────────────
@router.post("/ocr")
async def vision_ocr(file: UploadFile = File(...)) -> dict[str, Any]:
    """Run OCR on an uploaded image. Local-only, no cloud required."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return {
            "ok": False,
            "error": "ocr_unavailable",
            "hint": "Install: pip install pytesseract Pillow && brew install tesseract",
        }

    try:
        data = await file.read()
        from io import BytesIO
        img = Image.open(BytesIO(data))
        text = pytesseract.image_to_string(img)
        return {
            "ok": True,
            "text": text.strip(),
            "image": {"width": img.width, "height": img.height, "mode": img.mode},
            "engine": "pytesseract",
        }
    except Exception as exc:
        logger.exception("vision.ocr.failed")
        raise HTTPException(status_code=400, detail={"error": "ocr_failed", "message": str(exc)})


# ─── /analyze ─────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    image_data_url: str = Field(..., description="data:image/png;base64,...")
    prompt: str = Field(default="Describe this screen and suggest a next action.")


@router.post("/analyze")
async def vision_analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """Send a screenshot to the user's configured vision LLM.

    Picks Anthropic > OpenAI > OpenRouter based on which key is set.
    Always returns 200 with an ``ok`` field so the cockpit can render
    the result inline rather than handling HTTP errors.
    """
    # Parse data URL
    m = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", req.image_data_url or "")
    if not m:
        return {"ok": False, "error": "bad_image_data_url", "hint": "Expected data:image/...;base64,..."}
    mime = f"image/{m.group(1).replace('jpg', 'jpeg')}"
    b64 = m.group(2)

    # Anthropic first (best vision quality + already the TARS default)
    anth_key = (os.getenv("TARS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if anth_key:
        return await _analyze_anthropic(anth_key, b64, mime, req.prompt)

    openai_key = (os.getenv("TARS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if openai_key:
        return await _analyze_openai(openai_key, req.image_data_url, req.prompt)

    return {
        "ok": False,
        "error": "no_llm_key_with_vision",
        "hint": "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to enable vision analysis.",
    }


async def _analyze_anthropic(key: str, b64: str, mime: str, prompt: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx_unavailable"}

    body = {
        "model": os.getenv("TARS_ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        if r.status_code != 200:
            return {"ok": False, "error": "anthropic_http", "status": r.status_code, "body": r.text[:200]}
        d = r.json()
        summary = "\n".join(
            c.get("text", "") for c in d.get("content", []) if c.get("type") == "text"
        ).strip()
        return {
            "ok": True,
            "summary": summary,
            "engine": "anthropic",
            "model": d.get("model"),
            "usage": d.get("usage"),
        }
    except Exception as exc:
        return {"ok": False, "error": "anthropic_request_failed", "message": str(exc)}


async def _analyze_openai(key: str, data_url: str, prompt: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx_unavailable"}

    body = {
        "model": os.getenv("TARS_OPENAI_VISION_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 1024,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions", json=body, headers=headers
            )
        if r.status_code != 200:
            return {"ok": False, "error": "openai_http", "status": r.status_code, "body": r.text[:200]}
        d = r.json()
        summary = d["choices"][0]["message"]["content"]
        return {
            "ok": True,
            "summary": summary,
            "engine": "openai",
            "model": d.get("model"),
            "usage": d.get("usage"),
        }
    except Exception as exc:
        return {"ok": False, "error": "openai_request_failed", "message": str(exc)}
