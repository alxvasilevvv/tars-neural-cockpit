"""SearXNG adapter — for the self-host crowd.

SearXNG is a meta-search engine the operator can run locally
(``docker run searxng/searxng``) and configure as TARS's preferred
backend by setting ``TARS_SEARXNG_URL=http://127.0.0.1:8080``.

Endpoint: ``GET <base>/search?q=<query>&format=json``. Response is
``{"results": [{"title", "url", "content", "engine"}, …]}``.

This adapter is the most "private" of the three: query never leaves
the operator's network when SearXNG runs locally.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ...._http import NetworkError, get_text
from ._base import AdapterResult, SearchHit, trim


def _normalise_base(base: str) -> str:
    base = (base or "").strip()
    if not base:
        return ""
    if not base.endswith("/"):
        base = base + "/"
    return base


async def search(
    query: str,
    *,
    limit: int,
    base_url: str,
    timeout: float = 8.0,
) -> AdapterResult:
    base = _normalise_base(base_url)
    if not base:
        return AdapterResult(
            ok=False, adapter="searxng", error="base_url_missing"
        )

    endpoint = f"{base}search"
    try:
        status, body = await get_text(
            endpoint,
            params={"q": query, "format": "json", "safesearch": 1},
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except NetworkError as e:
        return AdapterResult(
            ok=False, adapter="searxng", error="network_error", detail=str(e)
        )

    if status >= 400 or not body:
        return AdapterResult(
            ok=False,
            adapter="searxng",
            error="upstream_status",
            upstream_status=status,
        )

    try:
        payload: Any = json.loads(body)
    except json.JSONDecodeError as e:
        return AdapterResult(
            ok=False, adapter="searxng", error="parse_error", detail=str(e)
        )

    rows = payload.get("results") or [] if isinstance(payload, Mapping) else []
    out: list[SearchHit] = []
    for row in rows[:limit]:
        if not isinstance(row, Mapping):
            continue
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        if not url or not title:
            continue
        snippet = trim(row.get("content") or "")
        extra: dict = {}
        engine = row.get("engine")
        if engine:
            extra["engine"] = str(engine)
        out.append(
            SearchHit(
                title=title,
                url=url,
                snippet=snippet,
                source="searxng",
                extra=extra,
            )
        )

    return AdapterResult(ok=True, adapter="searxng", hits=tuple(out))


__all__ = ["search", "_normalise_base"]
