"""Re-embed existing attachment chunks with a different model.

Why this slot exists: when an operator first installs TARS, the
embedder defaults to the offline ``HashEmbedder`` so the cockpit
works out of the box. Once they configure ``OPENAI_API_KEY`` (or
swap to a different model), every *new* attachment uses the better
embedder, but historical chunks are stuck on the old one — and
hybrid retrieval already works hit-by-hit, so the gap is silent.

This module is the *promote-on-demand* path: the operator hits an
endpoint, we re-embed the affected chunks in place, and BM25 + the
new vectors fuse going forward.

Three helpers, layered:

- :func:`reembed_chunks` — given a concrete list of :class:`Chunk`,
  run them through ``embedder`` and persist the new vectors.
- :func:`reembed_attachment` — fetch every chunk for one
  ``attachment_id`` and call :func:`reembed_chunks`.
- :func:`reembed_by_model` — find chunks whose current
  ``embedding_model`` matches ``old_model`` (with optional
  ``thread_id`` / ``limit`` scope) and re-embed them.

The functions are deliberately conservative:

- Empty / whitespace text is skipped (kept as-is, counted as
  ``skipped``).
- Per-batch failures surface as ``failed`` counts; the caller
  never sees a raised exception so a flapping upstream cannot
  starve the loop.
- The operation is idempotent — re-running with the same target
  model is a no-op for chunks already at that model unless
  ``force=True``.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from .embeddings import Embedder, detect_embedder
from .index import AttachmentStore, Chunk, get_attachment_store


log = logging.getLogger("tars.attachments.reembed")


_DEFAULT_BATCH = 32


async def reembed_chunks(
    chunks: Sequence[Chunk],
    *,
    embedder: Embedder | None = None,
    store: AttachmentStore | None = None,
    batch_size: int = _DEFAULT_BATCH,
    force: bool = False,
    target_model: str | None = None,
) -> dict[str, Any]:
    """Re-embed ``chunks`` with ``embedder`` and persist the result.

    Returns a stats dict::

        {
            ok: bool,
            embedded: int,        # chunks rewritten
            skipped_blank: int,   # chunks with blank text
            skipped_same: int,    # already at target model (force=False)
            failed: int,          # per-batch upstream failures
            batches: int,
            total: int,
            model: str,
            dim: int | None,
        }

    ``ok`` is False only when the embedder is not reachable. All
    per-batch failures surface as ``failed`` counts.
    """

    store = store or get_attachment_store()
    if not store.chat.enabled:
        return {"ok": False, "reason": "attachment_store_disabled"}
    embedder = embedder or detect_embedder()
    available = await embedder.is_available()
    if not available:
        return {
            "ok": False,
            "reason": "embedder_unavailable",
            "embedder": embedder.model,
        }

    chosen_model = target_model or embedder.model
    pending: list[Chunk] = []
    skipped_blank = 0
    skipped_same = 0
    for chunk in chunks:
        if not (chunk.text or "").strip():
            skipped_blank += 1
            continue
        if (
            not force
            and chunk.embedding_model == chosen_model
            and chunk.embedding
        ):
            skipped_same += 1
            continue
        pending.append(chunk)

    if not pending:
        return {
            "ok": True,
            "embedded": 0,
            "skipped_blank": skipped_blank,
            "skipped_same": skipped_same,
            "failed": 0,
            "batches": 0,
            "total": len(chunks),
            "model": chosen_model,
            "dim": None,
        }

    bs = max(1, min(int(batch_size), 128))
    embedded = 0
    failed = 0
    batches = 0
    final_dim: int | None = None

    for start in range(0, len(pending), bs):
        batch = pending[start : start + bs]
        texts = [c.text for c in batch]
        batches += 1
        try:
            res = await embedder.embed(texts)
        except Exception as exc:
            log.warning("reembed batch failed: %s", exc)
            failed += len(batch)
            continue
        if not res.vectors or len(res.vectors) != len(batch):
            log.warning(
                "reembed batch returned %s vectors for %s inputs",
                len(res.vectors), len(batch),
            )
            failed += len(batch)
            continue
        final_dim = res.dim or final_dim
        for chunk, vec in zip(batch, res.vectors):
            if not vec:
                failed += 1
                continue
            try:
                ok = await store.update_chunk_embedding(
                    chunk_id=chunk.id,
                    model=res.model or chosen_model,
                    dim=res.dim or len(vec),
                    vector=vec,
                )
                if ok:
                    embedded += 1
                else:
                    failed += 1
            except Exception as exc:
                log.warning(
                    "reembed persist failed for %s: %s", chunk.id, exc
                )
                failed += 1

    return {
        "ok": True,
        "embedded": embedded,
        "skipped_blank": skipped_blank,
        "skipped_same": skipped_same,
        "failed": failed,
        "batches": batches,
        "total": len(chunks),
        "model": chosen_model,
        "dim": final_dim,
    }


async def reembed_attachment(
    attachment_id: str,
    *,
    embedder: Embedder | None = None,
    store: AttachmentStore | None = None,
    force: bool = False,
    target_model: str | None = None,
) -> dict[str, Any]:
    """Re-embed every chunk attached to ``attachment_id``.

    Looks up the underlying ``thread_id`` from the attachment record
    (the chunks list is thread-scoped). Returns a stats dict from
    :func:`reembed_chunks` augmented with ``attachment_id`` and
    ``thread_id``.
    """

    store = store or get_attachment_store()
    if not store.chat.enabled:
        return {"ok": False, "reason": "attachment_store_disabled"}
    record = await store.get_attachment(attachment_id)
    if record is None:
        return {"ok": False, "reason": "attachment_not_found"}
    chunks = await store.list_chunks(
        record.thread_id, attachment_id=attachment_id
    )
    out = await reembed_chunks(
        chunks,
        embedder=embedder,
        store=store,
        force=force,
        target_model=target_model,
    )
    if out.get("ok"):
        out["attachment_id"] = attachment_id
        out["thread_id"] = record.thread_id
    return out


async def reembed_by_model(
    old_model: str,
    *,
    embedder: Embedder | None = None,
    store: AttachmentStore | None = None,
    thread_id: str | None = None,
    limit: int = 500,
    force: bool = False,
    target_model: str | None = None,
) -> dict[str, Any]:
    """Re-embed every chunk whose current ``embedding_model`` matches.

    Useful for the "promote hash → openai" workflow: pass
    ``old_model="tars-hash-bigram-v1-d384"`` and the new embedder
    runs over every chunk that's still on the offline embedder.
    The optional ``thread_id`` narrows the scope when an operator
    only wants to upgrade one conversation.
    """

    store = store or get_attachment_store()
    if not store.chat.enabled:
        return {"ok": False, "reason": "attachment_store_disabled"}
    chunks = await store.list_chunks_by_model(
        embedding_model=old_model,
        thread_id=thread_id,
        limit=max(1, min(int(limit), 5000)),
    )
    out = await reembed_chunks(
        chunks,
        embedder=embedder,
        store=store,
        force=force,
        target_model=target_model,
    )
    if out.get("ok"):
        out["old_model"] = old_model
        if thread_id is not None:
            out["thread_id"] = thread_id
    return out


__all__ = [
    "reembed_chunks",
    "reembed_attachment",
    "reembed_by_model",
]
