"""@-mention chat context resolver (W240).

Cursor-style ``@file:path``, ``@docs:query``, ``@web:query``,
``@recent``, ``@code:query`` mentions in the chat input. The
resolver dispatches to the right local source, returns a
4-KB-bounded markdown blob, and the orchestrator folds it into
the operator's turn as a context preamble.

Sources are wired best-effort: if a backend (knowledge brain,
web-search keys, code-rag index) isn't present, we return
``(source not wired)`` rather than crashing the chat turn.
"""

from __future__ import annotations

from .resolver import (
    MAX_CONTENT_BYTES,
    MENTION_KINDS,
    MentionResolved,
    extract_mentions,
    inject_context,
    resolve_mention,
    resolve_mentions,
    strip_mentions,
)

__all__ = [
    "MAX_CONTENT_BYTES",
    "MENTION_KINDS",
    "MentionResolved",
    "extract_mentions",
    "inject_context",
    "resolve_mention",
    "resolve_mentions",
    "strip_mentions",
]
