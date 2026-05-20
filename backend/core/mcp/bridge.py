"""MCP bridge facade — remote MCP tools as BridgedPack actions (Wave M5)."""

from __future__ import annotations

from .bridge_pkg.bootstrap import boot_mcp_bridges, unregister_bridges
from .bridge_pkg.discovery import discover_remote_tools
from .bridge_pkg.pack import BridgedPack, sanitize_action_id

__all__ = [
    "BridgedPack",
    "boot_mcp_bridges",
    "discover_remote_tools",
    "sanitize_action_id",
    "unregister_bridges",
]
