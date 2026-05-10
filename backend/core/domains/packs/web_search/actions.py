"""Action handlers for the web-search pack.

The single shipped action is ``search`` — a backend-agnostic wrapper
that picks one of three adapters based on what's configured:

1. **Brave** (`BRAVE_SEARCH_API_KEY`) — fastest + highest quality, free
   tier 2 000 q/month.
2. **SearXNG** (`TARS_SEARXNG_URL=…`) — self-host, max privacy.
3. **DuckDuckGo** (no key) — keyless fallback so a fresh install with
   nothing configured still returns useful results.

Operators can pin a specific adapter via the ``adapter`` arg
(``"brave" | "searxng" | "ddg" | "auto"``). ``auto`` (default) walks
the priority list and returns the first ``ok=True`` adapter, keeping
``tried`` in the response so the cockpit can show what was attempted.

Also includes a tiny ``health`` action so the cockpit / CLI can render
adapter availability without running a real query.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from backend.core.vault import get_secret

from ...base import ActionSpec
from .adapters import AdapterResult, dedupe
from .adapters import brave as brave_adapter
from .adapters import ddg as ddg_adapter
from .adapters import searxng as searxng_adapter

DEFAULT_LIMIT = 10
MAX_LIMIT = 25
ADAPTER_NAMES = ("brave", "searxng", "ddg")


def _coerce_limit(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


def _resolve_brave_key() -> str | None:
    """Vault-first lookup (env → Keychain inside ``get_secret``)."""
    val = get_secret("BRAVE_SEARCH_API_KEY")
    if val:
        return val
    return None


def _resolve_searxng_url() -> str | None:
    raw = os.environ.get("TARS_SEARXNG_URL", "").strip()
    return raw or None


def _planned_order(
    requested: str,
    *,
    have_brave: bool,
    have_searxng: bool,
) -> tuple[str, ...]:
    """Decide which adapters to try, in what order.

    ``requested`` is the user-supplied ``adapter`` arg. If it's a known
    backend, we try only that. ``auto`` walks the priority chain and
    skips backends that aren't configured.
    """
    if requested in ADAPTER_NAMES:
        return (requested,)
    chain: list[str] = []
    if have_brave:
        chain.append("brave")
    if have_searxng:
        chain.append("searxng")
    chain.append("ddg")  # keyless fallback always last
    return tuple(chain)


async def _run_one(
    name: str,
    *,
    query: str,
    limit: int,
    brave_key: str | None,
    searxng_url: str | None,
) -> AdapterResult:
    if name == "brave":
        if not brave_key:
            return AdapterResult(
                ok=False, adapter="brave", error="api_key_missing"
            )
        return await brave_adapter.search(
            query, limit=limit, api_key=brave_key
        )
    if name == "searxng":
        if not searxng_url:
            return AdapterResult(
                ok=False, adapter="searxng", error="base_url_missing"
            )
        return await searxng_adapter.search(
            query, limit=limit, base_url=searxng_url
        )
    if name == "ddg":
        return await ddg_adapter.search(query, limit=limit)
    return AdapterResult(
        ok=False, adapter=name, error="unknown_adapter"
    )


async def search(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Run a web search and return normalised hits.

    Args:
      ``query``: required, the search query.
      ``limit``: optional int, 1..25, default 10.
      ``adapter``: optional ``"auto" | "brave" | "searxng" | "ddg"``.
    """

    query = str(args.get("query", "")).strip()
    if not query:
        return {"ok": False, "error": "query_required"}

    limit = _coerce_limit(args.get("limit", DEFAULT_LIMIT))
    requested = str(args.get("adapter", "auto") or "auto").strip().lower()

    brave_key = _resolve_brave_key()
    searxng_url = _resolve_searxng_url()
    plan = _planned_order(
        requested,
        have_brave=bool(brave_key),
        have_searxng=bool(searxng_url),
    )

    tried: list[dict[str, Any]] = []
    chosen: AdapterResult | None = None
    for name in plan:
        result = await _run_one(
            name,
            query=query,
            limit=limit,
            brave_key=brave_key,
            searxng_url=searxng_url,
        )
        tried.append(
            {
                "adapter": result.adapter,
                "ok": result.ok,
                "error": result.error,
                "upstream_status": result.upstream_status,
                "count": len(result.hits),
            }
        )
        if result.ok and result.hits:
            chosen = result
            break

    if chosen is None:
        return {
            "ok": False,
            "error": "all_adapters_failed",
            "query": query,
            "tried": tried,
            "hint": (
                "Set BRAVE_SEARCH_API_KEY for the highest-quality path, "
                "or TARS_SEARXNG_URL=http://127.0.0.1:8080 to use a "
                "self-hosted SearXNG. Keyless DDG fallback may be "
                "rate-limited."
            ),
        }

    hits = dedupe(chosen.hits)
    return {
        "ok": True,
        "query": query,
        "adapter": chosen.adapter,
        "tried": tried,
        "count": len(hits),
        "results": [h.to_dict() for h in hits],
    }


async def health(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Adapter availability snapshot — no network calls.

    Useful for the cockpit / CLI "Web search · ready" badge: shows
    which backends will be tried, without burning a search quota.
    """

    brave_key = _resolve_brave_key()
    searxng_url = _resolve_searxng_url()
    plan = _planned_order(
        "auto", have_brave=bool(brave_key), have_searxng=bool(searxng_url)
    )
    return {
        "ok": True,
        "default_order": list(plan),
        "adapters": {
            "brave": {
                "configured": bool(brave_key),
                "via": "vault:BRAVE_SEARCH_API_KEY or env",
            },
            "searxng": {
                "configured": bool(searxng_url),
                "via": "env:TARS_SEARXNG_URL",
            },
            "ddg": {"configured": True, "via": "always-on (keyless)"},
        },
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="search",
        name="Web search",
        description=(
            "Search the public web via Brave (preferred), SearXNG, or "
            "DuckDuckGo (keyless fallback). Returns title / url / snippet "
            "rows the council can cite. Pass adapter='brave|searxng|ddg' "
            "to pin a specific backend; 'auto' (default) walks the "
            "priority chain."
        ),
        handler=search,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_LIMIT,
                    "default": DEFAULT_LIMIT,
                },
                "adapter": {
                    "type": "string",
                    "enum": ["auto", "brave", "searxng", "ddg"],
                    "default": "auto",
                },
            },
            "required": ["query"],
        },
    ),
    ActionSpec(
        id="health",
        name="Adapter health",
        description=(
            "Snapshot of which web-search adapters are configured. "
            "No network calls — safe to poll from the cockpit / CLI."
        ),
        handler=health,
        schema={"type": "object", "properties": {}},
    ),
)
