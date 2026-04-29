"""TARS conversation layer (Phase L1).

Threads, messages, tool-calls and (stubbed) attachments backed by
SQLite WAL at ``~/.tars/chat.sqlite`` (override with
``TARS_CHAT_DB_PATH``; disable with ``TARS_CHAT_STORE=disabled``).

The orchestrator (`backend/core/chat/orchestrator.py`) ties the chat
layer into the existing K-tier modules:

- Every assistant turn opens a `trace_scope` with the active
  ``session_id`` (from the cockpit's per-tab id) so cost / route /
  policy events all roll up to the same conversation.
- LLM voice replies stream token-by-token via
  ``Voice.propose_streaming`` (default impl chunks
  :meth:`Voice.propose` for deterministic voices).
- Tool-call structures emitted in the assistant stream are routed
  through the existing ``policy.PolicyGate`` and the domain action
  pipeline — destructive actions still queue confirmation tokens.

See ``docs/PHASE_L_ROADMAP.md`` §5.L1 for the full spec.
"""

from .models import (
    Attachment,
    AttachmentRef,
    Message,
    StreamEvent,
    Thread,
    ToolCall,
    new_attachment_id,
    new_message_id,
    new_thread_id,
    new_tool_call_id,
)
from .store import ChatStore, get_chat_store, reset_chat_store

__all__ = [
    "Attachment",
    "AttachmentRef",
    "ChatStore",
    "Message",
    "StreamEvent",
    "Thread",
    "ToolCall",
    "get_chat_store",
    "new_attachment_id",
    "new_message_id",
    "new_thread_id",
    "new_tool_call_id",
    "reset_chat_store",
]
