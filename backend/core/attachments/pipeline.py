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
from typing import Any, Awaitable, Callable, Mapping


ProgressCallback = Callable[[str, Mapping[str, Any]], Awaitable[None]]
"""Async callback invoked at each ingest phase.

Signature: ``async def cb(phase: str, payload: Mapping[str, Any]) -> None``.

Phases (each fired at most once per ingest call, in this order):

- ``started`` — bytes accepted, before any disk I/O.
- ``dedup_hit`` — terminal short-circuit when the same hash exists.
- ``extracted`` — text extracted, before chunking.
- ``chunked`` — chunks computed, before embedding.
- ``embedding`` — embedder running.
- ``embedded`` — vectors back, before persistence.
- ``indexed`` — FTS sync complete (or skipped).
- ``zip_walked`` — terminal for archive uploads.
- ``completed`` — terminal for non-archive uploads.
- ``error`` — terminal on transport / embedder failure (never raises).

The callback is fire-and-forget from the pipeline's perspective: any
exception inside it is logged and swallowed so a flaky SSE consumer
can never break the ingest flow."""

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


async def _safe_progress(
    cb: ProgressCallback | None,
    phase: str,
    payload: Mapping[str, Any],
) -> None:
    """Invoke ``cb`` exactly once for ``phase``; swallow & log any error.

    The pipeline must never fail because of a flaky SSE consumer.
    """

    if cb is None:
        return
    try:
        await cb(phase, payload)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("ingest progress callback raised on phase=%s: %s", phase, exc)


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
    parent_attachment_id: str | None = None,
    walk_archives: bool = True,
    progress: ProgressCallback | None = None,
) -> IngestResult:
    """Persist ``blob``, extract its text, chunk + embed, and index.

    Returns the (potentially deduped) :class:`AttachmentRecord` plus
    chunk count and the embedding model used. The pipeline is
    idempotent: re-uploading the same bytes in the same thread
    returns the existing record without re-embedding.

    When ``walk_archives`` is True (the default) and the upload is
    a zip, the archive itself is stored as a parent attachment and
    every safe member is recursively ingested as a child. The walk
    summary is recorded on the parent's ``meta`` under
    ``zip_walk``. Pass ``parent_attachment_id`` from the walker so
    children link back to the archive without bleeding into the
    public API. ``walk_archives=False`` is for the recursion guard
    inside :func:`walk_zip` (depth-limited walks).
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

    await _safe_progress(
        progress,
        "started",
        {
            "thread_id": thread_id,
            "bytes_total": len(blob),
            "filename": filename,
            "mime": mime,
        },
    )

    content_hash = hashlib.sha256(blob).hexdigest()
    existing = await store.find_by_hash(thread_id, content_hash)
    if existing is not None:
        log.info(
            "attachment dedup hit thread=%s hash=%s id=%s",
            thread_id,
            content_hash[:12],
            existing.id,
        )
        await _safe_progress(
            progress,
            "dedup_hit",
            {
                "attachment_id": existing.id,
                "thread_id": thread_id,
                "content_hash": content_hash,
            },
        )
        return IngestResult(
            record=existing,
            chunk_count=await store.chunk_count(thread_id),
            embedding_model=embedder.model,
            duplicate=True,
        )

    resolved_mime = sniff_mime(filename, mime)

    # Zip detection: if walking is enabled and the blob looks like a
    # zip, hand the heavy lifting to the zip walker. The parent zip
    # is recorded as a single attachment with ``zip_walk`` summary
    # in its meta so the cockpit can render the per-member outcome.
    from .zip_walker import is_zip_mime, looks_like_zip, walk_zip

    is_archive = (
        walk_archives
        and parent_attachment_id is None  # never auto-walk children
        and (is_zip_mime(resolved_mime) or looks_like_zip(blob, filename))
    )

    attachment_id = f"att_{secrets.token_urlsafe(8)}"
    safe_name = _safe_filename(filename) or _default_filename(resolved_mime)
    storage_dir = os.path.join(_storage_root(), attachment_id)
    storage_path = os.path.join(storage_dir, safe_name)

    await asyncio.to_thread(_write_file, storage_dir, storage_path, blob)

    extraction = extract(blob, filename=filename, mime=resolved_mime)
    text = extraction.text
    await _safe_progress(
        progress,
        "extracted",
        {
            "attachment_id": attachment_id,
            "thread_id": thread_id,
            "mime": extraction.mime,
            "char_count": len(text or ""),
            "extract_error": (
                str(extraction.meta.get("error"))
                if extraction.meta.get("error")
                else None
            ),
        },
    )
    await get_client().emit(
        "attachment.extracting",
        {
            "attachment_id": attachment_id,
            "thread_id": thread_id,
            "mime": extraction.mime,
            "char_count": len(text or ""),
        },
    )
    record_meta: dict = dict(extraction.meta)
    if parent_attachment_id is not None:
        record_meta["parent_attachment_id"] = parent_attachment_id
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
        meta=record_meta,
        char_count=len(text or ""),
    )
    await store.upsert_attachment(record)

    # Archives: expand into children before chunking so the parent
    # row stays opaque (no chunks); each child member gets its own
    # full ingest cycle.
    if is_archive:
        try:
            walk_summary = await walk_zip(
                parent_record=record,
                blob=blob,
                thread_id=thread_id,
                message_id=message_id,
                session_id=session_id,
                store=store,
                depth=0,
            )
        except Exception as exc:  # never crash the parent ingest
            log.warning("zip walk crashed for %s: %s", record.id, exc)
            walk_summary = None
        if walk_summary is not None:
            record_meta = dict(record.meta)
            record_meta["zip_walk"] = walk_summary.to_dict()
            record = AttachmentRecord(
                **{
                    **record.__dict__,
                    "meta": record_meta,
                    "status": "ready",
                }
            )
            await store.upsert_attachment(record)
        client = get_client()
        await client.emit(
            "attachment.zip_walked",
            {
                "attachment_id": record.id,
                "thread_id": thread_id,
                "expanded": walk_summary.expanded if walk_summary else 0,
                "skipped": walk_summary.skipped if walk_summary else 0,
                "failed": walk_summary.failed if walk_summary else 0,
                "truncated": (
                    walk_summary.truncated if walk_summary else False
                ),
            },
        )
        await _safe_progress(
            progress,
            "zip_walked",
            {
                "attachment_id": record.id,
                "thread_id": thread_id,
                "expanded": walk_summary.expanded if walk_summary else 0,
                "skipped": walk_summary.skipped if walk_summary else 0,
                "failed": walk_summary.failed if walk_summary else 0,
                "truncated": (
                    walk_summary.truncated if walk_summary else False
                ),
            },
        )
        return IngestResult(
            record=record,
            chunk_count=0,
            embedding_model=None,
            duplicate=False,
        )

    chunks: list[Chunk] = []
    embedding_model: str | None = None
    embed_tokens = 0
    embed_cost = 0.0

    with trace_scope(session=session_id, route="edge") as trace_id:
        if text and text.strip():
            slices = chunk_text(text)
            if slices:
                await _safe_progress(
                    progress,
                    "chunked",
                    {
                        "attachment_id": attachment_id,
                        "thread_id": thread_id,
                        "chunk_count": len(slices),
                    },
                )
                vectors: list[list[float]] = []
                model_name = embedder.model
                try:
                    if _is_cloud_embedder(embedder):
                        set_route("cloud")
                    if hasattr(embedder, "model"):
                        model_name = embedder.model
                    await _safe_progress(
                        progress,
                        "embedding",
                        {
                            "attachment_id": attachment_id,
                            "thread_id": thread_id,
                            "chunk_count": len(slices),
                            "embedding_model": model_name,
                        },
                    )
                    await get_client().emit(
                        "attachment.embedding",
                        {
                            "attachment_id": attachment_id,
                            "thread_id": thread_id,
                            "chunk_count": len(slices),
                            "embedding_model": model_name,
                        },
                    )
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
                await _safe_progress(
                    progress,
                    "embedded",
                    {
                        "attachment_id": attachment_id,
                        "thread_id": thread_id,
                        "chunk_count": len(chunks),
                        "embedding_model": embedding_model,
                        "tokens_used": embed_tokens,
                    },
                )
                # Cost: only the cloud embedder has non-zero default.
                embed_cost = _embedder_cost_usd(embedding_model, embed_tokens)
                await store.replace_chunks(attachment_id, thread_id, chunks)
                # Sync into the FTS5 keyword index — drives cross-thread
                # search + the BM25 side of L2's hybrid retrieval.
                fts_synced = False
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
                    fts_synced = True
                except Exception as exc:  # never break the pipeline on FTS issues
                    log.warning("chunk fts sync failed: %s", exc)
                await _safe_progress(
                    progress,
                    "indexed",
                    {
                        "attachment_id": attachment_id,
                        "thread_id": thread_id,
                        "chunk_count": len(chunks),
                        "fts_synced": fts_synced,
                    },
                )
                await get_client().emit(
                    "attachment.indexed",
                    {
                        "attachment_id": attachment_id,
                        "thread_id": thread_id,
                        "chunk_count": len(chunks),
                        "fts_synced": fts_synced,
                    },
                )
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

    await _safe_progress(
        progress,
        "completed",
        {
            "attachment_id": record.id,
            "thread_id": thread_id,
            "chunk_count": len(chunks),
            "embedding_model": embedding_model,
            "tokens_used": embed_tokens,
            "cost_usd": embed_cost,
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


# ---------------------------------------------------------------------
# Re-embed on demand
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class ReembedResult:
    """Outcome of a :func:`reembed_attachment` call."""

    ok: bool
    attachment_id: str
    chunk_count: int = 0
    embedding_model: str | None = None
    embedding_dim: int | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    previous_model: str | None = None
    error: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        body: dict = {
            "ok": self.ok,
            "attachment_id": self.attachment_id,
            "chunk_count": self.chunk_count,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "previous_model": self.previous_model,
        }
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        return body


def _resolve_embedder_by_name(name: str | None) -> Embedder:
    """Map a short name (``openai`` / ``hash``) to a concrete
    embedder. Anything else falls back to :func:`detect_embedder`.

    Raised model names like ``text-embedding-3-large`` are routed
    to :class:`OpenAIEmbedder` so an operator can promote the
    corpus to a higher-quality vector without setting an env var.
    """

    cleaned = (name or "").strip().lower()
    if not cleaned:
        return detect_embedder()
    if cleaned == "hash":
        from .embeddings import HashEmbedder

        return HashEmbedder()
    if cleaned == "openai":
        from .embeddings import OpenAIEmbedder

        return OpenAIEmbedder()
    if cleaned.startswith("text-embedding-"):
        from .embeddings import OpenAIEmbedder

        return OpenAIEmbedder(model=cleaned)
    return detect_embedder()


async def reembed_attachment(
    attachment_id: str,
    *,
    embedder: Embedder | None = None,
    embedder_name: str | None = None,
    store: AttachmentStore | None = None,
    session_id: str | None = None,
) -> ReembedResult:
    """Re-embed every chunk for ``attachment_id`` with a fresh
    (or explicitly-named) embedder.

    Use cases:

    - **Promote to OpenAI**: a thread was indexed with the
      offline ``HashEmbedder``; once the operator pastes an
      OpenAI key into the vault they want to upgrade existing
      attachments to ``text-embedding-3-small`` without
      re-uploading.
    - **Retire a model**: switch every chunk from a deprecated
      ``-3-small`` to ``-3-large`` for higher recall.
    - **Forced refresh**: same model name, but pricing tables
      changed and the operator wants the cost ledger to record
      the spend under the current rate.

    Args:
        attachment_id: target attachment id.
        embedder: explicit embedder instance (mutually exclusive
            with ``embedder_name``).
        embedder_name: short name (``openai`` / ``hash``) or a
            specific OpenAI model id.
        store: explicit store override (tests).
        session_id: optional session id for the meeet trace
            scope.

    Returns:
        :class:`ReembedResult`. ``ok=False`` when the attachment
        is missing (``error="attachment_not_found"``) or when
        there are no chunks to re-embed
        (``error="no_chunks"``). Never raises on bad operator
        input — returns the structured error instead.
    """

    store = store or get_attachment_store()
    record = await store.get_attachment(attachment_id)
    if record is None:
        return ReembedResult(
            ok=False,
            attachment_id=attachment_id,
            error="attachment_not_found",
        )

    chunks = await store.list_chunks(
        record.thread_id, attachment_id=attachment_id
    )
    if not chunks:
        return ReembedResult(
            ok=False,
            attachment_id=attachment_id,
            error="no_chunks",
            detail=(
                "attachment has no chunks to re-embed; ingest may "
                "have produced extract_pending or zero text"
            ),
            previous_model=record.embedding_id,
        )

    if embedder is not None and embedder_name is not None:
        return ReembedResult(
            ok=False,
            attachment_id=attachment_id,
            error="embedder_args_conflict",
            detail=(
                "pass either an embedder instance or an "
                "embedder_name, not both"
            ),
        )
    chosen = embedder or _resolve_embedder_by_name(embedder_name)

    previous_model = record.embedding_id
    new_chunks: list[Chunk] = []
    embed_tokens = 0
    embedding_model: str | None = None
    embedding_dim: int | None = None

    with trace_scope(session=session_id, route="edge") as trace_id:
        try:
            if _is_cloud_embedder(chosen):
                set_route("cloud")
            result = await chosen.embed([c.text or "" for c in chunks])
            vectors = result.vectors
            embedding_model = result.model
            embedding_dim = result.dim or (
                len(vectors[0]) if vectors else None
            )
            embed_tokens = result.tokens_used or sum(
                max(1, len((c.text or "")) // 4) for c in chunks
            )
        except Exception as exc:
            client = get_client()
            await client.emit(
                "attachment.reembedded",
                {
                    "attachment_id": attachment_id,
                    "thread_id": record.thread_id,
                    "ok": False,
                    "error": "embedder_failed",
                    "detail": str(exc),
                    "trace_id": trace_id,
                },
            )
            return ReembedResult(
                ok=False,
                attachment_id=attachment_id,
                previous_model=previous_model,
                error="embedder_failed",
                detail=str(exc),
            )

        now = time.time()
        for chunk, vector in zip(chunks, vectors):
            new_chunks.append(
                Chunk(
                    id=chunk.id,
                    attachment_id=chunk.attachment_id,
                    thread_id=chunk.thread_id,
                    ord=chunk.ord,
                    text=chunk.text,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    heading=chunk.heading,
                    page=chunk.page,
                    embedding_model=embedding_model,
                    embedding_dim=embedding_dim,
                    embedding=vector,
                    tokens_in=chunk.tokens_in,
                    created_at=now,
                )
            )
        await store.replace_chunks(
            attachment_id, record.thread_id, new_chunks
        )

        # Stamp the new model on the attachment row so the cockpit
        # can render "indexed via <model>" without reading chunks.
        record = AttachmentRecord(
            **{
                **record.__dict__,
                "embedding_id": embedding_model,
                "status": "ready",
            }
        )
        await store.upsert_attachment(record)

        cost_usd = _embedder_cost_usd(embedding_model, embed_tokens)

        client = get_client()
        await client.emit(
            "attachment.reembedded",
            {
                "attachment_id": attachment_id,
                "thread_id": record.thread_id,
                "previous_model": previous_model,
                "embedding_model": embedding_model,
                "embedding_dim": embedding_dim,
                "chunk_count": len(new_chunks),
                "tokens_used": embed_tokens,
                "cost_usd": cost_usd,
                "trace_id": trace_id,
                "route": current_route(),
                "ok": True,
            },
        )
        if embedding_model and embed_tokens > 0 and cost_usd > 0:
            await client.emit(
                "usage.tokens",
                {
                    "model": embedding_model,
                    "tokens_in": embed_tokens,
                    "tokens_out": 0,
                    "latency_ms": 0.0,
                    "cost_usd": cost_usd,
                    "topic": "attachment.reembed",
                    "thread_id": record.thread_id,
                },
            )

    return ReembedResult(
        ok=True,
        attachment_id=attachment_id,
        chunk_count=len(new_chunks),
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        tokens_used=embed_tokens,
        cost_usd=cost_usd,
        previous_model=previous_model,
    )


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
