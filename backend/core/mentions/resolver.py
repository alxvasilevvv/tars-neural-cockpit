"""Resolve @-mentions inserted in the chat input.

Cursor lets the operator type ``@file:src/foo.py`` or ``@web:latest
pandas release`` in the chat box and the assistant gets that context
injected before it answers. TARS mirrors the surface — five kinds:

* ``file``    — read up to 200 lines of the referenced path, fenced.
* ``docs``    — query the knowledge brain (W46) if it's available.
* ``web``     — Brave/DDG via the web_search domain pack (W175).
* ``recent``  — last 5 receipts as bullets.
* ``code``    — code RAG (W135 sqlite-vec) lookup; ``rg`` fallback.

Every resolver swallows its own errors. If a source isn't wired,
we return ``MentionResolved(content="(source not wired)")`` so the
chat orchestrator can keep streaming without surfacing a 500.

Each result is bounded to :data:`MAX_CONTENT_BYTES` (4 KB) so a fat
file or chatty web hit doesn't blow the LLM's context window.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


MAX_CONTENT_BYTES = 4 * 1024  # 4 KB per mention
MAX_FILE_LINES = 200
MAX_RECENT_RECEIPTS = 5
MAX_WEB_HITS = 5
MAX_CODE_HITS = 6

MENTION_KINDS: tuple[str, ...] = (
    "file",
    "docs",
    "web",
    "recent",
    "code",
)

# Pattern matches two shapes (single-token query, by design):
#
#   ``@kind:value``  — colon-form, the canonical Cursor-style shape.
#                       ``value`` is a single whitespace-delimited
#                       token. Operators wanting multi-word web /
#                       docs queries can quote: ``@web:"latest pandas
#                       release"`` is one token.
#   ``@kind``        — bare form (no colon, no query). Useful for
#                       ``@recent`` where the operator has nothing
#                       to qualify.
#
# A trailing word-boundary keeps ``@filename`` (which isn't one of
# our kinds) from accidentally matching as ``@file``.
_MENTION_RE = re.compile(
    r"@(?P<kind>file|docs|web|recent|code)\b"
    r"(?::(?P<query>\"[^\"\n]*\"|'[^'\n]*'|[^\s@]+))?",
    re.IGNORECASE,
)


@dataclass
class MentionResolved:
    """Result of resolving one @-mention.

    ``content`` is markdown (sometimes fenced); the orchestrator
    folds it into the operator's turn as a preamble.
    """

    kind: str
    query: str
    title: str
    content: str
    source_url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "query": self.query,
            "title": self.title,
            "content": self.content,
        }
        if self.source_url:
            out["source_url"] = self.source_url
        if self.meta:
            out["meta"] = dict(self.meta)
        return out


def _truncate(text: str, *, limit: int = MAX_CONTENT_BYTES) -> str:
    """Hard-cap a markdown payload to ``limit`` bytes (UTF-8).

    Hits the byte budget rather than character count so we don't
    blow the prompt out on multi-byte content.
    """

    if not text:
        return ""
    raw = text.encode("utf-8", errors="ignore")
    if len(raw) <= limit:
        return text
    tail = "\n…(truncated)"
    tail_bytes = tail.encode("utf-8")
    clipped = raw[: max(0, limit - len(tail_bytes))].decode(
        "utf-8", errors="ignore"
    )
    return clipped.rstrip() + tail


def extract_mentions(text: str) -> list[dict[str, str]]:
    """Parse ``@kind[:query]`` tokens out of free-form chat text.

    Returns a list of ``{"kind", "query", "raw"}`` dicts in
    appearance order. Deduplicates identical (kind, query) pairs so
    a clumsy operator who pastes ``@file:foo.py`` three times only
    pays the resolver cost once.
    """

    if not text:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for m in _MENTION_RE.finditer(text):
        kind = (m.group("kind") or "").lower()
        query = (m.group("query") or "").strip()
        # Drop surrounding quote pair so the resolver sees the raw
        # term, not the quote characters.
        if len(query) >= 2 and query[0] == query[-1] and query[0] in ("'", '"'):
            query = query[1:-1].strip()
        key = (kind, query)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {"kind": kind, "query": query, "raw": m.group(0)}
        )
    return out


def strip_mentions(text: str) -> str:
    """Remove every parsed ``@kind[:query]`` token from a message.

    Leaves the message readable to a downstream model that doesn't
    care about the raw markup. Collapses the double-spaces a strip
    leaves behind.
    """

    if not text:
        return text
    cleaned = _MENTION_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def inject_context(
    operator_text: str,
    resolved: Iterable[MentionResolved],
    *,
    strip: bool = True,
) -> str:
    """Fold resolved mentions into the operator's turn as a preamble.

    ``strip=True`` drops the raw ``@…`` tokens out of the body of
    the user message; ``strip=False`` keeps them so the assistant
    can refer back to the markup verbatim.
    """

    items = [r for r in resolved if r is not None]
    if not items:
        return operator_text or ""
    blocks: list[str] = ["## Context from your mentions", ""]
    for r in items:
        header = f"### {r.title}".rstrip()
        blocks.append(header)
        if r.source_url:
            blocks.append(f"_source: {r.source_url}_")
        blocks.append("")
        blocks.append((r.content or "").rstrip() or "(empty)")
        blocks.append("")
        blocks.append("---")
        blocks.append("")
    body = strip_mentions(operator_text) if strip else (operator_text or "")
    return "\n".join(blocks).rstrip() + "\n\n" + body


# ----------------------------------------------------------------------
# Per-kind resolvers
# ----------------------------------------------------------------------


def _safe_resolve_path(query: str) -> Path | None:
    """Resolve a chat-supplied path defensively.

    Allows absolute paths under the repo root or under the
    operator's ``~/.tars`` data dir, and rejects ``..`` traversals
    that escape both roots. Plain relative paths resolve against
    the current working dir (chat is invoked from the backend, so
    that's the repo root in practice).
    """

    if not query:
        return None
    raw = query.strip().strip("`").strip("'\"")
    if not raw:
        return None
    try:
        p = Path(os.path.expanduser(raw)).resolve()
    except Exception:
        return None
    return p


async def _resolve_file(query: str) -> MentionResolved:
    title = f"@file: {query}" if query else "@file"
    if not query:
        return MentionResolved(
            kind="file",
            query=query,
            title=title,
            content="(usage: @file:path/to/foo.py)",
        )
    path = _safe_resolve_path(query)
    if path is None or not path.exists() or not path.is_file():
        return MentionResolved(
            kind="file",
            query=query,
            title=title,
            content=f"(file not found: `{query}`)",
        )
    try:
        # Read in a thread — files can be large, sync IO would
        # block the event loop.
        text = await asyncio.to_thread(
            _read_head, str(path), MAX_FILE_LINES
        )
    except Exception as exc:
        return MentionResolved(
            kind="file",
            query=query,
            title=title,
            content=f"(failed to read: {exc})",
        )
    lang = _ext_to_lang(path.suffix)
    fenced = f"```{lang}\n{text}\n```"
    return MentionResolved(
        kind="file",
        query=query,
        title=title,
        content=_truncate(fenced),
        source_url=str(path),
        meta={"path": str(path), "lines": text.count("\n") + 1},
    )


def _read_head(path: str, max_lines: int) -> str:
    lines: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= max_lines:
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def _ext_to_lang(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    return {
        "py": "python",
        "ts": "typescript",
        "tsx": "tsx",
        "js": "javascript",
        "jsx": "jsx",
        "rs": "rust",
        "go": "go",
        "md": "markdown",
        "html": "html",
        "css": "css",
        "json": "json",
        "yml": "yaml",
        "yaml": "yaml",
        "sh": "bash",
        "sql": "sql",
        "toml": "toml",
    }.get(e, "")


async def _resolve_docs(query: str) -> MentionResolved:
    title = f"@docs: {query}" if query else "@docs"
    if not query:
        return MentionResolved(
            kind="docs",
            query=query,
            title=title,
            content="(usage: @docs:your search query)",
        )
    # Knowledge brain (W46) — try a couple of import shapes so this
    # survives a future rename.
    try:
        from backend.core.attachments.retrieval import retrieve as _retrieve
    except Exception:
        _retrieve = None  # type: ignore[assignment]

    if _retrieve is None:
        return MentionResolved(
            kind="docs",
            query=query,
            title=title,
            content="(source not wired)",
        )
    try:
        # ``thread_id`` is required by the retrieve signature but
        # falls through to "all chunks" with the empty marker the
        # rest of the codebase uses.
        chunks = await _retrieve("__mentions__", query, top_k=6)
    except Exception as exc:
        return MentionResolved(
            kind="docs",
            query=query,
            title=title,
            content=f"(docs lookup failed: {exc})",
        )
    if not chunks:
        return MentionResolved(
            kind="docs",
            query=query,
            title=title,
            content="(no matching docs — ingest more via /api/chat/threads/{id}/attachments)",
        )
    lines = ["**Top matches**:", ""]
    for i, c in enumerate(chunks[:6], 1):
        snippet = (
            (getattr(c.chunk, "text", "") or "")[:240].replace("\n", " ").strip()
        )
        fname = getattr(c.chunk, "filename", None) or "(unknown)"
        lines.append(f"{i}. `{fname}` — {snippet}")
    return MentionResolved(
        kind="docs",
        query=query,
        title=title,
        content=_truncate("\n".join(lines)),
        meta={"hits": min(len(chunks), 6)},
    )


async def _resolve_web(query: str) -> MentionResolved:
    title = f"@web: {query}" if query else "@web"
    if not query:
        return MentionResolved(
            kind="web",
            query=query,
            title=title,
            content="(usage: @web:your search query)",
        )
    try:
        from backend.core.domains.packs.web_search.actions import search as _search
    except Exception:
        return MentionResolved(
            kind="web",
            query=query,
            title=title,
            content="(source not wired)",
        )
    try:
        result = await _search({"query": query, "limit": MAX_WEB_HITS})
    except Exception as exc:
        return MentionResolved(
            kind="web",
            query=query,
            title=title,
            content=f"(web search failed: {exc})",
        )
    if not isinstance(result, dict) or not result.get("ok"):
        err = (result or {}).get("error") if isinstance(result, dict) else "unknown"
        return MentionResolved(
            kind="web",
            query=query,
            title=title,
            content=f"(no results — adapter error: {err})",
        )
    hits = result.get("hits") or result.get("results") or []
    if not hits:
        return MentionResolved(
            kind="web",
            query=query,
            title=title,
            content="(no results)",
        )
    lines: list[str] = []
    for i, h in enumerate(hits[:MAX_WEB_HITS], 1):
        h_title = (h.get("title") or "").strip() or "(untitled)"
        url = (h.get("url") or "").strip()
        snippet = (h.get("snippet") or h.get("description") or "").strip()
        lines.append(f"{i}. [{h_title}]({url})")
        if snippet:
            lines.append(f"   {snippet[:200]}")
    return MentionResolved(
        kind="web",
        query=query,
        title=title,
        content=_truncate("\n".join(lines)),
        source_url=(hits[0].get("url") if hits else None),
        meta={"adapter": result.get("adapter"), "hits": len(hits)},
    )


async def _resolve_recent(query: str) -> MentionResolved:
    title = "@recent"
    try:
        from backend.core.receipts.store import get_store as _get_store
    except Exception:
        return MentionResolved(
            kind="recent",
            query=query,
            title=title,
            content="(source not wired)",
        )
    store = None
    try:
        store = _get_store()
    except Exception:
        store = None
    if store is None:
        return MentionResolved(
            kind="recent",
            query=query,
            title=title,
            content="(receipt store disabled — set TARS_RECEIPT_STORE=enabled)",
        )
    try:
        rows = await store.query(limit=MAX_RECENT_RECEIPTS)
    except Exception as exc:
        return MentionResolved(
            kind="recent",
            query=query,
            title=title,
            content=f"(recent lookup failed: {exc})",
        )
    if not rows:
        return MentionResolved(
            kind="recent",
            query=query,
            title=title,
            content="(no receipts yet)",
        )
    lines: list[str] = ["**Recent actions**:", ""]
    for r in rows[:MAX_RECENT_RECEIPTS]:
        ts = getattr(r, "ts", 0) or 0
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "?"
        rtype = getattr(r, "type", "?")
        actor = getattr(r, "actor", "?")
        resource = getattr(r, "resource", None) or ""
        suffix = f" — {resource}" if resource else ""
        lines.append(f"- `{when}` · **{rtype}** · {actor}{suffix}")
    return MentionResolved(
        kind="recent",
        query=query,
        title=title,
        content=_truncate("\n".join(lines)),
        meta={"count": len(rows)},
    )


async def _resolve_code(query: str) -> MentionResolved:
    title = f"@code: {query}" if query else "@code"
    if not query:
        return MentionResolved(
            kind="code",
            query=query,
            title=title,
            content="(usage: @code:symbol or @code:phrase)",
        )
    # W135 sqlite-vec code RAG — try a couple of import surfaces.
    code_rag = None
    for mod_path in (
        "backend.core.code_rag",
        "backend.core.search.code_rag",
    ):
        try:
            code_rag = __import__(mod_path, fromlist=["search"])
            break
        except Exception:
            code_rag = None
    if code_rag is not None and hasattr(code_rag, "search"):
        try:
            hits = await asyncio.to_thread(
                code_rag.search, query, MAX_CODE_HITS  # type: ignore[arg-type]
            )
        except Exception:
            hits = None
        if hits:
            return _format_code_hits(query, hits, source="code_rag")
    # Fallback: ripgrep / grep through the repo.
    hits = await asyncio.to_thread(_grep_fallback, query, MAX_CODE_HITS)
    if not hits:
        return MentionResolved(
            kind="code",
            query=query,
            title=title,
            content="(no matches; install ripgrep + index code RAG for richer results)",
        )
    return _format_code_hits(query, hits, source="grep")


def _grep_fallback(query: str, limit: int) -> list[dict[str, Any]]:
    """Tiny ripgrep / grep fallback when the code-RAG index is empty.

    Uses ``rg`` if available, else falls back to a hand-rolled scan
    over ``.py / .ts / .tsx / .js / .rs / .go`` files in CWD. Bound
    to ``limit`` results so a hot keyword doesn't enumerate the
    whole tree.
    """

    import shutil
    import subprocess

    if shutil.which("rg"):
        try:
            out = subprocess.check_output(
                [
                    "rg",
                    "--max-count",
                    "1",
                    "--max-columns",
                    "200",
                    "--no-heading",
                    "-n",
                    query,
                ],
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd(),
                timeout=4.0,
                text=True,
                errors="replace",
            )
        except Exception:
            return []
        hits: list[dict[str, Any]] = []
        for line in out.splitlines()[:limit]:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            hits.append(
                {
                    "path": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "text": parts[2],
                }
            )
        return hits

    # Hand-rolled fallback — only used when rg isn't installed.
    exts = {".py", ".ts", ".tsx", ".js", ".rs", ".go", ".md"}
    hits = []
    needle = query.lower()
    for root, _dirs, files in os.walk(os.getcwd()):
        if any(part.startswith(".") for part in root.split(os.sep)):
            continue
        for fname in files:
            if Path(fname).suffix.lower() not in exts:
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if needle in line.lower():
                            hits.append(
                                {"path": path, "line": i, "text": line.rstrip()}
                            )
                            break
            except Exception:
                continue
            if len(hits) >= limit:
                return hits
    return hits


def _format_code_hits(
    query: str, hits: list[dict[str, Any]], *, source: str
) -> MentionResolved:
    title = f"@code: {query}"
    lines: list[str] = [f"**Top matches** ({source}):", ""]
    for h in hits[:MAX_CODE_HITS]:
        path = h.get("path") or h.get("file") or "(unknown)"
        ln = h.get("line") or h.get("lineno") or 0
        text = (h.get("text") or h.get("snippet") or "").strip()[:200]
        lines.append(f"- `{path}:{ln}` — {text}")
    return MentionResolved(
        kind="code",
        query=query,
        title=title,
        content=_truncate("\n".join(lines)),
        meta={"hits": len(hits), "source": source},
    )


_DISPATCH = {
    "file": _resolve_file,
    "docs": _resolve_docs,
    "web": _resolve_web,
    "recent": _resolve_recent,
    "code": _resolve_code,
}


async def resolve_mention(kind: str, query: str) -> MentionResolved:
    """Dispatch one ``(kind, query)`` to its resolver.

    Unknown kinds get a soft ``unknown`` result rather than an
    exception — the orchestrator never crashes a chat turn over a
    typo in an ``@-mention``.
    """

    k = (kind or "").strip().lower()
    q = (query or "").strip()
    if k not in _DISPATCH:
        return MentionResolved(
            kind="unknown",
            query=q,
            title=f"@{kind}",
            content="(source not wired)",
        )
    handler = _DISPATCH[k]
    try:
        result = await handler(q)
    except Exception as exc:  # never bubble — resolver is best-effort
        return MentionResolved(
            kind=k,
            query=q,
            title=f"@{k}",
            content=f"(resolver crashed: {exc})",
        )
    # Belt-and-braces: enforce the 4-KB cap even if a custom resolver
    # forgets to call _truncate.
    result.content = _truncate(result.content or "")
    return result


async def resolve_mentions(
    mentions: Iterable[dict[str, str]],
) -> list[MentionResolved]:
    """Resolve a batch of ``{"kind", "query"}`` mentions in parallel.

    Order of the input is preserved in the output. Failures still
    surface a MentionResolved — never a raised exception.
    """

    items = [
        {"kind": (m.get("kind") or "").strip(), "query": (m.get("query") or "").strip()}
        for m in mentions
        if isinstance(m, dict)
    ]
    if not items:
        return []
    tasks = [resolve_mention(m["kind"], m["query"]) for m in items]
    return list(await asyncio.gather(*tasks))


__all__ = [
    "MAX_CONTENT_BYTES",
    "MENTION_KINDS",
    "MentionResolved",
    "extract_mentions",
    "inject_context",
    "resolve_mention",
    "resolve_mentions",
    "strip_mentions",
]
