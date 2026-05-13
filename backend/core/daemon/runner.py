"""Headless daemon runtime — scheduler tick + heartbeat writer.

The runtime intentionally re-uses the scheduler module's existing
loop. It adds three things the web-app lifespan loop doesn't bother
with (because they're free in-process):

1. **Heartbeat file** — every tick writes
   ``~/.tars/daemon.heartbeat`` with ``{pid, last_tick, started_at}``
   so ``launchctl`` or ``tars-doctor`` can tell whether the agent
   is alive without poking the network.
2. **Graceful SIGTERM** — launchd sends SIGTERM on logout; we trap
   it so the current tick can drain instead of being killed mid-run.
3. **Disabled-mode log + exit** — if both
   ``TARS_SCHEDULER_ENABLED`` and ``TARS_DAEMON_FORCE`` are unset
   we log a clear "no work to do" message and exit 0 (don't sit in
   a 30-second sleep with nothing scheduled).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


log = logging.getLogger("tars.daemon")


HEARTBEAT_PATH = Path.home() / ".tars" / "daemon.heartbeat"
HEARTBEAT_INTERVAL_S = 30.0  # write the heartbeat file at least this often


# ---------- State -----------------------------------------------------


@dataclass
class DaemonState:
    """Runtime snapshot the heartbeat file persists."""

    pid: int = 0
    started_at: float = 0.0
    last_tick: float = 0.0
    tick_count: int = 0
    last_status: str = "starting"
    error_count: int = 0
    last_error: str | None = None
    contract_version: str = "0.1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_state: DaemonState | None = None


def get_state() -> DaemonState:
    global _state
    if _state is None:
        _state = DaemonState(pid=os.getpid(), started_at=time.time())
    return _state


def _reset_state_for_tests() -> None:
    global _state
    _state = None


# ---------- Heartbeat I/O --------------------------------------------


def write_heartbeat(state: DaemonState | None = None, *, path: Path | None = None) -> Path:
    """Persist the current state to the heartbeat file.

    Returns the path written. Best-effort: directory mkdir errors
    propagate (the caller's first call surfaces install issues
    early); subsequent write errors are swallowed at the call site.
    """

    s = state if state is not None else get_state()
    p = path or HEARTBEAT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(s.to_dict(), indent=2))
    tmp.replace(p)  # atomic on POSIX
    return p


def read_heartbeat(path: Path | None = None) -> dict[str, Any] | None:
    """Read the heartbeat file (used by tars-doctor / status CLI)."""

    p = path or HEARTBEAT_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text() or "{}")
    except (OSError, ValueError):
        return None


# ---------- Main loop ------------------------------------------------


def _force_run() -> bool:
    """Override the scheduler-enabled gate.

    ``TARS_DAEMON_FORCE=1`` keeps the daemon alive even when the
    scheduler is opt-out. Useful for: (a) test contexts that just
    want the heartbeat written; (b) operators who want the daemon
    running so the clone webhook / receipts loop ticks even though
    they don't have any cron'd playbooks yet.
    """

    flag = (os.getenv("TARS_DAEMON_FORCE") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _interval_s() -> float:
    raw = os.getenv("TARS_DAEMON_HEARTBEAT_S")
    if raw is None:
        return HEARTBEAT_INTERVAL_S
    try:
        # Floor at 0.05s — small enough for test contexts, still
        # high enough that runaway loops can't spin a CPU.
        return max(0.05, float(raw))
    except ValueError:
        return HEARTBEAT_INTERVAL_S


async def run_daemon() -> int:
    """Top-level entrypoint. Returns an exit code.

    Lifecycle:
      1. Write the initial heartbeat so external probes see the
         daemon as "starting" within ~1s of fork.
      2. Install SIGTERM/SIGINT handlers that flip ``_should_stop``
         instead of killing the loop mid-tick.
      3. If neither the scheduler nor force-mode is enabled, log a
         clear message and exit 0 — launchd won't respawn since
         exit code is 0 and the KeepAlive policy is OnDemand=false.
      4. Otherwise loop: tick → write heartbeat → sleep.
    """

    state = get_state()
    state.pid = os.getpid()
    state.started_at = state.started_at or time.time()
    write_heartbeat(state)

    stop_event = asyncio.Event()

    def _request_stop(signum: int, _frame: Any = None) -> None:
        log.info("daemon received signal %s — draining", signum)
        try:
            stop_event.set()
        except Exception:  # noqa: BLE001
            pass

    # Signals (Unix only — Windows ignores)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, OSError):
            # In some hosted contexts the main thread can't receive
            # signals. Best-effort.
            pass

    # Pull the scheduler module lazily so a daemon that doesn't have
    # the scheduler wired (e.g. unit-test contexts) still imports.
    try:
        from backend.core.scheduler.runner import (
            _is_enabled as scheduler_enabled,
            _tick_interval_s as scheduler_tick_s,
            get_runner as get_scheduler_runner,
        )
        from backend.core.scheduler.store import get_store as get_scheduler_store
    except Exception as exc:  # noqa: BLE001
        log.warning("daemon: scheduler import failed — running heartbeat-only (%s)", exc)
        scheduler_enabled = lambda: False  # type: ignore[assignment]
        scheduler_tick_s = lambda: 30.0  # type: ignore[assignment]
        get_scheduler_runner = None
        get_scheduler_store = None

    sched_on = scheduler_enabled()
    forced = _force_run()
    if not sched_on and not forced:
        state.last_status = "idle_exit"
        state.last_tick = time.time()
        write_heartbeat(state)
        log.info(
            "daemon: scheduler disabled and TARS_DAEMON_FORCE unset — exiting clean"
        )
        return 0

    tick_s = scheduler_tick_s() if sched_on else _interval_s()
    log.info(
        "daemon: starting loop pid=%s sched_on=%s forced=%s tick_s=%.1f hb=%s",
        state.pid, sched_on, forced, tick_s, HEARTBEAT_PATH,
    )

    # Recover scheduler state once at boot (mirrors web-app lifespan).
    if sched_on and get_scheduler_store:
        try:
            store = get_scheduler_store()
            if getattr(store, "enabled", False):
                recovery = await store.recover_state()
                log.info(
                    "daemon: scheduler recover_state total=%s recovered=%s errors=%s",
                    recovery.get("total"),
                    recovery.get("recovered"),
                    recovery.get("errors"),
                )
        except Exception as exc:
            log.warning("daemon: scheduler recover_state failed: %s", exc)

    runner = get_scheduler_runner() if (sched_on and get_scheduler_runner) else None

    state.last_status = "running"
    write_heartbeat(state)

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=tick_s)
        except asyncio.TimeoutError:
            pass  # normal tick path

        if stop_event.is_set():
            break

        state.tick_count += 1
        state.last_tick = time.time()
        try:
            if runner is not None:
                out = await runner.tick()
                fired = out.get("fired", 0) if isinstance(out, dict) else 0
                if fired:
                    log.info("daemon tick: fired=%s", fired)
                state.last_status = "running"
            else:
                # Heartbeat-only mode — nothing to fire.
                state.last_status = "heartbeat_only"
        except Exception as exc:  # noqa: BLE001
            state.error_count += 1
            state.last_status = "error"
            state.last_error = f"{type(exc).__name__}: {exc}"
            log.warning("daemon tick error: %s", exc, exc_info=True)
        finally:
            try:
                write_heartbeat(state)
            except Exception:  # noqa: BLE001
                # Heartbeat write failure shouldn't crash the loop.
                pass

    state.last_status = "stopped"
    write_heartbeat(state)
    log.info("daemon: clean shutdown after %s ticks", state.tick_count)
    return 0
