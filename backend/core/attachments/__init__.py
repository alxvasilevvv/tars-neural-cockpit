"""TARS attachments + RAG layer (Phase L2).

End-to-end pipeline for files dropped into a chat thread:

    upload bytes  →  storage (~/.tars/attachments/<id>/<filename>)
                  →  extractor  (per-mime text)
                  →  chunker    (token-aware, overlapping)
                  →  embedder   (OpenAI text-embedding-3-small  ▸  offline hash fallback)
                  →  chunk store (SQLite WAL + NumPy float32 blobs)
                  →  retrieval  (hybrid: vector cosine + keyword BM25-ish)

The orchestrator (`backend.core.chat.orchestrator`) pulls top-K chunks
relevant to the operator's prompt per turn and feeds them into the
system prompt with stable ``[chunk_N]`` citation markers so the
assistant can cite its sources.

Public surface:

- :class:`AttachmentRecord` — stored attachment row (mime + extracted
  text + bytes).
- :class:`Chunk` — a single retrievable slice of an attachment.
- :func:`ingest` — drop bytes in, get a record back. Idempotent if the
  same content hash already exists for the same thread.
- :func:`retrieve` — query a thread → ranked list of chunks.
- :class:`AttachmentStore` — SQLite-backed durable store.

Two new SQLite tables join the chat schema:

- ``attachments`` (already created in L1; gains ``content_hash``,
  ``status``, ``error`` columns via auto-migration).
- ``attachment_chunks`` (new) — per-chunk text + embedding blob +
  metadata.
"""

from .embeddings import (
    Embedder,
    EmbeddingResult,
    HashEmbedder,
    OpenAIEmbedder,
    detect_embedder,
)
from .index import AttachmentRecord, AttachmentStore, Chunk, get_attachment_store
from .pipeline import IngestError, IngestResult, ingest
from .retrieval import RetrievedChunk, retrieve

__all__ = [
    "AttachmentRecord",
    "AttachmentStore",
    "Chunk",
    "Embedder",
    "EmbeddingResult",
    "HashEmbedder",
    "IngestError",
    "IngestResult",
    "OpenAIEmbedder",
    "RetrievedChunk",
    "detect_embedder",
    "get_attachment_store",
    "ingest",
    "retrieve",
]
