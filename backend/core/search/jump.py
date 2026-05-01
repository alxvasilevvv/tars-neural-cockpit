"""Cross-thread Cmd+J jump — fuzzy picker over local entities.

Powers the cockpit's ⌘J palette: a single fuzzy-search surface that
fishes through multiple TARS entity catalogues at once. Today's
sources, ordered by typical hit rate:

- ``thread``         — chat threads (title + pack hint).
- ``attachment``     — file attachments (filename + mime).
- ``saved_search``   — saved-search palette presets.
- ``pack``           — registered domain packs (slug + name).
- ``playbook``       — registered playbooks (slug + name).

The scoring is intentionally cheap (char-class subsequence matching
with prefix + token-boundary bonuses) — we're aiming for "good
enough" relevance on local catalogues with O(thousands) of rows, not
a real vector retriever. The L8 unified search (BM25 + RRF) is still
the right path for content-bearing surfaces like chunks / messages /
events; the jump picker is for *navigation*, not retrieval.

Empty / no-match queries return a recent-first list so the palette
opens with "your last 10 threads" and feels useful even before
typing.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

from backend.core.attachments.index import (
    AttachmentStore,
    get_attachment_store,
)
from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.domains.registry import all_packs

try:  # playbooks module is optional — skip cleanly if missing.
    from backend.core.playbooks.loader import all_playbooks
except Exception:  # pragma: no cover — exercised by isolated tests
    all_playbooks = None  # type: ignore[assignment]


log = logging.getLogger("tars.search.jump")


JumpKind = Literal["thread", "attachment", "saved_search", "pack", "playbook"]


@dataclass(frozen=True)
class JumpHit:
    """One ranked entry the cockpit can render in the picker."""

    kind: JumpKind
    id: str
    label: str
    sublabel: str
    score: float
    ref: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "label": self.label,
            "sublabel": self.sublabel,
            "score": round(float(self.score), 4),
            "ref": dict(self.ref),
        }


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def fuzzy_score(query: str, text: str) -> float:
    """Cheap fuzzy-match score (0..1).

    The recipe is:

    - Empty query → 0 (caller decides whether to treat that as "show
      recents" or "show nothing").
    - Exact substring match → 0.9 (anchored at start) / 0.7 (mid-text).
    - Token-prefix match (e.g. ``mar`` over ``Marketing brief``) →
      0.6 + tiny bonus per matched token.
    - Subsequence match (every char in order, possibly with gaps) →
      0.3 + 0.3 * (matched_len / query_len) - small penalty for gaps.
    - No subsequence → 0.

    The function is case-insensitive and ignores leading/trailing
    whitespace. It's deliberately not BM25 — for navigation surfaces,
    the biggest win is "did the operator's prefix match a token?".
    """

    q = (query or "").strip().lower()
    t = (text or "").strip().lower()
    if not q or not t:
        return 0.0
    if t == q:
        return 1.0
    if t.startswith(q):
        return 0.9
    idx = t.find(q)
    if idx >= 0:
        # Bonus for matching at a token boundary.
        boundary = idx == 0 or not t[idx - 1].isalnum()
        return 0.7 + (0.05 if boundary else 0.0)

    tokens = _TOKEN_RE.findall(t)
    matched_tokens = sum(1 for tok in tokens if tok.startswith(q))
    if matched_tokens:
        return 0.6 + min(matched_tokens, 3) * 0.05

    # Subsequence: every char in q appears in t in order.
    qi = 0
    last = -1
    gaps = 0
    for ch_idx, ch in enumerate(t):
        if qi < len(q) and ch == q[qi]:
            if last >= 0:
                gaps += ch_idx - last - 1
            last = ch_idx
            qi += 1
    if qi < len(q):
        return 0.0
    coverage = len(q) / max(len(t), 1)
    gap_penalty = min(0.2, gaps / max(len(t), 1))
    return max(0.1, 0.3 + 0.3 * coverage - gap_penalty)


def _best_score(query: str, *fields: str) -> float:
    """Best fuzzy_score across multiple candidate strings."""

    return max(
        (fuzzy_score(query, f) for f in fields if f),
        default=0.0,
    )


# ---------------------------------------------------------------------
# Per-source candidate fetchers
# ---------------------------------------------------------------------


async def _thread_candidates(
    chat: ChatStore, *, limit: int
) -> list[JumpHit]:
    threads = await chat.list_threads(limit=limit, archived=False)
    out: list[JumpHit] = []
    for t in threads:
        title = t.title or "untitled"
        pack = t.pack_slug or ""
        sublabel = f"thread · {pack}" if pack else "thread"
        out.append(
            JumpHit(
                kind="thread",
                id=t.id,
                label=title,
                sublabel=sublabel,
                score=0.0,  # filled in by ``rank``
                ref={
                    "thread_id": t.id,
                    "pack_slug": pack,
                    "updated_at": t.updated_at,
                },
            )
        )
    return out


async def _attachment_candidates(
    chat: ChatStore,
    attachments: AttachmentStore,
    *,
    limit: int,
) -> list[JumpHit]:
    """Walk recent threads and pull their attachments.

    The attachments table doesn't carry a global ``updated_at``
    cursor today, so we hop through the most-recent threads and
    take their attachments. That gets us a recency-correlated
    candidate pool without extending the schema.
    """

    threads = await chat.list_threads(limit=max(20, limit // 2))
    out: list[JumpHit] = []
    for t in threads:
        try:
            atts = await attachments.list_attachments(t.id)
        except Exception:
            continue
        for a in atts:
            label = a.filename or a.id
            mime = a.mime or ""
            out.append(
                JumpHit(
                    kind="attachment",
                    id=a.id,
                    label=label,
                    sublabel=f"attachment · {mime}" if mime else "attachment",
                    score=0.0,
                    ref={
                        "attachment_id": a.id,
                        "thread_id": t.id,
                        "mime": mime,
                        "filename": a.filename,
                    },
                )
            )
            if len(out) >= limit * 4:
                return out
    return out


async def _saved_search_candidates(
    chat: ChatStore, *, limit: int
) -> list[JumpHit]:
    saved = await chat.list_saved_searches(limit=limit)
    return [
        JumpHit(
            kind="saved_search",
            id=s.id,
            label=s.label,
            sublabel=f"saved · {s.scope}",
            score=0.0,
            ref={
                "search_id": s.id,
                "scope": s.scope,
                "query": s.query,
                "pinned": bool(s.pinned),
            },
        )
        for s in saved
    ]


def _pack_candidates() -> list[JumpHit]:
    out: list[JumpHit] = []
    for pack in all_packs():
        m = pack.manifest
        out.append(
            JumpHit(
                kind="pack",
                id=m.slug,
                label=m.name or m.slug,
                sublabel=f"pack · {m.short or m.slug}",
                score=0.0,
                ref={"slug": m.slug},
            )
        )
    return out


def _playbook_candidates() -> list[JumpHit]:
    if all_playbooks is None:
        return []
    try:
        books = all_playbooks()
    except Exception:
        return []
    out: list[JumpHit] = []
    for pb in books:
        slug = getattr(pb, "id", None) or getattr(pb, "slug", "")
        name = getattr(pb, "name", None) or slug
        if not slug:
            continue
        out.append(
            JumpHit(
                kind="playbook",
                id=slug,
                label=name,
                sublabel="playbook",
                score=0.0,
                ref={"playbook_id": slug},
            )
        )
    return out


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def rank(
    query: str,
    candidates: Sequence[JumpHit],
    *,
    limit: int,
) -> list[JumpHit]:
    """Score every candidate against ``query`` and trim to ``limit``.

    Empty / blank query → returns the candidates as-is, capped at
    ``limit``. Otherwise scores via :func:`fuzzy_score` against
    label + sublabel + id; non-matching candidates drop out.
    """

    q = (query or "").strip()
    if not q:
        return list(candidates[:limit])
    scored: list[JumpHit] = []
    for c in candidates:
        s = _best_score(q, c.label, c.sublabel, c.id)
        if s <= 0:
            continue
        scored.append(
            JumpHit(
                kind=c.kind,
                id=c.id,
                label=c.label,
                sublabel=c.sublabel,
                score=s,
                ref=dict(c.ref),
            )
        )
    scored.sort(key=lambda h: (-h.score, h.label.lower()))
    return scored[:limit]


async def jump(
    query: str,
    *,
    limit: int = 20,
    chat: ChatStore | None = None,
    attachments: AttachmentStore | None = None,
    kinds: Iterable[JumpKind] | None = None,
) -> dict[str, Any]:
    """Single fuzzy hop across every local entity catalogue.

    Returns ``{ok, query, count, hits: [...]}`` with hits sorted by
    descending score. ``kinds`` lets the caller restrict the sources
    (e.g. ``["thread", "saved_search"]`` for a thread-only picker).
    """

    chat = chat or get_chat_store()
    attachments = attachments or get_attachment_store()

    requested = set(kinds) if kinds else None

    pool: list[JumpHit] = []
    if not requested or "pack" in requested:
        pool.extend(_pack_candidates())
    if not requested or "playbook" in requested:
        pool.extend(_playbook_candidates())
    if chat.enabled:
        if not requested or "thread" in requested:
            pool.extend(
                await _thread_candidates(chat, limit=max(50, limit * 5))
            )
        if not requested or "saved_search" in requested:
            pool.extend(
                await _saved_search_candidates(chat, limit=max(50, limit * 2))
            )
        if not requested or "attachment" in requested:
            pool.extend(
                await _attachment_candidates(
                    chat, attachments, limit=max(50, limit * 3)
                )
            )

    hits = rank(query, pool, limit=limit)
    return {
        "ok": True,
        "query": (query or "").strip(),
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }
