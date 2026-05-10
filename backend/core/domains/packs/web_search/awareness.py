"""Awareness sources for the web-search pack.

The pack is on-demand: the operator (or council) calls ``search`` and
gets results back. There's no background poller — search engines have
no "stream" semantics, and politeness-rate-limit-wise nobody wants TARS
firing background queries every minute.

We expose a single config-only awareness entry so the cockpit shows
*what the pack will do* in the awareness panel: the user picks Brave /
SearXNG / DDG and that decision is itself the awareness signal.
"""

from __future__ import annotations

from ...base import AwarenessSource


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="adapter_chain",
        name="Search adapter chain",
        description=(
            "Order in which the pack tries backends: Brave → SearXNG "
            "→ DuckDuckGo. Configure BRAVE_SEARCH_API_KEY (vault) or "
            "TARS_SEARXNG_URL (env) to override. Call the 'health' "
            "action for a current snapshot."
        ),
        kind="local",
        config={
            "priority": ["brave", "searxng", "ddg"],
            "env": ["BRAVE_SEARCH_API_KEY", "TARS_SEARXNG_URL"],
        },
        fetcher=None,
    ),
)
