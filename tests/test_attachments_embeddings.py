"""Embedder tests — focus on the offline hash embedder + detection.

The OpenAI path is exercised by mocking ``urllib.request.urlopen`` to
avoid burning credits during CI.
"""

from __future__ import annotations

import asyncio
import io
import json
from unittest.mock import patch

import pytest

from backend.core.attachments.embeddings import (
    HashEmbedder,
    OpenAIEmbedder,
    detect_embedder,
)


def _run(coro):
    return asyncio.run(coro)


def test_hash_embedder_is_always_available() -> None:
    emb = HashEmbedder()
    assert _run(emb.is_available())
    assert emb.dim == 384
    assert emb.model.startswith("tars-hash-bigram")


def test_hash_embedder_returns_normalised_vectors() -> None:
    emb = HashEmbedder()
    res = _run(emb.embed(["alpha beta gamma", "alpha beta delta"]))
    assert res.dim == 384
    assert len(res.vectors) == 2
    for v in res.vectors:
        norm = sum(x * x for x in v) ** 0.5
        assert 0.99 <= norm <= 1.01


def test_hash_embedder_similar_texts_have_high_cosine() -> None:
    emb = HashEmbedder()
    res = _run(
        emb.embed(
            [
                "EMEA conversion blockers",
                "EMEA conversion problems",
                "the cat sat on the mat",
            ]
        )
    )
    a, b, c = res.vectors

    def cos(x, y):
        return sum(p * q for p, q in zip(x, y))

    assert cos(a, b) > cos(a, c)


def test_hash_embedder_handles_empty_text() -> None:
    emb = HashEmbedder()
    res = _run(emb.embed(["", "ok"]))
    assert all(x == 0.0 for x in res.vectors[0])
    assert any(x != 0.0 for x in res.vectors[1])


def test_detect_embedder_respects_explicit_pin(monkeypatch) -> None:
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.delenv("TARS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    emb = detect_embedder()
    assert isinstance(emb, HashEmbedder)


def test_detect_embedder_falls_back_to_hash_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("TARS_EMBEDDER", raising=False)
    monkeypatch.delenv("TARS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Patch vault's get_secret to ensure no key is found.
    with patch("backend.core.attachments.embeddings.get_secret", return_value=None):
        emb = detect_embedder()
    assert isinstance(emb, HashEmbedder)


def test_openai_embedder_posts_to_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("TARS_OPENAI_API_KEY", "test-key")

    captured: dict = {}

    class FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = dict(req.headers)
        body = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ],
            "usage": {"total_tokens": 42},
        }
        return FakeResp(json.dumps(body).encode("utf-8"))

    with patch(
        "backend.core.attachments.embeddings.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        emb = OpenAIEmbedder(model="text-embedding-3-small")
        res = _run(emb.embed(["hello", "world"]))

    assert captured["url"].endswith("/v1/embeddings")
    assert captured["body"]["model"] == "text-embedding-3-small"
    assert captured["body"]["input"] == ["hello", "world"]
    assert "Authorization" in captured["headers"] or "authorization" in captured["headers"]
    assert res.tokens_used == 42
    assert res.dim == 3
    assert len(res.vectors) == 2
