"""ChatOrchestrator — bridges chat layer to council / policy / meeet.

Lifecycle of a single operator turn:

1. Persist the operator message (synchronously, before streaming
   starts — if the process dies mid-reply we still know what was
   asked).
2. Open a fresh ``trace_scope`` with ``route="edge"`` (the chat layer
   defaults to local; an LLM call upgrades it to ``cloud`` via the
   existing :func:`backend.core.meeet.set_route`).
3. Stream chunks from the configured :class:`ChatVoice`, parse out
   tool-call sentinels (`<tool name="slug.action_id">{...}</tool>`)
   on the fly, route them through :class:`PolicyGate` + the existing
   domain action pipeline, and yield their structured result back to
   the stream as ``tool_call.completed``.
4. Persist the assistant message + every tool call. Emit a final
   ``usage.tokens`` event (so the cost ledger picks it up alongside
   council / awareness / SMTP costs already tracked).

The orchestrator is the central seam between Phase L (chat / threads)
and Phase K (cost / route / policy / meeet) — everything else (search,
voice, mobile sync) lights up automatically by reading the same
durable buffer.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Mapping, Sequence

from backend.core.attachments.retrieval import RetrievedChunk, retrieve as retrieve_chunks
from backend.core.domains import packs as _packs  # noqa: F401  (registers built-ins)
from backend.core.domains.registry import get_pack
from backend.core.meeet import (
    current_route,
    get_client as get_meeet_client,
    set_route,
    trace_scope,
)
from backend.core.policy import PolicyMode, get_gate, resolve_mode
from backend.core.usage import default_price_table

from .models import (
    AttachmentRef,
    Message,
    StreamEvent,
    Thread,
    ToolCall,
)
from .store import ChatStore, get_chat_store
from .voices import (
    TOOL_BLOCK_RE,
    ChatChunk,
    ChatVoice,
    LocalChatVoice,
    detect_chat_voice,
)


DEFAULT_RETRIEVAL_TOP_K = 6
DEFAULT_RETRIEVAL_MIN_QUERY_CHARS = 6

DEFAULT_HISTORY_LIMIT = 30
_PRICE_TABLE = default_price_table()


class ChatOrchestrator:
    """Owns one assistant turn from operator-text in to stream out."""

    def __init__(
        self,
        *,
        store: ChatStore | None = None,
        voice: ChatVoice | None = None,
    ) -> None:
        self.store = store if store is not None else get_chat_store()
        self.voice: ChatVoice = voice if voice is not None else detect_chat_voice()

    async def post_message(
        self,
        thread_id: str,
        operator_text: str,
        *,
        session_id: str | None = None,
        attachments: Sequence[AttachmentRef] = (),
        policy_mode: PolicyMode | None = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> AsyncIterator[StreamEvent]:
        """Async-generate stream events for one operator turn.

        Use ``async for ev in orch.post_message(...)`` directly — this
        is itself an async generator, no extra ``await`` first.
        """

        thread = await self.store.get_thread(thread_id)
        if thread is None:
            yield StreamEvent(
                kind="error",
                data={"error": "thread_not_found", "thread_id": thread_id},
            )
            return

        history = await self.store.list_messages(
            thread_id, limit=history_limit
        )
        async for ev in self._run_turn(
            thread=thread,
            history=history,
            operator_text=operator_text,
            session_id=session_id,
            attachments=list(attachments),
            policy_mode=policy_mode,
        ):
            yield ev

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_turn(
        self,
        *,
        thread: Thread,
        history: Sequence[Message],
        operator_text: str,
        session_id: str | None,
        attachments: Sequence[AttachmentRef],
        policy_mode: PolicyMode | None,
    ) -> AsyncIterator[StreamEvent]:
        client = get_meeet_client()
        gate = get_gate()
        mode = policy_mode or resolve_mode()

        # 1. Persist the operator turn before opening the trace scope —
        #    the operator's message is real even if the network reply
        #    falls over.
        op_msg = Message.from_operator(thread.id, operator_text)
        await self.store.insert_message(op_msg)

        with trace_scope(
            session=session_id or thread.last_session_id,
            route="edge",
        ) as trace_id:
            assistant_id = self._mint_assistant_id()
            await client.emit(
                "chat.message.received",
                {
                    "thread_id": thread.id,
                    "msg_id": op_msg.id,
                    "len": len(operator_text or ""),
                },
            )
            yield StreamEvent(
                kind="message.started",
                data={
                    "msg_id": assistant_id,
                    "thread_id": thread.id,
                    "trace_id": trace_id,
                    "voice": getattr(self.voice, "model", "unknown"),
                    "policy_mode": mode.value,
                },
            )

            # 1a. Pull RAG context from indexed attachments, if any.
            retrieved: list[RetrievedChunk] = await self._maybe_retrieve(
                thread.id, operator_text
            )
            if retrieved:
                yield StreamEvent(
                    kind="context.retrieved",
                    data={
                        "msg_id": assistant_id,
                        "thread_id": thread.id,
                        "chunks": [r.to_dict() for r in retrieved],
                    },
                )
                await client.emit(
                    "chat.context.retrieved",
                    {
                        "thread_id": thread.id,
                        "msg_id": assistant_id,
                        "chunk_count": len(retrieved),
                        "files": sorted(
                            {
                                r.chunk.filename
                                for r in retrieved
                                if r.chunk.filename
                            }
                        ),
                    },
                )

            # 2. Stream from voice.
            voice_text_parts: list[str] = []
            buffered_text = ""
            tokens_in = 0
            tokens_out = 0
            voice_latency_ms = 0.0
            voice_error: str | None = None
            tool_calls: list[ToolCall] = []
            cloud_voice_used = self._is_cloud_voice(self.voice.model)
            if cloud_voice_used:
                set_route("cloud")

            # Phase M / P8 — vision agent inspects image attachments and
            # produces a text block we fold into the system prompt. The
            # block is harmless for multimodal voices (they still get
            # the native image refs through `attachments`) and gives
            # text-only voices enough context to acknowledge the image.
            vision_payload = await self._maybe_inspect_vision(attachments)
            if vision_payload.has_images:
                yield StreamEvent(
                    kind="context.vision",
                    data={
                        "msg_id": assistant_id,
                        "thread_id": thread.id,
                        "summaries": [s.to_dict() for s in vision_payload.summaries],
                    },
                )

            try:
                async for chunk in self.voice.stream(
                    thread,
                    history,
                    operator_text,
                    attachments,
                    system_prompt=self._compose_system_prompt(
                        thread, retrieved, vision_payload=vision_payload
                    ),
                ):
                    if chunk.kind == "text" and chunk.text:
                        buffered_text += chunk.text
                        # Try to extract a tool block if present.
                        text_for_user, tool_request, leftover = (
                            self._split_tool_block(buffered_text)
                        )
                        if text_for_user:
                            voice_text_parts.append(text_for_user)
                            yield StreamEvent(
                                kind="token",
                                data={"text": text_for_user},
                            )
                        if tool_request is not None:
                            buffered_text = leftover
                            async for ev, tc in self._handle_tool_call(
                                gate=gate,
                                client=client,
                                thread=thread,
                                assistant_msg_id=assistant_id,
                                tool_request=tool_request,
                                trace_id=trace_id,
                                mode=mode,
                            ):
                                if tc is not None:
                                    tool_calls.append(tc)
                                yield ev
                        else:
                            buffered_text = leftover
                    elif chunk.kind == "usage":
                        tokens_in = max(tokens_in, int(chunk.tokens_in or 0))
                        tokens_out = max(tokens_out, int(chunk.tokens_out or 0))
                        voice_latency_ms = max(
                            voice_latency_ms, float(chunk.latency_ms or 0.0)
                        )
                    elif chunk.kind == "error":
                        voice_error = chunk.error or "voice_error"
                        yield StreamEvent(
                            kind="error",
                            data={"error": voice_error},
                        )
                        break
                    elif chunk.kind == "done":
                        voice_latency_ms = max(
                            voice_latency_ms, float(chunk.latency_ms or 0.0)
                        )
            except Exception as exc:  # never crash the stream
                voice_error = f"orchestrator_exception: {exc}"
                yield StreamEvent(
                    kind="error", data={"error": voice_error}
                )

            # Flush any buffered tail (text after a partial tool block).
            if buffered_text:
                voice_text_parts.append(buffered_text)
                yield StreamEvent(
                    kind="token", data={"text": buffered_text}
                )

            assistant_text = "".join(voice_text_parts).strip()
            cost_usd = _PRICE_TABLE.cost_usd(
                self.voice.model, tokens_in, tokens_out
            )
            tool_cost = sum(
                (tc.cost_usd or 0.0) for tc in tool_calls if tc.cost_usd
            )
            total_cost = (cost_usd or 0.0) + tool_cost

            extra_payload: dict[str, Any] = {}
            if voice_error:
                extra_payload["voice_error"] = voice_error
            if retrieved:
                extra_payload["sources"] = [
                    {
                        "citation_id": r.citation_id,
                        "chunk_id": r.chunk.id,
                        "attachment_id": r.chunk.attachment_id,
                        "filename": r.chunk.filename,
                        "heading": r.chunk.heading,
                        "page": r.chunk.page,
                        "score": round(float(r.score), 4),
                    }
                    for r in retrieved
                ]
            assistant_msg = Message.from_tars(
                thread.id,
                assistant_text or "(empty reply)",
                trace_id=trace_id,
                parent_msg_id=op_msg.id,
                cost_usd=cost_usd,
                route=current_route(),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                voice_model=self.voice.model,
                extra=extra_payload,
            )
            # Force the freshly-minted assistant id so the SSE
            # `message.started` and the persisted row line up.
            assistant_msg = self._with_id(assistant_msg, assistant_id)
            await self.store.insert_message(assistant_msg)

            # Emit usage event so the cost ledger sees the chat turn.
            await client.emit(
                "usage.tokens",
                {
                    "model": self.voice.model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": round(voice_latency_ms, 3),
                    "cost_usd": cost_usd,
                    "topic": "chat",
                    "thread_id": thread.id,
                },
            )

            # Persist tool calls with final status snapshots.
            for tc in tool_calls:
                await self.store.upsert_tool_call(tc)

            # Update thread cursor.
            await self.store.patch_thread(
                thread.id,
                {"last_session_id": session_id or thread.last_session_id},
            )

            yield StreamEvent(
                kind="usage",
                data={
                    "msg_id": assistant_id,
                    "model": self.voice.model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost_usd,
                    "tool_cost_usd": round(tool_cost, 6),
                    "total_cost_usd": round(total_cost, 6),
                    "route": current_route(),
                    "latency_ms": round(voice_latency_ms, 3),
                },
            )
            yield StreamEvent(
                kind="message.completed",
                data={
                    "msg_id": assistant_id,
                    "thread_id": thread.id,
                    "trace_id": trace_id,
                    "content": assistant_text,
                    "tool_calls": [tc.to_dict() for tc in tool_calls],
                    "sources": extra_payload.get("sources", []),
                    "voice_error": voice_error,
                },
            )
            await client.emit(
                "chat.message.completed",
                {
                    "thread_id": thread.id,
                    "msg_id": assistant_id,
                    "tool_count": len(tool_calls),
                    "voice_error": voice_error,
                    "voice_model": self.voice.model,
                },
            )

    # ------------------------------------------------------------------
    # Tool-call routing
    # ------------------------------------------------------------------

    async def _handle_tool_call(
        self,
        *,
        gate,
        client,
        thread: Thread,
        assistant_msg_id: str,
        tool_request: dict[str, Any],
        trace_id: str | None,
        mode: PolicyMode,
    ):
        """Async generator that yields stream events + the resulting ToolCall."""

        slug = str(tool_request.get("slug") or "").strip()
        action_id = str(tool_request.get("action_id") or "").strip()
        args = dict(tool_request.get("args") or {})

        tc = ToolCall.fresh(
            message_id=assistant_msg_id,
            slug=slug,
            action_id=action_id,
            args=args,
            trace_id=trace_id,
        )
        yield StreamEvent(
            kind="tool_call.proposed",
            data={
                "tool_call_id": tc.id,
                "slug": slug,
                "action_id": action_id,
                "args": args,
            },
        ), None

        pack = get_pack(slug)
        spec = pack.find_action(action_id) if pack else None
        if pack is None or spec is None:
            tc = self._finish_tool_call(
                tc, status="failed", error="action_not_found"
            )
            yield StreamEvent(
                kind="tool_call.failed",
                data={"tool_call_id": tc.id, "error": "action_not_found"},
            ), tc
            return

        # Run policy gate.
        decision = await gate.check(
            slug=slug,
            action_id=action_id,
            args=args,
            destructive=spec.destructive,
            mode=mode,
            confirmed=False,
            trace_id=trace_id,
        )
        if not decision.allowed:
            reason = decision.reason or "blocked"
            tc = self._finish_tool_call(
                tc,
                status="queued"
                if reason == "awaiting_confirmation"
                else "failed",
                policy_token=decision.confirmation_token,
                error=None
                if reason == "awaiting_confirmation"
                else reason,
            )
            yield StreamEvent(
                kind="tool_call.queued"
                if reason == "awaiting_confirmation"
                else "tool_call.failed",
                data={
                    "tool_call_id": tc.id,
                    "reason": reason,
                    "policy_token": decision.confirmation_token,
                    "preview": decision.preview,
                },
            ), tc
            return

        yield StreamEvent(
            kind="tool_call.allowed",
            data={
                "tool_call_id": tc.id,
                "mode": decision.mode.value,
                "reason": decision.reason,
            },
        ), None

        # Execute.
        started = time.perf_counter()
        try:
            result = await spec.handler(args)
        except Exception as exc:  # surface as failed tool call
            tc = self._finish_tool_call(
                tc, status="failed", error=str(exc)
            )
            yield StreamEvent(
                kind="tool_call.failed",
                data={"tool_call_id": tc.id, "error": str(exc)},
            ), tc
            await client.emit(
                "chat.tool_call.failed",
                {
                    "tool_call_id": tc.id,
                    "slug": slug,
                    "action_id": action_id,
                    "error": str(exc),
                },
            )
            return

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        tc = self._finish_tool_call(
            tc, status="completed", result=dict(result or {})
        )
        yield StreamEvent(
            kind="tool_call.completed",
            data={
                "tool_call_id": tc.id,
                "slug": slug,
                "action_id": action_id,
                "took_ms": round(elapsed_ms, 3),
                "result": dict(result or {}),
            },
        ), tc
        await client.emit(
            "chat.tool_call.completed",
            {
                "tool_call_id": tc.id,
                "slug": slug,
                "action_id": action_id,
                "took_ms": round(elapsed_ms, 3),
            },
        )

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_tool_block(buffer: str) -> tuple[str, dict[str, Any] | None, str]:
        """Pull the first complete tool block out of ``buffer``.

        Returns ``(emit_now, tool_request_or_None, remaining_buffer)``.

        ``emit_now`` is the text *before* the tool block — safe to
        stream to the operator immediately. The tool block itself is
        consumed and parsed; whatever follows lands in
        ``remaining_buffer`` for the next chunk.
        """

        match = TOOL_BLOCK_RE.search(buffer)
        if match is None:
            # Hold back any text that *might* be the start of a tool
            # block to avoid leaking the sentinel on screen.
            tail_idx = buffer.rfind("<tool")
            if tail_idx == -1:
                return buffer, None, ""
            return buffer[:tail_idx], None, buffer[tail_idx:]

        emit_now = buffer[: match.start()]
        full_name = match.group(1)
        args_raw = match.group(2)
        leftover = buffer[match.end() :]

        if "." in full_name:
            slug, action_id = full_name.split(".", 1)
        else:
            slug, action_id = "", full_name
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            args = {}
        return (
            emit_now,
            {"slug": slug, "action_id": action_id, "args": args},
            leftover,
        )

    @staticmethod
    def _finish_tool_call(
        tc: ToolCall,
        *,
        status,
        result: Mapping[str, Any] | None = None,
        error: str | None = None,
        policy_token: str | None = None,
    ) -> ToolCall:
        return ToolCall(
            id=tc.id,
            message_id=tc.message_id,
            slug=tc.slug,
            action_id=tc.action_id,
            args=tc.args,
            status=status,
            started_at=tc.started_at,
            completed_at=time.time(),
            policy_token=policy_token or tc.policy_token,
            result=result,
            cost_usd=tc.cost_usd,
            error=error,
            trace_id=tc.trace_id,
        )

    @staticmethod
    def _mint_assistant_id() -> str:
        from .models import new_message_id

        return new_message_id()

    @staticmethod
    def _with_id(msg: Message, msg_id: str) -> Message:
        return Message(
            id=msg_id,
            thread_id=msg.thread_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            trace_id=msg.trace_id,
            parent_msg_id=msg.parent_msg_id,
            cost_usd=msg.cost_usd,
            route=msg.route,
            council_id=msg.council_id,
            tokens_in=msg.tokens_in,
            tokens_out=msg.tokens_out,
            voice_model=msg.voice_model,
            extra=msg.extra,
        )

    @staticmethod
    def _is_cloud_voice(model: str) -> bool:
        if not model:
            return False
        return model.startswith(("anthropic/", "openai/"))

    @staticmethod
    def _system_prompt_for(thread: Thread) -> str | None:
        # Phase M / P7 — the active operator role overlay always
        # prepends the pack prompt. The overlay names the operator's
        # position + priorities; the pack prompt names the toolset.
        # Together they describe both *who* the assistant works for and
        # *what* tools are reachable.
        try:
            from backend.core.roles import get_active_role
        except Exception:  # pragma: no cover — defensive
            get_active_role = None  # type: ignore[assignment]

        overlay: str | None = None
        if get_active_role is not None:
            try:
                role = get_active_role()
                if role is not None and role.overlay:
                    overlay = role.overlay
            except Exception:
                overlay = None

        pack_prompt: str | None = None
        if thread.pack_slug:
            pack = get_pack(thread.pack_slug)
            if pack is not None:
                try:
                    pack_prompt = pack.system_prompt()
                except Exception:
                    pack_prompt = None

        if overlay and pack_prompt:
            return f"{overlay}\n\n---\n\n{pack_prompt}"
        return overlay or pack_prompt

    @staticmethod
    async def _maybe_retrieve(
        thread_id: str, operator_text: str
    ) -> list[RetrievedChunk]:
        """Fetch top-K chunks for the operator's query, or empty list.

        Skipped for very short prompts (greetings, "yes", emoji) so the
        embedder isn't pinged needlessly. Always safe — retrieval
        gracefully returns ``[]`` when there are no chunks at all.
        """

        if not operator_text or len(operator_text.strip()) < DEFAULT_RETRIEVAL_MIN_QUERY_CHARS:
            return []
        try:
            return await retrieve_chunks(
                thread_id, operator_text, top_k=DEFAULT_RETRIEVAL_TOP_K
            )
        except Exception:
            return []

    @staticmethod
    async def _maybe_inspect_vision(
        attachments: Sequence[AttachmentRef],
    ):
        """Lazy import keeps the agent dep-free for non-vision turns."""

        try:
            from backend.agents import VisionAgent
        except Exception:
            from backend.agents.vision_agent import VisionPayload  # type: ignore[import-not-found]

            return VisionPayload()

        try:
            agent = VisionAgent()
            return await agent.inspect(list(attachments))
        except Exception:
            from backend.agents.vision_agent import VisionPayload

            return VisionPayload()

    def _compose_system_prompt(
        self,
        thread: Thread,
        retrieved: Sequence[RetrievedChunk],
        *,
        vision_payload: object | None = None,
    ) -> str | None:
        base = self._system_prompt_for(thread)
        # Phase M / P8 — fold the vision agent's text block into the
        # prompt. Always includes a short structured description of
        # the image; OCR text is appended when available.
        vision_block: str = ""
        if vision_payload is not None:
            block = getattr(vision_payload, "text_block", "") or ""
            has = getattr(vision_payload, "has_images", False)
            if has and block:
                vision_block = block.rstrip() + "\n"
        if not retrieved and not vision_block:
            return base
        if not retrieved and vision_block:
            return f"{(base or '').rstrip()}\n\n{vision_block}".lstrip()
        # Inject reference materials with stable [chunk_N] citation
        # markers — so the assistant can ground answers in real files.
        lines = [
            "## Reference materials",
            (
                "The operator has uploaded files relevant to this thread."
                " The most likely sources for their question are listed"
                " below. Each source has a stable id like [chunk_1]."
                " When you draw on a source, cite it inline with the id"
                " in square brackets so the operator can verify it."
            ),
            "",
        ]
        for r in retrieved:
            heading = r.chunk.heading or ""
            page = f" · page {r.chunk.page}" if r.chunk.page else ""
            location = (
                f" · {heading}{page}".strip()
                if (heading or page)
                else ""
            )
            label = (
                f"[{r.citation_id}] {r.chunk.filename or r.chunk.attachment_id}"
                f"{location}"
            )
            body = (r.chunk.text or "").strip()
            # Trim each chunk to 1.5k chars so the prompt doesn't blow up.
            if len(body) > 1500:
                body = body[:1500].rstrip() + "…"
            lines.append(label)
            lines.append(body)
            lines.append("")
        block = "\n".join(lines).rstrip() + "\n"
        if vision_block:
            block = block.rstrip() + "\n\n" + vision_block
        if base:
            return f"{base.rstrip()}\n\n{block}"
        return block
