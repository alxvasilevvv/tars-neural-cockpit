from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec


async def search_literature(args: Mapping[str, Any]) -> Mapping[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"ok": False, "error": "query_required"}
    return {
        "ok": True,
        "query": query,
        "results": [],
        "sources": ["arxiv", "crossref", "semantic_scholar"],
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
        description="Query arXiv / Crossref / Semantic Scholar in parallel.",
        handler=search_literature,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
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
