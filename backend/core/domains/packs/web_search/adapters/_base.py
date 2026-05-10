"""Common shape for web-search backend adapters.

Each adapter implements ``async search(query, limit) -> AdapterResult``.
The pack-level ``search`` action picks one based on a deterministic
priority list (env override → `BRAVE_SEARCH_API_KEY` present → SearXNG
URL configured → DuckDuckGo HTML fallback). The fallback is intentional:
TARS is local-first and "no API key" must still produce useful output
rather than `error: not_configured`.

The shape is dataclass-only on purpose so the dispatcher can serialise
results without per-adapter knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class SearchHit:
    """One result row, normalised across providers."""

    title: str
    url: str
    snippet: str = ""
    source: str = ""  # provider tag, e.g. "brave" / "ddg" / "searxng"
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }
        if self.extra:
            out["extra"] = dict(self.extra)
        return out


@dataclass(frozen=True)
class AdapterResult:
    """Outcome of one adapter call.

    ``ok=True`` with empty ``hits`` is a valid "no results" state — the
    pack still records it. ``ok=False`` means the adapter failed for a
    reason worth surfacing to the operator (network down, bad key,
    upstream 5xx). The dispatcher then falls through to the next
    available adapter.
    """

    ok: bool
    adapter: str
    hits: tuple[SearchHit, ...] = ()
    error: str | None = None
    detail: str | None = None
    upstream_status: int | None = None

    def to_dict(self) -> dict:
        out: dict = {
            "ok": self.ok,
            "adapter": self.adapter,
            "hits": [h.to_dict() for h in self.hits],
            "count": len(self.hits),
        }
        if self.error:
            out["error"] = self.error
        if self.detail:
            out["detail"] = self.detail
        if self.upstream_status is not None:
            out["upstream_status"] = self.upstream_status
        return out


def trim(s: str, max_chars: int = 360) -> str:
    """Collapse whitespace + truncate snippet so payloads stay small."""
    s = " ".join((s or "").split())
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def dedupe(hits: Iterable[SearchHit]) -> tuple[SearchHit, ...]:
    """Stable de-duplication by URL; first occurrence wins."""
    seen: set[str] = set()
    out: list[SearchHit] = []
    for h in hits:
        key = (h.url or "").strip().rstrip("/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
    return tuple(out)
