"""Chat-grade voices: free-form text streaming.

The council :class:`backend.core.council.voices.Voice` returns a single
structured ``Proposal``. Chat instead needs **streaming free-form text**
plus optional tool-calls.

Three flavours ship in L1:

- :class:`LocalChatVoice` — deterministic, pulls a templated reply from
  the conversation context. Useful for offline dev + tests; the
  orchestrator falls back to it whenever no LLM key is configured.
- :class:`AnthropicChatVoice` — wraps Anthropic Messages SSE streaming
  via stdlib ``urllib`` + ``asyncio.to_thread`` (no httpx).
- :class:`OpenAIChatVoice` — same shape, OpenAI Chat Completions SSE.

LLM voices emit tool-call requests inline by writing a sentinel
``<tool name="<slug>.<action_id>">{...args...}</tool>`` block. The
orchestrator detects this and routes it through the existing policy
gate. The sentinel is part of the **system prompt contract** in
``_TOOL_USE_PROMPT`` below — the same string is shipped to every
LLM voice so the protocol stays stable.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Literal, Mapping, Sequence

from backend.core.vault import get_secret

from .models import AttachmentRef, Message, Thread

ChunkKind = Literal["text", "tool_call", "usage", "done", "error"]


@dataclass(frozen=True)
class ChatChunk:
    """A single streamed chunk from a chat voice.

    ``text`` carries token deltas (already tool-call-stripped for LLM
    voices). ``tool_call`` is a fully-parsed proposal; the orchestrator
    decides what to do with it.
    """

    kind: ChunkKind
    text: str | None = None
    tool_call: Mapping[str, Any] | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    latency_ms: float = 0.0


_TOOL_USE_PROMPT = (
    "You are TARS, a local-first operator-grade neural cockpit. Speak"
    " concisely and ground every claim in the operator's data. When a"
    " domain action is needed, emit a single fenced block:\n"
    '\n<tool name="<slug>.<action_id>">{ "arg": "..." }</tool>\n\n'
    "Rules for tool calls:\n"
    "- Slugs are: traders, business, mlm, science, plus composites"
    " research_lab and ops_room.\n"
    "- Composite actions are namespaced: <sub>__<id>"
    " (e.g. business__draft_email).\n"
    "- Destructive actions (e.g. business.draft_email,"
    " business.log_deal, traders.place_alert) require operator"
    " confirmation. The cockpit handles that — you just propose.\n"
    "- One tool call per turn. After the tool returns its structured"
    " result, summarise the answer in plain markdown."
)


# Public sentinel regex (also used by tests).
TOOL_BLOCK_RE = re.compile(
    r'<tool\s+name=\"([^\"]+)\"\s*>\s*(\{[\s\S]*?\})\s*</tool>',
    re.MULTILINE,
)


class ChatVoice(ABC):
    """Base class for streaming chat voices."""

    model: str
    # Phase M / P8 — voice declares whether it can natively consume
    # image attachments. The orchestrator + vision_agent use this flag
    # to decide between (a) sending raw image refs through the model
    # call, or (b) folding OCR text into the system prompt instead.
    supports_multimodal: bool = False

    @abstractmethod
    def stream(
        self,
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        attachments: Sequence[AttachmentRef] = (),
        *,
        system_prompt: str | None = None,
    ) -> AsyncIterator[ChatChunk]:  # pragma: no cover - abstract
        ...


# ----------------------------------------------------------------------
# Local deterministic voice (offline / tests).
# ----------------------------------------------------------------------


class LocalChatVoice(ChatVoice):
    """Deterministic chat voice — no API calls.

    Produces a templated, useful response based on the operator's
    last message and any attached files. The point isn't to be
    impressive; it's to be a stable fallback so the chat stack
    never crashes when a key is missing.
    """

    model = "tars-local-chat-v1"

    async def stream(
        self,
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        attachments: Sequence[AttachmentRef] = (),
        *,
        system_prompt: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        started = time.perf_counter()
        text = self._compose(thread, history, operator_text, attachments)
        # Stream sentence-by-sentence so the cockpit feels alive even
        # without an LLM in the loop.
        for chunk in _split_sentences(text):
            yield ChatChunk(kind="text", text=chunk)
            # Tiny artificial pacing so the cockpit's typing animation
            # has time to render. 8ms is below human perception of jank.
            await asyncio.sleep(0.008)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        yield ChatChunk(
            kind="usage",
            tokens_in=_approx_tokens(operator_text + (system_prompt or "")),
            tokens_out=_approx_tokens(text),
            latency_ms=elapsed_ms,
        )
        yield ChatChunk(kind="done", latency_ms=elapsed_ms)

    # -- internals ------------------------------------------------------

    @staticmethod
    def _compose(
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        attachments: Sequence[AttachmentRef],
    ) -> str:
        op = (operator_text or "").strip()
        if not op:
            return "I'm here. What would you like to look at?"

        lower = op.lower()
        # Cheap pattern matches keep the local voice useful without
        # pretending to be a real LLM.
        if any(g in lower for g in ("hello", "hi", "hey", "привет", "здравствуй")):
            return (
                f"Hello — TARS standing by"
                + (f" on the **{thread.pack_slug}** pack" if thread.pack_slug else "")
                + ". Ask anything; tools are policy-gated, costs land in the"
                " ledger, and every reply rolls up under your session."
            )
        if "?" in op:
            return (
                "I read your question. Without an LLM voice configured I"
                " can't answer freely — set `TARS_ANTHROPIC_API_KEY` or"
                " `TARS_OPENAI_API_KEY` (env or macOS Keychain) and I'll"
                " stream a real reply. Meanwhile, the policy gate, the"
                " cost ledger, and every domain action are still live."
            )
        if attachments:
            names = ", ".join(
                a.filename or a.id for a in attachments[:3]
            )
            return (
                f"Got it — I'll keep `{names}` in context. Drop in"
                " `TARS_ANTHROPIC_API_KEY` to let a real voice reason"
                " over them; otherwise I can still run domain actions"
                " against their extracted text."
            )
        # Fallback echo + nudge.
        return (
            "Noted. I'm running in local-only mode — no LLM voice is"
            " configured, so my replies are deterministic placeholders."
            " The full council, policy gate, and cost ledger still"
            " work; configure a vault key to unlock free-form replies."
        )


# ----------------------------------------------------------------------
# Anthropic streaming voice.
# ----------------------------------------------------------------------


_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_MAX_TOKENS = 1024


class AnthropicChatVoice(ChatVoice):
    """Anthropic-backed chat voice using the SSE stream API.

    Configurable via env / vault:

    - ``TARS_ANTHROPIC_API_KEY`` (or ``ANTHROPIC_API_KEY``)
    - ``TARS_ANTHROPIC_MODEL`` (default ``claude-3-5-sonnet-20241022``)
    """

    # Anthropic 3.5 Sonnet (and the 3-family upwards) accept native
    # image content blocks, so the orchestrator can hand image refs
    # straight through. Older models still work fine for text-only
    # turns; the orchestrator falls back to the OCR-text path when
    # this flag is False.
    supports_multimodal = True

    def __init__(
        self,
        *,
        anthropic_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self.anthropic_model = (
            anthropic_model
            or os.getenv("TARS_ANTHROPIC_MODEL")
            or "claude-3-5-sonnet-20241022"
        )
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.model = f"anthropic/{self.anthropic_model}"

    async def stream(
        self,
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        attachments: Sequence[AttachmentRef] = (),
        *,
        system_prompt: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        key = get_secret("TARS_ANTHROPIC_API_KEY") or get_secret(
            "ANTHROPIC_API_KEY"
        )
        if not key:
            yield ChatChunk(
                kind="error",
                error="anthropic_key_missing",
            )
            return

        sys_text = _build_system(thread, system_prompt, attachments)
        body = {
            "model": self.anthropic_model,
            "max_tokens": self.max_tokens,
            "system": sys_text,
            "stream": True,
            "messages": _to_anthropic_messages(history, operator_text),
        }
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": key,
        }

        started = time.perf_counter()
        try:
            async for chunk in self._iter(body, headers):
                yield chunk
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            yield ChatChunk(kind="error", error=f"transport_error: {exc}")
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        yield ChatChunk(kind="done", latency_ms=elapsed_ms)

    async def _iter(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> AsyncIterator[ChatChunk]:
        # Run the blocking urlopen in a thread; pump SSE lines back via
        # an asyncio.Queue so this method stays an async generator.
        queue: asyncio.Queue[ChatChunk | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _worker() -> None:
            usage_in = 0
            usage_out = 0
            try:
                req = urllib.request.Request(
                    _ANTHROPIC_URL,
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    event_name: str | None = None
                    for raw in resp:
                        line = raw.decode("utf-8", errors="replace").rstrip(
                            "\r\n"
                        )
                        if not line:
                            event_name = None
                            continue
                        if line.startswith("event:"):
                            event_name = line[6:].strip()
                            continue
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            payload = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        kind = payload.get("type") or event_name
                        if kind == "content_block_delta":
                            delta = payload.get("delta") or {}
                            text = delta.get("text") or ""
                            if text:
                                loop.call_soon_threadsafe(
                                    queue.put_nowait,
                                    ChatChunk(kind="text", text=text),
                                )
                        elif kind == "message_start":
                            usage = (payload.get("message") or {}).get(
                                "usage"
                            ) or {}
                            usage_in = int(usage.get("input_tokens") or 0)
                        elif kind == "message_delta":
                            usage = payload.get("usage") or {}
                            if "output_tokens" in usage:
                                usage_out = int(usage["output_tokens"])
                        elif kind == "error":
                            err = payload.get("error") or {}
                            loop.call_soon_threadsafe(
                                queue.put_nowait,
                                ChatChunk(
                                    kind="error",
                                    error=str(err.get("message") or "error"),
                                ),
                            )
            except Exception as exc:  # surfaced as ChatChunk(error)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ChatChunk(kind="error", error=str(exc)),
                )
            finally:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ChatChunk(
                        kind="usage",
                        tokens_in=usage_in,
                        tokens_out=usage_out,
                    ),
                )
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_running_loop().run_in_executor(None, _worker)
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk


# ----------------------------------------------------------------------
# OpenAI streaming voice (Chat Completions SSE).
# ----------------------------------------------------------------------


class OpenAIChatVoice(ChatVoice):
    """OpenAI-backed chat voice (gpt-4o-mini by default)."""

    # gpt-4o family is multimodal. Older Chat Completions models
    # (gpt-3.5-turbo) ignore image_url blocks gracefully — but that's
    # only safe to flip on when the configured model is one of the
    # vision-capable ones. The class flag stays True; the orchestrator
    # additionally checks the model string for the vision tier.
    supports_multimodal = True

    def __init__(
        self,
        *,
        openai_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self.openai_model = (
            openai_model or os.getenv("TARS_OPENAI_MODEL") or "gpt-4o-mini"
        )
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.model = f"openai/{self.openai_model}"

    async def stream(
        self,
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        attachments: Sequence[AttachmentRef] = (),
        *,
        system_prompt: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        key = get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")
        if not key:
            yield ChatChunk(kind="error", error="openai_key_missing")
            return

        sys_text = _build_system(thread, system_prompt, attachments)
        body = {
            "model": self.openai_model,
            "max_tokens": self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": sys_text}]
            + _to_openai_messages(history, operator_text),
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        }
        started = time.perf_counter()
        try:
            async for chunk in self._iter(body, headers):
                yield chunk
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            yield ChatChunk(kind="error", error=f"transport_error: {exc}")
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        yield ChatChunk(kind="done", latency_ms=elapsed_ms)

    async def _iter(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> AsyncIterator[ChatChunk]:
        queue: asyncio.Queue[ChatChunk | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _worker() -> None:
            usage_in = 0
            usage_out = 0
            try:
                req = urllib.request.Request(
                    _OPENAI_URL,
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    for raw in resp:
                        line = raw.decode("utf-8", errors="replace").rstrip(
                            "\r\n"
                        )
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            payload = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = payload.get("choices") or []
                        if choices:
                            delta = (choices[0] or {}).get("delta") or {}
                            text = delta.get("content") or ""
                            if text:
                                loop.call_soon_threadsafe(
                                    queue.put_nowait,
                                    ChatChunk(kind="text", text=text),
                                )
                        usage = payload.get("usage") or {}
                        if usage:
                            usage_in = int(usage.get("prompt_tokens") or usage_in)
                            usage_out = int(
                                usage.get("completion_tokens") or usage_out
                            )
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ChatChunk(kind="error", error=str(exc)),
                )
            finally:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ChatChunk(
                        kind="usage",
                        tokens_in=usage_in,
                        tokens_out=usage_out,
                    ),
                )
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_running_loop().run_in_executor(None, _worker)
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------


def detect_chat_voice() -> ChatVoice:
    """Pick the best available chat voice.

    Anthropic > OpenAI > LocalChatVoice. Always returns something —
    the local fallback never raises so the chat stack stays online.
    """

    if get_secret("TARS_ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_API_KEY"):
        return AnthropicChatVoice()
    if get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY"):
        return OpenAIChatVoice()
    return LocalChatVoice()


def _build_system(
    thread: Thread,
    system_prompt: str | None,
    attachments: Sequence[AttachmentRef],
) -> str:
    parts: list[str] = [_TOOL_USE_PROMPT]
    if system_prompt:
        parts.append(system_prompt.strip())
    if thread.pack_slug:
        parts.append(
            f"Operator pinned the conversation to the '{thread.pack_slug}'"
            " pack — bias your suggestions toward its actions and"
            " awareness sources."
        )
    if attachments:
        names = ", ".join(
            a.filename or a.id for a in attachments if (a.filename or a.id)
        )
        parts.append(
            "The operator attached files: "
            + names
            + ". Their extracted text is appended below if available."
        )
        for att in attachments:
            if att.extracted_text:
                parts.append(f"\n--- attached: {att.filename or att.id} ---\n")
                parts.append(att.extracted_text[:4000])
    return "\n\n".join(p for p in parts if p)


def _to_anthropic_messages(
    history: Sequence[Message], operator_text: str
) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for m in history:
        if m.role == "operator":
            msgs.append({"role": "user", "content": m.content})
        elif m.role == "tars":
            msgs.append({"role": "assistant", "content": m.content})
        elif m.role == "tool":
            msgs.append({"role": "user", "content": f"[tool result] {m.content}"})
    msgs.append({"role": "user", "content": operator_text})
    return msgs


def _to_openai_messages(
    history: Sequence[Message], operator_text: str
) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for m in history:
        if m.role == "operator":
            msgs.append({"role": "user", "content": m.content})
        elif m.role == "tars":
            msgs.append({"role": "assistant", "content": m.content})
        elif m.role == "tool":
            msgs.append({"role": "tool", "content": m.content, "tool_call_id": m.id})
    msgs.append({"role": "user", "content": operator_text})
    return msgs


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> Iterable[str]:
    parts = _SENT_SPLIT.split(text)
    for p in parts:
        if p:
            # Re-attach trailing whitespace so the stream visually matches
            # the original.
            yield p + " "


def _approx_tokens(text: str) -> int:
    """Rough token count — ~4 chars per token. Good enough for ledger."""

    if not text:
        return 0
    return max(1, len(text) // 4)
