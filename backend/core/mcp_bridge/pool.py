"""Long-lived ``ClientSession`` pool for the MCP bridge.

Wave M6. The M5 bridge ships with a per-call session model:
each bridged tool call spawns a fresh subprocess, runs the
handshake, calls the tool, closes. That's ~100-300ms
overhead per call — fine for one-shot CLI use, painful for
high-volume callers (cockpit autocomplete, workshop demo
loops, MCP-host driven sessions).

This module adds an opt-in pool. Long-lived TARS hosts
(HTTP server, MCP server) own a single ``SessionPool`` and
hand it to ``boot_mcp_bridges(pool=...)``. Pooled bridges
keep one ``ClientSession`` alive per remote server, reused
across calls. The pool is **thread-pool-safe in single-loop
contexts** but bound to one event loop — see the lifecycle
docstring on :class:`SessionPool`.

Backwards compatibility: ``BridgedPack`` accepts ``pool=None``
and falls back to per-call session. So nothing in the M5 PR
needs to change to keep working.

Failure recovery: when a pooled session's transport closes
(remote crashed, network blip), the bridge handler detects
the ``ConnectionError`` on the next call, evicts the dead
session from the pool, and reconnects automatically.
Operators see at most one failed call per remote crash.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.mcp.client import ClientSession, ServerConfig, StdioTransport


log = logging.getLogger(__name__)


@dataclass
class _PoolEntry:
    """Internal pool slot."""

    session: ClientSession
    transport: StdioTransport
    created_at: float
    last_used_at: float


class SessionPool:
    """One ``ClientSession`` per remote server, kept alive
    across handler calls.

    Lifecycle constraints:

    - The pool is bound to a single asyncio event loop —
      the loop that ran the first ``get_or_create`` call.
      Cross-loop access raises ``RuntimeError``. In
      practice TARS hosts use one loop per process; the
      pool is created once at boot and lives for the
      process lifetime.
    - The pool is concurrency-safe: a per-server lock
      serialises construction so two coroutines racing for
      ``get_or_create("filesystem")`` will share a single
      session, not two.
    - Once constructed, ``call_tool`` invocations on a
      session run **concurrently** without any extra
      locking — the JSON-RPC layer correlates replies by
      id (see ``StdioTransport``).

    Always call :meth:`close_all` at host shutdown to reap
    every subprocess. Long-lived hosts can also call
    :meth:`evict_idle` periodically to drop sessions that
    have been unused for a long time.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _PoolEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # get / evict / close
    # ------------------------------------------------------------------

    async def get_or_create(self, config: ServerConfig) -> ClientSession:
        """Return a live session for ``config``. Creates one
        on demand. Reuses on subsequent calls. If the cached
        session's transport has died (e.g. the remote crashed),
        evicts it and creates a fresh one in the same call."""

        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError(
                f"SessionPool is bound to event loop {id(self._loop):#x}; "
                f"called from loop {id(loop):#x}. Pools cannot cross "
                "event loops — create one pool per host process."
            )

        name = config.name
        async with self._lock_for(name):
            entry = self._entries.get(name)
            if entry is not None and not self._entry_is_dead(entry):
                entry.last_used_at = time.monotonic()
                return entry.session

            if entry is not None:
                # Dead transport — evict before reconnecting.
                log.info(
                    "mcp.pool.evict_dead server=%s reason=transport_closed",
                    name,
                )
                self._entries.pop(name, None)
                try:
                    await entry.transport.close()
                except Exception:  # noqa: BLE001
                    pass

            transport = StdioTransport(
                command=config.command,
                args=config.args,
                env=dict(config.env) if config.env else None,
                cwd=config.cwd,
            )
            session = ClientSession(transport)
            await transport.start()
            await session.initialize()
            now = time.monotonic()
            self._entries[name] = _PoolEntry(
                session=session,
                transport=transport,
                created_at=now,
                last_used_at=now,
            )
            log.info("mcp.pool.created server=%s", name)
            return session

    async def evict(self, name: str) -> bool:
        """Drop one server's session. Returns True if there
        was one to drop. Called by the bridge handler on
        transient transport errors so the next call gets a
        fresh subprocess."""

        async with self._lock_for(name):
            entry = self._entries.pop(name, None)
            if entry is None:
                return False
            try:
                await entry.transport.close()
            except Exception:  # noqa: BLE001
                pass
            log.info("mcp.pool.evict server=%s", name)
            return True

    async def evict_idle(self, *, max_idle_seconds: float = 300.0) -> int:
        """Drop sessions unused for ``max_idle_seconds`` or
        more. Returns the number evicted. Default 5 minutes
        — matches the typical MCP host idle timeout."""

        now = time.monotonic()
        stale = [
            name
            for name, entry in self._entries.items()
            if (now - entry.last_used_at) >= max_idle_seconds
        ]
        for name in stale:
            await self.evict(name)
        return len(stale)

    async def close_all(self) -> int:
        """Close every pooled session. Returns the count.
        Idempotent — safe to call multiple times."""

        names = list(self._entries.keys())
        for name in names:
            await self.evict(name)
        return len(names)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return a serialisable snapshot of pool state for
        the cockpit / `bridge-pool-stats` CLI verb."""

        now = time.monotonic()
        return {
            "count": len(self._entries),
            "sessions": [
                {
                    "name": name,
                    "age_seconds": round(now - entry.created_at, 1),
                    "idle_seconds": round(now - entry.last_used_at, 1),
                    "server_info": dict(entry.session.server_info),
                    "tool_count": entry.session.server_capabilities.get(
                        "tools", {}
                    ).get("_count", "?"),
                }
                for name, entry in sorted(self._entries.items())
            ],
        }

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _lock_for(self, name: str) -> asyncio.Lock:
        lock = self._locks.get(name)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[name] = lock
        return lock

    @staticmethod
    def _entry_is_dead(entry: _PoolEntry) -> bool:
        """Best-effort liveness probe — checks the transport's
        internal _closed flag. Cheap; no IO."""

        return bool(getattr(entry.transport, "_closed", False))


# ---------------------------------------------------------------------
# Process-scoped singleton (used by long-lived hosts)
# ---------------------------------------------------------------------


_SINGLETON: SessionPool | None = None


def get_default_pool() -> SessionPool:
    """Return the process-scoped default pool. Created on
    first call. Hosts that want isolation (tests,
    multi-tenant) should construct their own ``SessionPool``
    instances and pass them explicitly to
    ``boot_mcp_bridges(pool=...)``."""

    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = SessionPool()
    return _SINGLETON


def reset_default_pool() -> None:
    """Test helper. Drops the singleton reference so the next
    ``get_default_pool`` returns a fresh instance. Does not
    close existing sessions — callers should ``await
    pool.close_all()`` before resetting if they care."""

    global _SINGLETON
    _SINGLETON = None
