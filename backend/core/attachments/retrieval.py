"""Hybrid retrieval — semantic + keyword fused via reciprocal rank.

For tiny corpora (a handful of attachments per thread) we keep the
implementation simple and self-contained: load all chunks for the
thread, score them two ways (cosine over vectors + lowercase keyword
overlap), then merge with reciprocal rank fusion (k=60). This is
within ms for thousands of chunks and avoids a hard NumPy/FAISS
dependency.

When a corpus eventually outgrows this, the same call signature will
move behind a faster index without changing callers — keep the public
surface small.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .embeddings import Embedder, detect_embedder
from .index import AttachmentStore, Chunk, get_attachment_store


_RRF_K = 60.0  # reciprocal rank fusion damping (de facto standard)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    rank_semantic: int | None
    rank_keyword: int | None
    citation_id: str  # stable [chunk_<n>] for prompt injection

    def to_dict(self) -> Mapping[str, object]:
        c = self.chunk
        return {
            "citation_id": self.citation_id,
            "score": round(float(self.score), 4),
            "rank_semantic": self.rank_semantic,
            "rank_keyword": self.rank_keyword,
            "chunk": {
                "id": c.id,
                "attachment_id": c.attachment_id,
                "filename": c.filename,
                "mime": c.mime,
                "page": c.page,
                "heading": c.heading,
                "ord": c.ord,
                "text": c.text,
            },
        }


async def retrieve(
    thread_id: str,
    query: str,
    *,
    top_k: int = 6,
    store: AttachmentStore | None = None,
    embedder: Embedder | None = None,
    semantic_pool: int = 30,
    keyword_pool: int = 30,
) -> list[RetrievedChunk]:
    """Return up to ``top_k`` chunks ranked by hybrid score.

    Always safe — empty thread / empty query → ``[]``.
    """

    if not query or not query.strip():
        return []
    store = store or get_attachment_store()
    chunks = await store.list_chunks(thread_id, limit=5000)
    if not chunks:
        return []

    embedder = embedder or detect_embedder()

    # 1. Semantic ranking (when both query and chunks have vectors).
    semantic_ranking: list[tuple[Chunk, float]] = []
    if any(c.embedding for c in chunks):
        try:
            qv = (await embedder.embed([query])).vectors
        except Exception:
            qv = []
        if qv and qv[0]:
            qvec = qv[0]
            scored: list[tuple[Chunk, float]] = []
            for c in chunks:
                if not c.embedding:
                    continue
                if c.embedding_dim and c.embedding_dim != len(qvec):
                    # Embedder mismatch (model changed). Skip.
                    continue
                scored.append((c, _cosine(qvec, c.embedding)))
            scored.sort(key=lambda x: x[1], reverse=True)
            semantic_ranking = scored[:semantic_pool]

    # 2. Keyword scoring via SQLite FTS5 BM25 (preferred) with a
    #    tf-overlap fallback for callers running without the FTS5
    #    indexes initialised yet (e.g. very early test boots).
    keyword_ranking: list[tuple[Chunk, float]] = []
    chunks_by_id = {c.id: c for c in chunks}
    fts_rows: list[dict] = []
    try:
        from backend.core.search.fts import (
            ensure_fts_indexes,
            fts_match_chunks,
        )

        ensure_fts_indexes(chat=store.chat)
        fts_rows = fts_match_chunks(
            query,
            chat=store.chat,
            limit=keyword_pool,
            thread_id=thread_id,
        )
    except Exception:
        fts_rows = []
    if fts_rows:
        for row in fts_rows:
            c = chunks_by_id.get(row["chunk_id"])
            if c is not None:
                keyword_ranking.append((c, 1.0))  # rank-only signal
    else:
        q_terms = _tokenise(query)
        if q_terms:
            kw_scored: list[tuple[Chunk, float]] = []
            for c in chunks:
                score = _keyword_score(q_terms, c.text)
                if score > 0:
                    kw_scored.append((c, score))
            kw_scored.sort(key=lambda x: x[1], reverse=True)
            keyword_ranking = kw_scored[:keyword_pool]

    if not semantic_ranking and not keyword_ranking:
        return []

    # 3. Reciprocal rank fusion.
    fused: dict[str, dict[str, float | int | None | Chunk]] = {}

    def _bump(
        ranking: list[tuple[Chunk, float]], key: str
    ) -> None:
        for rank, (chunk, _score) in enumerate(ranking, start=1):
            entry = fused.setdefault(
                chunk.id,
                {
                    "chunk": chunk,
                    "rrf": 0.0,
                    "rank_semantic": None,
                    "rank_keyword": None,
                },
            )
            entry["rrf"] = float(entry["rrf"]) + 1.0 / (_RRF_K + rank)
            entry[key] = rank

    _bump(semantic_ranking, "rank_semantic")
    _bump(keyword_ranking, "rank_keyword")

    ordered = sorted(
        fused.values(), key=lambda e: float(e["rrf"]), reverse=True
    )
    out: list[RetrievedChunk] = []
    for i, entry in enumerate(ordered[:top_k], start=1):
        out.append(
            RetrievedChunk(
                chunk=entry["chunk"],  # type: ignore[arg-type]
                score=float(entry["rrf"]),
                rank_semantic=entry["rank_semantic"],  # type: ignore[arg-type]
                rank_keyword=entry["rank_keyword"],  # type: ignore[arg-type]
                citation_id=f"chunk_{i}",
            )
        )
    return out


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


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


def _tokenise(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return [t for t in out if len(t) >= 2]


def _keyword_score(query_terms: Sequence[str], text: str) -> float:
    if not query_terms or not text:
        return 0.0
    q = set(query_terms)
    body_terms = _tokenise(text)
    body = {}  # tf
    for t in body_terms:
        body[t] = body.get(t, 0) + 1
    overlap = q.intersection(body.keys())
    if not overlap:
        return 0.0
    tf = sum(body[t] for t in overlap)
    # Slight length normalisation so a 5k-char chunk doesn't crush a 200-char one.
    norm = math.log(2 + len(body_terms))
    return tf / norm
