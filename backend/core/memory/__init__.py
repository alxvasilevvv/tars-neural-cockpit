"""Per-pack memory partitions + persistent conversation memory.

This module exposes two distinct stores:

* :class:`MemoryStore` (key-value scoped to domain packs) — used by
  agents for facts, preferences, drafts, caches.
* :class:`ConversationMemory` (W274) — persistent multi-turn chat
  history with FTS search + session summaries. Powers TARS' ability
  to "remember" across sessions.
"""

from __future__ import annotations

from .conversation import (
    ConversationMemory,
    ConversationTurn,
    get_conversation_memory,
    reset_conversation_memory,
)
from .models import MemoryEntry
from .store import MemoryStore, get_memory_store, reset_memory_store

__all__ = [
    "MemoryEntry",
    "MemoryStore",
    "get_memory_store",
    "reset_memory_store",
    "ConversationMemory",
    "ConversationTurn",
    "get_conversation_memory",
    "reset_conversation_memory",
]
