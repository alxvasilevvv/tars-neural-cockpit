"""MCP client facade (Wave M3 consolidated rewrite).

Re-exports the stdio client package so callers can use either::

    from backend.core.mcp import client
    from backend.core.mcp.client import ClientSession

or import the subpackage directly::

    from backend.core.mcp.client_pkg import ClientSession
"""

from __future__ import annotations

from .client_pkg import (
    ClientSession,
    RemoteToolError,
    ServerConfig,
    StdioTransport,
    get_client_registry,
    load_servers_file,
)
from .client_pkg.registry import ClientRegistry as ServerRegistry
from .client_pkg.transport import RemoteRpcError

__all__ = [
    "ClientSession",
    "RemoteRpcError",
    "RemoteToolError",
    "ServerConfig",
    "ServerRegistry",
    "StdioTransport",
    "get_client_registry",
    "load_servers_file",
]
