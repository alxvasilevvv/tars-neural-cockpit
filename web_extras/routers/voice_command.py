"""W220 — Voice command dispatcher for the full-screen cockpit.

The cockpit speaks to TARS via Web SpeechRecognition. Each final
transcript hits this router. We:

  1. regex-match against a small set of "system" intents
     (run_doctor, open_tab:agents, show_today, reload). These map to
     client-side actions executed by the cockpit (Tauri webview).
  2. if no regex matches, ask the configured LLM (Anthropic >
     OpenAI > OpenRouter) for a short reply in the same language.

Endpoint:
  POST /api/voice/command   body: {transcript: str, lang?: str}
  → {ok: bool, reply: str, action: str|None, action_payload: any|None}

Designed to be a thin shim. Heavy intent routing belongs in
``backend.agents.persona_router`` once it's available — this is the
launch-day stopgap that gets the voice cockpit working end-to-end.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ─── Regex intent table ───────────────────────────────────────────────
# Keep these simple and explicit. Russian + English. Each pattern is
# searched (not matched) so it works on partial sentences too.
INTENT_PATTERNS: list[tuple[str, str, Any]] = [
    # (regex, action, action_payload)
    (r"(доктор|doctor|здоровье|health(?:\s*check)?)", "run_doctor", None),
    (r"(агенты|агентов|agents|агентами)", "open_tab:agents", None),
    (r"(сегодня|today|briefing|брифинг|утренн)", "show_today", None),
    (r"(перезагрузи|reload|обнови интерфейс|refresh ui)", "reload", None),
]


REPLY_FOR_ACTION = {
    "run_doctor": {
        "ru-RU": "Запускаю полную диагностику. Открываю доктор.",
        "en-US": "Running the full health check.",
    },
    "open_tab:agents": {
        "ru-RU": "Открываю агентов.",
        "en-US": "Opening the agents panel.",
    },
    "show_today": {
        "ru-RU": "Показываю сегодняшний брифинг.",
        "en-US": "Here is today's briefing.",
    },
    "reload": {
        "ru-RU": "Перезагружаю интерфейс.",
        "en-US": "Reloading the cockpit.",
    },
}


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=4000)
    lang: str = Field(default="ru-RU", max_length=12)


def _short_reply(action: str, lang: str) -> str:
    table = REPLY_FOR_ACTION.get(action) or {}
    if lang.startswith("ru"):
        return table.get("ru-RU") or table.get("en-US") or "Ок."
    return table.get("en-US") or table.get("ru-RU") or "Ok."


def _match_intent(transcript: str) -> tuple[str | None, Any]:
    t = transcript.lower()
    for pattern, action, payload in INTENT_PATTERNS:
        if re.search(pattern, t, flags=re.IGNORECASE):
            return action, payload
    return None, None


# ─── LLM fallback (thin client; mirrors web_extras/routers/vision.py) ─


async def _llm_fallback(transcript: str, lang: str) -> str:
    """Call the configured cloud LLM. Returns ``""`` on failure so the
    router can supply a graceful fallback reply.

    Order of preference: Anthropic → OpenAI → OpenRouter. Picks
    whichever has a key set. Each branch can be monkey-patched in tests
    by replacing this function on the module.
    """
    sys_prompt = (
        "You are TARS, a local-first AI assistant. Reply in <= 2 short "
        "sentences in the same language as the user. If the user asks "
        "you to do something on the computer that you can't do, say so "
        "politely."
    )

    anth_key = (os.getenv("TARS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    openai_key = (os.getenv("TARS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    openrouter_key = (
        os.getenv("TARS_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""
    ).strip()

    try:
        import httpx
    except ImportError:
        return ""

    if anth_key:
        try:
            body = {
                "model": os.getenv("TARS_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                "max_tokens": 256,
                "system": sys_prompt,
                "messages": [{"role": "user", "content": transcript}],
            }
            headers = {
                "x-api-key": anth_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages", json=body, headers=headers
                )
            if r.status_code == 200:
                d = r.json()
                return "\n".join(
                    c.get("text", "") for c in d.get("content", []) if c.get("type") == "text"
                ).strip()
        except Exception as exc:
            logger.warning("voice.llm.anthropic_failed: %s", exc)

    if openai_key:
        try:
            body = {
                "model": os.getenv("TARS_OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": transcript},
                ],
                "max_tokens": 256,
            }
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions", json=body, headers=headers
                )
            if r.status_code == 200:
                d = r.json()
                return (d.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except Exception as exc:
            logger.warning("voice.llm.openai_failed: %s", exc)

    if openrouter_key:
        try:
            body = {
                "model": os.getenv("TARS_OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": transcript},
                ],
                "max_tokens": 256,
            }
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions", json=body, headers=headers
                )
            if r.status_code == 200:
                d = r.json()
                return (d.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except Exception as exc:
            logger.warning("voice.llm.openrouter_failed: %s", exc)

    return ""


@router.post("/command")
async def voice_command(req: VoiceCommandRequest) -> dict[str, Any]:
    """Dispatch a transcript to an action or an LLM-generated reply."""
    transcript = (req.transcript or "").strip()
    lang = (req.lang or "ru-RU").strip() or "ru-RU"

    action, payload = _match_intent(transcript)
    if action:
        return {
            "ok": True,
            "reply": _short_reply(action, lang),
            "action": action,
            "action_payload": payload,
            "engine": "regex",
        }

    # No intent matched — ask the LLM.
    reply = await _llm_fallback(transcript, lang)
    if not reply:
        reply = (
            "Извини, сейчас я не могу ответить — нужен ключ LLM в .env."
            if lang.startswith("ru")
            else "Sorry, I cannot reply right now — add an LLM key to .env."
        )
        return {
            "ok": True,
            "reply": reply,
            "action": None,
            "action_payload": None,
            "engine": "fallback",
        }

    return {
        "ok": True,
        "reply": reply,
        "action": None,
        "action_payload": None,
        "engine": "llm",
    }
