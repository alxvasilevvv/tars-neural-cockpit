"""Central registry for the marketplace (Wave 106).

Default source is a JSON manifest at the public repo
``alxvasilevvv/tars-marketplace`` (raw URL pinned below). The file
may not exist yet -- the registry falls back to the bundled
:mod:`.seed` list. Cached on disk for 1h at
``~/.tars/marketplace/registry.json``; ``force_refresh=True``
always re-fetches.

The fetcher uses ``urllib.request`` with a 5s timeout so the
endpoint is import-safe in environments without ``httpx``. Errors
fall through to the seed; the FE renders a "registry unreachable"
banner using the ``source`` field returned alongside the listings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .models import Listing
from .seed import seed_listings


log = logging.getLogger("tars.marketplace.registry")


DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/alxvasilevvv/"
    "tars-marketplace/main/registry.json"
)
DEFAULT_CACHE_DIR = "~/.tars/marketplace"
DEFAULT_CACHE_FILE = "registry.json"
CACHE_TTL_S = 3600  # 1 hour


def _cache_dir() -> Path:
    raw = os.getenv("TARS_MARKETPLACE_CACHE_DIR") or DEFAULT_CACHE_DIR
    p = Path(os.path.expanduser(raw))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_path() -> Path:
    return _cache_dir() / DEFAULT_CACHE_FILE


def _registry_url() -> str:
    return os.getenv("TARS_MARKETPLACE_URL") or DEFAULT_REGISTRY_URL


def _is_offline() -> bool:
    """Skip the network fetch entirely when the env says so.

    Useful in CI / tests so we don't wait for a 5s timeout every
    time. The flag also short-circuits the cache file write so
    test isolation is clean.
    """

    flag = (os.getenv("TARS_MARKETPLACE_OFFLINE") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _read_cache() -> dict[str, Any] | None:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception as exc:  # pragma: no cover - corruption path
        log.warning("registry_cache_unreadable: %s", exc)
        return None


def _write_cache(payload: dict[str, Any]) -> None:
    if _is_offline():
        return
    p = _cache_path()
    try:
        p.write_text(json.dumps(payload, indent=2), "utf-8")
    except Exception as exc:  # pragma: no cover - permissions path
        log.warning("registry_cache_unwritable: %s", exc)


def _fresh_enough(payload: dict[str, Any]) -> bool:
    fetched_at = float(payload.get("fetched_at") or 0.0)
    return (time.time() - fetched_at) < CACHE_TTL_S


def _fetch_remote_sync() -> list[dict[str, Any]] | None:
    """Synchronous fetch -- called from a thread by ``fetch_registry``.

    Returns ``None`` on any failure so the caller can fall back to
    the seed without raising into the request handler.
    """

    if _is_offline():
        return None
    url = _registry_url()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tars-marketplace/v0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
        body = json.loads(raw.decode("utf-8"))
        items = body.get("listings") if isinstance(body, dict) else body
        if not isinstance(items, list):
            return None
        return [dict(item) for item in items if isinstance(item, dict)]
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        log.info("registry_fetch_failed source=%s err=%s", url, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("registry_fetch_unexpected source=%s err=%s", url, exc)
        return None


def _normalise(items: list[dict[str, Any]]) -> list[Listing]:
    out: list[Listing] = []
    for raw in items:
        try:
            out.append(Listing.from_dict(raw))
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("listing_normalise_failed: %s", exc)
    return out


async def fetch_registry(
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return the merged registry: ``{source, fetched_at, listings}``.

    Resolution order:

    1. Cached file < 1h old (skipped when ``force_refresh=True``).
    2. Remote fetch from ``TARS_MARKETPLACE_URL`` (5s timeout).
    3. Bundled seed.

    The result is always a dict with ``source`` in
    ``{cache, remote, seed}`` and ``listings`` as plain dicts (the
    FE expects JSON; the router deserialises into Listing objects
    only when it needs to filter / sort).
    """

    if not force_refresh:
        cached = _read_cache()
        if cached and _fresh_enough(cached):
            return cached

    remote_items = await asyncio.to_thread(_fetch_remote_sync)
    if remote_items is not None:
        payload = {
            "source": "remote",
            "fetched_at": time.time(),
            "listings": remote_items,
        }
        _write_cache(payload)
        return payload

    # Fall back to seed -- still record fetched_at so the cache TTL
    # logic doesn't hammer the network on every refresh.
    payload = {
        "source": "seed",
        "fetched_at": time.time(),
        "listings": seed_listings(),
    }
    _write_cache(payload)
    return payload


async def list_listings(
    *,
    category: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    min_rating: float | None = None,
    force_refresh: bool = False,
) -> list[Listing]:
    """Filtered listing query used by ``GET /api/marketplace/listings``."""

    payload = await fetch_registry(force_refresh=force_refresh)
    items = _normalise(list(payload.get("listings") or []))

    if category:
        c = category.strip().lower()
        items = [it for it in items if it.category.lower() == c]
    if kind:
        k = kind.strip().lower()
        items = [it for it in items if it.kind.lower() == k]
    if q:
        needle = q.strip().lower()
        if needle:
            items = [
                it
                for it in items
                if needle in it.name.lower()
                or needle in it.description.lower()
                or any(needle in t.lower() for t in it.tags)
            ]
    if min_rating is not None:
        try:
            threshold = float(min_rating)
        except (TypeError, ValueError):
            threshold = 0.0
        items = [it for it in items if (it.ratings_avg or 0.0) >= threshold]
    return items


async def get_listing(listing_id: str) -> Listing | None:
    """Single-listing lookup by id (or slug -- caller can decide)."""

    payload = await fetch_registry()
    for raw in payload.get("listings") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("id") == listing_id or raw.get("slug") == listing_id:
            return Listing.from_dict(raw)
    return None


def reset_cache() -> None:
    """Test helper -- wipe the on-disk registry cache."""

    p = _cache_path()
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


__all__ = [
    "DEFAULT_REGISTRY_URL",
    "CACHE_TTL_S",
    "fetch_registry",
    "get_listing",
    "list_listings",
    "reset_cache",
]
