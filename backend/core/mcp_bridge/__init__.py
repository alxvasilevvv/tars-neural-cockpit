"""MCP bridge — external MCP tools as TARS DomainPack actions.

Wave M5. Closes the round-trip:

    Claude Desktop / Cursor (MCP host)
              ↓ MCP protocol
       TARS MCP server (Wave M4)
              ↓ DomainPack action surface
       BridgedPack (this module)
              ↓ MCP client (Wave M3)
       External MCP server (filesystem, GitHub, …)

Result: every MCP server out there in the wider ecosystem
becomes a first-class TARS action. Cockpit / CLI / HTTP /
TARS MCP server all see them. Audit log, risk gate, and
council voices treat them like any other action.

Usage from TARS host code:

    from backend.core.mcp_bridge import boot_mcp_bridges
    boot_mcp_bridges()  # reads $TARS_HOME/mcp/servers.json

The bridge is **opt-in** at boot — packs/__init__.py does
not auto-call ``boot_mcp_bridges`` because cold-boot for
unit tests should not touch the network/filesystem servers
the operator may have configured. Production hosts (HTTP
server, MCP server, CLI) explicitly call it.

See ``docs/MCP_BRIDGE.md`` for the full operator manual.
"""

from .bootstrap import (
    BridgeBootResult,
    boot_mcp_bridges,
    unregister_bridges,
)
from .cache import CachedDiscovery, ToolCache
from .discovery import DiscoveryError, discover_remote_tools
from .pack import BridgedPack, sanitize_action_id

__all__ = [
    "BridgeBootResult",
    "BridgedPack",
    "CachedDiscovery",
    "DiscoveryError",
    "ToolCache",
    "boot_mcp_bridges",
    "discover_remote_tools",
    "sanitize_action_id",
    "unregister_bridges",
]
