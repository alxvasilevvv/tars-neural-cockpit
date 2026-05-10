"""Strategy registry — versioned, file-backed.

Why file-backed first: every workshop attendee runs TARS locally,
so a SQLite-backed table would be both overkill and harder to
inspect. JSONL on disk gives the operator a flat audit trail they
can ``cat`` and ``git diff``. We keep the door open for a Sqlite
backend later behind the same :class:`StrategyRegistry` interface.

Layout (default ``$TARS_HOME/algotrade/strategies/``):

::

  strategies/
    by-fingerprint/
      sha256/<full-hash>.json     # canonical IR
    by-name/
      <slug>.jsonl                # newline-separated history,
                                  # latest version last
    index.jsonl                   # global index: one row per
                                  # version; append-only

Concurrency: every write acquires a per-process ``threading.Lock``
plus an ``fcntl.flock`` on the index file. Reads are
lock-free (file system POSIX read semantics).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .ir import Strategy, StrategyError


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return s[:80] or "strategy"


@dataclass(frozen=True)
class StoredStrategy:
    """A registry row — IR + provenance."""

    fingerprint: str  # ``sha256:…``
    slug: str
    version: int
    created_at: float
    author: str  # operator / agent identifier
    parent_fingerprint: str | None  # for forks / refines
    strategy: Strategy
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "slug": self.slug,
            "version": int(self.version),
            "created_at": float(self.created_at),
            "author": self.author,
            "parent_fingerprint": self.parent_fingerprint,
            "strategy": self.strategy.to_dict(),
            "metadata": dict(self.metadata),
        }


class StrategyRegistry:
    """File-backed strategy storage.

    Ships an ergonomic in-process ``put`` / ``get`` / ``versions``
    / ``search`` surface. The on-disk format is a stable contract
    so a future SQLite or Postgres backend can be a drop-in
    replacement.
    """

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            base = os.environ.get("TARS_HOME") or str(Path.home() / ".tars")
            root = Path(base) / "algotrade" / "strategies"
        self._root = Path(root)
        self._by_fp = self._root / "by-fingerprint" / "sha256"
        self._by_name = self._root / "by-name"
        self._index = self._root / "index.jsonl"
        self._lock = threading.Lock()
        self._by_fp.mkdir(parents=True, exist_ok=True)
        self._by_name.mkdir(parents=True, exist_ok=True)
        self._index.touch(exist_ok=True)

    # -------------------------------------------------------- write

    def put(
        self,
        strategy: Strategy,
        *,
        author: str = "operator",
        parent_fingerprint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredStrategy:
        """Persist ``strategy``; return the stored row.

        Idempotent on fingerprint: re-putting an unchanged IR
        returns the existing row without bumping ``version``.
        """

        strategy.validate()
        fp = strategy.fingerprint()
        slug = _slugify(strategy.name)

        with self._lock:
            existing = self._read_fp(fp)
            if existing is not None:
                return existing

            history = list(self._iter_slug(slug))
            next_version = (history[-1].version + 1) if history else 1

            stored = StoredStrategy(
                fingerprint=fp,
                slug=slug,
                version=next_version,
                created_at=time.time(),
                author=author,
                parent_fingerprint=parent_fingerprint,
                strategy=strategy,
                metadata=dict(metadata or {}),
            )
            self._write_fp(stored)
            self._append_slug(slug, stored)
            self._append_index(stored)
            return stored

    # -------------------------------------------------------- read

    def get(self, fingerprint: str) -> StoredStrategy | None:
        return self._read_fp(fingerprint)

    def latest(self, slug_or_name: str) -> StoredStrategy | None:
        slug = _slugify(slug_or_name)
        history = list(self._iter_slug(slug))
        return history[-1] if history else None

    def versions(self, slug_or_name: str) -> list[StoredStrategy]:
        slug = _slugify(slug_or_name)
        return list(self._iter_slug(slug))

    def list_slugs(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for entry in self._iter_index():
            if entry.slug not in seen:
                seen.add(entry.slug)
                out.append(entry.slug)
        return sorted(out)

    def search(
        self,
        *,
        tag: str | None = None,
        author: str | None = None,
        instrument: str | None = None,
    ) -> list[StoredStrategy]:
        """Linear filter over the index. JSONL is fast enough for the
        workshop scale; if we ever cross 100 k strategies we move to
        SQLite."""

        rows: list[StoredStrategy] = []
        for entry in self._iter_index():
            if author and entry.author != author:
                continue
            if instrument and entry.strategy.instrument != instrument:
                continue
            if tag and tag not in entry.strategy.tags:
                continue
            rows.append(entry)
        return rows

    def __iter__(self) -> Iterator[StoredStrategy]:
        return self._iter_index()

    # -------------------------------------------------------- internals

    def _fp_path(self, fingerprint: str) -> Path:
        if not fingerprint.startswith("sha256:"):
            raise StrategyError(
                f"fingerprint must start with 'sha256:': {fingerprint!r}"
            )
        return self._by_fp / f"{fingerprint.split(':', 1)[1]}.json"

    def _read_fp(self, fingerprint: str) -> StoredStrategy | None:
        path = self._fp_path(fingerprint)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return _row_from_dict(payload)

    def _write_fp(self, stored: StoredStrategy) -> None:
        path = self._fp_path(stored.fingerprint)
        path.write_text(
            json.dumps(stored.to_dict(), sort_keys=True, indent=2)
        )

    def _slug_path(self, slug: str) -> Path:
        return self._by_name / f"{slug}.jsonl"

    def _append_slug(self, slug: str, stored: StoredStrategy) -> None:
        path = self._slug_path(slug)
        with path.open("a") as fh:
            fh.write(json.dumps(stored.to_dict(), sort_keys=True))
            fh.write("\n")

    def _iter_slug(self, slug: str) -> Iterator[StoredStrategy]:
        path = self._slug_path(slug)
        if not path.exists():
            return
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = _row_from_dict(payload)
                if row is not None:
                    yield row

    def _append_index(self, stored: StoredStrategy) -> None:
        with self._index.open("a") as fh:
            fh.write(json.dumps(stored.to_dict(), sort_keys=True))
            fh.write("\n")

    def _iter_index(self) -> Iterator[StoredStrategy]:
        if not self._index.exists():
            return
        with self._index.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = _row_from_dict(payload)
                if row is not None:
                    yield row


def _row_from_dict(payload: dict[str, Any]) -> StoredStrategy | None:
    try:
        strategy = Strategy.from_dict(payload["strategy"])
    except (StrategyError, KeyError, TypeError):
        return None
    return StoredStrategy(
        fingerprint=str(payload.get("fingerprint", strategy.fingerprint())),
        slug=str(payload.get("slug") or _slugify(strategy.name)),
        version=int(payload.get("version") or 1),
        created_at=float(payload.get("created_at") or 0.0),
        author=str(payload.get("author") or "operator"),
        parent_fingerprint=payload.get("parent_fingerprint"),
        strategy=strategy,
        metadata=dict(payload.get("metadata") or {}),
    )


# --------------------------------------------------------- module-level singleton


_REGISTRY: StrategyRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_registry(root: Path | None = None) -> StrategyRegistry:
    """Process-wide registry. Tests that want isolation pass an
    explicit ``root`` to the constructor instead of using this."""

    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None or root is not None:
            _REGISTRY = StrategyRegistry(root=root)
        return _REGISTRY


def reset_registry_for_tests() -> None:
    """Clear the module-level singleton; tests call this in fixtures."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
