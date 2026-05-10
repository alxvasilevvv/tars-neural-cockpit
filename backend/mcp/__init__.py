"""TARS MCP server (Wave M4).

Exposes the same action handlers the cockpit / HTTP layer /
``tars`` CLI drive — but as an **MCP (Model Context Protocol)
server**, so any MCP-aware host (Claude Desktop, Cursor,
Continue, custom MCP clients) can drive TARS verbs natively.

Why MCP and not just HTTP?

- **Native to AI hosts.** Claude Desktop and Cursor speak MCP
  out of the box. No bespoke API key plumbing, no per-host
  adapter code.
- **stdio transport** means zero network surface area —
  the host launches us as a subprocess and talks JSON-RPC
  over stdin/stdout. Operators get TARS-as-a-tool with the
  same trust model they already give Claude Desktop.
- **Same audit log.** Every `tools/call` invocation routes
  through the canonical action handler, so the audit trail,
  risk gate, and council voices behave identically whether
  the operator drives from cockpit, CLI, or an MCP host.

Architecture mirrors ``backend.cli`` — stdlib-only, no
``mcp`` package dependency, hand-rolled JSON-RPC 2.0 +
MCP-spec-compliant message handling. Keeps the cold-start
under 100ms (matters when Claude Desktop launches us per
session) and the dependency tree empty.

Entry point: ``python -m backend.mcp`` (and a ``tars mcp
serve`` CLI verb in a follow-up once #174 lands).
"""

from .protocol import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    Tool,
    ToolCallResult,
)
from .server import McpServer
from .tools import build_tool_registry

__all__ = [
    "JsonRpcError",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "McpServer",
    "Tool",
    "ToolCallResult",
    "build_tool_registry",
]
