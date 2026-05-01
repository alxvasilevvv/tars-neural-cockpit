"""Dataclasses for the chat layer.

Stay close to dict-on-the-wire (SSE consumers + the SQLite store both
serialise these). Frozen, lightweight, no external deps.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def new_thread_id() -> str:
    return _new_id("thr")


def new_message_id() -> str:
    return _new_id("msg")


def new_tool_call_id() -> str:
    return _new_id("tcl")


def new_attachment_id() -> str:
    return _new_id("att")


def new_saved_search_id() -> str:
    return _new_id("sv")


SavedSearchScope = Literal["all", "chunks", "messages", "traces"]


@dataclass(frozen=True)
class SavedSearch:
    """A persisted search filter combination.

    The cockpit ⌘K palette uses these to let operators re-run their
    common queries with one click. ``filters`` is a free-form JSON
    bag — current consumers honour ``thread_id`` / ``role`` /
    ``kind`` / ``trace_id``, additive keys are forward-compat.
    """

    id: str
    label: str
    query: str
    scope: SavedSearchScope
    filters: Mapping[str, Any]
    pinned: bool
    created_at: float
    updated_at: float
    last_run_at: float | None
    # Snapshot of hit fingerprints last observed by ``poll_saved_search``.
    # Populated lazily — older rows materialise as an empty tuple, which
    # the alert path treats as "first poll" (everything counts as new
    # for the fingerprint diff, but we suppress the event because there
    # was no prior baseline to compare against).
    seen_hits: tuple[str, ...] = ()
    last_alert_at: float | None = None
    # When set, ``poll_saved_search`` updates the fingerprint snapshot
    # and records new hits but suppresses the meeet
    # ``saved_search.new_hits`` emit until ``time.time() >=
    # snoozed_until``. Snooze is a "mute the alarm, not the watcher"
    # signal — useful when a saved search is temporarily noisy.
    snoozed_until: float | None = None

    @staticmethod
    def fresh(
        *,
        label: str,
        query: str,
        scope: SavedSearchScope = "all",
        filters: Mapping[str, Any] | None = None,
        pinned: bool = False,
    ) -> "SavedSearch":
        now = time.time()
        return SavedSearch(
            id=new_saved_search_id(),
            label=label.strip() or "untitled",
            query=query,
            scope=scope,
            filters=dict(filters or {}),
            pinned=bool(pinned),
            created_at=now,
            updated_at=now,
            last_run_at=None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "query": self.query,
            "scope": self.scope,
            "filters": dict(self.filters),
            "pinned": bool(self.pinned),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_at": self.last_run_at,
            "seen_hit_count": len(self.seen_hits),
            "last_alert_at": self.last_alert_at,
            "snoozed_until": self.snoozed_until,
        }

    def is_snoozed(self, *, now: float | None = None) -> bool:
        if self.snoozed_until is None:
            return False
        import time
        return float(self.snoozed_until) > (now or time.time())


MessageRole = Literal["operator", "tars", "tool", "system"]
ToolStatus = Literal["pending", "queued", "allowed", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class Thread:
    """A conversation root.

    Threads carry an optional ``pack_slug`` pin (so the assistant uses
    that pack's system prompt + actions by default) and an optional
    ``project_id`` grouping hint for the cockpit.
    """

    id: str
    title: str | None
    pack_slug: str | None
    project_id: str | None
    created_at: float
    updated_at: float
    last_session_id: str | None = None
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "pack_slug": self.pack_slug,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_session_id": self.last_session_id,
            "archived": self.archived,
        }

    @classmethod
    def fresh(
        cls,
        *,
        title: str | None = None,
        pack_slug: str | None = None,
        project_id: str | None = None,
        now: float | None = None,
    ) -> "Thread":
        ts = now if now is not None else time.time()
        return cls(
            id=new_thread_id(),
            title=title,
            pack_slug=pack_slug,
            project_id=project_id,
            created_at=ts,
            updated_at=ts,
        )


@dataclass(frozen=True)
class Message:
    """A single conversational turn.

    ``role='tool'`` rows are produced by the orchestrator after a
    domain action returns; they carry the structured result so the
    cockpit can render an inline tool-call card.
    """

    id: str
    thread_id: str
    role: MessageRole
    content: str
    created_at: float
    trace_id: str | None = None
    parent_msg_id: str | None = None
    cost_usd: float | None = None
    route: str | None = None
    council_id: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    voice_model: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "trace_id": self.trace_id,
            "parent_msg_id": self.parent_msg_id,
            "cost_usd": self.cost_usd,
            "route": self.route,
            "council_id": self.council_id,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "voice_model": self.voice_model,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_operator(
        cls,
        thread_id: str,
        text: str,
        *,
        trace_id: str | None = None,
        now: float | None = None,
    ) -> "Message":
        return cls(
            id=new_message_id(),
            thread_id=thread_id,
            role="operator",
            content=text,
            created_at=now if now is not None else time.time(),
            trace_id=trace_id,
        )

    @classmethod
    def from_tars(
        cls,
        thread_id: str,
        text: str,
        *,
        trace_id: str | None = None,
        parent_msg_id: str | None = None,
        cost_usd: float | None = None,
        route: str | None = None,
        council_id: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        voice_model: str | None = None,
        extra: Mapping[str, Any] | None = None,
        now: float | None = None,
    ) -> "Message":
        return cls(
            id=new_message_id(),
            thread_id=thread_id,
            role="tars",
            content=text,
            created_at=now if now is not None else time.time(),
            trace_id=trace_id,
            parent_msg_id=parent_msg_id,
            cost_usd=cost_usd,
            route=route,
            council_id=council_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            voice_model=voice_model,
            extra=extra or {},
        )

    @classmethod
    def from_tool(
        cls,
        thread_id: str,
        *,
        parent_msg_id: str,
        text: str,
        trace_id: str | None = None,
        cost_usd: float | None = None,
        route: str | None = None,
        extra: Mapping[str, Any] | None = None,
        now: float | None = None,
    ) -> "Message":
        return cls(
            id=new_message_id(),
            thread_id=thread_id,
            role="tool",
            content=text,
            created_at=now if now is not None else time.time(),
            trace_id=trace_id,
            parent_msg_id=parent_msg_id,
            cost_usd=cost_usd,
            route=route,
            extra=extra or {},
        )


@dataclass(frozen=True)
class ToolCall:
    """A domain-action invocation requested by the assistant.

    Lifecycle:
        pending → (queued | allowed) → (completed | failed | cancelled)
    """

    id: str
    message_id: str
    slug: str
    action_id: str
    args: Mapping[str, Any]
    status: ToolStatus
    started_at: float
    policy_token: str | None = None
    result: Mapping[str, Any] | None = None
    cost_usd: float | None = None
    completed_at: float | None = None
    error: str | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "slug": self.slug,
            "action_id": self.action_id,
            "args": dict(self.args),
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "policy_token": self.policy_token,
            "result": dict(self.result) if self.result is not None else None,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "trace_id": self.trace_id,
        }

    @classmethod
    def fresh(
        cls,
        *,
        message_id: str,
        slug: str,
        action_id: str,
        args: Mapping[str, Any],
        trace_id: str | None = None,
        now: float | None = None,
    ) -> "ToolCall":
        return cls(
            id=new_tool_call_id(),
            message_id=message_id,
            slug=slug,
            action_id=action_id,
            args=dict(args),
            status="pending",
            started_at=now if now is not None else time.time(),
            trace_id=trace_id,
        )


@dataclass(frozen=True)
class Attachment:
    """A file attached to a thread (full pipeline ships in L2)."""

    id: str
    thread_id: str
    message_id: str | None
    mime: str
    filename: str | None
    bytes_total: int
    storage_path: str
    extracted_text: str | None
    embedding_id: str | None
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "message_id": self.message_id,
            "mime": self.mime,
            "filename": self.filename,
            "bytes_total": self.bytes_total,
            "storage_path": self.storage_path,
            "extracted_text": self.extracted_text,
            "embedding_id": self.embedding_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AttachmentRef:
    """Lightweight reference passed in operator messages.

    The full file lives in :class:`Attachment`; the orchestrator only
    needs the id + extracted text + filename to assemble the prompt
    context. Real upload pipeline is L2.
    """

    id: str
    filename: str | None = None
    mime: str | None = None
    extracted_text: str | None = None


# ----------------------------------------------------------------------
# Streaming events (SSE wire format).
# ----------------------------------------------------------------------


StreamKind = Literal[
    "message.started",
    "context.retrieved",
    "token",
    "tool_call.proposed",
    "tool_call.queued",
    "tool_call.allowed",
    "tool_call.completed",
    "tool_call.failed",
    "usage",
    "message.completed",
    "error",
]


@dataclass(frozen=True)
class StreamEvent:
    """A single chunk yielded by the ChatOrchestrator stream.

    SSE encoding (handled by the router):
        ``event: <kind>\\ndata: <json>\\n\\n``
    """

    kind: StreamKind
    data: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "data": dict(self.data)}
