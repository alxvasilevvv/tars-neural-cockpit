"""Brave Search adapter.

Brave's free Data-for-AI tier ships 2 000 queries/month at no cost
and only needs a single header (`X-Subscription-Token`). It returns
JSON, so parsing is one ``json.loads`` away. We deliberately request
only the ``web`` results vertical (no images / news / video) — those
verticals can be added later behind explicit args.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ...._http import NetworkError, get_text
from ._base import AdapterResult, SearchHit, trim


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


async def search(
    query: str,
    *,
    limit: int,
    api_key: str,
    timeout: float = 8.0,
) -> AdapterResult:
    """Run a Brave web search and normalise the result rows.

    ``api_key`` is required. The caller (pack-level dispatcher) is
    responsible for resolving it from the vault and only invoking this
    adapter when the key is present.
    """

    if not api_key:
        return AdapterResult(
            ok=False, adapter="brave", error="api_key_missing"
        )

    try:
        status, body = await get_text(
            BRAVE_ENDPOINT,
            params={
                "q": query,
                "count": max(1, min(limit, 20)),
                "safesearch": "moderate",
                "result_filter": "web",
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "X-Subscription-Token": api_key,
            },
            timeout=timeout,
        )
    except NetworkError as e:
        return AdapterResult(
            ok=False, adapter="brave", error="network_error", detail=str(e)
        )

    if status == 401 or status == 403:
        return AdapterResult(
            ok=False,
            adapter="brave",
            error="unauthorized",
            detail="Brave rejected the API key — rotate or check rate limit.",
            upstream_status=status,
        )
    if status == 429:
        return AdapterResult(
            ok=False,
            adapter="brave",
            error="rate_limited",
            detail="Brave free tier exceeded — falls back to next adapter.",
            upstream_status=status,
        )
    if status >= 400 or not body:
        return AdapterResult(
            ok=False,
            adapter="brave",
            error="upstream_status",
            upstream_status=status,
        )

    try:
        payload: Any = json.loads(body)
    except json.JSONDecodeError as e:
        return AdapterResult(
            ok=False, adapter="brave", error="parse_error", detail=str(e)
        )

    hits = _extract_hits(payload, limit=limit)
    return AdapterResult(ok=True, adapter="brave", hits=tuple(hits))


def _extract_hits(payload: Mapping[str, Any], *, limit: int) -> list[SearchHit]:
    web = payload.get("web") or {}
    rows = web.get("results") or []
    out: list[SearchHit] = []
    for row in rows[:limit]:
        if not isinstance(row, Mapping):
            continue
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        if not url or not title:
            continue
        snippet = trim(row.get("description") or "")
        extra: dict = {}
        if row.get("age"):
            extra["age"] = row["age"]
        if row.get("language"):
            extra["language"] = row["language"]
        out.append(
            SearchHit(
                title=title,
                url=url,
                snippet=snippet,
                source="brave",
                extra=extra,
            )
        )
    return out
