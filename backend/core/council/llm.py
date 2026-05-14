"""LLM-backed council voice.

Stdlib-only HTTP via ``urllib`` wrapped in ``asyncio.to_thread``.
Anthropic by default; OpenAI fallback. When no key is configured the
voice is *unavailable* (its proposal carries ``stance='unavailable'``
and ``confidence=0.0``); the orchestrator filters those out before
counting.

Why we don't introduce httpx / anthropic-py: the entire backend stays
stdlib. The bridge is dead-simple and survives offline tests.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

from backend.core.privacy import check_can_call
from backend.core.vault import get_secret

from .voices import Proposal, Voice


_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_TIMEOUT_S = 12.0
_DEFAULT_MAX_TOKENS = 384

_VALID_STANCES = {
    # market
    "risk_on", "risk_off", "neutral", "uncertain",
    # kpi
    "expanding", "contracting", "steady",
}


_SYSTEM_PROMPT = (
    "You are one voice on the TARS council — a small panel that interprets "
    "operator-grade signals (markets, KPIs, networks) and emits a single "
    "structured proposal.\n\n"
    "Reply with a JSON object only — no prose, no markdown fences. The "
    "schema is:\n"
    "{\n"
    '  "stance": "<one of: risk_on, risk_off, neutral, uncertain, expanding, contracting, steady>",\n'
    '  "summary": "<one-line ALL-CAPS-prefixed sentence, e.g. RISK_OFF — basket -1.2% / 24h>",\n'
    '  "actions_recommended": ["<snake_case_action>", ...],\n'
    '  "confidence": <float 0..1>,\n'
    '  "rationale": "<1-2 sentences>"\n'
    "}\n\n"
    "Rules:\n"
    "- Use the topic field of the user payload to pick stances from the "
    "  right set (market topic → risk_*, neutral, uncertain; kpi topic → "
    "  expanding, contracting, steady; otherwise → uncertain).\n"
    "- Keep the rationale grounded in the supplied numbers; do not invent.\n"
    "- Never call yourself the 'arbiter' — you are one voice."
)


def _resolve_anthropic_key() -> str | None:
    return get_secret("TARS_ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_API_KEY")


def _resolve_openai_key() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def _post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout_s: float,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8") or "{}")


def _safe_parse_proposal(raw_text: str) -> dict[str, Any] | None:
    """Parse a JSON proposal from the model response.

    Tolerates a fenced block or surrounding prose.
    """

    if not raw_text:
        return None
    text = raw_text.strip()
    # Strip a single fenced block if present.
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    # Find the first JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        out = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(out, dict):
        return None
    return out


def _coerce_actions(actions: Any) -> tuple[str, ...]:
    if not isinstance(actions, list):
        return ()
    out = []
    for a in actions:
        if isinstance(a, str):
            tok = a.strip()
            if tok:
                out.append(tok)
    return tuple(out[:5])


def _normalise_stance(stance: Any, topic: str) -> str:
    if not isinstance(stance, str):
        return "uncertain"
    s = stance.strip().lower().replace("-", "_")
    if s not in _VALID_STANCES:
        return "uncertain"
    market_set = {"risk_on", "risk_off", "neutral", "uncertain"}
    kpi_set = {"expanding", "contracting", "steady"}
    if topic == "market" and s not in market_set:
        return "uncertain"
    if topic == "kpi" and s not in kpi_set:
        return "steady"
    return s


def _unavailable_proposal(model: str, *, reason: str, latency_ms: float = 0.0) -> Proposal:
    return Proposal(
        model=model,
        stance="unavailable",
        summary=f"UNAVAILABLE — {reason}.",
        actions_recommended=(),
        confidence=0.0,
        rationale=reason,
        latency_ms=latency_ms,
        tokens_in=0,
        tokens_out=0,
    )


class AnthropicVoice(Voice):
    """Anthropic-backed council voice.

    Configurable via:

    - ``TARS_ANTHROPIC_API_KEY`` (or ``ANTHROPIC_API_KEY``)
    - ``TARS_ANTHROPIC_MODEL`` env var (default ``claude-3-5-sonnet-20241022``)

    When the key is missing the voice is unavailable.
    """

    model = "tars-anthropic"

    def __init__(
        self,
        *,
        anthropic_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        import os
        self.anthropic_model = (
            anthropic_model
            or os.getenv("TARS_ANTHROPIC_MODEL")
            or "claude-3-5-sonnet-20241022"
        )
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.model = f"anthropic/{self.anthropic_model}"

    def _build_user_message(self, prompt: str, context: Mapping[str, Any]) -> str:
        return json.dumps(
            {"prompt": prompt, "context": dict(context)},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    async def propose(
        self, prompt: str, context: Mapping[str, Any]
    ) -> Proposal:
        key = _resolve_anthropic_key()
        if not key:
            return _unavailable_proposal(self.model, reason="api_key_missing")

        # W244 privacy gate -- privacy / strict modes block cloud LLMs.
        allowed, reason = check_can_call("anthropic", source="council.llm")
        if not allowed:
            return _unavailable_proposal(
                self.model, reason=f"privacy_block:{reason}"
            )

        topic = str(context.get("topic") or "").lower()
        body = {
            "model": self.anthropic_model,
            "max_tokens": self.max_tokens,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": self._build_user_message(prompt, context),
                }
            ],
        }
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": key,
        }

        started = time.perf_counter()
        try:
            payload = await asyncio.to_thread(
                _post_json, _ANTHROPIC_URL, body, headers, self.timeout_s
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return _unavailable_proposal(
                self.model,
                reason=f"transport_error: {exc}",
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        # Anthropic returns ``content``: list of {type, text}. Concatenate text blocks.
        content = payload.get("content")
        if not isinstance(content, list) or not content:
            return _unavailable_proposal(
                self.model, reason="empty_response", latency_ms=latency_ms
            )
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    text_parts.append(t)
        text = "\n".join(text_parts)
        parsed = _safe_parse_proposal(text)
        if parsed is None:
            return _unavailable_proposal(
                self.model, reason="invalid_json_response", latency_ms=latency_ms
            )

        stance = _normalise_stance(parsed.get("stance"), topic)
        confidence_raw = parsed.get("confidence")
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)

        return Proposal(
            model=self.model,
            stance=stance,
            summary=str(parsed.get("summary") or stance.upper()),
            actions_recommended=_coerce_actions(parsed.get("actions_recommended")),
            confidence=confidence,
            rationale=str(parsed.get("rationale") or ""),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


class OpenAIVoice(Voice):
    """OpenAI-backed council voice (gpt-4o-mini by default)."""

    model = "tars-openai"

    def __init__(
        self,
        *,
        openai_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        import os
        self.openai_model = (
            openai_model or os.getenv("TARS_OPENAI_MODEL") or "gpt-4o-mini"
        )
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.model = f"openai/{self.openai_model}"

    async def propose(
        self, prompt: str, context: Mapping[str, Any]
    ) -> Proposal:
        key = _resolve_openai_key()
        if not key:
            return _unavailable_proposal(self.model, reason="api_key_missing")

        # W244 privacy gate -- privacy / strict modes block cloud LLMs.
        allowed, reason = check_can_call("openai", source="council.llm")
        if not allowed:
            return _unavailable_proposal(
                self.model, reason=f"privacy_block:{reason}"
            )

        topic = str(context.get("topic") or "").lower()
        body = {
            "model": self.openai_model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"prompt": prompt, "context": dict(context)},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        }

        started = time.perf_counter()
        try:
            payload = await asyncio.to_thread(
                _post_json, _OPENAI_URL, body, headers, self.timeout_s
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return _unavailable_proposal(
                self.model,
                reason=f"transport_error: {exc}",
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return _unavailable_proposal(
                self.model, reason="empty_response", latency_ms=latency_ms
            )
        msg = (choices[0] or {}).get("message") or {}
        text = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(text, str):
            return _unavailable_proposal(
                self.model, reason="empty_response", latency_ms=latency_ms
            )
        parsed = _safe_parse_proposal(text)
        if parsed is None:
            return _unavailable_proposal(
                self.model, reason="invalid_json_response", latency_ms=latency_ms
            )

        stance = _normalise_stance(parsed.get("stance"), topic)
        try:
            confidence = float(parsed.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        return Proposal(
            model=self.model,
            stance=stance,
            summary=str(parsed.get("summary") or stance.upper()),
            actions_recommended=_coerce_actions(parsed.get("actions_recommended")),
            confidence=confidence,
            rationale=str(parsed.get("rationale") or ""),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


def detect_llm_voice() -> Voice | None:
    """Return the first LLM voice whose key is configured, else None."""

    if _resolve_anthropic_key():
        return AnthropicVoice()
    if _resolve_openai_key():
        return OpenAIVoice()
    return None
