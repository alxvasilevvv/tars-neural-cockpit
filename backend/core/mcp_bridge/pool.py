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
import contextlib
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from backend.mcp.client import ClientSession, ServerConfig, StdioTransport


log = logging.getLogger(__name__)


@dataclass
class _PoolEntry:
    """Internal pool slot."""

    session: ClientSession
    transport: StdioTransport
    created_at: float
    last_used_at: float
    # Wave M7 — per-server concurrency limit. Initialised lazily
    # by ``SessionPool._slot_for`` so a server with no explicit
    # cap pays no semaphore cost.
    in_flight: int = 0
    inflight_peak: int = 0
    calls_total: int = 0


@dataclass
class PoolSweeperStats:
    """Snapshot of the background sweeper's recent activity.

    Surfaced via :meth:`SessionPool.stats` so the cockpit panel
    can show sweeper health without poking at internals.
    """

    started_at: float | None = None
    last_run_at: float | None = None
    last_run_evicted: int = 0
    runs_total: int = 0
    sessions_evicted_total: int = 0
    interval_seconds: float = 60.0
    max_idle_seconds: float = 300.0
    running: bool = False

    def to_dict(self) -> dict[str, Any]:
        now = time.monotonic()
        age_s = (
            round(now - self.started_at, 1) if self.started_at is not None else None
        )
        last_age_s = (
            round(now - self.last_run_at, 1) if self.last_run_at is not None else None
        )
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "max_idle_seconds": self.max_idle_seconds,
            "runs_total": self.runs_total,
            "sessions_evicted_total": self.sessions_evicted_total,
            "last_run_evicted": self.last_run_evicted,
            "uptime_seconds": age_s,
            "seconds_since_last_run": last_age_s,
        }


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

    def __init__(
        self,
        *,
        default_max_concurrency: int | None = None,
    ) -> None:
        self._entries: dict[str, _PoolEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        # Wave M7 — per-server concurrency caps. ``None`` (the
        # default) means "no cap"; a positive int means the
        # bridge handler must hold a slot before issuing
        # ``call_tool``. Defaults are merged from
        # ``ServerConfig.max_concurrency`` at session-create time.
        self._concurrency_limits: dict[str, int | None] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._default_max_concurrency = default_max_concurrency
        # Wave M7 — background idle-eviction sweeper. Lazily
        # started via :meth:`start_sweeper`. The sweeper
        # captures the loop the pool is bound to so cancel /
        # wait operations land on the right loop.
        self._sweeper_task: asyncio.Task[None] | None = None
        self._sweeper_stop: asyncio.Event | None = None
        self._sweeper_stats = PoolSweeperStats()

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
                    # Wave M7 — surface concurrency / call counters
                    # so the cockpit panel can show "filesystem:
                    # 2/4 in flight, 137 calls".
                    "in_flight": entry.in_flight,
                    "in_flight_peak": entry.inflight_peak,
                    "calls_total": entry.calls_total,
                    "concurrency_limit": self._concurrency_limits.get(name),
                }
                for name, entry in sorted(self._entries.items())
            ],
            # Wave M7 — sweeper status. Always present so a
            # cockpit panel can render "sweeper: stopped" without
            # branching on key presence.
            "sweeper": self._sweeper_stats.to_dict(),
            "default_max_concurrency": self._default_max_concurrency,
        }

    # ------------------------------------------------------------------
    # Wave M7 — per-server concurrency limits
    # ------------------------------------------------------------------

    def set_concurrency_limit(self, name: str, limit: int | None) -> None:
        """Cap concurrent ``call_tool`` invocations against
        server ``name``. ``None`` removes the cap.

        Safe to call before or after the session is constructed —
        the semaphore is recreated transparently. Existing
        in-flight calls keep their slots; new calls observe the
        new cap.
        """

        if limit is not None and limit < 1:
            raise ValueError(f"concurrency limit must be >= 1, got {limit!r}")
        if limit is None:
            self._concurrency_limits.pop(name, None)
            self._semaphores.pop(name, None)
            return
        self._concurrency_limits[name] = limit
        self._semaphores[name] = asyncio.Semaphore(limit)

    def get_concurrency_limit(self, name: str) -> int | None:
        return self._concurrency_limits.get(name)

    def _ensure_semaphore(self, config: ServerConfig) -> asyncio.Semaphore | None:
        """Return the semaphore for ``config`` if a cap is set,
        creating one from ``config.max_concurrency`` /
        ``self._default_max_concurrency`` when first observed."""

        name = config.name
        if name not in self._concurrency_limits:
            cap = getattr(config, "max_concurrency", None)
            if cap is None:
                cap = self._default_max_concurrency
            if cap is None:
                self._concurrency_limits[name] = None
            else:
                if cap < 1:
                    raise ValueError(
                        f"max_concurrency for {name!r} must be >= 1, got {cap!r}"
                    )
                self._concurrency_limits[name] = cap
                self._semaphores[name] = asyncio.Semaphore(cap)
        return self._semaphores.get(name)

    @contextlib.asynccontextmanager
    async def acquire_slot(
        self, config: ServerConfig
    ) -> "AsyncIterator[None]":
        """Async context manager bridge handlers wrap around
        ``call_tool`` so the pool can enforce per-server caps and
        track in-flight / total counts. When no cap is configured
        this is a near-zero-cost no-op (still bumps counters)."""

        semaphore = self._ensure_semaphore(config)
        entry = self._entries.get(config.name)
        if semaphore is None:
            try:
                if entry is not None:
                    entry.in_flight += 1
                    entry.inflight_peak = max(
                        entry.inflight_peak, entry.in_flight
                    )
                yield
            finally:
                if entry is not None:
                    entry.in_flight = max(0, entry.in_flight - 1)
                    entry.calls_total += 1
            return

        async with semaphore:
            try:
                if entry is not None:
                    entry.in_flight += 1
                    entry.inflight_peak = max(
                        entry.inflight_peak, entry.in_flight
                    )
                yield
            finally:
                if entry is not None:
                    entry.in_flight = max(0, entry.in_flight - 1)
                    entry.calls_total += 1

    # ------------------------------------------------------------------
    # Wave M7 — background sweeper task
    # ------------------------------------------------------------------

    async def start_sweeper(
        self,
        *,
        interval_seconds: float = 60.0,
        max_idle_seconds: float = 300.0,
    ) -> None:
        """Start a background task that calls ``evict_idle`` every
        ``interval_seconds``. Idempotent — calling twice while the
        sweeper is running raises ``RuntimeError`` to surface the
        misuse instead of silently dropping the second call.

        Long-lived hosts (FastAPI app, MCP server) wire this into
        their lifespan; short-lived CLI invocations don't need it.
        """

        if interval_seconds <= 0:
            raise ValueError(
                f"sweeper interval must be > 0, got {interval_seconds!r}"
            )
        if max_idle_seconds <= 0:
            raise ValueError(
                f"max_idle_seconds must be > 0, got {max_idle_seconds!r}"
            )
        if self._sweeper_task is not None and not self._sweeper_task.done():
            raise RuntimeError("sweeper already running")

        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError(
                "sweeper must be started on the same event loop "
                "the pool is bound to"
            )

        self._sweeper_stop = asyncio.Event()
        self._sweeper_stats = PoolSweeperStats(
            started_at=time.monotonic(),
            interval_seconds=interval_seconds,
            max_idle_seconds=max_idle_seconds,
            running=True,
        )
        self._sweeper_task = loop.create_task(
            self._sweeper_loop(interval_seconds, max_idle_seconds),
            name="mcp.pool.sweeper",
        )
        log.info(
            "mcp.pool.sweeper.started interval=%.1fs max_idle=%.1fs",
            interval_seconds,
            max_idle_seconds,
        )

    async def stop_sweeper(self) -> bool:
        """Stop the background sweeper. Returns True if a
        sweeper was running. Safe to call repeatedly."""

        task = self._sweeper_task
        stop_event = self._sweeper_stop
        if task is None or task.done():
            self._sweeper_task = None
            self._sweeper_stop = None
            self._sweeper_stats.running = False
            return False

        if stop_event is not None:
            stop_event.set()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            # Either way the task is done; the stats reflect the
            # last successful run via _sweeper_stats updates.
            pass
        self._sweeper_task = None
        self._sweeper_stop = None
        self._sweeper_stats.running = False
        log.info("mcp.pool.sweeper.stopped")
        return True

    @property
    def sweeper_running(self) -> bool:
        task = self._sweeper_task
        return task is not None and not task.done()

    async def _sweeper_loop(
        self,
        interval_seconds: float,
        max_idle_seconds: float,
    ) -> None:
        """Periodic eviction of idle sessions. Caller-cancellable
        via ``stop_sweeper``. Errors inside ``evict_idle`` are
        logged and the loop continues — the sweeper is best-effort
        and must never crash the host process."""

        stop_event = self._sweeper_stop
        assert stop_event is not None
        try:
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=interval_seconds
                    )
                except asyncio.TimeoutError:
                    pass
                else:
                    break

                if stop_event.is_set():
                    break

                try:
                    evicted = await self.evict_idle(
                        max_idle_seconds=max_idle_seconds
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("mcp.pool.sweeper.run_failed: %s", exc)
                    evicted = 0

                self._sweeper_stats.runs_total += 1
                self._sweeper_stats.sessions_evicted_total += evicted
                self._sweeper_stats.last_run_evicted = evicted
                self._sweeper_stats.last_run_at = time.monotonic()
                if evicted:
                    log.info(
                        "mcp.pool.sweeper.run evicted=%d total=%d",
                        evicted,
                        self._sweeper_stats.sessions_evicted_total,
                    )
        except asyncio.CancelledError:
            raise

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
