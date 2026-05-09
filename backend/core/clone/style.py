"""Style trait store + draft suggester (Wave 73 Feature 4 internals).

Schema lives at ``~/.tars/clone.sqlite`` (override via
``TARS_CLONE_DB_PATH``; ``CLONE_STORE=disabled`` short-circuits the
whole module). One row per operator message we've seen, columns for:

- raw text + char + word + sentence count
- exclamation / question / casual / formal counts (heuristics)
- embedding blob (float32) when an embedder is reachable
- created_at

The :func:`profile` function rolls the last N (default 500) rows
into a snapshot. :func:`draft` uses cosine similarity (or
hash-trigram bag overlap when no embedder exists) to pick the K
most-similar past messages, then asks the chat LLM to rewrite the
caller's prompt in the operator's voice.

All paths are best-effort: missing keys, missing embedder, disabled
store — none of those crash the chat write path that calls us.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import sqlite3
import struct
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.core.attachments.embeddings import Embedder, detect_embedder
from backend.core.vault import get_secret


log = logging.getLogger("tars.clone.style")


_DEFAULT_DB = Path.home() / ".tars" / "clone.sqlite"
_VERSION = "0.1"
_PROFILE_WINDOW = 500
_TOP_K = 5

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DRAFT_TIMEOUT_S = 20.0


_SENTENCE_END_RE = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_CASUAL_TOKENS = {
    "lol", "lmao", "haha", "yeah", "yep", "nope", "gonna", "wanna",
    "ya", "btw", "imo", "tbh", "ngl", "ok", "kinda", "sorta",
}
_FORMAL_TOKENS = {
    "however", "therefore", "moreover", "furthermore", "consequently",
    "nevertheless", "regards", "sincerely", "thus", "hence",
}
_STOPWORDS = {
    "the", "and", "for", "you", "with", "this", "that", "have",
    "from", "your", "are", "but", "not", "can", "all", "was", "they",
    "what", "when", "where", "who", "how", "which", "would", "could",
    "should", "about", "into", "just", "like", "want", "need", "make",
    "more", "than", "then", "also", "been", "were", "very", "much",
    "still", "only", "even", "there", "here", "some", "other", "thing",
    "things", "okay", "well", "really", "going", "didnt", "dont",
    "lets", "think", "know", "thanks", "tars", "operator", "user",
    "assistant", "system", "message", "text", "him", "her", "his",
    "she", "him",
}


def _is_disabled() -> bool:
    raw = (os.getenv("CLONE_STORE") or "").strip().lower()
    return raw in {"disabled", "off", "0", "no", "false"}


def _resolve_db_path() -> Optional[Path]:
    if _is_disabled():
        return None
    override = os.getenv("TARS_CLONE_DB_PATH")
    return Path(override) if override else _DEFAULT_DB


_SCHEMA = """
CREATE TABLE IF NOT EXISTS style_traits (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    chars INTEGER NOT NULL,
    words INTEGER NOT NULL,
    sentences INTEGER NOT NULL,
    exclaim INTEGER NOT NULL,
    question INTEGER NOT NULL,
    casual INTEGER NOT NULL,
    formal INTEGER NOT NULL,
    embedding BLOB,
    embed_model TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_style_traits_created ON style_traits(created_at);
"""


@dataclass
class StyleProfile:
    version: str = _VERSION
    sample_count: int = 0
    avg_sentence_length: float = 0.0
    avg_message_length_words: float = 0.0
    exclamation_rate: float = 0.0  # exclaim / sentences
    question_rate: float = 0.0
    casual_score: float = 0.0  # casual_tokens / words
    formal_score: float = 0.0
    casual_vs_formal: str = "neutral"  # casual | neutral | formal
    top_vocab: list[str] = field(default_factory=list)
    embedded_share: float = 0.0
    last_message_at: Optional[float] = None
    note: str = (
        "v0.1 — style hint, not full clone. Heuristic metrics over the "
        "operator's last 500 messages."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack_vector(blob: bytes) -> list[float]:
    if not blob:
        return []
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def _hash_trigram_bag(text: str) -> Counter:
    norm = "".join(c.lower() if c.isalnum() else " " for c in text)
    parts = norm.split()
    bag: Counter = Counter()
    for p in parts:
        for i in range(len(p) - 2):
            bag[p[i : i + 3]] += 1
    return bag


def _bag_cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


class CloneStore:
    """Thin sqlite wrapper. All async via ``asyncio.to_thread``."""

    def __init__(self, *, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or _resolve_db_path()
        self.enabled = self.db_path is not None
        if self.enabled:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._init_schema()
            except Exception as exc:
                log.warning("clone store init failed: %s", exc)
                self.enabled = False

    def _connect(self) -> sqlite3.Connection:
        assert self.db_path
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # --- writes -----------------------------------------------------

    def _insert_sync(
        self,
        *,
        text: str,
        metrics: dict[str, int],
        embedding: list[float] | None,
        embed_model: str | None,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO style_traits
                (id, text, chars, words, sentences, exclaim, question,
                 casual, formal, embedding, embed_model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"st_{uuid.uuid4().hex[:14]}",
                    text[:4000],
                    metrics["chars"],
                    metrics["words"],
                    metrics["sentences"],
                    metrics["exclaim"],
                    metrics["question"],
                    metrics["casual"],
                    metrics["formal"],
                    _pack_vector(embedding) if embedding else None,
                    embed_model,
                    time.time(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def insert(
        self,
        *,
        text: str,
        metrics: dict[str, int],
        embedding: list[float] | None = None,
        embed_model: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        await asyncio.to_thread(
            self._insert_sync,
            text=text,
            metrics=metrics,
            embedding=embedding,
            embed_model=embed_model,
        )

    # --- reads ------------------------------------------------------

    def _list_sync(self, *, limit: int) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM style_traits ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return list(rows)
        finally:
            conn.close()

    async def recent(self, *, limit: int = _PROFILE_WINDOW) -> list[sqlite3.Row]:
        if not self.enabled:
            return []
        return await asyncio.to_thread(self._list_sync, limit=limit)


_store_singleton: CloneStore | None = None


def get_clone_store() -> CloneStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = CloneStore()
    return _store_singleton


def reset_clone_store() -> None:
    global _store_singleton
    _store_singleton = None


# ---------- metric extraction ------------------------------------------


def _metrics(text: str) -> dict[str, int]:
    chars = len(text)
    words = _WORD_RE.findall(text)
    sentence_split = [s for s in _SENTENCE_END_RE.split(text) if s.strip()]
    sentences = max(1, len(sentence_split))
    exclaim = text.count("!")
    question = text.count("?")
    lower = text.lower()
    casual = sum(1 for t in _CASUAL_TOKENS if t in lower)
    formal = sum(1 for t in _FORMAL_TOKENS if t in lower)
    return {
        "chars": chars,
        "words": len(words),
        "sentences": sentences,
        "exclaim": exclaim,
        "question": question,
        "casual": casual,
        "formal": formal,
    }


# ---------- public API ------------------------------------------------


async def record_message(text: str) -> bool:
    """Record one operator message into the style store.

    Returns True iff a row was written. Never raises.
    """

    text = (text or "").strip()
    if not text or len(text) < 4:
        return False
    store = get_clone_store()
    if not store.enabled:
        return False
    metrics = _metrics(text)
    embedding: list[float] | None = None
    embed_model: str | None = None
    try:
        emb = detect_embedder()
        if await emb.is_available():
            res = await emb.embed([text])
            if res.vectors:
                embedding = res.vectors[0]
                embed_model = res.model
    except Exception as exc:
        log.debug("clone embed skip: %s", exc)
    try:
        await store.insert(
            text=text, metrics=metrics,
            embedding=embedding, embed_model=embed_model,
        )
        return True
    except Exception as exc:
        log.warning("clone insert failed: %s", exc)
        return False


async def profile() -> StyleProfile:
    """Roll the last N rows into a :class:`StyleProfile`."""

    store = get_clone_store()
    if not store.enabled:
        return StyleProfile(note="clone store disabled (CLONE_STORE=disabled)")
    rows = await store.recent(limit=_PROFILE_WINDOW)
    if not rows:
        return StyleProfile(note="no operator messages recorded yet — talk to TARS to seed the v0.1 clone")

    n = len(rows)
    total_words = sum(r["words"] for r in rows)
    total_sents = sum(r["sentences"] for r in rows)
    total_exclaim = sum(r["exclaim"] for r in rows)
    total_question = sum(r["question"] for r in rows)
    total_casual = sum(r["casual"] for r in rows)
    total_formal = sum(r["formal"] for r in rows)
    embedded = sum(1 for r in rows if r["embedding"])

    avg_sent_len = (total_words / total_sents) if total_sents else 0.0
    avg_msg_words = total_words / n
    excl_rate = total_exclaim / total_sents if total_sents else 0.0
    q_rate = total_question / total_sents if total_sents else 0.0
    casual_score = total_casual / total_words if total_words else 0.0
    formal_score = total_formal / total_words if total_words else 0.0

    if casual_score > formal_score * 1.5 and casual_score > 0.005:
        cvf = "casual"
    elif formal_score > casual_score * 1.5 and formal_score > 0.005:
        cvf = "formal"
    else:
        cvf = "neutral"

    # top vocab over the window
    vocab: Counter = Counter()
    for r in rows:
        for w in _WORD_RE.findall(r["text"]):
            wl = w.lower()
            if len(wl) >= 4 and wl not in _STOPWORDS:
                vocab[wl] += 1

    return StyleProfile(
        version=_VERSION,
        sample_count=n,
        avg_sentence_length=round(avg_sent_len, 2),
        avg_message_length_words=round(avg_msg_words, 2),
        exclamation_rate=round(excl_rate, 4),
        question_rate=round(q_rate, 4),
        casual_score=round(casual_score, 4),
        formal_score=round(formal_score, 4),
        casual_vs_formal=cvf,
        top_vocab=[w for w, _ in vocab.most_common(50)],
        embedded_share=round(embedded / n, 3),
        last_message_at=rows[0]["created_at"] if rows else None,
    )


async def _nearest_examples(query: str, *, k: int) -> list[str]:
    store = get_clone_store()
    if not store.enabled:
        return []
    rows = await store.recent(limit=_PROFILE_WINDOW)
    if not rows:
        return []

    # Try embedding similarity first; fall back to hash-trigram bag.
    qvec: list[float] | None = None
    try:
        emb = detect_embedder()
        if await emb.is_available():
            res = await emb.embed([query])
            qvec = res.vectors[0] if res.vectors else None
    except Exception:
        qvec = None

    scored: list[tuple[float, str]] = []
    if qvec is not None:
        for r in rows:
            blob = r["embedding"]
            if not blob:
                continue
            v = _unpack_vector(blob)
            scored.append((_cosine(qvec, v), r["text"]))
    if not scored:
        # fallback path
        qbag = _hash_trigram_bag(query)
        for r in rows:
            scored.append((_bag_cosine(qbag, _hash_trigram_bag(r["text"])), r["text"]))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [text for _, text in scored[:k]]


def _resolve_anthropic_key() -> str | None:
    return get_secret("TARS_ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_API_KEY")


def _resolve_openai_key() -> str | None:
    return get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout_s: float) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


async def _llm_rewrite(*, context: str, examples: list[str], style: StyleProfile) -> str | None:
    """Ask an LLM to draft a reply in the operator's voice."""

    if not examples:
        return None
    style_hint = (
        f"Style profile (v{style.version}): "
        f"avg sentence ≈ {style.avg_sentence_length} words; "
        f"register {style.casual_vs_formal}; "
        f"exclamation_rate={style.exclamation_rate}; "
        f"question_rate={style.question_rate}; "
        f"top vocab: {', '.join(style.top_vocab[:15]) or '(none)'}."
    )
    examples_block = "\n---\n".join(
        f"Example {i + 1}:\n{ex[:400]}" for i, ex in enumerate(examples)
    )
    prompt = (
        "You are TARS's AI Clone v0.1. Draft what the operator would "
        "likely say next, given the context. Match the cadence and "
        "vocabulary in the examples — do not invent a new voice.\n\n"
        f"{style_hint}\n\n"
        f"Past examples (most-similar first):\n{examples_block}\n\n"
        f"Context the operator is responding to:\n{context}\n\n"
        "Reply with the draft only — no preamble, no quotes."
    )

    a_key = _resolve_anthropic_key()
    if a_key:
        body = {
            "model": os.getenv("TARS_ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": a_key,
        }
        try:
            payload = await asyncio.to_thread(
                _post_json, _ANTHROPIC_URL, body, headers, _DRAFT_TIMEOUT_S
            )
            content = payload.get("content")
            if isinstance(content, list):
                text = "".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if text.strip():
                    return text.strip()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("clone draft anthropic fail: %s", exc)

    o_key = _resolve_openai_key()
    if o_key:
        body = {
            "model": os.getenv("TARS_OPENAI_MODEL") or "gpt-4o-mini",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {o_key}",
        }
        try:
            payload = await asyncio.to_thread(
                _post_json, _OPENAI_URL, body, headers, _DRAFT_TIMEOUT_S
            )
            choices = payload.get("choices") or []
            if choices:
                msg = (choices[0] or {}).get("message") or {}
                text = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(text, str) and text.strip():
                    return text.strip()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("clone draft openai fail: %s", exc)
    return None


async def draft(*, context: str, k: int = _TOP_K) -> dict[str, Any]:
    """Draft a "what would the operator say" reply for ``context``.

    Returns ``{ok, draft, examples_used, profile, version, ...}``.
    Falls back to "echo the most-similar example" when no LLM key
    is configured.
    """

    examples = await _nearest_examples(context or "", k=max(1, min(k, 10)))
    style = await profile()
    if not examples:
        return {
            "ok": False,
            "version": _VERSION,
            "reason": "no_seed_messages",
            "draft": None,
            "examples_used": 0,
            "profile": style.to_dict(),
        }

    draft_text = await _llm_rewrite(context=context, examples=examples, style=style)
    fallback = False
    if not draft_text:
        # Honest fallback: surface the closest past message verbatim.
        draft_text = examples[0]
        fallback = True

    return {
        "ok": True,
        "version": _VERSION,
        "draft": draft_text,
        "fallback": fallback,
        "examples_used": len(examples),
        "examples_preview": [ex[:200] for ex in examples],
        "profile": style.to_dict(),
    }
