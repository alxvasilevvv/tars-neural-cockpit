"""HTTP surface for the @-mention chat-context resolver (W240).

Two endpoints, both intentionally tiny:

- ``GET  /api/mentions/autocomplete?q=<partial>`` — frontend dropdown
  suggestions. Returns the five built-in kinds whenever the partial
  is empty / generic, plus narrowed completions for kind-specific
  partials (``file:`` paths from the repo, ``recent`` snapshots,
  etc.).

- ``POST /api/mentions/resolve`` — body ``{"mentions": [{"kind",
  "query"}, …]}`` — runs the batch through
  :func:`backend.core.mentions.resolve_mentions` and returns the
  list of :class:`MentionResolved` dicts.

Both calls are read-only and policy-mode-agnostic — there is no
spend, no LLM round-trip, and no side-effect on the receipt
ledger. The chat orchestrator handles the actual context
injection at message-send time; these routes exist so the
frontend can render previews and chips without having to ship the
same resolver code in JS.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Query

from backend.core.mentions import (
    MENTION_KINDS,
    resolve_mentions,
)


router = APIRouter(prefix="/api/mentions", tags=["mentions"])


_KIND_PREVIEWS: dict[str, str] = {
    "file": "Read up to 200 lines of a file as fenced context.",
    "docs": "Search the knowledge brain for matching chunks.",
    "web": "Brave / SearXNG / DDG live web search.",
    "recent": "Last 5 signed receipts (actions you took).",
    "code": "Code RAG / ripgrep across the repo.",
}


def _default_suggestions(q: str) -> list[dict[str, str]]:
    """The unfiltered top-level dropdown shown right after typing ``@``.

    Returns one entry per kind in display order.
    """

    needle = (q or "").lower().strip().lstrip("@").rstrip(":")
    out: list[dict[str, str]] = []
    for kind in MENTION_KINDS:
        if needle and not kind.startswith(needle):
            continue
        out.append(
            {
                "kind": kind,
                "query": "",
                "label": f"@{kind}",
                "preview": _KIND_PREVIEWS.get(kind, ""),
            }
        )
    return out


def _file_suggestions(partial: str, *, limit: int = 8) -> list[dict[str, str]]:
    """Best-effort file-path autocomplete rooted at CWD.

    Walks one directory level off the partial path; cheap enough
    to run synchronously inside the request handler, never errors
    out — a missing dir just returns ``[]``.
    """

    raw = (partial or "").strip()
    base = Path(os.path.expanduser(raw)) if raw else Path(".")
    try:
        if base.is_dir():
            entries = list(base.iterdir())
            prefix = ""
        else:
            entries = list((base.parent if base.parent.exists() else Path(".")).iterdir())
            prefix = base.name.lower()
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for p in entries:
        if p.name.startswith("."):
            continue
        if prefix and not p.name.lower().startswith(prefix):
            continue
        if p.is_dir():
            label = f"@file:{p}/"
        else:
            label = f"@file:{p}"
        out.append(
            {
                "kind": "file",
                "query": str(p),
                "label": label,
                "preview": "directory" if p.is_dir() else (p.suffix or "file"),
            }
        )
        if len(out) >= limit:
            break
    return out


@router.get("/autocomplete")
async def autocomplete(
    q: str = Query(default="", description="Partial @-mention text"),
) -> dict[str, Any]:
    """Return dropdown suggestions for what the operator has typed.

    Three shapes are supported:

    * Empty / bare ``@`` → return the five built-in kinds.
    * ``@kind`` prefix   → narrow the kind list to matches.
    * ``@kind:partial``  → drill into per-kind autocomplete
      (currently: ``file:`` does a path scan).
    """

    raw = (q or "").strip()
    # Strip a leading ``@`` if the frontend kept it.
    body = raw.lstrip("@")
    if not body or ":" not in body:
        return {"ok": True, "suggestions": _default_suggestions(raw)}

    kind, _, partial = body.partition(":")
    kind = kind.strip().lower()
    partial = partial.strip()
    if kind not in MENTION_KINDS:
        return {"ok": True, "suggestions": _default_suggestions(raw)}

    if kind == "file":
        return {"ok": True, "suggestions": _file_suggestions(partial)}

    # Generic per-kind hint when no special autocomplete is wired.
    return {
        "ok": True,
        "suggestions": [
            {
                "kind": kind,
                "query": partial,
                "label": f"@{kind}:{partial or '…'}",
                "preview": _KIND_PREVIEWS.get(kind, ""),
            }
        ],
    }


@router.post("/resolve")
async def resolve(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Resolve a batch of mentions and return the markdown context.

    Body shape::

        {"mentions": [{"kind": "file", "query": "src/foo.py"}, …]}

    Returns ``{"ok": true, "resolved": [MentionResolved…]}`` in the
    same order as the input list. Failures inside any one resolver
    produce a "(source not wired)" / "(failed)" payload rather
    than a 5xx — the chat orchestrator depends on this.
    """

    body = payload or {}
    raw = body.get("mentions") or []
    if not isinstance(raw, list):
        return {"ok": False, "error": "mentions_must_be_list", "resolved": []}
    parsed: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        parsed.append(
            {
                "kind": str(item.get("kind") or "").strip(),
                "query": str(item.get("query") or "").strip(),
            }
        )
    resolved = await resolve_mentions(parsed)
    return {
        "ok": True,
        "resolved": [r.to_dict() for r in resolved],
    }


@router.get("/kinds")
async def kinds() -> dict[str, Any]:
    """List supported mention kinds + their previews.

    Convenience endpoint for the UI when it wants to render the
    full menu without typing ``@`` first.
    """

    return {
        "ok": True,
        "kinds": [
            {"kind": k, "label": f"@{k}", "preview": _KIND_PREVIEWS.get(k, "")}
            for k in MENTION_KINDS
        ],
    }
