"""Action handlers for the science pack.

``search_literature`` is a real adapter against the public arXiv Atom
feed. Other actions remain typed stubs until they get real ground.
"""

from __future__ import annotations

from typing import Any, Mapping
from xml.etree import ElementTree as ET

from ...base import ActionSpec
from ..._http import get_text, NetworkError

ARXIV_URL = "http://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _parse_arxiv(body: str) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    out: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _NS):
        title_node = entry.find("atom:title", _NS)
        summary_node = entry.find("atom:summary", _NS)
        published_node = entry.find("atom:published", _NS)
        id_node = entry.find("atom:id", _NS)

        authors = [
            (a.findtext("atom:name", default="", namespaces=_NS) or "").strip()
            for a in entry.findall("atom:author", _NS)
        ]
        categories = [
            c.attrib.get("term", "")
            for c in entry.findall("atom:category", _NS)
            if c.attrib.get("term")
        ]

        primary = entry.find("arxiv:primary_category", _NS)
        primary_term = primary.attrib.get("term") if primary is not None else None

        out.append(
            {
                "id": (id_node.text or "").strip() if id_node is not None else "",
                "title": " ".join((title_node.text or "").split())
                if title_node is not None
                else "",
                "summary": " ".join((summary_node.text or "").split())
                if summary_node is not None
                else "",
                "published": (published_node.text or "").strip()
                if published_node is not None
                else None,
                "authors": [a for a in authors if a],
                "categories": categories,
                "primary_category": primary_term,
            }
        )
    return out


async def search_literature(args: Mapping[str, Any]) -> Mapping[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"ok": False, "error": "query_required"}

    limit = int(args.get("limit", 10))
    limit = max(1, min(limit, 50))

    try:
        status, body = await get_text(
            ARXIV_URL,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=8.0,
        )
    except NetworkError as e:
        return {
            "ok": False,
            "error": "network_error",
            "hint": "arxiv unreachable",
            "detail": str(e),
            "query": query,
        }

    if status != 200 or not body:
        return {
            "ok": False,
            "error": "upstream_status",
            "status": status,
            "query": query,
        }

    try:
        results = _parse_arxiv(body)
    except ET.ParseError as e:
        return {
            "ok": False,
            "error": "parse_error",
            "detail": str(e),
            "query": query,
        }

    return {
        "ok": True,
        "query": query,
        "count": len(results),
        "results": results,
        "sources": ["arxiv"],
    }


async def summarize_paper(args: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = str(args.get("ref", "")).strip()
    if not ref:
        return {"ok": False, "error": "ref_required"}
    return {
        "ok": True,
        "ref": ref,
        "tldr": "Paper summary stub.",
        "claims": [],
        "experiments": [],
    }


async def extract_dataset(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "datasets": [],
        "as_of": None,
    }


async def hypothesis_tree(args: Mapping[str, Any]) -> Mapping[str, Any]:
    seed = str(args.get("seed", "")).strip()
    if not seed:
        return {"ok": False, "error": "seed_required"}
    return {
        "ok": True,
        "seed": seed,
        "tree": {"node": seed, "children": []},
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="search_literature",
        name="Search literature",
        description="Live arXiv search via the public Atom API.",
        handler=search_literature,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    ),
    ActionSpec(
        id="summarize_paper",
        name="Summarize paper",
        description="Summarize an arXiv id, DOI, or local PDF path.",
        handler=summarize_paper,
        schema={
            "type": "object",
            "properties": {"ref": {"type": "string"}},
            "required": ["ref"],
        },
    ),
    ActionSpec(
        id="extract_dataset",
        name="Extract dataset",
        description="Extract dataset references and pinned versions.",
        handler=extract_dataset,
        schema={"type": "object", "properties": {}},
    ),
    ActionSpec(
        id="hypothesis_tree",
        name="Hypothesis tree",
        description="Grow a hypothesis tree from a seed claim.",
        handler=hypothesis_tree,
        schema={
            "type": "object",
            "properties": {"seed": {"type": "string"}},
            "required": ["seed"],
        },
    ),
)
