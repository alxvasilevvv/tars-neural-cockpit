"""TARS MCP server bridge (Wave 150).

Real MCP server — closes the reality-audit gap where tasks #17 and
#85 were marked complete but no code existed.

What this is:
  - A Model Context Protocol (MCP) server that exposes TARS skills
    as tools so any MCP host (Claude Desktop, Cursor, MCP Inspector,
    Continue.dev, any future MCP client) can invoke them.
  - Pure stdlib JSON-RPC 2.0 over stdio. No external `mcp` package
    dependency — TARS already trims its deps aggressively.

What this is NOT:
  - Not a network server (no SSE / HTTP transport in v0.1). Stdio
    is what Claude Desktop wants; SSE arrives in v9.2.
  - Not a remote orchestrator. Tools run locally in the TARS process
    that spawns this server. The host gets stdout/stderr back through
    stdio framing.

Architecture:
  - :mod:`.protocol` — JSON-RPC 2.0 message types + framing helpers
    (newline-delimited JSON).
  - :mod:`.tools` — tool registry. Each tool is `(name, description,
    json_schema, handler)`. Built-in tools wired in :func:`builtin_tools`.
  - :mod:`.server` — main loop: parse request → dispatch → write
    response. Handles `initialize`, `tools/list`, `tools/call`.

Run via:
  python3 -m backend.core.mcp           # stdio server
  python3 -m backend.core.mcp --probe   # local self-test
"""

from __future__ import annotations

import logging

from .protocol import (
    CONTRACT_VERSION,
    JsonRpcError,
    JsonRpcMethodNotFound,
    JsonRpcRequest,
    JsonRpcResponse,
    decode_message,
    encode_message,
)
from . import bridge, client, pool
from .server import MCPServer, run_stdio
from .tools import (
    Tool,
    ToolRegistry,
    builtin_tools,
    register_tool,
)


logger = logging.getLogger(__name__)


__all__ = [
    "bridge",
    "client",
    "pool",
    "CONTRACT_VERSION",
    "JsonRpcError",
    "JsonRpcMethodNotFound",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "MCPServer",
    "Tool",
    "ToolRegistry",
    "builtin_tools",
    "decode_message",
    "encode_message",
    "register_tool",
    "run_stdio",
]
