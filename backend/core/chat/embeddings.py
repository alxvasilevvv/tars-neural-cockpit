"""Embed pending chat messages so they can fuse into hybrid search.

The L2 attachment retrieval already pairs FTS5 (BM25) with vector
cosine; this module is the equivalent for the ``messages`` table. The
contract:

- ``ChatStore.set_message_embedding`` persists ``(model, dim, blob)``
  on the message row.
- ``ChatStore.list_messages_pending_embedding`` walks rows whose
  ``embedding_blob`` is null.
- :func:`embed_pending_messages` batches them through whatever
  :class:`Embedder` is reachable, swallowing per-batch failures so a
  flapping upstream cannot starve the loop.

The endpoint and the future ``_message_embed_loop`` (not part of this
slice) call into the same helper. The search path uses the embeddings
opportunistically — if a message is missing one, the hybrid fuse
silently falls back to keyword-only.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.attachments.embeddings import Embedder, detect_embedder
from backend.core.chat.store import ChatStore, get_chat_store


log = logging.getLogger("tars.chat.embeddings")


_DEFAULT_BATCH = 32
_DEFAULT_LIMIT = 200


async def embed_pending_messages(
    *,
    chat: ChatStore | None = None,
    embedder: Embedder | None = None,
    limit: int = _DEFAULT_LIMIT,
    batch_size: int = _DEFAULT_BATCH,
) -> dict[str, Any]:
    """Embed up to ``limit`` pending messages and persist the vectors.

    Returns a stats dict:
    ``{ok, embedded, skipped, failed, batches, total_pending,
       remaining, model}``. ``ok`` is False only when the embedder is
    not reachable (no API key, no fallback). All per-batch failures
    surface as ``failed`` counts, never as raised exceptions.
    """

    chat = chat or get_chat_store()
    if not chat.enabled:
        return {"ok": False, "reason": "chat_store_disabled"}

    embedder = embedder or detect_embedder()
    available = await embedder.is_available()
    if not available:
        remaining = await chat.count_messages_pending_embedding()
        return {
            "ok": False,
            "reason": "embedder_unavailable",
            "embedder": embedder.model,
            "remaining": remaining,
        }

    pending = await chat.list_messages_pending_embedding(limit=limit)
    if not pending:
        return {
            "ok": True,
            "embedded": 0,
            "skipped": 0,
            "failed": 0,
            "batches": 0,
            "total_pending": 0,
            "remaining": 0,
            "model": embedder.model,
        }

    embedded = 0
    skipped = 0
    failed = 0
    batches = 0
    bs = max(1, min(int(batch_size), 256))

    for start in range(0, len(pending), bs):
        batch = pending[start : start + bs]
        texts: list[str] = []
        targets: list[str] = []
        for msg in batch:
            text = (msg.content or "").strip()
            if not text:
                skipped += 1
                continue
            texts.append(text)
            targets.append(msg.id)
        if not texts:
            continue
        batches += 1
        try:
            res = await embedder.embed(texts)
        except Exception as exc:
            log.warning("message embed batch failed: %s", exc)
            failed += len(targets)
            continue
        if not res.vectors or len(res.vectors) != len(targets):
            failed += len(targets)
            continue
        for msg_id, vec in zip(targets, res.vectors):
            if not vec:
                skipped += 1
                continue
            try:
                await chat.set_message_embedding(
                    msg_id,
                    model=res.model or embedder.model,
                    dim=res.dim or len(vec),
                    vector=vec,
                )
                embedded += 1
            except Exception as exc:
                log.warning("set_message_embedding failed for %s: %s", msg_id, exc)
                failed += 1

    remaining = await chat.count_messages_pending_embedding()
    return {
        "ok": True,
        "embedded": embedded,
        "skipped": skipped,
        "failed": failed,
        "batches": batches,
        "total_pending": len(pending),
        "remaining": remaining,
        "model": embedder.model,
    }
