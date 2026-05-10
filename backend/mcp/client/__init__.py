"""TARS MCP **client** (Wave M3).

Lets TARS itself drive *external* MCP servers — filesystem,
GitHub, Postgres, third-party tool servers, **and our own
TARS MCP server** (Wave M4) when running TARS-as-client
against TARS-as-server. Same protocol the cockpit / CLI /
MCP-server side already speak; this module just inverts the
direction.

Three layers:

- ``transport`` — async subprocess-stdio transport: spawn
  the remote server, write JSON-RPC requests on its stdin,
  read JSON-RPC responses from its stdout.
- ``session`` — high-level ``ClientSession`` with
  ``initialize``, ``ping``, ``list_tools``, ``call_tool``,
  ``close``. Handles request/response correlation by id.
- ``registry`` — file-backed roster of remote servers
  (``$TARS_HOME/mcp/servers.json``) so an operator can wire
  up e.g. ``filesystem`` + ``github`` + ``postgres`` once
  and address them by name from playbooks / agents.

Entry: ``python -m backend.mcp.client <verb>`` (the server
side lives at ``python -m backend.mcp``).
"""

from .registry import (
    ClientRegistry,
    ServerConfig,
    get_client_registry,
    load_servers_file,
    reset_client_registry,
)
from .session import ClientSession, RemoteToolError
from .transport import StdioTransport

__all__ = [
    "ClientRegistry",
    "ClientSession",
    "RemoteToolError",
    "ServerConfig",
    "StdioTransport",
    "get_client_registry",
    "load_servers_file",
    "reset_client_registry",
]
