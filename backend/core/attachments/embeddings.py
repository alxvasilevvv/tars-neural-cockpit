"""Embedders — real OpenAI vectors with deterministic offline fallback.

Two implementations:

- :class:`OpenAIEmbedder` calls the OpenAI ``text-embedding-3-small``
  (or ``text-embedding-3-large``) endpoint via stdlib ``urllib`` —
  same pattern as the chat voices. Returns 1536-dim float32 vectors
  by default. Configurable via:
  ``TARS_OPENAI_EMBEDDING_MODEL`` and the existing
  ``TARS_OPENAI_API_KEY`` / ``OPENAI_API_KEY`` vault keys.

- :class:`HashEmbedder` is a deterministic hash-bigram embedder that
  lets the whole pipeline work offline. It produces sparse 384-dim
  vectors; quality is closer to keyword search than semantic, but
  retrieval still works (cosine over hashed bigrams ≈ trigram-Jaccard
  on small corpora). No deps.

:func:`detect_embedder` chooses the best one available — same pattern
as :func:`backend.core.chat.voices.detect_chat_voice`.

Vectors are returned as ``list[float]`` (float32 precision) so the
caller can serialise them however it likes; the chunk store packs
them as raw little-endian float32 blobs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import struct
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from backend.core.vault import get_secret


log = logging.getLogger("tars.embeddings")


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dim: int
    tokens_used: int = 0


class Embedder(ABC):
    """Embedders take batches of strings and return float vectors."""

    model: str
    dim: int

    @abstractmethod
    async def is_available(self) -> bool:  # pragma: no cover - abstract
        ...

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:  # pragma: no cover
        ...


# ---------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------

_OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbedder(Embedder):
    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_s: float = 30.0,
        max_batch: int = 64,
    ) -> None:
        self.model = (
            model
            or os.getenv("TARS_OPENAI_EMBEDDING_MODEL")
            or "text-embedding-3-small"
        )
        self.timeout_s = timeout_s
        self.max_batch = max_batch
        # text-embedding-3-small = 1536, -3-large = 3072. Resolved
        # lazily after first call by reading the response shape.
        self.dim = 1536

    async def is_available(self) -> bool:
        return bool(get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY"))

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        key = get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("openai_key_missing")

        vectors: list[list[float]] = []
        tokens = 0
        for batch in _chunks(list(texts), self.max_batch):
            body = {"model": self.model, "input": list(batch)}
            req = urllib.request.Request(
                _OPENAI_EMBEDDINGS_URL,
                data=json.dumps(body).encode("utf-8"),
                method="POST",
                headers={
                    "authorization": f"Bearer {key}",
                    "content-type": "application/json",
                    "accept": "application/json",
                },
            )

            def _post() -> dict:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            try:
                data = await asyncio.to_thread(_post)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                log.warning("openai embeddings failed: %s", exc)
                raise
            for item in data.get("data") or []:
                emb = item.get("embedding")
                if emb:
                    vectors.append([float(x) for x in emb])
            usage = data.get("usage") or {}
            tokens += int(usage.get("total_tokens") or 0)
        if vectors:
            self.dim = len(vectors[0])
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            dim=self.dim,
            tokens_used=tokens,
        )


# ---------------------------------------------------------------------
# Offline hash embedder
# ---------------------------------------------------------------------


_HASH_DIM = 384
_BIGRAM_RE = None  # not used; we tokenise by lowercase word bigrams


class HashEmbedder(Embedder):
    """Deterministic hash-bigram embedder — works fully offline.

    Each text is tokenised into lowercase word bigrams; each bigram
    hashes into one of ``dim`` buckets and increments that bucket.
    Vectors are L2-normalised so cosine similarity is meaningful.
    """

    def __init__(self, *, dim: int = _HASH_DIM) -> None:
        self.model = f"tars-hash-bigram-v1-d{dim}"
        self.dim = int(dim)

    async def is_available(self) -> bool:
        return True

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(_hash_embed_one(text, self.dim))
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            dim=self.dim,
            tokens_used=sum(_approx_tokens(t) for t in texts),
        )


def _hash_embed_one(text: str, dim: int) -> list[float]:
    if not text or not text.strip():
        return [0.0] * dim
    tokens = [t for t in _tokenise(text) if t]
    bigrams = list(zip(tokens, tokens[1:])) if len(tokens) > 1 else [(t, "") for t in tokens]
    vec = [0.0] * dim
    for a, b in bigrams:
        h = _bucket(f"{a}|{b}", dim)
        vec[h] += 1.0
        # Also fold each unigram so single-word queries still hit.
        for tok in (a, b):
            if tok:
                vec[_bucket(tok, dim)] += 0.5
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _tokenise(text: str) -> list[str]:
    out: list[str] = []
    cur = []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


def _bucket(key: str, dim: int) -> int:
    digest = hashlib.blake2s(key.encode("utf-8"), digest_size=4).digest()
    return struct.unpack("<I", digest)[0] % dim


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _chunks(items: list[str], n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------


def detect_embedder() -> Embedder:
    """Pick the best embedder reachable right now.

    Pinned via ``TARS_EMBEDDER`` env (``openai`` / ``hash``) — useful
    in tests + offline dev so the cockpit doesn't burn API credits.
    """

    pinned = (os.getenv("TARS_EMBEDDER") or "").strip().lower()
    if pinned == "openai":
        return OpenAIEmbedder()
    if pinned == "hash":
        return HashEmbedder()
    if get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY"):
        return OpenAIEmbedder()
    return HashEmbedder()
