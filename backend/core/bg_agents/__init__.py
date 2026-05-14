"""W258 — Managed background agents via macOS launchd.

W241 shipped the cockpit tray + SQLite store for *task-shaped*
background work. This module is the sibling lane: long-running
background **processes** that the user wants to keep alive across
reboots, scheduled via launchd, with TARS-managed plists living in
``~/Library/LaunchAgents/world.meeet.tars.agent.<id>.plist``.

The two stores are intentionally separate:

  - ``web_extras.routers.bg_agents``  — short-lived agent tasks
    (created via chat, finite event log, SSE stream).
  - ``backend.core.bg_agents.launchd`` — *registered* processes
    that run forever-ish under launchd. The cockpit tray shows
    them next to the task rows so the operator has one place to
    look.

Cross-platform note: register/unregister/status all degrade
gracefully on non-Darwin hosts (return ``ok=False`` with
``error="launchd_not_supported_on_platform"``). The HTTP router
surfaces this so the frontend can show a sensible "Linux/Windows
parity is on the roadmap" affordance instead of a 500.
"""

from __future__ import annotations

from .launchd import (
    AGENT_LABEL_PREFIX,
    DEFAULT_AGENT_PLIST_DIR,
    LOG_DIR,
    AgentSpec,
    is_supported,
    list_managed,
    register,
    render_agent_plist,
    status,
    tail_logs,
    unregister,
)


__all__ = [
    "AGENT_LABEL_PREFIX",
    "DEFAULT_AGENT_PLIST_DIR",
    "LOG_DIR",
    "AgentSpec",
    "is_supported",
    "list_managed",
    "register",
    "render_agent_plist",
    "status",
    "tail_logs",
    "unregister",
]
