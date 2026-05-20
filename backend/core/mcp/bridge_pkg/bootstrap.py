"""Bootstrap: read servers.json → discover → register packs.

Single entry point operators call from the host process:

    from backend.core.mcp.bridge_pkg import boot_mcp_bridges
    result = boot_mcp_bridges()
    log.info("MCP bridge: %d packs registered, %d failed",
             len(result.registered), len(result.failed))

The bootstrap loop is tolerant — one bad server config does
not break the others. Each server independently:

1. Tries the cache. If fresh, use it.
2. Otherwise, runs ``discover_remote_tools`` with a per-
   server timeout. If discovery succeeds, write the cache.
3. If discovery fails AND there's a stale cache entry,
   fall back to it. If discovery fails and there's no
   cache, skip the server (logged warning).
4. Build a ``BridgedPack`` from the descriptors, call
   ``register(pack)``.

Returns a structured ``BridgeBootResult`` so the caller can
log / surface what happened in the cockpit "domain pack
status" panel.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from backend.core.domains.registry import _REGISTRY, all_packs, register
from backend.core.mcp.client_pkg.registry import (
    ClientRegistry,
    ServerConfig,
    get_client_registry,
)

from .cache import DEFAULT_MAX_AGE_SECONDS, CachedDiscovery, ToolCache
from .discovery import DiscoveryError, discover_remote_tools
from .pack import BridgedPack
from .pool import SessionPool


log = logging.getLogger(__name__)


def _default_cache_root() -> Path:
    home = (
        os.environ.get("TARS_HOME")
        or os.environ.get("TARS_ALGOTRADE_HOME")
        or str(Path.home() / ".tars")
    )
    return Path(home).expanduser() / "mcp" / "cache"


@dataclass(frozen=True)
class BridgeBootResult:
    """Per-server outcomes from one ``boot_mcp_bridges`` call."""

    registered: tuple[BridgedPack, ...] = field(default_factory=tuple)
    cache_hits: tuple[str, ...] = field(default_factory=tuple)
    discovered: tuple[str, ...] = field(default_factory=tuple)
    failed: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    skipped: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "registered": [p.manifest.slug for p in self.registered],
            "cache_hits": list(self.cache_hits),
            "discovered": list(self.discovered),
            "failed": [{"server": s, "reason": r} for s, r in self.failed],
            "skipped": [{"server": s, "reason": r} for s, r in self.skipped],
            "total": len(self.registered),
        }


def boot_mcp_bridges(
    *,
    client_registry: ClientRegistry | None = None,
    cache: ToolCache | None = None,
    pool: SessionPool | None = None,
    discovery_timeout: float = 10.0,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    refresh: bool = False,
    only: Iterable[str] | None = None,
) -> BridgeBootResult:
    """Sync entry. Read configured servers, discover or
    cache-hit, register a ``BridgedPack`` per healthy server.

    Use this from synchronous contexts (CLI, tests, plain
    scripts). From inside a running event loop, call
    :func:`aboot_mcp_bridges` instead — this wrapper would
    raise ``RuntimeError("asyncio.run() cannot be called from
    a running event loop")``.

    ``refresh`` forces re-discovery even when a fresh cache
    exists. ``only`` restricts to a subset of server names
    (useful for tests + selective re-discovery from the
    cockpit). ``pool`` (Wave M6) opts the synthesised bridges
    into the long-lived session pool — pass the host's
    process-scoped ``SessionPool`` here so handler calls
    reuse one subprocess instead of spawning per call.
    Returns the structured boot result; it never raises
    (every per-server failure is captured)."""

    return asyncio.run(
        aboot_mcp_bridges(
            client_registry=client_registry,
            cache=cache,
            pool=pool,
            discovery_timeout=discovery_timeout,
            max_age_seconds=max_age_seconds,
            refresh=refresh,
            only=only,
        )
    )


async def aboot_mcp_bridges(
    *,
    client_registry: ClientRegistry | None = None,
    cache: ToolCache | None = None,
    pool: SessionPool | None = None,
    discovery_timeout: float = 10.0,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    refresh: bool = False,
    only: Iterable[str] | None = None,
) -> BridgeBootResult:
    """Async entry — same as :func:`boot_mcp_bridges` but
    safe to call from inside a running event loop. Use this
    from the HTTP server / MCP server startup hooks where
    the loop is already running. Same arguments, same return
    shape."""

    registry = client_registry or get_client_registry()
    tool_cache = cache or ToolCache(_default_cache_root())
    only_set = {s for s in only} if only is not None else None

    servers = registry.list()
    if only_set is not None:
        servers = [s for s in servers if s.name in only_set]

    registered: list[BridgedPack] = []
    cache_hits: list[str] = []
    discovered: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    for server in servers:
        try:
            outcome = await _aboot_one(
                server,
                cache=tool_cache,
                discovery_timeout=discovery_timeout,
                max_age_seconds=max_age_seconds,
                refresh=refresh,
                pool=pool,
            )
        except Exception as exc:  # noqa: BLE001 — never crash the boot loop
            log.exception("mcp.bridge.boot.uncaught server=%s", server.name)
            failed.append((server.name, f"uncaught: {exc}"))
            continue

        if outcome.skipped_reason:
            skipped.append((server.name, outcome.skipped_reason))
            continue

        if outcome.failed_reason:
            failed.append((server.name, outcome.failed_reason))
            continue

        assert outcome.pack is not None
        register(outcome.pack)
        registered.append(outcome.pack)
        if outcome.from_cache:
            cache_hits.append(server.name)
        else:
            discovered.append(server.name)
        log.info(
            "mcp.bridge.registered slug=%s tools=%d source=%s",
            outcome.pack.manifest.slug,
            len(outcome.pack.tool_descriptors),
            "cache" if outcome.from_cache else "discovery",
        )

    return BridgeBootResult(
        registered=tuple(registered),
        cache_hits=tuple(cache_hits),
        discovered=tuple(discovered),
        failed=tuple(failed),
        skipped=tuple(skipped),
    )


@dataclass
class _OneOutcome:
    """Per-server outcome returned by :func:`_boot_one`."""

    pack: BridgedPack | None = None
    from_cache: bool = False
    failed_reason: str | None = None
    skipped_reason: str | None = None


async def _aboot_one(
    server: ServerConfig,
    *,
    cache: ToolCache,
    discovery_timeout: float,
    max_age_seconds: int,
    refresh: bool,
    pool: SessionPool | None = None,
) -> _OneOutcome:
    """Bootstrap one server. Returns ``_OneOutcome`` describing
    cache/discovery/skip outcome — never raises."""

    cached = cache.read(server.name)
    if cached is not None and not refresh and cached.is_fresh(
        max_age_seconds=max_age_seconds
    ):
        if not cached.tools:
            return _OneOutcome(
                skipped_reason="cache_hit_but_empty_tool_list"
            )
        return _OneOutcome(
            pack=BridgedPack(server, cached.tools, pool=pool),
            from_cache=True,
        )

    try:
        tools, server_info = await discover_remote_tools(
            server, timeout=discovery_timeout
        )
    except DiscoveryError as exc:
        if cached is not None and cached.tools:
            log.warning(
                "mcp.bridge.boot.using_stale_cache server=%s reason=%s",
                server.name,
                exc.reason,
            )
            return _OneOutcome(
                pack=BridgedPack(server, cached.tools, pool=pool),
                from_cache=True,
            )
        return _OneOutcome(failed_reason=exc.reason)

    cache.write(server.name, server_info=server_info, tools=tools)
    if not tools:
        return _OneOutcome(
            skipped_reason="server_advertised_no_tools"
        )
    return _OneOutcome(
        pack=BridgedPack(server, tools, pool=pool), from_cache=False
    )


def unregister_bridges() -> int:
    """Remove every ``BridgedPack`` from the global registry.

    Used by tests + by ``tars mcp bridge refresh`` to wipe
    the bridge surface before re-bootstrapping. Returns the
    number of packs removed.
    """

    bridge_slugs = [
        p.manifest.slug
        for p in all_packs()
        if p.manifest.slug.startswith("mcp-")
    ]
    for slug in bridge_slugs:
        _REGISTRY.pop(slug, None)
    if bridge_slugs:
        log.info("mcp.bridge.unregistered %d packs", len(bridge_slugs))
    return len(bridge_slugs)
