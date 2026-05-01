"""Crossref REST fallback for OLD-style arXiv ids.

OpenAlex resolution piggybacks on the Crossref DOI ``10.48550/arXiv.<id>``
that arXiv started minting only for new-style ids (and only retroactively
for a slice of older ones). For pre-2007 ids like ``cs/9901001`` or
``math.AT/0701035`` the OpenAlex DOI lookup 404s, so we fall back to a
Crossref bibliographic search using title + first-author surname pulled
from the arXiv Atom record.

Polite-pool usage: send ``mailto`` in the User-Agent if
``CROSSREF_EMAIL`` (or ``OPENALEX_EMAIL``) is set in the vault.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from backend.core.vault import get_secret

from ..._http import DEFAULT_UA, get_json

_TITLE_NORMALISE = re.compile(r"[^a-z0-9 ]+")


def _user_agent() -> str:
    mail = get_secret("CROSSREF_EMAIL") or get_secret("OPENALEX_EMAIL")
    if mail:
        return f"TARS/meeet (mailto:{mail})"
    return DEFAULT_UA


def _normalise_title(s: str) -> str:
    return _TITLE_NORMALISE.sub(" ", (s or "").lower()).strip()


def _title_overlap(a: str, b: str) -> float:
    """Crude Jaccard over space-split tokens; good enough for a sanity gate."""

    ta = {t for t in _normalise_title(a).split() if len(t) > 2}
    tb = {t for t in _normalise_title(b).split() if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _first_surname(authors: Sequence[str]) -> str | None:
    for raw in authors:
        if not raw:
            continue
        parts = raw.strip().split()
        if parts:
            return parts[-1]
    return None


def _publication_year(item: dict[str, Any]) -> int | None:
    for k in ("issued", "published-print", "published-online", "created"):
        node = item.get(k)
        if not isinstance(node, dict):
            continue
        date_parts = node.get("date-parts") or []
        if date_parts and isinstance(date_parts, list):
            head = date_parts[0]
            if isinstance(head, list) and head and isinstance(head[0], int):
                return int(head[0])
    return None


async def enrich_via_crossref(
    arxiv_id: str,
    *,
    title: str | None,
    authors: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    """Resolve an OLD-style arXiv id against Crossref's bibliographic search.

    Returns ``None`` when the response is missing, the network is down, or
    the top hit's title is not a plausible match (Jaccard < 0.4) — the
    caller is expected to keep the arXiv-only result rather than attach a
    confidently-wrong DOI.
    """

    if not title:
        return None

    params: dict[str, Any] = {
        "query.bibliographic": title,
        "rows": 3,
        "select": (
            "DOI,title,author,publisher,is-referenced-by-count,issued,"
            "published-print,published-online,created"
        ),
    }
    surname = _first_surname(authors or ())
    if surname:
        params["query.author"] = surname

    try:
        status, data = await get_json(
            "https://api.crossref.org/works",
            params=params,
            headers={"User-Agent": _user_agent()},
            timeout=12.0,
        )
    except Exception:
        return None
    if status != 200 or not isinstance(data, dict):
        return None

    items = (data.get("message") or {}).get("items") or []
    if not isinstance(items, list) or not items:
        return None

    best: dict[str, Any] | None = None
    best_score = 0.0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        cand_title = ""
        title_node = raw.get("title")
        if isinstance(title_node, list) and title_node:
            cand_title = str(title_node[0])
        elif isinstance(title_node, str):
            cand_title = title_node
        score = _title_overlap(title, cand_title)
        if score > best_score:
            best = raw
            best_score = score

    if not best or best_score < 0.4:
        return None

    doi = best.get("DOI")
    if not isinstance(doi, str) or not doi:
        return None

    out: dict[str, Any] = {
        "source": "crossref",
        "arxiv_id": arxiv_id,
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "publisher": best.get("publisher"),
        "publication_year": _publication_year(best),
        "cited_by_count": best.get("is-referenced-by-count"),
        "title_match": round(best_score, 3),
    }
    return out
