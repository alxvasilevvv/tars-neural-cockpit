"""Dataclass models for the per-pack memory store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryEntry:
    """One key-value entry scoped to a domain pack.

    ``value`` is materialised as parsed JSON — the store handles the
    encoding round-trip transparently. ``kind`` is a free-form string
    so packs can tag entries (``fact``, ``preference``, ``draft``,
    ``cache``…) without us pre-committing to an enum; the cockpit can
    filter on it.

    ``ttl_until`` is a POSIX timestamp; ``None`` means "no TTL".
    Entries with ``ttl_until`` in the past are filtered out by
    list/get unless the caller passes ``include_expired=True``.
    """

    id: str
    pack_slug: str
    key: str
    value: Any
    kind: str
    ttl_until: float | None
    created_at: float
    updated_at: float
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, *, now: float | None = None) -> bool:
        if self.ttl_until is None:
            return False
        import time
        return float(self.ttl_until) <= (now or time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pack_slug": self.pack_slug,
            "key": self.key,
            "value": self.value,
            "kind": self.kind,
            "ttl_until": self.ttl_until,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "metadata": dict(self.metadata),
        }
