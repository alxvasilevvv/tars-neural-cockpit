# MCP operator guide (consolidated rewrite)

TARS speaks MCP in two directions:

- **Server** (`python3 -m backend.core.mcp`) — expose native TARS tools to external MCP hosts.
- **Client** (`backend.core.mcp.client_pkg`) — drive external MCP servers from playbooks, the bridge, and the CLI.

## Server registry

Remote servers are listed in `$TARS_HOME/mcp/servers.json` (same schema as the desktop panel at `~/.tars/mcp_servers.json` for UI edits).

## HTTP surface

- `GET /api/mcp/servers` — panel registry (W238)
- `GET /api/mcp/bridge/status` — bridge + pool health
- `GET /api/mcp/pool/stats` — active pooled sessions

## Boot bridged packs

```python
from backend.core.mcp.bridge import boot_mcp_bridges

boot_mcp_bridges()  # registers BridgedPack actions for each configured server
```

See `docs/handoff/MCP_REWRITE_BRIEF.md` for the full M-wave consolidation scope.
