"""W246 — HTTP surface for the Cmd+K command palette v2.

The palette v2 aggregates *every* action the user can take in the
desktop shell into a single flat array of records the frontend can
fuzzy-search over.  Each record looks like::

    {
      "id":       "quick.reload",
      "category": "Quick actions",
      "label":    "Reload",
      "icon":     "Z",
      "hint":     "Reload the cockpit",
      "hotkey":   "Cmd+R",        # optional
      "payload":  {"kind": "reload"},
    }

Categories
----------

The router merges six sources into one list:

1. **Quick actions** -- hardcoded shell commands (reload, settings,
   new chat, model switch, privacy, usage console, etc.).
2. **Agents** -- live list from ``GET /api/agents`` plus a single
   "Start new background task" entry.
3. **Notepads** -- live list from ``GET /api/notepads``.  Missing /
   un-seeded notepads result in zero entries, never a crash.
4. **MCP servers** -- live list from ``GET /api/mcp/servers`` (W238).
   Each entry's payload carries the server id so the frontend can
   toggle it.
5. **Mentions** -- one entry per built-in mention kind (file / docs
   / web / recent / code).  The frontend treats these as
   *category-prefix* hints, not directly executable.
6. **Recent** -- *not* served by the backend.  Recent is purely a
   ``localStorage`` thing maintained client-side; the router only
   advertises it as a category so the frontend can render the
   header consistently.

Endpoint
--------

``GET /api/palette/actions`` -> aggregated payload (see ``list_actions``).

The backend is intentionally read-only -- executing an action is
client-side glue (clicking a "Reload" entry calls ``location.reload``,
clicking a "Switch model" entry opens the existing model picker,
etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter


router = APIRouter(prefix="/api/palette", tags=["palette"])

log = logging.getLogger("tars.palette")


# ---------------------------------------------------------------------
# Category labels -- kept identical between backend and frontend so
# the dropdown headers match the payload's ``category`` field 1:1.
# ---------------------------------------------------------------------

CAT_QUICK = "Quick actions"
CAT_AGENTS = "Agents"
CAT_NOTEPADS = "Notepads"
CAT_MCP = "MCP servers"
CAT_MENTIONS = "Mentions"
CAT_RECENT = "Recent"

CATEGORIES: list[str] = [
    CAT_QUICK,
    CAT_AGENTS,
    CAT_NOTEPADS,
    CAT_MCP,
    CAT_MENTIONS,
    CAT_RECENT,
]


# ---------------------------------------------------------------------
# 1. Quick actions -- hardcoded.  Each entry is a desktop-shell verb
#    the frontend already knows how to perform; we expose them as
#    palette rows so users can find them without remembering chrome.
# ---------------------------------------------------------------------

QUICK_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "quick.reload",
        "category": CAT_QUICK,
        "label": "Reload",
        "icon": "⚡",  # high voltage
        "hint": "Reload the cockpit window",
        "hotkey": "Cmd+R",
        "payload": {"kind": "reload"},
    },
    {
        "id": "quick.settings",
        "category": CAT_QUICK,
        "label": "Open Settings",
        "icon": "⚙",  # gear
        "hint": "Open the settings drawer",
        "hotkey": "Cmd+,",
        "payload": {"kind": "open_settings"},
    },
    {
        "id": "quick.new_chat",
        "category": CAT_QUICK,
        "label": "New chat",
        "icon": "💬",
        "hint": "Start a fresh chat thread",
        "hotkey": "Cmd+N",
        "payload": {"kind": "new_chat"},
    },
    {
        "id": "quick.switch_model",
        "category": CAT_QUICK,
        "label": "Switch model",
        "icon": "🤖",
        "hint": "Open the models switcher (W237)",
        "payload": {"kind": "open_providers"},
    },
    {
        "id": "quick.privacy",
        "category": CAT_QUICK,
        "label": "Toggle privacy mode",
        "icon": "🛡",
        "hint": "Local-only data plane",
        "payload": {"kind": "toggle_privacy"},
    },
    {
        "id": "quick.usage",
        "category": CAT_QUICK,
        "label": "Show usage console",
        "icon": "📈",
        "hint": "Open the consumption console (W235)",
        "payload": {"kind": "open_usage"},
    },
    {
        "id": "quick.mcp_panel",
        "category": CAT_QUICK,
        "label": "MCP servers panel",
        "icon": "🔌",
        "hint": "Manage external MCP servers (W238)",
        "payload": {"kind": "open_mcp_panel"},
    },
    {
        "id": "quick.notepads",
        "category": CAT_QUICK,
        "label": "Open notepads",
        "icon": "📒",
        "hint": "Reusable AI workflows (W243)",
        "payload": {"kind": "open_notepads"},
    },
    {
        "id": "quick.bg_agents",
        "category": CAT_QUICK,
        "label": "Background tasks",
        "icon": "🕒",
        "hint": "Open the background-agent tray (W241)",
        "payload": {"kind": "open_bg_agents"},
    },
]


# Built-in @-mention kinds -- surfaced as palette rows so users can
# discover the syntax without leaving the palette.
_MENTION_KINDS_SAFE: tuple[str, ...] = ("file", "docs", "web", "recent", "code")
_MENTION_ICONS = {
    "file": "📄",
    "docs": "📚",
    "web": "🌐",
    "recent": "🕘",
    "code": "💻",
}


# ---------------------------------------------------------------------
# Helpers -- each "_collect_*" reads its source defensively so a single
# missing module never breaks the aggregate response.
# ---------------------------------------------------------------------


async def _collect_agents() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out.append({
        "id": "agents.new_bg_task",
        "category": CAT_AGENTS,
        "label": "Start new background task",
        "icon": "✨",
        "hint": "Spawn a long-running background agent",
        "payload": {"kind": "new_bg_task"},
    })
    try:
        from backend.core.agents.store import get_agent_store  # type: ignore

        store = get_agent_store()
        items = await store.list_agents()
        for a in items:
            try:
                d = a.to_dict()
            except Exception:
                d = {}
            aid = d.get("id") or d.get("agent_id") or ""
            name = d.get("name") or d.get("title") or aid[:8]
            if not aid:
                continue
            out.append({
                "id": f"agents.open.{aid}",
                "category": CAT_AGENTS,
                "label": str(name),
                "icon": "🤖",
                "hint": d.get("description") or "Open agent",
                "payload": {"kind": "open_agent", "agent_id": aid},
            })
    except Exception:
        # Agents source unavailable (no DB, no module, etc.) -- leave
        # the "Start new background task" entry as the only one.
        pass
    return out


def _collect_notepads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.notepads import get_notepad_store  # type: ignore

        store = get_notepad_store()
        rows = store.list(limit=100)
        # rows may be objects or dicts depending on store impl
        for row in (rows or [])[:100]:
            try:
                if isinstance(row, dict):
                    nid = row.get("id")
                    title = row.get("title")
                    pack = row.get("pack") or ""
                else:
                    nid = getattr(row, "id", None)
                    title = getattr(row, "title", None)
                    pack = getattr(row, "pack", "") or ""
            except Exception:
                continue
            if not nid or not title:
                continue
            hint = "Run notepad" + (f" ({pack})" if pack else "")
            out.append({
                "id": f"notepads.run.{nid}",
                "category": CAT_NOTEPADS,
                "label": str(title),
                "icon": "📒",
                "hint": hint,
                "payload": {"kind": "run_notepad", "notepad_id": str(nid)},
            })
    except Exception:
        # Notepad module missing or store empty -- return empty list.
        pass
    return out


def _collect_mcp_servers() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from web_extras.routers.mcp_panel import (  # type: ignore
            _public_view,
            _read_servers,
        )

        for row in _read_servers():
            view = _public_view(row)
            sid = view.get("id") or ""
            name = view.get("name") or sid[:8]
            enabled = bool(view.get("enabled"))
            status = view.get("status") or ("enabled" if enabled else "stopped")
            if not sid:
                continue
            out.append({
                "id": f"mcp.toggle.{sid}",
                "category": CAT_MCP,
                "label": str(name),
                "icon": "🔌",
                "hint": f"{status} -- click to toggle",
                "payload": {
                    "kind": "toggle_mcp",
                    "server_id": sid,
                    "enabled": enabled,
                    "status": status,
                },
            })
    except Exception:
        pass
    return out


def _collect_mentions() -> list[dict[str, Any]]:
    try:
        from backend.core.mentions.resolver import MENTION_KINDS  # type: ignore

        kinds = tuple(MENTION_KINDS)
    except Exception:
        kinds = _MENTION_KINDS_SAFE
    out: list[dict[str, Any]] = []
    for k in kinds:
        out.append({
            "id": f"mention.{k}",
            "category": CAT_MENTIONS,
            "label": f"@{k}",
            "icon": _MENTION_ICONS.get(k, "@"),
            "hint": f"Insert @{k}: context into the chat",
            "payload": {"kind": "insert_mention", "mention_kind": k},
        })
    return out


# ---------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------


@router.get("/actions")
async def list_actions() -> dict[str, Any]:
    """Return every palette action the desktop shell knows about.

    The response is a single flat ``actions`` array (the frontend
    does its own fuzzy-search + sectioning).  Each entry has a
    stable ``id`` and a ``category`` matching one of
    :data:`CATEGORIES`.
    """

    actions: list[dict[str, Any]] = []
    actions.extend(QUICK_ACTIONS)
    actions.extend(await _collect_agents())
    actions.extend(_collect_notepads())
    actions.extend(_collect_mcp_servers())
    actions.extend(_collect_mentions())

    return {
        "ok": True,
        "categories": list(CATEGORIES),
        "count": len(actions),
        "actions": actions,
    }
