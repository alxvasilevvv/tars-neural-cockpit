"""Unified search engine — chunks + messages + traces.

Three independent searches share the same FTS5 backbone (BM25 keyword
score) and a single :class:`SearchHit` row format so the cockpit's
⌘K palette can render every kind in one list.

Chunk search additionally fuses the BM25 score with vector cosine
when an embedder is reachable — same RRF (k=60) trick as the L2
in-thread retrieval, just dropping the per-thread filter.

Engine-level safety nets:

- Sanitised queries (no FTS5 syntax injection).
- Bounded fan-out (per-scope ``top_k`` cap).
- Graceful fallback when an embedder is offline (keyword-only).
- Returns empty list for empty queries.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

from backend.core.attachments.embeddings import Embedder, detect_embedder
from backend.core.attachments.index import (
    AttachmentStore,
    Chunk,
    get_attachment_store,
)
from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.meeet import get_store as get_meeet_store

from .filters import ParsedQuery, parse_query_filters
from .fts import (
    ensure_events_fts,
    ensure_fts_indexes,
    fts_match_chunks,
    fts_match_events,
    fts_match_messages,
)


log = logging.getLogger("tars.search.engine")


SearchKind = Literal["chunk", "message", "trace"]
SearchScope = Literal["all", "chunks", "messages", "traces"]


_RRF_K = 60.0


@dataclass(frozen=True)
class SearchHit:
    """A single ranked result row.

    ``kind`` discriminates between the three sources; ``ref`` is a
    structured pointer the cockpit can navigate to (thread id, msg id,
    attachment id, trace id).
    """

    kind: SearchKind
    score: float
    title: str
    snippet: str
    ref: dict[str, Any]
    rank_keyword: int | None = None
    rank_semantic: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "score": round(float(self.score), 4),
            "title": self.title,
            "snippet": self.snippet,
            "ref": dict(self.ref),
            "rank_keyword": self.rank_keyword,
            "rank_semantic": self.rank_semantic,
        }


@dataclass(frozen=True)
class SearchResult:
    query: str
    scope: SearchScope
    hits: list[SearchHit]
    counts: dict[str, int] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    cleaned_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "scope": self.scope,
            "count": len(self.hits),
            "counts": dict(self.counts),
            "filters": dict(self.filters),
            "cleaned_query": self.cleaned_query,
            "hits": [h.to_dict() for h in self.hits],
        }


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


async def search(
    query: str,
    *,
    scope: SearchScope = "all",
    top_k: int = 12,
    chat: ChatStore | None = None,
    attachments: AttachmentStore | None = None,
    embedder: Embedder | None = None,
) -> SearchResult:
    """Run a unified hybrid search and return ranked hits.

    The fan-out runs per-scope sequentially (each individual search is
    fast since they're SQLite-local). For ``scope='all'`` we pull the
    top ~K from each scope, then trim down to ``top_k`` overall by
    score.

    Operator-friendly filters embedded in the query
    (``role:operator``, ``pack:business``, ``since:7d``, ``kind:…``,
    ``thread:thr_…``, ``trace:trc_…``, ``mime:pdf``) are parsed out via
    :func:`parse_query_filters` and applied to each scope.
    """

    chat = chat or get_chat_store()
    if not query or not query.strip():
        return SearchResult(query=query, scope=scope, hits=[], counts={})

    ensure_fts_indexes(chat=chat)

    parsed = parse_query_filters(query)
    cleaned = parsed.text or query  # never run an FTS with an empty body
    f = parsed.filters

    counts: dict[str, int] = {}
    hits: list[SearchHit] = []

    if scope in ("all", "chunks"):
        chunk_hits = await search_chunks(
            cleaned,
            top_k=top_k,
            chat=chat,
            attachments=attachments,
            embedder=embedder,
            thread_id=f.get("thread"),
            pack=f.get("pack"),
            mime=f.get("mime"),
            since=f.get("since"),
            until=f.get("until"),
        )
        counts["chunks"] = len(chunk_hits)
        hits.extend(chunk_hits)
    if scope in ("all", "messages"):
        msg_hits = await search_messages(
            cleaned,
            top_k=top_k,
            chat=chat,
            thread_id=f.get("thread"),
            role=f.get("role"),
            pack=f.get("pack"),
            since=f.get("since"),
            until=f.get("until"),
        )
        counts["messages"] = len(msg_hits)
        hits.extend(msg_hits)
    if scope in ("all", "traces"):
        trace_hits = await search_traces(
            cleaned,
            top_k=top_k,
            kind=f.get("kind"),
            trace_id=f.get("trace"),
            since=f.get("since"),
            until=f.get("until"),
        )
        counts["traces"] = len(trace_hits)
        hits.extend(trace_hits)

    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[:top_k]
    return SearchResult(
        query=query, scope=scope, hits=hits, counts=counts,
        filters=dict(parsed.filters),
        cleaned_query=parsed.text,
    )


# ---------------------------------------------------------------------
# Per-scope searches
# ---------------------------------------------------------------------


async def search_chunks(
    query: str,
    *,
    top_k: int = 12,
    chat: ChatStore | None = None,
    attachments: AttachmentStore | None = None,
    embedder: Embedder | None = None,
    thread_id: str | None = None,
    pack: str | None = None,
    mime: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[SearchHit]:
    """Cross-thread (or single-thread) hybrid chunk search.

    ``thread_id`` scopes to one thread (used by the L2 in-thread
    retrieval rebuilt on top of FTS5 — see :func:`hybrid_chunks_in_thread`).

    Operator-DSL tokens parsed via :func:`parse_query_filters`:

    - ``thread:`` → ``thread_id`` (caller-supplied wins).
    - ``pack:``   → ``threads.pack_slug`` (JOIN ``threads``).
    - ``mime:``   → ``attachments.mime`` (literal or ``image/*``
      wildcard prefix; JOIN ``attachments``).
    - ``since:``  → POSIX seconds, ``attachments.created_at >=``.
    - ``until:``  → POSIX seconds, ``attachments.created_at <=``.

    Explicit kwargs always win over inline filters. The vector
    fallback path doesn't honour ``pack``/``mime``/time bounds today —
    it only fires when keyword has zero hits, which is rare for
    real queries; tightening it is a separate slice if it ever
    matters in practice.
    """

    chat = chat or get_chat_store()
    attachments = attachments or get_attachment_store()
    embedder = embedder or detect_embedder()
    if not query.strip():
        return []
    parsed = parse_query_filters(query)
    query = parsed.text or query
    if thread_id is None:
        thread_id = parsed.filters.get("thread")
    if pack is None:
        pack = parsed.filters.get("pack")
    if mime is None:
        mime = parsed.filters.get("mime")
    if since is None:
        since_val = parsed.filters.get("since")
        if isinstance(since_val, (int, float)):
            since = float(since_val)
    if until is None:
        until_val = parsed.filters.get("until")
        if isinstance(until_val, (int, float)):
            until = float(until_val)

    ensure_fts_indexes(chat=chat)

    keyword_rows = await asyncio.to_thread(
        fts_match_chunks,
        query,
        chat=chat,
        limit=max(top_k * 4, 30),
        thread_id=thread_id,
        pack=pack,
        mime=mime,
        since=since,
        until=until,
    )
    if not keyword_rows:
        # No keyword hits at all — fall back to vector-only over the
        # thread / global pool (cheaper than SQL roundtrip when the
        # corpus is tiny).
        return await _vector_only_chunk_search(
            query,
            top_k=top_k,
            attachments=attachments,
            embedder=embedder,
            thread_id=thread_id,
        )

    # Pull full chunk rows for the keyword hits.
    chunks_by_id: dict[str, Chunk] = {}
    if thread_id:
        chunks = await attachments.list_chunks(thread_id, limit=5000)
        for c in chunks:
            chunks_by_id[c.id] = c
    else:
        chunks = await _list_chunks_by_ids(
            [row["chunk_id"] for row in keyword_rows], chat=chat
        )
        for c in chunks:
            chunks_by_id[c.id] = c

    keyword_ranking: list[tuple[Chunk, float, str]] = []
    for rank_idx, row in enumerate(keyword_rows, start=1):
        c = chunks_by_id.get(row["chunk_id"])
        if c is None:
            continue
        keyword_ranking.append((c, _bm25_to_score(row.get("rank")), row["snippet"]))

    semantic_ranking: list[tuple[Chunk, float]] = []
    try:
        if embedder and any(c.embedding for c in chunks_by_id.values()):
            qv = (await embedder.embed([query])).vectors
            if qv and qv[0]:
                qvec = qv[0]
                scored: list[tuple[Chunk, float]] = []
                for c in chunks_by_id.values():
                    if not c.embedding:
                        continue
                    if c.embedding_dim and c.embedding_dim != len(qvec):
                        continue
                    scored.append((c, _cosine(qvec, c.embedding)))
                scored.sort(key=lambda x: x[1], reverse=True)
                semantic_ranking = scored[:top_k * 4]
    except Exception:
        log.exception("embedder failed during chunk search; keyword-only")

    # Reciprocal-rank fusion.
    fused: dict[str, dict[str, Any]] = {}
    for rank, (c, _bm, snippet) in enumerate(keyword_ranking, start=1):
        fused.setdefault(
            c.id,
            {
                "chunk": c,
                "score": 0.0,
                "snippet": snippet,
                "rank_keyword": None,
                "rank_semantic": None,
            },
        )
        fused[c.id]["score"] += 1.0 / (_RRF_K + rank)
        fused[c.id]["rank_keyword"] = rank
        if not fused[c.id].get("snippet"):
            fused[c.id]["snippet"] = snippet
    for rank, (c, _cos) in enumerate(semantic_ranking, start=1):
        fused.setdefault(
            c.id,
            {
                "chunk": c,
                "score": 0.0,
                "snippet": (c.text or "")[:240],
                "rank_keyword": None,
                "rank_semantic": None,
            },
        )
        fused[c.id]["score"] += 1.0 / (_RRF_K + rank)
        fused[c.id]["rank_semantic"] = rank

    threads_by_id = await _load_thread_titles(
        {fused[k]["chunk"].thread_id for k in fused},
        chat=chat,
    )

    ordered = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
    out: list[SearchHit] = []
    for entry in ordered[:top_k]:
        c: Chunk = entry["chunk"]
        thr = threads_by_id.get(c.thread_id)
        title = c.filename or c.attachment_id
        if thr:
            title = f"{title} · {thr['title'] or 'untitled'}"
        out.append(
            SearchHit(
                kind="chunk",
                score=float(entry["score"]),
                title=title,
                snippet=entry["snippet"] or (c.text or "")[:240],
                ref={
                    "chunk_id": c.id,
                    "attachment_id": c.attachment_id,
                    "thread_id": c.thread_id,
                    "thread_title": thr["title"] if thr else None,
                    "filename": c.filename,
                    "page": c.page,
                    "heading": c.heading,
                },
                rank_keyword=entry["rank_keyword"],
                rank_semantic=entry["rank_semantic"],
            )
        )
    return out


async def search_messages(
    query: str,
    *,
    top_k: int = 12,
    chat: ChatStore | None = None,
    embedder: Embedder | None = None,
    thread_id: str | None = None,
    role: str | None = None,
    pack: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[SearchHit]:
    """Hybrid keyword + vector search over chat messages.

    Pulls ``top_k * 4`` keyword candidates so the RRF fuse has room
    to re-rank, then (when an embedder is reachable AND at least one
    candidate carries an embedding) blends BM25 with cosine via the
    same RRF formula used by chunk search. Falls back to keyword-only
    silently when no embedder is available.

    Operator-DSL tokens (``role:``, ``pack:``, ``since:``, ``until:``,
    ``thread:``) embedded directly in ``query`` are parsed via
    :func:`parse_query_filters`. Caller-supplied kwargs win over
    parsed values (explicit > inline).
    """

    chat = chat or get_chat_store()
    if not query.strip():
        return []
    ensure_fts_indexes(chat=chat)

    parsed = parse_query_filters(query)
    cleaned = parsed.text or query
    pf = parsed.filters
    eff_thread = thread_id if thread_id is not None else pf.get("thread")
    eff_role = role if role is not None else pf.get("role")
    eff_pack = pack if pack is not None else pf.get("pack")
    eff_since = since if since is not None else pf.get("since")
    eff_until = until if until is not None else pf.get("until")

    keyword_pool = max(top_k * 4, 30)
    rows = await asyncio.to_thread(
        fts_match_messages,
        cleaned,
        chat=chat,
        limit=keyword_pool,
        thread_id=eff_thread,
        role=eff_role,
        pack=eff_pack,
        since=eff_since,
        until=eff_until,
    )
    if not rows:
        return []

    embeddings_by_id = await chat.get_message_embeddings(
        [r["msg_id"] for r in rows]
    )

    semantic_ranking: list[tuple[str, float]] = []
    if embeddings_by_id:
        active = embedder or detect_embedder()
        try:
            qv: list[list[float]] | None = None
            if await active.is_available():
                qv = (await active.embed([query])).vectors
            if qv and qv[0]:
                qvec = qv[0]
                qlen = len(qvec)
                scored: list[tuple[str, float]] = []
                for msg_id, info in embeddings_by_id.items():
                    vec = info.get("vector") or []
                    if not vec:
                        continue
                    if info.get("dim") and info["dim"] != qlen:
                        continue
                    if len(vec) != qlen:
                        continue
                    scored.append((msg_id, _cosine(qvec, vec)))
                scored.sort(key=lambda x: x[1], reverse=True)
                semantic_ranking = scored[: keyword_pool]
        except Exception:
            log.exception(
                "embedder failed during message search; keyword-only"
            )

    fused: dict[str, dict[str, Any]] = {}
    rows_by_id = {r["msg_id"]: r for r in rows}
    for rank, row in enumerate(rows, start=1):
        msg_id = row["msg_id"]
        bucket = fused.setdefault(
            msg_id,
            {
                "row": row,
                "score": 0.0,
                "rank_keyword": None,
                "rank_semantic": None,
            },
        )
        bucket["score"] += 1.0 / (_RRF_K + rank)
        bucket["rank_keyword"] = rank
    for rank, (msg_id, _cos) in enumerate(semantic_ranking, start=1):
        bucket = fused.get(msg_id)
        if bucket is None:
            # Vector hit only — synth-row from store if available; we
            # already constrained semantic candidates to the keyword
            # pool, so this branch only fires when the keyword row was
            # filtered out (e.g. dropped by FTS scoring).
            row = rows_by_id.get(msg_id)
            if row is None:
                continue
            bucket = fused.setdefault(
                msg_id,
                {
                    "row": row,
                    "score": 0.0,
                    "rank_keyword": None,
                    "rank_semantic": None,
                },
            )
        bucket["score"] += 1.0 / (_RRF_K + rank)
        bucket["rank_semantic"] = rank

    threads = await _load_thread_titles(
        {fused[k]["row"]["thread_id"] for k in fused}, chat=chat
    )

    ordered = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
    out: list[SearchHit] = []
    for entry in ordered[:top_k]:
        row = entry["row"]
        thr = threads.get(row["thread_id"])
        title = (
            f"{row['role']} · {thr['title'] or 'untitled'}"
            if thr
            else f"{row['role']} · {row['thread_id']}"
        )
        out.append(
            SearchHit(
                kind="message",
                score=float(entry["score"]),
                title=title,
                snippet=row["snippet"] or "",
                ref={
                    "msg_id": row["msg_id"],
                    "thread_id": row["thread_id"],
                    "thread_title": thr["title"] if thr else None,
                    "role": row["role"],
                },
                rank_keyword=entry["rank_keyword"],
                rank_semantic=entry["rank_semantic"],
            )
        )
    return out


async def search_traces(
    query: str,
    *,
    top_k: int = 12,
    kind: str | None = None,
    trace_id: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[SearchHit]:
    if not query.strip():
        return []
    store = get_meeet_store()
    if not store or not getattr(store, "enabled", False):
        return []
    db_path = store.db_path
    if not db_path:
        return []

    parsed = parse_query_filters(query)
    cleaned = parsed.text or query
    pf = parsed.filters
    eff_kind = kind if kind is not None else pf.get("kind")
    eff_trace = trace_id if trace_id is not None else pf.get("trace")
    eff_since = since if since is not None else pf.get("since")
    eff_until = until if until is not None else pf.get("until")

    def _ensure_and_query() -> list[dict]:
        ensure_events_fts(db_path)
        return fts_match_events(
            cleaned,
            meeet_db_path=db_path,
            limit=top_k,
            kind=eff_kind,
            trace_id=eff_trace,
            since=eff_since,
            until=eff_until,
        )

    rows = await asyncio.to_thread(_ensure_and_query)
    if not rows:
        return []
    out: list[SearchHit] = []
    for rank, row in enumerate(rows, start=1):
        out.append(
            SearchHit(
                kind="trace",
                score=_bm25_to_score(row.get("rank")),
                title=f"{row['kind']} · {(row.get('trace_id') or '')[:18] or 'untraced'}",
                snippet=row["snippet"] or "",
                ref={
                    "event_id": row["event_id"],
                    "kind": row["kind"],
                    "trace_id": row.get("trace_id"),
                    "session_id": row.get("session_id"),
                },
                rank_keyword=rank,
            )
        )
    return out


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _bm25_to_score(rank: float | None) -> float:
    """Convert FTS5 BM25 rank (lower = better) to a 'higher = better' score.

    BM25 in SQLite returns a negative-ish small float for matches.
    A simple monotone transform: ``score = 1 / (1 + |rank|)``.
    """

    if rank is None:
        return 0.0
    return 1.0 / (1.0 + abs(float(rank)))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        x = a[i]
        y = b[i]
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return 0.0
    return dot / denom


async def _list_chunks_by_ids(
    chunk_ids: Iterable[str],
    *,
    chat: ChatStore | None,
) -> list[Chunk]:
    chat = chat or get_chat_store()
    if not chat.enabled:
        return []
    ids = list({cid for cid in chunk_ids if cid})
    if not ids:
        return []

    def _run() -> list[Chunk]:
        from backend.core.attachments.index import _row_to_chunk

        conn = chat._connect()
        try:
            placeholders = ",".join(["?"] * len(ids))
            rows = conn.execute(
                f"""
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE c.id IN ({placeholders})
                """,
                ids,
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r) for r in rows]

    return await asyncio.to_thread(_run)


async def _load_thread_titles(
    thread_ids: Iterable[str], *, chat: ChatStore | None
) -> dict[str, dict[str, Any]]:
    chat = chat or get_chat_store()
    ids = list({tid for tid in thread_ids if tid})
    if not chat.enabled or not ids:
        return {}

    def _run() -> dict[str, dict[str, Any]]:
        conn = chat._connect()
        try:
            placeholders = ",".join(["?"] * len(ids))
            rows = conn.execute(
                f"SELECT id, title, pack_slug FROM threads "
                f"WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        finally:
            conn.close()
        return {
            r["id"]: {"title": r["title"], "pack_slug": r["pack_slug"]}
            for r in rows
        }

    return await asyncio.to_thread(_run)


async def _vector_only_chunk_search(
    query: str,
    *,
    top_k: int,
    attachments: AttachmentStore,
    embedder: Embedder,
    thread_id: str | None,
) -> list[SearchHit]:
    if thread_id:
        chunks = await attachments.list_chunks(thread_id, limit=5000)
    else:
        chunks = await _all_embedded_chunks(attachments)
    if not chunks:
        return []
    try:
        qv = (await embedder.embed([query])).vectors
    except Exception:
        return []
    if not qv or not qv[0]:
        return []
    qvec = qv[0]
    scored: list[tuple[Chunk, float]] = []
    for c in chunks:
        if not c.embedding:
            continue
        if c.embedding_dim and c.embedding_dim != len(qvec):
            continue
        scored.append((c, _cosine(qvec, c.embedding)))
    scored.sort(key=lambda x: x[1], reverse=True)
    selected = [s for s in scored if s[1] > 0.05][:top_k]
    if not selected:
        return []
    threads = await _load_thread_titles(
        {c.thread_id for c, _ in selected},
        chat=None,
    )
    out: list[SearchHit] = []
    for rank, (c, cos_score) in enumerate(selected, start=1):
        thr = threads.get(c.thread_id)
        title = (c.filename or c.attachment_id)
        if thr:
            title = f"{title} · {thr['title'] or 'untitled'}"
        out.append(
            SearchHit(
                kind="chunk",
                score=cos_score,
                title=title,
                snippet=(c.text or "")[:240],
                ref={
                    "chunk_id": c.id,
                    "attachment_id": c.attachment_id,
                    "thread_id": c.thread_id,
                    "thread_title": thr["title"] if thr else None,
                    "filename": c.filename,
                    "page": c.page,
                    "heading": c.heading,
                },
                rank_semantic=rank,
            )
        )
    return out


async def _all_embedded_chunks(attachments: AttachmentStore) -> list[Chunk]:
    if not attachments.chat.enabled:
        return []

    def _run() -> list[Chunk]:
        from backend.core.attachments.index import _row_to_chunk

        conn = attachments._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    c.*,
                    a.filename AS att_filename,
                    a.mime AS att_mime
                FROM attachment_chunks c
                LEFT JOIN attachments a ON a.id = c.attachment_id
                WHERE c.embedding_blob IS NOT NULL
                ORDER BY c.created_at DESC
                LIMIT 5000
                """
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r) for r in rows]

    return await asyncio.to_thread(_run)
