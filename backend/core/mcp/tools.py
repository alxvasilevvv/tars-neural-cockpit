"""Tool registry + built-in tools for the MCP server (Wave 150).

A tool is the unit the MCP host invokes. Each tool has:
  - ``name``         — wire identifier (Claude Desktop sees this)
  - ``description``  — what it does, in 1-2 sentences (shows up in UI)
  - ``input_schema`` — JSON Schema for the params object
  - ``handler``      — async callable: ``(params: dict) -> Any``

Built-in tools (v0.1) expose the highest-leverage TARS surfaces:
  - ``tars.version``         — quick health / version probe
  - ``tars.list_playbooks``  — discover what skills are runnable
  - ``tars.run_playbook``    — invoke a playbook by slug
  - ``tars.recent_events``   — last N orchestrator events
  - ``tars.cowork_session``  — peek a Cowork session by id

Adding more tools later: call :func:`register_tool` from any module
imported during server boot, or pass to :class:`ToolRegistry` directly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class Tool:
    """One MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    tags: list[str] = field(default_factory=list)

    def manifest(self) -> dict[str, Any]:
        """Shape MCP `tools/list` returns."""

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class ToolRegistry:
    """In-process registry of MCP tools. Singleton at module load."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning("MCP tool %s re-registered — overwriting", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        # Stable order by name.
        return [self._tools[k] for k in sorted(self._tools)]

    def manifest(self) -> dict[str, Any]:
        return {"tools": [t.manifest() for t in self.all()]}


_REGISTRY = ToolRegistry()


def register_tool(tool: Tool) -> None:
    """Module-level helper used by callers that need to mutate the
    global registry (e.g. from a plugin module imported at boot)."""

    _REGISTRY.register(tool)


def registry() -> ToolRegistry:
    """Test seam — let test cases swap in a fresh registry."""

    return _REGISTRY


# ─── Built-in tool handlers ────────────────────────────────────────────────


async def _handle_version(_params: dict[str, Any]) -> dict[str, Any]:
    """Return TARS version + MCP contract version."""

    # Try to read the live product manifest if available; fall back to
    # a hardcoded constant when the module can't be imported.
    try:
        from backend.core.product.manifest import current_version

        version = current_version()
    except Exception:  # noqa: BLE001
        version = "9.3.0-beta.1"
    from . import CONTRACT_VERSION

    return {
        "ok": True,
        "tars": version,
        "mcp_contract": CONTRACT_VERSION,
        "timestamp": time.time(),
    }


async def _handle_list_playbooks(_params: dict[str, Any]) -> dict[str, Any]:
    """List available TARS playbooks (skills) the MCP host can invoke."""

    try:
        from backend.core.playbooks.loader import list_playbooks

        plays = list_playbooks()
        # Coerce to a stable JSON shape. Each playbook may carry its
        # own keys; we surface the common ones and let extras pass.
        out = []
        for p in plays:
            if hasattr(p, "to_dict"):
                d = p.to_dict()
            elif isinstance(p, dict):
                d = p
            else:
                d = {"slug": str(p), "name": str(p)}
            out.append(
                {
                    "slug": d.get("slug") or d.get("id") or "",
                    "name": d.get("name") or d.get("title") or "",
                    "description": d.get("description") or "",
                    "tags": d.get("tags") or [],
                }
            )
        return {"ok": True, "playbooks": out, "count": len(out)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_playbooks tool failed: %s", exc)
        return {"ok": False, "error": str(exc), "playbooks": []}


async def _handle_run_playbook(params: dict[str, Any]) -> dict[str, Any]:
    """Invoke a playbook by slug. Best-effort; returns whatever the
    runner emits or an error envelope.

    Params:
      slug: str (required) — playbook identifier
      inputs: dict (optional) — playbook-specific input bag
      mode: str (optional, default 'dry_run') — autopilot|confirm|dry_run
    """

    slug = params.get("slug")
    if not isinstance(slug, str) or not slug:
        return {"ok": False, "error": "param 'slug' is required"}
    inputs = params.get("inputs") or {}
    mode = params.get("mode", "dry_run")
    try:
        from backend.core.playbooks.runner import run_playbook_by_slug

        result = await run_playbook_by_slug(slug, inputs=inputs, mode=mode)
        return {"ok": True, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.warning("run_playbook tool failed: %s", exc)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _handle_recent_events(params: dict[str, Any]) -> dict[str, Any]:
    """Return the last N orchestrator events from the trace store.

    Params:
      limit: int (optional, default 20) — number of events
    """

    limit = int(params.get("limit", 20))
    limit = max(1, min(limit, 200))
    try:
        # Try to import meeet trace store. Best-effort; if absent,
        # return an empty envelope rather than failing the call.
        from backend.core.meeet import recent_events

        events = await recent_events(limit=limit)
        return {"ok": True, "events": events, "count": len(events)}
    except Exception as exc:  # noqa: BLE001
        logger.debug("recent_events tool returned empty (%s)", exc)
        return {"ok": True, "events": [], "count": 0}


async def _handle_cowork_session(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch a Cowork session record by id or slug.

    Params:
      slug_or_id: str (required)
    """

    key = params.get("slug_or_id")
    if not isinstance(key, str) or not key:
        return {"ok": False, "error": "param 'slug_or_id' is required"}
    try:
        from backend.core.cowork import get_store

        store = await get_store()
        s = await store.get_session_by_slug(key)
        if s is None:
            s = await store.get_session(key)
        if s is None:
            return {"ok": False, "error": "session_not_found", "key": key}
        return {
            "ok": True,
            "session": {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "owner_user_id": s.owner_user_id,
                "status": s.status.value,
                "created_at": s.created_at,
                "workspace_id": s.workspace_id,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("cowork_session tool failed: %s", exc)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ─── Built-in tool definitions ─────────────────────────────────────────────


_BUILTIN_TOOLS = [
    Tool(
        name="tars.version",
        description="Probe TARS version + MCP contract version. Useful as a connectivity check.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=_handle_version,
        tags=["health", "meta"],
    ),
    Tool(
        name="tars.list_playbooks",
        description="List available TARS playbooks (skills) the host can invoke.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=_handle_list_playbooks,
        tags=["discovery"],
    ),
    Tool(
        name="tars.run_playbook",
        description="Run a TARS playbook by slug with optional inputs. Default mode is dry_run; pass mode='autopilot' or 'confirm' to actually execute.",
        input_schema={
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Playbook identifier (from tars.list_playbooks)",
                },
                "inputs": {
                    "type": "object",
                    "description": "Playbook-specific input bag",
                    "additionalProperties": True,
                },
                "mode": {
                    "type": "string",
                    "enum": ["dry_run", "confirm", "autopilot"],
                    "default": "dry_run",
                },
            },
            "required": ["slug"],
            "additionalProperties": False,
        },
        handler=_handle_run_playbook,
        tags=["execute"],
    ),
    Tool(
        name="tars.recent_events",
        description="Return the last N orchestrator events from the trace store (watch-me-work feed).",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
        handler=_handle_recent_events,
        tags=["telemetry"],
    ),
    Tool(
        name="tars.cowork_session",
        description="Fetch a Cowork session by id or slug (status, owner, name).",
        input_schema={
            "type": "object",
            "properties": {
                "slug_or_id": {
                    "type": "string",
                    "description": "Cowork session slug (URL-friendly) or id (cw_…)",
                },
            },
            "required": ["slug_or_id"],
            "additionalProperties": False,
        },
        handler=_handle_cowork_session,
        tags=["cowork"],
    ),
]


def builtin_tools() -> list[Tool]:
    """Return the canonical built-in tool list (idempotent)."""

    return list(_BUILTIN_TOOLS)


# Auto-register on first import so a fresh `python -m backend.core.mcp`
# boot has tools available without explicit setup.
for _t in _BUILTIN_TOOLS:
    register_tool(_t)
