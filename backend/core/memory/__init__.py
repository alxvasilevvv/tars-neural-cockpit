"""Per-pack memory partitions.

A small key-value store that lets every domain pack persist facts
*scoped to that pack* — so the business pack's "Q3 OKR list" doesn't
leak into the science pack's "lit-review queue", and vice versa.
This is the foundation for cross-session memory; future slices will
add semantic search over the same partitions.

Public API:

- :class:`MemoryEntry` — the dataclass row.
- :class:`MemoryStore` — async CRUD with TTL eviction.
- :func:`get_memory_store` — process-wide singleton.
"""

from __future__ import annotations

from .models import MemoryEntry
from .store import MemoryStore, get_memory_store, reset_memory_store

__all__ = [
    "MemoryEntry",
    "MemoryStore",
    "get_memory_store",
    "reset_memory_store",
]
