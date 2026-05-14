"""W240 — tests for the @-mention chat-context resolver.

Five cases, matching the spec:

1. ``@file:`` mentions resolve to a fenced code block.
2. Unknown kinds return ``(source not wired)`` without raising.
3. Resolved content is bounded to 4 KB.
4. Autocomplete suggests the five default kinds for an empty query.
5. The chat orchestrator strips ``@kind:query`` tokens out of the
   message body and prepends a "Context from your mentions" preamble.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from backend.core.mentions import (
    MAX_CONTENT_BYTES,
    MENTION_KINDS,
    MentionResolved,
    extract_mentions,
    inject_context,
    resolve_mention,
    strip_mentions,
)


# ----------------------------------------------------------------------
# Case 1 — file mention resolves to a fenced code block.
# ----------------------------------------------------------------------


def test_file_mention_returns_fenced_code_block(tmp_path):
    p = tmp_path / "snippet.py"
    p.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    out = asyncio.run(resolve_mention("file", str(p)))

    assert isinstance(out, MentionResolved)
    assert out.kind == "file"
    assert out.title == f"@file: {p}"
    assert "```python" in out.content
    assert "def hello" in out.content
    assert out.source_url == str(p)


def test_file_mention_missing_file_is_soft():
    out = asyncio.run(resolve_mention("file", "/no/such/path/here.txt"))
    assert out.kind == "file"
    assert "not found" in out.content.lower()


# ----------------------------------------------------------------------
# Case 2 — unknown kind returns "(source not wired)" gracefully.
# ----------------------------------------------------------------------


def test_unknown_kind_returns_source_not_wired():
    out = asyncio.run(resolve_mention("notakind", "whatever"))
    assert out.kind == "unknown"
    assert out.content == "(source not wired)"
    # Title is preserved for the UI to show.
    assert out.title == "@notakind"


# ----------------------------------------------------------------------
# Case 3 — content is bound to 4 KB.
# ----------------------------------------------------------------------


def test_content_bound_to_4kb(tmp_path):
    # 50 KB file — well over the limit.
    big = tmp_path / "huge.txt"
    big.write_text("x" * 50_000, encoding="utf-8")

    out = asyncio.run(resolve_mention("file", str(big)))
    assert len(out.content.encode("utf-8")) <= MAX_CONTENT_BYTES
    assert "(truncated)" in out.content


# ----------------------------------------------------------------------
# Case 4 — autocomplete suggests the 5 default kinds for empty query.
# ----------------------------------------------------------------------


def test_autocomplete_returns_five_default_kinds(monkeypatch):
    # Import the FastAPI app and use its TestClient — that exercises
    # the actual route, not just the helper function.
    from fastapi.testclient import TestClient
    from web_extras.app import app

    client = TestClient(app)
    r = client.get("/api/mentions/autocomplete", params={"q": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    kinds = {s["kind"] for s in body["suggestions"]}
    assert set(MENTION_KINDS).issubset(kinds), (
        f"expected all of {MENTION_KINDS} in {kinds}"
    )


def test_kinds_endpoint_lists_all_five():
    from fastapi.testclient import TestClient
    from web_extras.app import app

    client = TestClient(app)
    r = client.get("/api/mentions/kinds")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert len(body["kinds"]) == len(MENTION_KINDS)


# ----------------------------------------------------------------------
# Case 5 — chat orchestrator strips @-tokens and prepends context.
# ----------------------------------------------------------------------


def test_extract_and_strip_mentions():
    # Single-token query is the canonical Cursor-style shape;
    # multi-word queries use quotes to opt into a longer span.
    raw = 'Look at @file:foo.py and search @web:"python 3.13 release"'
    parsed = extract_mentions(raw)
    assert len(parsed) == 2
    kinds = [m["kind"] for m in parsed]
    assert kinds == ["file", "web"]
    assert parsed[0]["query"] == "foo.py"
    # Quotes are stripped by extract_mentions.
    assert parsed[1]["query"] == "python 3.13 release"

    cleaned = strip_mentions(raw)
    assert "@file" not in cleaned
    assert "@web" not in cleaned
    assert "Look at" in cleaned
    assert "search" in cleaned


def test_inject_context_prepends_preamble():
    resolved = [
        MentionResolved(
            kind="file",
            query="foo.py",
            title="@file: foo.py",
            content="```python\ndef f(): pass\n```",
        )
    ]
    body = "Read @file:foo.py and explain it"
    out = inject_context(body, resolved)
    assert "## Context from your mentions" in out
    # @-token stripped from the body.
    assert "@file:foo.py" not in out
    # Content block is present.
    assert "def f(): pass" in out
    # The user's question survives.
    assert "explain it" in out


def test_orchestrator_integration_strips_and_prepends(tmp_path):
    """End-to-end: feeding an operator message with an ``@file:``
    mention through the resolver helpers produces an LLM-bound
    string that has the file content as a preamble and no leftover
    raw markup. This is the exact pipeline the chat orchestrator
    runs in ``_run_turn``.
    """

    target = tmp_path / "module.py"
    target.write_text("VALUE = 42\n", encoding="utf-8")

    async def _go():
        operator_text = f"Please summarise @file:{target}"
        parsed = extract_mentions(operator_text)
        # Resolve through the real dispatcher.
        resolved = [
            await resolve_mention(m["kind"], m["query"]) for m in parsed
        ]
        return inject_context(operator_text, resolved)

    out = asyncio.run(_go())
    # Preamble injected.
    assert out.startswith("## Context from your mentions")
    # Content from the file is folded in.
    assert "VALUE = 42" in out
    # The user's raw ``@file:<path>`` token (no space after colon) is
    # gone from the body. The preamble title is ``@file: <path>``
    # WITH a space, so the colon-and-tight-path form should not
    # reappear anywhere downstream.
    assert f"@file:{target}" not in out
    # The user's request survives in the body.
    assert "Please summarise" in out
