"""Background TARS daemon — headless scheduler/playbook runner (Wave 152).

The Wave 148 reality audit flagged the "Background TARS" row in
``WHAT_WORKS.md`` as honesty drift — task #65 (Wave 8.4.0) marked
it FULLY IMPLEMENTED, but no daemon code, no launchd plist, no CLI.
This module ships the real thing.

What this is:
  - A headless Python process that runs the scheduler tick loop
    (already implemented at ``backend.core.scheduler.runner``) plus
    a watchdog heartbeat so ``launchctl`` and ``tars-doctor`` can
    tell whether the daemon is alive.
  - A real macOS launchd plist (LaunchAgent, user-domain) that
    boots the daemon at login and respawns on crash.
  - A CLI (``scripts/tars-daemon``) that installs / uninstalls /
    starts / stops / status-checks the agent against ``launchctl``.

What this is NOT:
  - A replacement for the FastAPI host. The web app keeps owning
    HTTP, WS, and the cockpit. The daemon is the *autopilot* path —
    everything that should happen even when no human has the app
    open.
  - A Linux/Windows daemon. v0.1 is macOS only (launchd). systemd
    is on the v9.2 roadmap.
  - Real-time. The scheduler ticks every
    ``TARS_SCHEDULER_TICK_S`` seconds (default 30) — same cadence
    the web-app lifespan loop uses.

Public surface:
  - :class:`DaemonState` — runtime status snapshot (started_at,
    heartbeats, last_fire, error_count).
  - :func:`run_daemon` — top-level coroutine that the
    ``__main__`` entry awaits.
  - :func:`render_plist` — build a macOS launchd plist for the
    current install (project path, python exe, env).
  - :func:`install_plist` / :func:`uninstall_plist` — write/erase
    the plist + ``launchctl bootstrap``/``bootout``.
  - :data:`PLIST_LABEL` — the canonical agent label
    (``com.tars.background``).
"""

from __future__ import annotations

from .launchd import (
    PLIST_LABEL,
    PLIST_FILENAME,
    DEFAULT_PLIST_DIR,
    install_plist,
    plist_status,
    render_plist,
    uninstall_plist,
)
from .runner import (
    DaemonState,
    HEARTBEAT_PATH,
    get_state,
    read_heartbeat,
    run_daemon,
    write_heartbeat,
)
from .systemd import (
    DEFAULT_UNIT_DIR,
    UNIT_FILENAME,
    UNIT_NAME,
    install_unit,
    render_unit,
    uninstall_unit,
    unit_status,
)
from . import doctor_watch  # noqa: F401  -- importable as backend.core.daemon.doctor_watch


__all__ = [
    "DaemonState",
    "DEFAULT_PLIST_DIR",
    "DEFAULT_UNIT_DIR",
    "HEARTBEAT_PATH",
    "PLIST_FILENAME",
    "PLIST_LABEL",
    "UNIT_FILENAME",
    "UNIT_NAME",
    "doctor_watch",
    "get_state",
    "install_plist",
    "install_unit",
    "plist_status",
    "read_heartbeat",
    "render_plist",
    "render_unit",
    "run_daemon",
    "uninstall_plist",
    "uninstall_unit",
    "unit_status",
    "write_heartbeat",
]
