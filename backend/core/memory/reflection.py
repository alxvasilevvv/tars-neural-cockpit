"""Weekly memory reflection (Wave 73 Feature 3).

Closes Task #72 which closed in the task list with no shipped code.
Walks the operator's chat history over the last N days, asks an LLM
voice to summarise themes / blockers / wins, and writes the result
into the ``_global`` memory pack under ``weekly_reflection_<isoweek>``
so it shows up in the cockpit's memory UI.

Public surface:

- :func:`run_reflection` — async, returns ``{ok, key, summary,
  message_count, ...}``. Idempotent on the ISO week key (re-running
  the same week overwrites the row).
- :func:`should_run_now` — boolean clock helper used by the
  background poll: returns True when "Sunday 18:00 local" has passed
  for the current ISO week and no row exists yet.
- :func:`reflection_loop` — the optional background task itself,
  enabled with ``TARS_REFLECTION_AUTO=1``. Defaults off.

Design notes:

- LLM call goes through the same urllib path as
  :mod:`backend.core.council.llm`. We don't reuse the council
  voice directly because the council expects a strict JSON
  proposal schema that doesn't fit a long-form summary. Instead
  we hit Anthropic / OpenAI completions with our own prompt and
  ask for JSON ``{summary, themes[], blockers[], wins[],
  next_focus}``.
- When no LLM key is configured the function falls back to a
  deterministic keyword-frequency summary so the cockpit never
  shows an empty row.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.memory import MemoryEntry, get_memory_store
from backend.core.vault import get_secret


log = logging.getLogger("tars.memory.reflection")


_PACK_SLUG = "_global"
_KIND = "reflection"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_TIMEOUT_S = 30.0
_MAX_THREADS = 30
_MAX_MSGS_PER_THREAD = 60
_MAX_PROMPT_CHARS = 16000


_SYSTEM_PROMPT = (
    "You are TARS's memory reflection module. The operator just gave "
    "you the last 7 days of their chat history. Read it like a journal "
    "and produce a useful weekly retrospective. Be specific (cite the "
    "actual topics they raised), short (no fluff), and practical.\n\n"
    "Reply with a JSON object only, no markdown:\n"
    "{\n"
    '  "summary": "<2-4 sentence prose summary>",\n'
    '  "themes": ["<short tag>", ...],   // up to 8\n'
    '  "blockers": ["<thing in the way>", ...],  // up to 5\n'
    '  "wins": ["<concrete progress>", ...],     // up to 5\n'
    '  "next_focus": "<one sentence on what to chase next week>"\n'
    "}\n"
)


def iso_week_key(now: float | None = None) -> str:
    ts = now if now is not None else time.time()
    iso = _dt.datetime.utcfromtimestamp(ts).isocalendar()
    # iso is (year, week, weekday); cast the first two to int because
    # `datetime.IsoCalendarDate` and the legacy tuple both index .[0/1].
    year = int(iso[0])
    week = int(iso[1])
    return f"weekly_reflection_{year}-W{week:02d}"


def _resolve_anthropic() -> str | None:
    return get_secret("TARS_ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_API_KEY")


def _resolve_openai() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout_s: float) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


async def _llm_summarise(transcript: str) -> dict[str, Any] | None:
    """Try Anthropic, then OpenAI, then None."""

    if not transcript.strip():
        return None

    user_msg = f"Operator's last 7 days:\n\n{transcript[:_MAX_PROMPT_CHARS]}"

    a_key = _resolve_anthropic()
    if a_key:
        body = {
            "model": os.getenv("TARS_ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022",
            "max_tokens": 800,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        }
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": a_key,
        }
        try:
            payload = await asyncio.to_thread(
                _post_json, _ANTHROPIC_URL, body, headers, _DEFAULT_TIMEOUT_S
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("reflection anthropic fail: %s", exc)
        else:
            content = payload.get("content")
            if isinstance(content, list) and content:
                text = "".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                parsed = _safe_json(text)
                if parsed:
                    return parsed

    o_key = _resolve_openai()
    if o_key:
        body = {
            "model": os.getenv("TARS_OPENAI_MODEL") or "gpt-4o-mini",
            "max_tokens": 800,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {o_key}",
        }
        try:
            payload = await asyncio.to_thread(
                _post_json, _OPENAI_URL, body, headers, _DEFAULT_TIMEOUT_S
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("reflection openai fail: %s", exc)
        else:
            choices = payload.get("choices") or []
            if choices:
                msg = (choices[0] or {}).get("message") or {}
                text = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(text, str):
                    parsed = _safe_json(text)
                    if parsed:
                        return parsed
    return None


def _safe_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        out = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{3,}")
_STOPWORDS = {
    "this", "that", "with", "from", "have", "your", "their", "what", "when",
    "where", "they", "them", "would", "could", "should", "about", "into",
    "just", "like", "want", "need", "make", "made", "more", "than", "then",
    "also", "been", "were", "very", "much", "still", "only", "even", "there",
    "here", "some", "other", "thing", "things", "okay", "well", "really",
    "going", "didn't", "don't", "let's", "think", "know", "thanks", "tars",
    "operator", "user", "assistant", "system", "message", "text",
}


def _fallback_summary(transcript: str, message_count: int) -> dict[str, Any]:
    """Deterministic keyword-roll when no LLM is reachable."""

    tokens = [
        t.lower() for t in _WORD_RE.findall(transcript)
        if t.lower() not in _STOPWORDS
    ]
    counts = Counter(tokens).most_common(15)
    themes = [w for w, _ in counts[:8]]
    return {
        "summary": (
            f"Reflection over {message_count} message(s) from the past 7 days. "
            f"No LLM key configured — falling back to keyword roll-up. "
            f"Top topics: {', '.join(themes[:5]) or 'none'}."
        ),
        "themes": themes,
        "blockers": [],
        "wins": [],
        "next_focus": "Configure ANTHROPIC_API_KEY or OPENAI_API_KEY for richer reflections.",
        "_provider": "fallback",
    }


async def _gather_transcript(
    *, chat: ChatStore, days: int
) -> tuple[str, int]:
    """Concatenate operator + assistant messages from the last N days."""

    if not chat.enabled:
        return "", 0
    cutoff = time.time() - max(1, days) * 86400.0
    threads = await chat.list_threads(limit=_MAX_THREADS, archived=None)
    lines: list[str] = []
    total = 0
    for thread in threads:
        msgs = await chat.list_messages(thread.id, limit=_MAX_MSGS_PER_THREAD)
        for m in msgs:
            if m.created_at < cutoff:
                continue
            if m.role not in ("operator", "tars"):
                continue
            content = (m.content or "").strip()
            if not content:
                continue
            speaker = "Operator" if m.role == "operator" else "TARS"
            lines.append(f"[{speaker}] {content[:600]}")
            total += 1
            if total >= 600:  # hard cap so we don't blow prompt budget
                break
        if total >= 600:
            break
    return "\n".join(lines), total


async def run_reflection(
    *,
    days: int = 7,
    chat: ChatStore | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Generate this week's reflection and persist it.

    Returns ``{ok, key, summary, themes, blockers, wins, next_focus,
    message_count, provider, skipped?}``.

    When ``force`` is False and a row already exists for this ISO
    week, the function is a no-op (returns ``skipped=true``).
    """

    chat = chat or get_chat_store()
    store = get_memory_store()
    if not store.enabled:
        return {"ok": False, "reason": "memory_store_disabled"}

    key = iso_week_key()
    if not force:
        existing = await store.get(pack_slug=_PACK_SLUG, key=key)
        if existing is not None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_present",
                "key": key,
                "entry": existing.to_dict(),
            }

    transcript, msg_count = await _gather_transcript(chat=chat, days=days)
    if msg_count == 0:
        result = {
            "summary": "No operator activity in the last 7 days.",
            "themes": [],
            "blockers": [],
            "wins": [],
            "next_focus": "Pick up something small to get the loop moving.",
            "_provider": "empty",
        }
    else:
        parsed = await _llm_summarise(transcript)
        if parsed is None:
            result = _fallback_summary(transcript, msg_count)
        else:
            parsed.setdefault("_provider", "llm")
            result = parsed

    payload = {
        "summary": result.get("summary", ""),
        "themes": list(result.get("themes") or [])[:8],
        "blockers": list(result.get("blockers") or [])[:5],
        "wins": list(result.get("wins") or [])[:5],
        "next_focus": result.get("next_focus", ""),
        "provider": result.get("_provider") or "llm",
        "message_count": msg_count,
        "days": days,
        "iso_week_key": key,
        "generated_at": time.time(),
    }
    entry = await store.upsert(
        pack_slug=_PACK_SLUG,
        key=key,
        value=payload,
        kind=_KIND,
        source="memory.reflection",
        metadata={"days": days, "message_count": msg_count},
    )
    return {
        "ok": True,
        "key": key,
        "message_count": msg_count,
        "provider": payload["provider"],
        "entry": entry.to_dict() if isinstance(entry, MemoryEntry) else None,
        **{k: v for k, v in payload.items() if k != "iso_week_key"},
    }


def _is_auto_enabled() -> bool:
    raw = (os.getenv("TARS_REFLECTION_AUTO") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _poll_interval_s() -> float:
    raw = os.getenv("TARS_REFLECTION_INTERVAL_S")
    if raw is None:
        return 1800.0  # 30 min
    try:
        return max(60.0, float(raw))
    except ValueError:
        return 1800.0


def should_run_now(now: float | None = None) -> bool:
    """True iff ``Sunday 18:00 local`` has passed for this ISO week."""

    ts = now if now is not None else time.time()
    local = _dt.datetime.fromtimestamp(ts)
    # Monday=0 ... Sunday=6
    if local.weekday() != 6:
        return False
    return local.hour >= 18


async def reflection_loop() -> None:
    """Background poll. OFF by default (TARS_REFLECTION_AUTO=1 to enable).

    Same safety contract as other lifespan loops — never propagates,
    never crashes the host. Skips if a row is already present for
    the current ISO week.
    """

    if not _is_auto_enabled():
        return
    interval = _poll_interval_s()
    log.info(
        "memory reflection loop active: interval_s=%.1f", interval
    )
    while True:
        try:
            await asyncio.sleep(interval)
            if not should_run_now():
                continue
            store = get_memory_store()
            if not store.enabled:
                continue
            key = iso_week_key()
            existing = await store.get(pack_slug=_PACK_SLUG, key=key)
            if existing is not None:
                continue
            out = await run_reflection()
            log.info(
                "memory reflection auto-tick: ok=%s key=%s msgs=%s",
                out.get("ok"), out.get("key"), out.get("message_count"),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("reflection loop tick failed: %s", exc)


__all__ = [
    "iso_week_key",
    "reflection_loop",
    "run_reflection",
    "should_run_now",
]
