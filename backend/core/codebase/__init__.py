"""W245 — Codebase indexer for TARS.

Cursor indexes the user's codebase (millions of LoC), serves it as
the ``@codebase`` mention context. TARS already has an sqlite-vec
code RAG (W135). This module hardens that scaffold to production:

- **Incremental indexing**: per-file mtime check, only re-embed
  changed files. ``force=True`` rewrites the whole table.
- **Language-aware chunking**: Python uses ``def`` / ``class``
  boundaries, JS/TS uses function-ish boundaries, Markdown splits
  on heading sections, everything else uses a sliding 200-line
  window.
- **Persistence**: ``~/.tars/codebase.sqlite``. We try to reuse the
  W135 sqlite-vec embedder if present (``backend.core.code_rag``);
  if missing, fall back to a deterministic hash-based stub vector
  + plain SQLite cosine — good enough for unit tests and the
  product's "open-source repo at home" persona.
- **File watcher**: an opt-in background thread polls mtimes every
  30 s (configurable) and re-indexes anything that moved. The
  granularity is per-file, not per-byte; a single keystroke in a
  long file still re-chunks the whole file (cheap enough at the
  hundreds-of-MB scale this targets).
- **Status snapshot**: file count, chunk count, last-indexed
  timestamp, on-disk size, list of supported languages.

The module is framework-free. The HTTP surface lives in
``web_extras/routers/codebase.py``; ``backend.core.mentions``
calls :func:`search` directly when the operator types
``@code:<query>``.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Iterable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_TARS_DIR = Path.home() / ".tars"
DEFAULT_DB_NAME = "codebase.sqlite"

# Per-language chunkers — see below for the implementations.
SUPPORTED_EXTS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".md": "markdown",
    ".mdx": "markdown",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}


# Ignore everything that looks like generated / vendored noise. Cursor
# applies the same denylist. The list is intentionally aggressive — a
# user wanting node_modules indexed can override via the ``force``
# flag + custom root.
IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        ".cache",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "coverage",
        ".coverage",
        "site-packages",
        "out",
    }
)

# Files bigger than this get skipped — vendored bundle blobs are
# poisonous to embed and useless to grep.
MAX_FILE_BYTES = 256 * 1024  # 256 KB

# Default chunk granularity for languages without a tailored chunker.
DEFAULT_CHUNK_LINES = 200

# How often the watcher polls mtimes.
WATCH_INTERVAL_S = 30.0

# Embedding dimension when we fall back to the deterministic-hash
# embedder. Small enough to stay fast on a few hundred chunks, large
# enough that hash collisions don't make cosine sim meaningless.
HASH_EMBED_DIM = 64


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChunkHit:
    """One search result row."""

    path: str
    line: int
    end_line: int
    lang: str
    snippet: str
    score: float
    symbol: str | None = None
    root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IndexProgress:
    """Background-indexing trace state.

    The router polls this via ``GET /api/codebase/index/{trace_id}``.
    """

    trace_id: str
    root: str
    state: str = "running"  # running | done | error
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    files_scanned: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    chunks_total: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Resolve DB path
# ---------------------------------------------------------------------------


def _tars_dir() -> Path:
    raw = os.getenv("TARS_HOME")
    base = Path(raw).expanduser() if raw else DEFAULT_TARS_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _db_path() -> Path:
    raw = os.getenv("TARS_CODEBASE_DB_PATH")
    if raw:
        return Path(raw).expanduser()
    return _tars_dir() / DEFAULT_DB_NAME


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path        TEXT PRIMARY KEY,
    root        TEXT NOT NULL,
    lang        TEXT NOT NULL,
    mtime       REAL NOT NULL,
    size        INTEGER NOT NULL,
    indexed_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_root ON files (root);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files (mtime);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL,
    root        TEXT NOT NULL,
    lang        TEXT NOT NULL,
    symbol      TEXT,
    start_line  INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    tokens      TEXT NOT NULL DEFAULT '',
    embedding   BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks (path);
CREATE INDEX IF NOT EXISTS idx_chunks_root ON chunks (root);

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------


def _try_w135_embedder() -> Callable[[str], list[float]] | None:
    """Return the W135 sqlite-vec embedder if it's importable.

    The exact module surface has drifted across iterations; we try
    a couple of import shapes and a couple of attribute names. Any
    failure simply falls back to the deterministic hash embedder.
    """

    for mod_path in (
        "backend.core.code_rag",
        "backend.core.code_rag.embed",
        "backend.core.code_rag.store",
        "backend.core.search.code_rag",
    ):
        try:
            mod = __import__(mod_path, fromlist=["embed"])
        except Exception:
            continue
        for attr in ("embed", "embed_text", "embed_chunk", "compute_embedding"):
            fn = getattr(mod, attr, None)
            if callable(fn):
                return fn  # type: ignore[return-value]
    return None


def _hash_embed(text: str, dim: int = HASH_EMBED_DIM) -> list[float]:
    """Deterministic hash-based bag-of-tokens embedding.

    Cheap, has no external dep, gives plausible cosine similarity
    when sqlite-vec isn't around. Tokenises on alphanumerics, lower
    cases, then hashes each token into one of ``dim`` bins. The
    final vector is L2-normalised so cosine = dot.
    """

    vec = [0.0] * dim
    for tok in _tokenise(text):
        h = int(hashlib.blake2s(tok.encode("utf-8"), digest_size=8).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _tokenise(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text or "")]


def _embed(text: str) -> list[float]:
    """Embed text via W135 (if wired) or the hash fallback."""

    fn = _try_w135_embedder()
    if fn is not None:
        try:
            v = fn(text)
            if isinstance(v, (list, tuple)) and v:
                # Normalise so cosine = dot — W135 may already do
                # this, but cheap to enforce.
                norm = math.sqrt(sum(float(x) * float(x) for x in v)) or 1.0
                return [float(x) / norm for x in v]
        except Exception:
            pass
    return _hash_embed(text)


def _serialise_vec(vec: list[float]) -> bytes:
    import struct

    return struct.pack(f"<I{len(vec)}f", len(vec), *vec)


def _deserialise_vec(blob: bytes) -> list[float]:
    import struct

    if not blob or len(blob) < 4:
        return []
    n = struct.unpack_from("<I", blob, 0)[0]
    if len(blob) < 4 + 4 * n:
        return []
    return list(struct.unpack_from(f"<{n}f", blob, 4))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    # Both are L2-normalised already; cosine == dot in that case.
    return float(dot)


# ---------------------------------------------------------------------------
# Walk / filter
# ---------------------------------------------------------------------------


def _iter_files(root: Path) -> Iterable[Path]:
    """Yield every candidate file under ``root``.

    Honours :data:`IGNORE_DIRS` and the supported-extension allowlist;
    files bigger than :data:`MAX_FILE_BYTES` get skipped silently.
    """

    if not root.exists() or not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # Prune in-place so os.walk skips them on the recurse.
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                continue
            p = Path(dirpath) / fname
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size > MAX_FILE_BYTES:
                continue
            yield p


# ---------------------------------------------------------------------------
# Language-aware chunkers
# ---------------------------------------------------------------------------


def _chunk_python(text: str) -> list[dict[str, Any]]:
    """Split a Python source on top-level ``def`` / ``class`` lines.

    Anything before the first top-level definition becomes a header
    chunk so module-level imports + docstring don't get lost. The
    function avoids using :mod:`ast` so syntactically broken files
    (which a real codebase has plenty of) still chunk gracefully.
    """

    return _chunk_by_boundary(
        text,
        boundary=re.compile(r"^\s*(def|class|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)"),
        symbol_group=2,
    )


def _chunk_js_ts(text: str) -> list[dict[str, Any]]:
    """JS / TS chunker — boundary on ``function``, ``export``, ``class``."""

    boundary = re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?"
        r"(function|async\s+function|class|const|let|var)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)"
    )
    return _chunk_by_boundary(text, boundary=boundary, symbol_group=2)


def _chunk_markdown(text: str) -> list[dict[str, Any]]:
    """Markdown chunker — split on ATX headings (``#``…``######``)."""

    return _chunk_by_boundary(
        text,
        boundary=re.compile(r"^(#{1,6})\s+(.+?)\s*$"),
        symbol_group=2,
    )


def _chunk_by_boundary(
    text: str,
    *,
    boundary: re.Pattern[str],
    symbol_group: int,
) -> list[dict[str, Any]]:
    """Generic boundary-driven chunker shared by Python / JS / Markdown.

    Each match opens a new chunk; the body of that chunk runs until
    the next match (or EOF). Lines before the first match form a
    ``__header__`` chunk so module-top imports / front-matter don't
    fall on the floor.
    """

    lines = text.splitlines()
    if not lines:
        return []
    indices: list[tuple[int, str | None]] = []
    for i, line in enumerate(lines, start=1):
        m = boundary.match(line)
        if m:
            try:
                sym = m.group(symbol_group)
            except (IndexError, ValueError):
                sym = None
            indices.append((i, sym))
    if not indices:
        # No structure — fall through to sliding window.
        return _chunk_sliding(text)
    chunks: list[dict[str, Any]] = []
    # Header chunk: bytes before the first boundary line.
    first_line = indices[0][0]
    if first_line > 1:
        body = "\n".join(lines[: first_line - 1]).strip()
        if body:
            chunks.append(
                {
                    "start_line": 1,
                    "end_line": first_line - 1,
                    "symbol": "__header__",
                    "text": body,
                }
            )
    # Body chunks.
    for idx, (start, sym) in enumerate(indices):
        end = indices[idx + 1][0] - 1 if idx + 1 < len(indices) else len(lines)
        body = "\n".join(lines[start - 1 : end]).strip()
        if not body:
            continue
        chunks.append(
            {
                "start_line": start,
                "end_line": end,
                "symbol": sym,
                "text": body,
            }
        )
    # Re-chunk anything that ballooned past 2x default — keeps the
    # embedding payload bounded per row.
    return _split_oversized(chunks)


def _chunk_sliding(text: str, lines_per_chunk: int = DEFAULT_CHUNK_LINES) -> list[dict[str, Any]]:
    """Generic fallback — fixed-line sliding window."""

    lines = text.splitlines()
    if not lines:
        return []
    chunks: list[dict[str, Any]] = []
    for i in range(0, len(lines), lines_per_chunk):
        block = lines[i : i + lines_per_chunk]
        body = "\n".join(block).strip()
        if not body:
            continue
        chunks.append(
            {
                "start_line": i + 1,
                "end_line": i + len(block),
                "symbol": None,
                "text": body,
            }
        )
    return chunks


def _split_oversized(
    chunks: list[dict[str, Any]],
    *,
    max_lines: int = DEFAULT_CHUNK_LINES * 2,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in chunks:
        line_span = max(1, c["end_line"] - c["start_line"] + 1)
        if line_span <= max_lines:
            out.append(c)
            continue
        # Re-chunk the body keeping the symbol.
        body_lines = c["text"].splitlines()
        for i in range(0, len(body_lines), DEFAULT_CHUNK_LINES):
            block = body_lines[i : i + DEFAULT_CHUNK_LINES]
            body = "\n".join(block).strip()
            if not body:
                continue
            out.append(
                {
                    "start_line": c["start_line"] + i,
                    "end_line": c["start_line"] + i + len(block) - 1,
                    "symbol": c["symbol"],
                    "text": body,
                }
            )
    return out


def _chunk_file(path: Path, lang: str, text: str) -> list[dict[str, Any]]:
    """Dispatch a file's text to the right chunker."""

    if lang == "python":
        return _chunk_python(text)
    if lang in {"typescript", "tsx", "javascript", "jsx"}:
        return _chunk_js_ts(text)
    if lang == "markdown":
        return _chunk_markdown(text)
    return _chunk_sliding(text)


# ---------------------------------------------------------------------------
# Index API
# ---------------------------------------------------------------------------


_indexing_lock = threading.Lock()
_progress: dict[str, IndexProgress] = {}


def _read_file(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def index_path(
    root: str,
    force: bool = False,
    *,
    on_progress: Callable[[IndexProgress], None] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Walk ``root`` and (re-)embed every supported file.

    With ``force=False`` we skip files whose ``mtime`` is unchanged
    since the last index — that keeps incremental runs cheap.
    With ``force=True`` we drop every row for the root and re-embed
    from scratch.

    Returns a summary dict suitable for the HTTP response.
    """

    root_path = Path(os.path.expanduser(root)).resolve()
    if not root_path.exists() or not root_path.is_dir():
        return {
            "ok": False,
            "error": f"root not found or not a directory: {root_path}",
            "root": str(root_path),
        }

    progress = IndexProgress(
        trace_id=trace_id or uuid.uuid4().hex[:12],
        root=str(root_path),
    )
    _progress[progress.trace_id] = progress

    def _tick() -> None:
        if on_progress:
            try:
                on_progress(progress)
            except Exception:
                pass

    with _indexing_lock:
        conn = _connect()
        try:
            if force:
                conn.execute("DELETE FROM chunks WHERE root = ?", (str(root_path),))
                conn.execute("DELETE FROM files WHERE root = ?", (str(root_path),))
                conn.commit()

            # Snapshot of what we already have.
            existing: dict[str, tuple[float, int]] = {}
            for row in conn.execute(
                "SELECT path, mtime, size FROM files WHERE root = ?",
                (str(root_path),),
            ):
                existing[row["path"]] = (row["mtime"], row["size"])

            seen: set[str] = set()
            for fp in _iter_files(root_path):
                progress.files_scanned += 1
                seen.add(str(fp))
                try:
                    st = fp.stat()
                except OSError:
                    progress.files_skipped += 1
                    continue
                prior = existing.get(str(fp))
                if prior is not None and not force and abs(prior[0] - st.st_mtime) < 1e-3 and prior[1] == st.st_size:
                    progress.files_skipped += 1
                    continue
                text = _read_file(fp)
                if text is None:
                    progress.files_skipped += 1
                    continue
                lang = SUPPORTED_EXTS.get(fp.suffix.lower(), "text")
                _reindex_file(conn, fp, lang, text, root_path)
                progress.files_indexed += 1
                if progress.files_indexed % 25 == 0:
                    _tick()

            # Prune files that have been removed from disk since the last run.
            removed = set(existing) - seen
            for path in removed:
                conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
                conn.execute("DELETE FROM files WHERE path = ?", (path,))

            conn.commit()
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM chunks WHERE root = ?",
                (str(root_path),),
            )
            progress.chunks_total = int(cur.fetchone()["n"] or 0)
            _set_meta(conn, "last_indexed_at", str(time.time()))
            _set_meta(conn, "last_root", str(root_path))
            conn.commit()
        finally:
            conn.close()

    progress.state = "done"
    progress.finished_at = time.time()
    _tick()
    return {
        "ok": True,
        "trace_id": progress.trace_id,
        "root": str(root_path),
        "files_scanned": progress.files_scanned,
        "files_indexed": progress.files_indexed,
        "files_skipped": progress.files_skipped,
        "files_removed": len(set(existing) - seen),
        "chunks_total": progress.chunks_total,
        "elapsed_s": round((progress.finished_at or time.time()) - progress.started_at, 3),
    }


def _reindex_file(
    conn: sqlite3.Connection,
    path: Path,
    lang: str,
    text: str,
    root: Path,
) -> None:
    """Drop + re-embed every chunk for one file."""

    conn.execute("DELETE FROM chunks WHERE path = ?", (str(path),))
    chunks = _chunk_file(path, lang, text)
    now = time.time()
    for c in chunks:
        vec = _embed(c["text"])
        conn.execute(
            """
            INSERT INTO chunks
                (path, root, lang, symbol, start_line, end_line, text, tokens, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(path),
                str(root),
                lang,
                c.get("symbol"),
                int(c["start_line"]),
                int(c["end_line"]),
                c["text"],
                " ".join(_tokenise(c["text"])),
                _serialise_vec(vec),
            ),
        )
    st = path.stat()
    conn.execute(
        """
        INSERT INTO files (path, root, lang, mtime, size, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            root = excluded.root,
            lang = excluded.lang,
            mtime = excluded.mtime,
            size = excluded.size,
            indexed_at = excluded.indexed_at
        """,
        (str(path), str(root), lang, st.st_mtime, st.st_size, now),
    )


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def get_progress(trace_id: str) -> dict[str, Any] | None:
    p = _progress.get(trace_id)
    return p.to_dict() if p else None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search(
    query: str,
    limit: int = 10,
    root: str | None = None,
) -> list[ChunkHit]:
    """Cosine-similarity search over the embedded chunks.

    A token-overlap score is folded in (BM25-lite) so a literal
    keyword still floats to the top even when the embeddings are
    the hash fallback.
    """

    q = (query or "").strip()
    if not q:
        return []
    q_vec = _embed(q)
    q_tokens = set(_tokenise(q))
    if not q_tokens and not any(q_vec):
        return []

    conn = _connect()
    try:
        params: list[Any] = []
        sql = "SELECT path, root, lang, symbol, start_line, end_line, text, tokens, embedding FROM chunks"
        if root:
            sql += " WHERE root = ?"
            params.append(str(Path(os.path.expanduser(root)).resolve()))
        rows = conn.execute(sql, params).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vec = _deserialise_vec(row["embedding"])
            cos = _cosine(q_vec, vec)
            chunk_tokens = set((row["tokens"] or "").split())
            overlap = len(q_tokens & chunk_tokens)
            tok_score = overlap / (len(q_tokens) or 1)
            score = 0.6 * cos + 0.4 * tok_score
            if score <= 0.0:
                continue
            scored.append((score, row))
    finally:
        conn.close()

    scored.sort(key=lambda t: t[0], reverse=True)
    out: list[ChunkHit] = []
    for score, row in scored[: max(1, int(limit))]:
        snippet = row["text"]
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "…"
        out.append(
            ChunkHit(
                path=row["path"],
                line=int(row["start_line"]),
                end_line=int(row["end_line"]),
                lang=row["lang"],
                snippet=snippet,
                score=round(float(score), 6),
                symbol=row["symbol"],
                root=row["root"],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def status() -> dict[str, Any]:
    """Report indexer health to the cockpit settings panel."""

    path = _db_path()
    files_n = 0
    chunks_n = 0
    last_indexed_at: float | None = None
    last_root: str | None = None
    size_mb = 0.0
    if path.exists():
        try:
            size_mb = round(path.stat().st_size / (1024.0 * 1024.0), 3)
        except OSError:
            size_mb = 0.0
        conn = _connect()
        try:
            files_n = int(conn.execute("SELECT COUNT(*) AS n FROM files").fetchone()["n"] or 0)
            chunks_n = int(conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"] or 0)
            raw = _get_meta(conn, "last_indexed_at")
            if raw:
                try:
                    last_indexed_at = float(raw)
                except ValueError:
                    last_indexed_at = None
            last_root = _get_meta(conn, "last_root")
        finally:
            conn.close()
    embedder = "sqlite-vec (W135)" if _try_w135_embedder() else "hash-fallback"
    return {
        "files_indexed": files_n,
        "chunks_total": chunks_n,
        "last_indexed_at": last_indexed_at,
        "last_root": last_root,
        "size_mb": size_mb,
        "supported_languages": sorted(set(SUPPORTED_EXTS.values())),
        "db_path": str(path),
        "embedder": embedder,
        "watcher_active_for": list(_watchers.keys()),
    }


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------


_watchers: dict[str, "_WatcherThread"] = {}
_watchers_lock = threading.Lock()


class _WatcherThread(threading.Thread):
    """Polls mtimes every ``interval`` seconds and re-indexes drift.

    Granularity is *per-file*: a single edited file gets re-chunked
    in full, the rest of the tree is left alone. We honour the
    `_indexing_lock` so a manual ``index_path`` call and the watcher
    can't trample each other.
    """

    def __init__(self, root: str, interval: float = WATCH_INTERVAL_S) -> None:
        super().__init__(daemon=True, name=f"codebase-watch:{root}")
        self.root = root
        self.interval = max(1.0, float(interval))
        self._stop = threading.Event()
        self.last_tick: float | None = None
        self.last_change_count: int = 0

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # pragma: no cover - threading timing
        while not self._stop.is_set():
            try:
                out = index_path(self.root, force=False)
                self.last_change_count = int(out.get("files_indexed", 0))
                self.last_tick = time.time()
            except Exception:
                pass
            if self._stop.wait(self.interval):
                break


def watch_for_changes(root: str, enable: bool = True, *, interval: float | None = None) -> dict[str, Any]:
    """Start or stop a background mtime watcher for ``root``.

    Returns the new state so the router can echo it.
    """

    root_path = str(Path(os.path.expanduser(root)).resolve())
    with _watchers_lock:
        existing = _watchers.get(root_path)
        if not enable:
            if existing:
                existing.stop()
                _watchers.pop(root_path, None)
                return {"ok": True, "root": root_path, "watching": False, "stopped": True}
            return {"ok": True, "root": root_path, "watching": False, "stopped": False}
        if existing and existing.is_alive():
            return {"ok": True, "root": root_path, "watching": True, "already": True}
        th = _WatcherThread(root_path, interval=interval or WATCH_INTERVAL_S)
        th.start()
        _watchers[root_path] = th
    return {"ok": True, "root": root_path, "watching": True, "interval_s": th.interval}


def stop_all_watchers() -> None:
    with _watchers_lock:
        for w in list(_watchers.values()):
            w.stop()
        _watchers.clear()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def reset_for_tests() -> None:
    """Drop in-process state.

    The router test fixture clears ``TARS_CODEBASE_DB_PATH`` /
    ``TARS_HOME`` first; this helper just guarantees the next call
    re-resolves the DB and discards any progress / watcher state.
    """

    stop_all_watchers()
    _progress.clear()


__all__ = [
    "ChunkHit",
    "IndexProgress",
    "SUPPORTED_EXTS",
    "index_path",
    "search",
    "status",
    "watch_for_changes",
    "stop_all_watchers",
    "get_progress",
    "reset_for_tests",
]
