"""TARS unified search + observability layer (Phase L8).

Three indexes, one query surface:

- **chunks**   — :mod:`backend.core.attachments` already stores chunks
  with float32 vector blobs; we layer an FTS5 virtual table over the
  ``text`` column for proper BM25 keyword scoring (replaces the
  hand-rolled tf-overlap from L2).
- **messages** — FTS5 virtual table over ``messages.content`` lets the
  cockpit do cross-thread keyword search ("find when I asked about
  GDPR").
- **events**   — FTS5 virtual table over the meeet event ``payload``
  column so operators can fish for traces by free text ("find the
  trade where the council disagreed").

The unified :func:`search` runs the three searches in parallel
(when scope allows it), enriches each hit with the surrounding
context (thread title, message role, file name, trace id), and
returns a single :class:`SearchHit` list ranked by reciprocal-rank
fusion of (a) FTS5 BM25 score, (b) optional vector cosine for chunks
where an embedder is available.

The module is stdlib-only — no FAISS / no sentence-transformers,
keeps the local-first contract intact.
"""

from .engine import (
    SearchHit,
    SearchScope,
    SearchResult,
    search,
    search_chunks,
    search_messages,
    search_traces,
)
from .filters import ParsedQuery, merge_filters, parse_query_filters
from .fts import (
    backfill_chunk_fts,
    backfill_message_fts,
    drop_fts_tables,
    ensure_events_fts,
    ensure_fts_indexes,
    fts_match_chunks,
    fts_match_events,
    fts_match_messages,
    verify_and_repair_chat_fts,
    verify_and_repair_events_fts,
)
from .timeline import ThreadTimelineEntry, get_thread_timeline

__all__ = [
    "ParsedQuery",
    "SearchHit",
    "SearchResult",
    "SearchScope",
    "ThreadTimelineEntry",
    "backfill_chunk_fts",
    "backfill_message_fts",
    "drop_fts_tables",
    "ensure_events_fts",
    "ensure_fts_indexes",
    "fts_match_chunks",
    "fts_match_events",
    "fts_match_messages",
    "get_thread_timeline",
    "merge_filters",
    "parse_query_filters",
    "search",
    "search_chunks",
    "search_messages",
    "search_traces",
    "verify_and_repair_chat_fts",
    "verify_and_repair_events_fts",
]
