"""W245 — codebase indexer regression tests.

Five cases per the W245 spec:

1. Indexing an empty directory returns 0 files / 0 chunks.
2. Indexing a small fixture dir returns N files (Python + JS + MD).
3. ``search`` returns hits sorted by score (descending).
4. ``status`` reports correct file / chunk counts after an index.
5. Mention resolver ``_resolve_code`` returns hits from the indexer.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path


PY_FIXTURE = '''"""Sample helper module."""

import math


def cosine(a, b):
    """Return cosine similarity between two L2-normalised vectors."""
    return sum(x * y for x, y in zip(a, b))


def softmax(values):
    """Plain softmax for a list of floats."""
    m = max(values)
    exp = [math.exp(v - m) for v in values]
    s = sum(exp)
    return [e / s for e in exp]


class Indexer:
    """Toy class so the chunker emits more than one symbol."""

    def __init__(self, root):
        self.root = root

    def walk(self):
        yield from []
'''

JS_FIXTURE = """// Sample JS module
export function greet(name) {
  return `hello, ${name}`;
}

export const farewell = (name) => `bye, ${name}`;

class Greeter {
  constructor(prefix) { this.prefix = prefix; }
  hello(name) { return `${this.prefix}, ${name}`; }
}
"""

MD_FIXTURE = """# Welcome

This is the project README.

## Installation

Run `pip install` and start `serve.py`.

## Usage

Use the cosine helper to compute similarity between two vectors.
"""


def _build_fixture(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src" / "helpers.py").write_text(PY_FIXTURE, encoding="utf-8")
    (root / "src" / "greet.js").write_text(JS_FIXTURE, encoding="utf-8")
    (root / "docs" / "README.md").write_text(MD_FIXTURE, encoding="utf-8")


class TestCodebaseIndexer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w245-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._fixture = Path(self._tmp) / "fixture"
        self._fixture.mkdir()
        os.environ["HOME"] = str(self._home)
        os.environ["TARS_HOME"] = str(self._home / ".tars")
        os.environ["TARS_CODEBASE_DB_PATH"] = str(
            self._home / ".tars" / "codebase.sqlite"
        )

        # Wipe any in-process state from a previous test in the same
        # process — the module-level dicts survive across cases.
        from backend.core import codebase as cb

        cb.reset_for_tests()
        # Belt-and-braces: drop a stale DB if one survived a prior run.
        try:
            os.remove(os.environ["TARS_CODEBASE_DB_PATH"])
        except FileNotFoundError:
            pass
        self.cb = cb

    def tearDown(self) -> None:
        try:
            self.cb.reset_for_tests()
        except Exception:
            pass
        for k in ("TARS_CODEBASE_DB_PATH", "TARS_HOME"):
            os.environ.pop(k, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ---- 1: empty dir -----------------------------------------------------

    def test_index_empty_dir_returns_zero(self) -> None:
        empty = Path(self._tmp) / "empty"
        empty.mkdir()
        out = self.cb.index_path(str(empty))
        self.assertTrue(out["ok"])
        self.assertEqual(out["files_indexed"], 0)
        self.assertEqual(out["chunks_total"], 0)

    # ---- 2: small fixture dir --------------------------------------------

    def test_index_fixture_dir_returns_files(self) -> None:
        _build_fixture(self._fixture)
        out = self.cb.index_path(str(self._fixture))
        self.assertTrue(out["ok"])
        # Three files: .py + .js + .md
        self.assertEqual(out["files_indexed"], 3)
        self.assertGreater(out["chunks_total"], 0)

        # Incremental run: nothing changed → 0 re-embeds, files all skipped.
        again = self.cb.index_path(str(self._fixture))
        self.assertEqual(again["files_indexed"], 0)
        self.assertEqual(again["files_skipped"], 3)

    # ---- 3: search returns ordered hits ----------------------------------

    def test_search_returns_sorted_hits(self) -> None:
        _build_fixture(self._fixture)
        self.cb.index_path(str(self._fixture))
        hits = self.cb.search("cosine similarity", limit=5)
        self.assertGreater(len(hits), 0)
        # Sorted descending by score.
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # The top hit should mention "cosine" — either the Python
        # helper or the README usage section.
        top = hits[0]
        self.assertIn("cosine", top.snippet.lower())

    # ---- 4: status reports counters --------------------------------------

    def test_status_reports_counts(self) -> None:
        _build_fixture(self._fixture)
        self.cb.index_path(str(self._fixture))
        st = self.cb.status()
        self.assertEqual(st["files_indexed"], 3)
        self.assertGreater(st["chunks_total"], 0)
        self.assertIsNotNone(st["last_indexed_at"])
        self.assertIn("python", st["supported_languages"])
        self.assertIn("markdown", st["supported_languages"])
        self.assertTrue(st["db_path"].endswith("codebase.sqlite"))
        self.assertIn(st["embedder"], ("sqlite-vec (W135)", "hash-fallback"))

    # ---- 5: mention resolver wraps the indexer ---------------------------

    def test_mention_resolver_uses_codebase(self) -> None:
        _build_fixture(self._fixture)
        self.cb.index_path(str(self._fixture))
        from backend.core.mentions.resolver import _resolve_code

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_resolve_code("cosine"))
        finally:
            loop.close()
        self.assertEqual(result.kind, "code")
        # Should source from the indexer, not the rg fallback.
        self.assertEqual(result.meta.get("source"), "codebase")
        # The content body lists at least one match.
        self.assertIn("cosine", result.content.lower())
        self.assertGreater(result.meta.get("hits", 0), 0)


if __name__ == "__main__":
    unittest.main()
