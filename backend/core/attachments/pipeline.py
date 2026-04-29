"""Ingest pipeline: bytes → record → chunks → embeddings → store.

Idempotent on ``(thread_id, content_hash)`` — re-uploading the same
file in the same thread is a no-op (returns the existing record).

The pipeline never writes the same blob twice and always emits a
``attachment.ingested`` meeet event so the cost ledger sees embedding
spend (we also bump the meeet route to ``cloud`` when the OpenAI
embedder ran).

Storage layout:

    ~/.tars/attachments/
    └── <attachment_id>/
        └── <safe_filename>

The directory is created lazily and cleaned up on
:func:`delete_attachment`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Mapping

from backend.core.meeet import current_route, get_client, set_route, trace_scope

from .chunking import chunk_text
from .embeddings import Embedder, detect_embedder
from .extractors import extract, sniff_mime
from .index import (
    AttachmentRecord,
    AttachmentStore,
    Chunk,
    get_attachment_store,
)


log = logging.getLogger("tars.attachments")


DEFAULT_STORAGE_ROOT = "~/.tars/attachments"
MAX_BYTES = 25 * 1024 * 1024  # 25 MB hard cap; tunable via env


def _storage_root() -> str:
    raw = os.getenv("TARS_ATTACHMENT_ROOT") or DEFAULT_STORAGE_ROOT
    return os.path.expanduser(raw)


def _max_bytes() -> int:
    raw = os.getenv("TARS_ATTACHMENT_MAX_BYTES")
    if raw:
        try:
            return max(1024, int(raw))
        except ValueError:
            pass
    return MAX_BYTES


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestResult:
    record: AttachmentRecord
    chunk_count: int
    embedding_model: str | None
    duplicate: bool


async def ingest(
    *,
    thread_id: str,
    blob: bytes,
    filename: str | None = None,
    mime: str | None = None,
    message_id: str | None = None,
    session_id: str | None = None,
    embedder: Embedder | None = None,
    store: AttachmentStore | None = None,
) -> IngestResult:
    """Persist ``blob``, extract its text, chunk + embed, and index.

    Returns the (potentially deduped) :class:`AttachmentRecord` plus
    chunk count and the embedding model used. The pipeline is
    idempotent: re-uploading the same bytes in the same thread
    returns the existing record without re-embedding.
    """

    if not blob:
        raise IngestError("empty_blob")
    if len(blob) > _max_bytes():
        raise IngestError(
            f"too_large bytes={len(blob)} max={_max_bytes()}"
        )
    if not thread_id:
        raise IngestError("thread_id_required")

    store = store or get_attachment_store()
    embedder = embedder or detect_embedder()

    content_hash = hashlib.sha256(blob).hexdigest()
    existing = await store.find_by_hash(thread_id, content_hash)
    if existing is not None:
        log.info(
            "attachment dedup hit thread=%s hash=%s id=%s",
            thread_id,
            content_hash[:12],
            existing.id,
        )
        return IngestResult(
            record=existing,
            chunk_count=await store.chunk_count(thread_id),
            embedding_model=embedder.model,
            duplicate=True,
        )

    resolved_mime = sniff_mime(filename, mime)
    attachment_id = f"att_{secrets.token_urlsafe(8)}"
    safe_name = _safe_filename(filename) or _default_filename(resolved_mime)
    storage_dir = os.path.join(_storage_root(), attachment_id)
    storage_path = os.path.join(storage_dir, safe_name)

    await asyncio.to_thread(_write_file, storage_dir, storage_path, blob)

    extraction = extract(blob, filename=filename, mime=resolved_mime)
    text = extraction.text
    record = AttachmentRecord(
        id=attachment_id,
        thread_id=thread_id,
        message_id=message_id,
        mime=extraction.mime,
        filename=safe_name,
        bytes_total=len(blob),
        storage_path=storage_path,
        extracted_text=text or None,
        embedding_id=None,
        created_at=time.time(),
        content_hash=content_hash,
        status="ready" if text else "extract_pending",
        error=str(extraction.meta.get("error")) if extraction.meta.get("error") else None,
        meta=dict(extraction.meta),
        char_count=len(text or ""),
    )
    await store.upsert_attachment(record)

    chunks: list[Chunk] = []
    embedding_model: str | None = None
    embed_tokens = 0
    embed_cost = 0.0

    with trace_scope(session=session_id, route="edge") as trace_id:
        if text and text.strip():
            slices = chunk_text(text)
            if slices:
                vectors: list[list[float]] = []
                model_name = embedder.model
                try:
                    if _is_cloud_embedder(embedder):
                        set_route("cloud")
                    if hasattr(embedder, "model"):
                        model_name = embedder.model
                    result = await embedder.embed([s.text for s in slices])
                    vectors = result.vectors
                    embedding_model = result.model
                    embed_tokens = result.tokens_used or sum(
                        max(1, len(s.text) // 4) for s in slices
                    )
                except Exception as exc:
                    log.warning(
                        "embedder %s failed, falling back: %s", model_name, exc
                    )
                    # Fallback: HashEmbedder is always available and cheap.
                    from .embeddings import HashEmbedder

                    fallback = HashEmbedder()
                    result = await fallback.embed([s.text for s in slices])
                    vectors = result.vectors
                    embedding_model = result.model
                    embed_tokens = result.tokens_used

                now = time.time()
                for s, v in zip(slices, vectors):
                    chunks.append(
                        Chunk(
                            id=f"chk_{secrets.token_urlsafe(8)}",
                            attachment_id=attachment_id,
                            thread_id=thread_id,
                            ord=s.ord,
                            text=s.text,
                            char_start=s.char_start,
                            char_end=s.char_end,
                            heading=s.heading,
                            page=s.page,
                            embedding_model=embedding_model,
                            embedding_dim=len(v) if v else None,
                            embedding=v,
                            tokens_in=max(1, len(s.text) // 4),
                            created_at=now,
                        )
                    )
                # Cost: only the cloud embedder has non-zero default.
                embed_cost = _embedder_cost_usd(embedding_model, embed_tokens)
                await store.replace_chunks(attachment_id, thread_id, chunks)
                # Sync into the FTS5 keyword index — drives cross-thread
                # search + the BM25 side of L2's hybrid retrieval.
                try:
                    from backend.core.search.fts import (
                        ensure_fts_indexes,
                        index_chunks_bulk,
                    )

                    ensure_fts_indexes(chat=store.chat)
                    index_chunks_bulk(
                        [
                            (c.id, attachment_id, thread_id, c.text)
                            for c in chunks
                        ],
                        chat=store.chat,
                    )
                except Exception as exc:  # never break the pipeline on FTS issues
                    log.warning("chunk fts sync failed: %s", exc)
                # Patch the record with the resolved embedding model so
                # the UI can show "indexed via openai/text-embedding-3-small".
                record = AttachmentRecord(
                    **{
                        **record.__dict__,
                        "embedding_id": embedding_model,
                        "status": "ready",
                    }
                )
                await store.upsert_attachment(record)

        client = get_client()
        await client.emit(
            "attachment.ingested",
            {
                "attachment_id": record.id,
                "thread_id": thread_id,
                "filename": record.filename,
                "mime": record.mime,
                "bytes_total": record.bytes_total,
                "char_count": record.char_count,
                "chunk_count": len(chunks),
                "embedding_model": embedding_model,
                "embed_tokens": embed_tokens,
                "embed_cost_usd": embed_cost,
                "extract_error": record.error,
                "trace_id": trace_id,
                "route": current_route(),
            },
        )
        if embedding_model and embed_tokens > 0 and embed_cost > 0:
            await client.emit(
                "usage.tokens",
                {
                    "model": embedding_model,
                    "tokens_in": embed_tokens,
                    "tokens_out": 0,
                    "latency_ms": 0.0,
                    "cost_usd": embed_cost,
                    "topic": "attachment.embed",
                    "thread_id": thread_id,
                },
            )

    return IngestResult(
        record=record,
        chunk_count=len(chunks),
        embedding_model=embedding_model,
        duplicate=False,
    )


def _is_cloud_embedder(embedder: Embedder) -> bool:
    return type(embedder).__name__ == "OpenAIEmbedder"


async def delete_attachment(
    attachment_id: str, *, store: AttachmentStore | None = None
) -> bool:
    """Remove the row, its chunks, and the bytes on disk."""

    store = store or get_attachment_store()
    record = await store.get_attachment(attachment_id)
    if record is None:
        return False
    await store.delete_attachment(attachment_id)
    try:
        from backend.core.search.fts import remove_chunks_for_attachment

        remove_chunks_for_attachment(attachment_id, chat=store.chat)
    except Exception:
        pass

    def _rm() -> None:
        try:
            if record.storage_path and os.path.isfile(record.storage_path):
                os.unlink(record.storage_path)
            parent = os.path.dirname(record.storage_path)
            if parent and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except OSError:
            pass

    await asyncio.to_thread(_rm)
    return True


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


_FILENAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9._\- ]+")


def _safe_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = os.path.basename(name).strip()
    base = _FILENAME_SAFE_RE.sub("_", base)[:120]
    return base or None


def _default_filename(mime: str) -> str:
    ext = "bin"
    if "/" in mime:
        ext = mime.split("/", 1)[1].split(";")[0] or "bin"
        ext = re.sub(r"[^a-zA-Z0-9]+", "", ext)[:6] or "bin"
    return f"upload.{ext}"


def _write_file(directory: str, path: str, blob: bytes) -> None:
    os.makedirs(directory, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(blob)


# Pricing (USD per 1M input tokens). Override per-model via env.
_DEFAULT_EMBED_PRICES: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}


def _embedder_cost_usd(model: str | None, tokens: int) -> float:
    if not model or tokens <= 0:
        return 0.0
    raw = os.getenv(f"TARS_EMBED_PRICE_{model.upper().replace('-', '_')}")
    if raw:
        try:
            price = float(raw)
        except ValueError:
            price = 0.0
    else:
        price = _DEFAULT_EMBED_PRICES.get(model, 0.0)
    if price <= 0:
        return 0.0
    return round((tokens / 1_000_000.0) * price, 6)
