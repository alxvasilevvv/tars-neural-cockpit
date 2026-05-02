"""Action handlers for the science pack.

``search_literature`` is a real adapter against the public arXiv Atom
feed. Other actions remain typed stubs until they get real ground.
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from xml.etree import ElementTree as ET

from ...base import ActionSpec
from ..._http import NetworkError, get_text
from .crossref import enrich_via_crossref
from .datasets import extract_datasets_from_text
from .hypothesis import grow_tree
from .openalex import enrich_arxiv

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


_ARXIV_ID_RE = re.compile(
    r"(\d{4}\.\d{4,5}(?:v\d+)?)|((?:[a-z\-]+(?:\.[A-Z]{2})?)/\d{7})"
)
_ARXIV_NEW_STYLE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")


def _is_old_style_arxiv(arxiv_id: str) -> bool:
    return "/" in arxiv_id and not _ARXIV_NEW_STYLE.match(arxiv_id)


def _normalize_arxiv_ref(ref: str) -> str | None:
    """Pull a canonical arXiv id out of common shapes.

    Accepts: ``2305.13245``, ``arxiv:2305.13245``, full URLs like
    ``https://arxiv.org/abs/2305.13245`` and old-style ``cs/9901001`` or
    ``cs.AI/0301001``. Returns ``None`` if nothing recognisable is found.
    """

    if not ref:
        return None
    candidate = ref.strip()
    candidate = candidate.replace("arxiv:", "").replace("arXiv:", "")
    m = _ARXIV_ID_RE.search(candidate)
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip() or None


async def summarize_paper(args: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = str(args.get("ref", "")).strip()
    if not ref:
        return {"ok": False, "error": "ref_required"}

    arxiv_id = _normalize_arxiv_ref(ref)
    if not arxiv_id:
        return {
            "ok": False,
            "error": "ref_unrecognised",
            "hint": "expected arxiv id like 2305.13245 or full arxiv url",
            "ref": ref,
        }

    try:
        status, body = await get_text(
            ARXIV_URL,
            params={"id_list": arxiv_id, "max_results": 1},
            timeout=8.0,
        )
    except NetworkError as e:
        return {
            "ok": False,
            "error": "network_error",
            "hint": "arxiv unreachable",
            "detail": str(e),
            "arxiv_id": arxiv_id,
        }

    if status != 200 or not body:
        return {
            "ok": False,
            "error": "upstream_status",
            "status": status,
            "arxiv_id": arxiv_id,
        }

    try:
        results = _parse_arxiv(body)
    except ET.ParseError as e:
        return {
            "ok": False,
            "error": "parse_error",
            "detail": str(e),
            "arxiv_id": arxiv_id,
        }

    if not results:
        return {
            "ok": False,
            "error": "not_found",
            "arxiv_id": arxiv_id,
        }

    paper = results[0]
    abstract = paper.get("summary") or ""
    sentences = [s.strip() for s in abstract.replace("\n", " ").split(". ") if s.strip()]
    tldr = ". ".join(sentences[:2])
    if tldr and not tldr.endswith("."):
        tldr += "."

    out: dict[str, Any] = {
        "ok": True,
        "arxiv_id": arxiv_id,
        "ref": ref,
        "title": paper.get("title"),
        "authors": paper.get("authors"),
        "published": paper.get("published"),
        "primary_category": paper.get("primary_category"),
        "categories": paper.get("categories"),
        "tldr": tldr,
        "abstract": abstract,
        "sentences": len(sentences),
        "url": paper.get("id"),
        "sources": ["arxiv"],
    }
    try:
        olex = await enrich_arxiv(arxiv_id)
    except Exception:
        olex = None
    if olex:
        out["openalex"] = olex
        src = list(out["sources"])
        src.append("openalex")
        out["sources"] = src
    elif _is_old_style_arxiv(arxiv_id):
        try:
            cref = await enrich_via_crossref(
                arxiv_id,
                title=paper.get("title"),
                authors=paper.get("authors") or (),
            )
        except Exception:
            cref = None
        if cref:
            out["crossref"] = cref
            src = list(out["sources"])
            src.append("crossref")
            out["sources"] = src
    return out


async def extract_dataset(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Surface dataset references in a paper abstract or raw text.

    Three input shapes are supported (in priority order):

    - ``text``: any operator-provided string. Useful for the
      cockpit's "paste a paper passage" affordance and to keep
      the detector unit-testable without network or storage.
    - ``attachment_id``: id of a chat attachment that's already
      been ingested. The handler reads ``record.extracted_text``
      (the same field that backs the chunker / FTS index) and
      runs the detector over it. Lets an operator point at a
      PDF they've uploaded and ask "what datasets does this
      paper cite?" without re-fetching arXiv.
    - ``ref``: an arXiv id / DOI / arxiv URL. The handler fetches
      the title + abstract via the same arXiv Atom path that
      backs ``summarize_paper`` and runs the detector over
      ``title + ". " + summary``.

    If multiple are provided, the priority above wins. The
    detector is the same in all three cases — it operates on
    text, so the input shape only changes the *source* of that
    text.

    Returns ``{ok, datasets[], count, sources[]}`` where each
    dataset row is ``{canonical_id, name, source, evidence,
    url?, domain?}``. ``sources`` lists the high-level providers
    that contributed (``known_dataset``, ``zenodo``, etc.) so
    the cockpit can render lane chips.

    Errors flow through the same ``ok=False, error=…`` shape as
    ``summarize_paper`` so domain pack policy stays uniform.
    """

    text = str(args.get("text") or "").strip()
    attachment_id = str(args.get("attachment_id") or "").strip()
    ref = str(args.get("ref") or "").strip()

    if not text and not attachment_id and not ref:
        return {"ok": False, "error": "ref_or_text_or_attachment_required"}

    payload: dict[str, Any] = {"ok": True}

    if not text and attachment_id:
        # Lazy import to keep the science pack importable in test
        # environments that don't bring up the chat / attachment
        # stack.
        from backend.core.attachments import get_attachment_store

        store = get_attachment_store()
        record = await store.get_attachment(attachment_id)
        if record is None:
            return {
                "ok": False,
                "error": "attachment_not_found",
                "attachment_id": attachment_id,
            }
        attachment_text = (record.extracted_text or "").strip()
        if not attachment_text:
            return {
                "ok": False,
                "error": "attachment_empty",
                "hint": (
                    "attachment has no extracted text — re-ingest with a "
                    "supported extractor or run with text=… instead"
                ),
                "attachment_id": attachment_id,
            }
        text = attachment_text
        payload["attachment_id"] = attachment_id
        payload["filename"] = record.filename
        payload["mime"] = record.mime
        payload["thread_id"] = record.thread_id

    if not text:
        arxiv_id = _normalize_arxiv_ref(ref)
        if not arxiv_id:
            return {
                "ok": False,
                "error": "ref_unrecognised",
                "hint": "expected arxiv id like 2305.13245 or full arxiv url",
                "ref": ref,
            }
        try:
            status, body = await get_text(
                ARXIV_URL,
                params={"id_list": arxiv_id, "max_results": 1},
                timeout=8.0,
            )
        except NetworkError as e:
            return {
                "ok": False,
                "error": "network_error",
                "hint": "arxiv unreachable",
                "detail": str(e),
                "arxiv_id": arxiv_id,
            }
        if status != 200 or not body:
            return {
                "ok": False,
                "error": "upstream_status",
                "status": status,
                "arxiv_id": arxiv_id,
            }
        try:
            results = _parse_arxiv(body)
        except ET.ParseError as e:
            return {
                "ok": False,
                "error": "parse_error",
                "detail": str(e),
                "arxiv_id": arxiv_id,
            }
        if not results:
            return {
                "ok": False,
                "error": "not_found",
                "arxiv_id": arxiv_id,
            }
        paper = results[0]
        title = (paper.get("title") or "").strip()
        summary = (paper.get("summary") or "").strip()
        text = (title + ". " + summary).strip(". ").strip()
        payload["arxiv_id"] = arxiv_id
        payload["ref"] = ref
        payload["title"] = paper.get("title")

    mentions = extract_datasets_from_text(text)
    payload["datasets"] = [m.to_dict() for m in mentions]
    payload["count"] = len(mentions)
    payload["sources"] = sorted({m.source for m in mentions})
    return payload


async def hypothesis_tree(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Grow a deterministic hypothesis tree from a seed claim.

    Args:
      ``seed``: required, the parent claim (e.g. "X causes Y").
      ``depth``: optional int in ``[0, 3]``; default ``1`` (seed +
        one child layer along the five canonical dimensions).
        Garbage / negative values are coerced to ``1``.

    Returns ``{ok: True, seed, depth, tree, model}`` on success or
    ``{ok: False, error: "seed_required"}`` if the seed is blank.

    The tree carries stable ``h-NNNN`` ids so the cockpit can pin
    expand state across renders, and a ``kind`` per node
    (`seed / mechanism / alternatives / confounders / conditions /
    evidence / step / alternative / confounder / condition / test`)
    so the renderer can colour-code the layers.
    """

    seed_raw = str(args.get("seed", "")).strip()
    if not seed_raw:
        return {"ok": False, "error": "seed_required"}

    depth_arg = args.get("depth", 1)
    if isinstance(depth_arg, bool):
        depth = 1
    elif isinstance(depth_arg, int):
        depth = depth_arg
    else:
        depth = 1

    try:
        tree = grow_tree(seed_raw, depth=depth)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    # The action echoes the *effective* depth so callers can verify
    # what the tree actually contains. ``grow_tree`` clamps negatives
    # back to the default (1) and clips above 3.
    effective_depth = depth if depth >= 0 else 1
    effective_depth = min(effective_depth, 3)
    return {
        "ok": True,
        "seed": tree.node,
        "depth": effective_depth,
        "tree": tree.to_dict(),
        "model": "heuristic-v1",
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
        description=(
            "Surface dataset references in a paper (arXiv ref), an "
            "uploaded attachment, or operator-provided text. Detects "
            "~25 named datasets (ImageNet, COCO, GLUE, SQuAD, …) plus "
            "repository URL patterns (Zenodo, Figshare, HuggingFace, "
            "Kaggle, …)."
        ),
        handler=extract_dataset,
        schema={
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "arXiv id / DOI / arxiv URL.",
                },
                "text": {
                    "type": "string",
                    "description": (
                        "Raw text to scan; takes priority over "
                        "'attachment_id' and 'ref' when provided."
                    ),
                },
                "attachment_id": {
                    "type": "string",
                    "description": (
                        "Id of an ingested chat attachment. Reads "
                        "extracted_text from the attachment store; "
                        "falls back to 'ref' when both are missing."
                    ),
                },
            },
        },
    ),
    ActionSpec(
        id="hypothesis_tree",
        name="Hypothesis tree",
        description=(
            "Grow a deterministic hypothesis tree from a seed claim. "
            "Each child probes one of five canonical dimensions a peer "
            "reviewer would interrogate (mechanism, alternatives, "
            "confounders, conditions, evidence). Nodes carry stable "
            "h-NNNN ids and a typed 'kind' so the cockpit can colour-"
            "code the layers. Set 'depth' to 0 for the seed only, 1 "
            "for one layer (default), 2 for grandchildren, max 3."
        ),
        handler=hypothesis_tree,
        schema={
            "type": "object",
            "properties": {
                "seed": {"type": "string"},
                "depth": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 3,
                    "default": 1,
                },
            },
            "required": ["seed"],
        },
    ),
)
