"""Science pack awareness sources.

The arXiv source has a live fetcher (uses the same Atom client as
``search_literature``). Crossref / Semantic Scholar / local-papers /
datasets-dir stay config-only until they get implementations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from ...base import AwarenessSource
from .actions import search_literature


async def _fetch_arxiv(args: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_categories = args.get("categories")
    if isinstance(raw_categories, list) and raw_categories:
        categories = [str(c).strip() for c in raw_categories if c]
    else:
        categories = ["cs.AI", "cs.LG", "stat.ML"]
    limit = int(args.get("limit") or 6)
    limit = max(1, min(limit, 30))

    query = " OR ".join(f"cat:{c}" for c in categories)
    res = await search_literature({"query": query, "limit": limit})
    if not res.get("ok"):
        return dict(res)
    return {
        "ok": True,
        "categories": categories,
        "limit": limit,
        "count": res.get("count"),
        "results": res.get("results"),
        "sources": ["arxiv"],
    }


async def _fetch_local_papers(args: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = str(args.get("path") or os.path.expanduser("~/Documents/papers"))
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_dir():
        return {
            "ok": True,
            "path": str(path),
            "count": 0,
            "files": [],
            "hint": "no local papers dir; create one to feed the science pack",
        }
    files: list[dict[str, Any]] = []
    for p in sorted(path.glob("*"))[:200]:
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".pdf", ".md", ".txt"}:
            continue
        try:
            stat = p.stat()
        except OSError:
            continue
        files.append(
            {
                "name": p.name,
                "ext": p.suffix.lstrip("."),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    return {
        "ok": True,
        "path": str(path),
        "count": len(files),
        "files": files,
    }


async def _fetch_datasets_dir(args: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = str(args.get("path") or os.path.expanduser("~/Datasets"))
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_dir():
        return {
            "ok": True,
            "path": str(path),
            "count": 0,
            "datasets": [],
            "hint": "no datasets dir; create one to register dataset versions",
        }
    datasets: list[dict[str, Any]] = []
    for child in sorted(path.iterdir())[:200]:
        if not child.is_dir():
            continue
        try:
            stat = child.stat()
        except OSError:
            continue
        datasets.append(
            {
                "name": child.name,
                "modified_at": stat.st_mtime,
            }
        )
    return {
        "ok": True,
        "path": str(path),
        "count": len(datasets),
        "datasets": datasets,
    }


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="arxiv",
        name="arXiv",
        description="arXiv listings filtered by user-selected categories.",
        kind="poll",
        config={
            "interval_s": 1800,
            "categories": ["cs.AI", "cs.LG", "stat.ML"],
        },
        fetcher=_fetch_arxiv,
    ),
    AwarenessSource(
        id="crossref",
        name="Crossref",
        description="DOI metadata + citations.",
        kind="poll",
        config={"interval_s": 3600},
    ),
    AwarenessSource(
        id="semantic_scholar",
        name="Semantic Scholar",
        description="Author / paper graph with embeddings.",
        kind="poll",
        config={"interval_s": 3600},
    ),
    AwarenessSource(
        id="local_papers",
        name="Local papers",
        description="A folder of PDFs/markdown indexed locally.",
        kind="local",
        config={"path": "~/Documents/papers"},
        fetcher=_fetch_local_papers,
    ),
    AwarenessSource(
        id="datasets_dir",
        name="Datasets dir",
        description="Versioned local datasets surface.",
        kind="local",
        config={"path": "~/Datasets"},
        fetcher=_fetch_datasets_dir,
    ),
)
