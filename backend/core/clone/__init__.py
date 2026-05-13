"""AI Clone v0.1 — minimal honest style learning (Wave 73 Feature 4).

Closes Task #104 (AI Clone v1) which the task list marked complete
without shipping code. This is the v0.1 — *style hint, not full
clone* — that the README and marketing now point at instead of
overpromising.

Public surface:

- :class:`StyleProfile` — structured snapshot of what the operator
  sounds like (avg sentence length, casual/formal lean, top vocab).
- :func:`record_message` — non-blocking call into the chat write
  path; appends one row to the ``style_traits`` SQLite table and
  refreshes the rolling profile.
- :func:`profile` — current best-effort profile JSON.
- :func:`draft` — RAG-style "what would the operator say" using the
  top-K nearest past messages by embedding (or hash-trigram fallback)
  and a quick LLM rewrite.
"""

from __future__ import annotations

from .style import (
    StyleProfile,
    draft,
    get_clone_store,
    profile,
    record_message,
    reset_clone_store,
)

__all__ = [
    "StyleProfile",
    "draft",
    "get_clone_store",
    "profile",
    "record_message",
    "reset_clone_store",
]
