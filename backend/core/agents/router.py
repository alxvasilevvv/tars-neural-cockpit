"""Smart Agent Router — LLM-based intent classification (Wave 73 F5).

Closes Task #116 (closed in the task list with no shipped code beyond
the regex-based ``backend/core/speech/intents.py``). This module adds
an *opt-in* LLM classifier that picks the best domain pack for a
free-form operator request.

Public surface:

- :func:`route_intent` — async, returns
  ``{pack, confidence, reason, source}`` where ``source`` is one of
  ``llm | regex | cache | disabled``. Falls back to the regex
  parser (``backend.core.speech.intents``) on any LLM failure.
- :func:`is_enabled` — reads ``TARS_SMART_ROUTER`` env. OFF by
  default so the regex remains the primary route until operators
  flip it on.

Caching: results are memoised by SHA-1(text) for 5 minutes in a
process-local dict. That's enough to dampen the cost when the
cockpit re-routes during a streaming reply or an autopilot loop
fires the same prompt twice.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from backend.core.speech.intents import parse_intent
from backend.core.vault import get_secret


log = logging.getLogger("tars.agents.router")


_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_TIMEOUT_S = 8.0
_CACHE_TTL_S = 300.0  # 5 min

# hash -> (expires_at, result_dict)
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


_SYSTEM_PROMPT = (
    "You are TARS's intent classifier. Given an operator request and "
    "a list of available domain packs, pick the single best pack for "
    "this request. Be conservative: when nothing fits clearly, return "
    "an empty pack and a low confidence so the regex fallback can "
    "take over.\n\n"
    "Reply with a JSON object only — no prose, no markdown:\n"
    "{\n"
    '  "pack": "<one of the supplied slugs, or empty string>",\n'
    '  "confidence": <float 0..1>,\n'
    '  "reason": "<one short sentence>"\n'
    "}\n"
)


def _cache_get(key: str) -> dict[str, Any] | None:
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if not hit:
            return None
        expires, value = hit
        if expires < now:
            _CACHE.pop(key, None)
            return None
        return dict(value)


def _cache_put(key: str, value: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + _CACHE_TTL_S, dict(value))


def _hash(text: str, packs: list[str]) -> str:
    h = hashlib.sha1()
    h.update(text.encode("utf-8"))
    h.update(b"|")
    h.update(",".join(sorted(packs)).encode("utf-8"))
    return h.hexdigest()


def is_enabled() -> bool:
    raw = (os.getenv("TARS_SMART_ROUTER") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_anthropic_key() -> str | None:
    return get_secret("TARS_ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_API_KEY")


def _resolve_openai_key() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout_s: float) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _safe_parse(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
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


async def _llm_classify(
    text: str, packs: list[str]
) -> dict[str, Any] | None:
    user_msg = json.dumps(
        {"text": text, "available_packs": packs},
        ensure_ascii=False,
        separators=(",", ":"),
    )

    a_key = _resolve_anthropic_key()
    if a_key:
        body = {
            "model": (
                os.getenv("TARS_ROUTER_MODEL")
                or os.getenv("TARS_ANTHROPIC_HAIKU_MODEL")
                or "claude-3-5-haiku-20241022"
            ),
            "max_tokens": 200,
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
            log.warning("router anthropic fail: %s", exc)
        else:
            content = payload.get("content")
            if isinstance(content, list):
                tx = "".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                parsed = _safe_parse(tx)
                if parsed:
                    return parsed

    o_key = _resolve_openai_key()
    if o_key:
        body = {
            "model": (
                os.getenv("TARS_ROUTER_MODEL")
                or os.getenv("TARS_OPENAI_FAST_MODEL")
                or "gpt-4o-mini"
            ),
            "max_tokens": 200,
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
            log.warning("router openai fail: %s", exc)
        else:
            choices = payload.get("choices") or []
            if choices:
                msg = (choices[0] or {}).get("message") or {}
                tx = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(tx, str):
                    parsed = _safe_parse(tx)
                    if parsed:
                        return parsed
    return None


def _regex_route(text: str, packs: list[str]) -> dict[str, Any]:
    """Use the deterministic intent parser as a fallback / disabled path.

    The regex parser only knows ``run_action`` / ``run_playbook`` /
    ``jump`` / ``search`` etc — when it matches one of those, the
    target is shaped ``<pack>.<action>`` so we can pluck the prefix.
    Otherwise we return a low-confidence "unknown" routing decision
    for the caller to fall through to a default pack.
    """

    intent = parse_intent(text)
    if intent.kind in ("run_action", "run_playbook") and intent.target:
        prefix = intent.target.split(".", 1)[0]
        if prefix in packs:
            return {
                "pack": prefix,
                "confidence": 0.85,
                "reason": f"regex matched {intent.kind}: {intent.target}",
                "source": "regex",
            }
    if intent.kind == "jump" and intent.target:
        prefix = intent.target.split(".", 1)[0] if "." in intent.target else intent.target
        if prefix in packs:
            return {
                "pack": prefix,
                "confidence": 0.7,
                "reason": f"regex matched jump: {intent.target}",
                "source": "regex",
            }
    return {
        "pack": "",
        "confidence": 0.1,
        "reason": "regex no match",
        "source": "regex",
    }


async def route_intent(
    user_text: str, available_packs: list[str]
) -> dict[str, Any]:
    """Classify ``user_text`` into one of ``available_packs``.

    Returns ``{pack, confidence, reason, source}``. ``source`` is
    ``cache | llm | regex | disabled``; ``pack`` may be empty if
    nothing fit. Caller decides what to do with low-confidence
    answers (typical pattern: route to default pack and ask for
    confirmation).
    """

    text = (user_text or "").strip()
    packs = [p for p in (available_packs or []) if isinstance(p, str) and p]
    if not text or not packs:
        return {
            "pack": "",
            "confidence": 0.0,
            "reason": "empty_input",
            "source": "disabled",
        }

    if not is_enabled():
        out = _regex_route(text, packs)
        out["source"] = "disabled"
        return out

    cache_key = _hash(text, packs)
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["source"] = "cache"
        return cached

    parsed = await _llm_classify(text, packs)
    if parsed is None:
        # LLM unavailable — fall back to regex but flag it.
        out = _regex_route(text, packs)
        out["source"] = "regex_fallback"
        return out

    pack = str(parsed.get("pack") or "").strip()
    if pack and pack not in packs:
        # LLM hallucinated a pack — drop it.
        log.warning("router LLM returned unknown pack: %s", pack)
        pack = ""
    try:
        confidence = float(parsed.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    reason = str(parsed.get("reason") or "")[:280]
    out = {
        "pack": pack,
        "confidence": round(confidence, 3),
        "reason": reason,
        "source": "llm",
    }
    _cache_put(cache_key, out)
    return out


__all__ = ["is_enabled", "route_intent"]
