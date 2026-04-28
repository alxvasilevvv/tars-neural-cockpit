"""OpenAlex REST enrichment for arXiv ids (polite pool — mailto in UA)."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from backend.core.vault import get_secret

from ..._http import DEFAULT_UA, get_json

_ARXIV_NEW = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")


def _user_agent() -> str:
    mail = get_secret("OPENALEX_EMAIL")
    if mail:
        return f"TARS/meeet (mailto:{mail})"
    return DEFAULT_UA


def _core_arxiv_id(raw: str) -> str | None:
    s = raw.strip().replace("arxiv:", "").split("/")[-1]
    m = _ARXIV_NEW.match(s)
    if not m:
        return None
    return m.group(1)


async def enrich_arxiv(arxiv_id: str) -> dict[str, Any] | None:
    """Fetch OpenAlex work metadata for a **new-style** arXiv id.

    Uses the Crossref DOI minted by arXiv (``10.48550/arXiv.<id>``).
    Old-style categories (``cs/9901001``) are not looked up.
    """

    core = _core_arxiv_id(arxiv_id)
    if not core:
        return None
    doi_url = f"https://doi.org/10.48550/arXiv.{core}"
    enc = urllib.parse.quote(doi_url, safe="")
    url = f"https://api.openalex.org/works/{enc}"
    status, data = await get_json(
        url,
        headers={"User-Agent": _user_agent()},
        timeout=12.0,
    )
    if status != 200 or not isinstance(data, dict):
        return None
    oa = data.get("open_access") or {}
    return {
        "openalex_id": data.get("id"),
        "cited_by_count": data.get("cited_by_count"),
        "publication_year": data.get("publication_year"),
        "is_open_access": bool(oa.get("is_oa")),
        "oa_url": oa.get("oa_url"),
    }
