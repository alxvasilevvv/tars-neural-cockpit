# TARS MCP server contract — v0.1 (Wave 150)

**Module:** `backend/core/mcp/` · **Transport:** stdio JSON-RPC 2.0 · **MCP spec:** 2024-11-05

The TARS MCP server bridge exposes the TARS local agent surface as
tools to any [Model Context Protocol](https://modelcontextprotocol.io)
host — Claude Desktop, Cursor, Continue.dev, MCP Inspector, etc.

This closes the historic "MCP server bridge" gap (tasks #17 + #85
were marked complete but no code existed; W148 reality audit flagged
the drift; W150 actually delivers it).

## Architecture

```
MCP host (Claude Desktop) ─stdio─► backend.core.mcp.server
                                        │
                                        ▼
                                   ToolRegistry (5 builtin)
                                        │
                                        ├─ tars.version
                                        ├─ tars.list_playbooks
                                        ├─ tars.run_playbook
                                        ├─ tars.recent_events
                                        └─ tars.cowork_session
```

Stdlib-only: no `mcp` package dependency. JSON-RPC over newline-
delimited JSON on stdin/stdout. stderr is unstructured diagnostics
that the host typically surfaces to the operator.

## Run

```bash
# stdio server (what the MCP host spawns)
python3 -m backend.core.mcp

# self-test without a host
python3 -m backend.core.mcp --probe

# inspect tool catalog
python3 -m backend.core.mcp --list-tools
```

## Wiring into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tars": {
      "command": "python3",
      "args": [
        "-m",
        "backend.core.mcp"
      ],
      "cwd": "/Users/alien/Documents/Claude/Projects/Jarvis/jarvis",
      "env": {
        "PYTHONPATH": "/Users/alien/Documents/Claude/Projects/Jarvis/jarvis"
      }
    }
  }
}
```

Restart Claude Desktop. The 5 TARS tools appear in the tools picker.

## Wiring into Cursor

Cursor reads `~/.cursor/mcp.json` with the same shape. Identical config.

## Wiring into MCP Inspector (debugging)

```bash
npx @modelcontextprotocol/inspector \
  python3 -m backend.core.mcp \
  --cwd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
```

## Built-in tools

### `tars.version`

Connectivity probe. Returns `{tars, mcp_contract, timestamp}`.

```json
{"name":"tars.version","arguments":{}}
```

### `tars.list_playbooks`

Discover available TARS skills.

```json
{"name":"tars.list_playbooks","arguments":{}}
```

Returns `{playbooks:[{slug,name,description,tags}], count}`.

### `tars.run_playbook`

Invoke a playbook by slug.

```json
{
  "name": "tars.run_playbook",
  "arguments": {
    "slug": "daily.briefing",
    "inputs": {"focus": "fundraising"},
    "mode": "dry_run"
  }
}
```

`mode` ∈ `dry_run` (default) | `confirm` | `autopilot`. Default is
`dry_run` for safety — the host must explicitly opt into autopilot.

### `tars.recent_events`

Last N orchestrator events (watch-me-work feed).

```json
{"name":"tars.recent_events","arguments":{"limit":20}}
```

### `tars.cowork_session`

Peek a Cowork session (status, owner, name) by slug or id.

```json
{"name":"tars.cowork_session","arguments":{"slug_or_id":"weekly-review-abc123"}}
```

## Adding new tools

```python
from backend.core.mcp import Tool, register_tool

async def my_handler(params: dict) -> dict:
    return {"ok": True, "echo": params}

register_tool(Tool(
    name="custom.echo",
    description="Echo whatever the host sends.",
    input_schema={"type": "object", "additionalProperties": True},
    handler=my_handler,
    tags=["debug"],
))
```

Import the module at server boot — the tool is auto-discovered via
the global registry singleton.

## Error model

| Error | When | Wire shape |
| --- | --- | --- |
| Parse error | malformed JSON line | `{error:{code:-32700, message:...}}` (id=null) |
| Invalid request | missing/bad `jsonrpc` or `method` | code -32600 |
| Method not found | unknown JSON-RPC method | code -32601 |
| Invalid params | tool/call missing `name`, bad arg shape | code -32602 |
| Internal error | uncaught handler exception | code -32603 |
| Tool execution failure | tool handler raised | `result:{content:[...],isError:true}` |

Per MCP spec, tool-level failures (handler raised) return a
**successful** JSON-RPC response with `isError:true` inside, so the
host renders the error to the user without treating it as a transport
failure.

## Versioning

- `CONTRACT_VERSION = "0.1.0"` — TARS server version (this file)
- `MCP_PROTOCOL_VERSION = "2024-11-05"` — MCP spec version we conform to

Bump CONTRACT_VERSION on every breaking change to the tool surface.
Additive new tools = patch bump. Renames / removed tools = minor bump.

## Roadmap

- **v0.1 (this release):** stdio transport, 5 built-in tools, manual config
- **v0.2 (v9.1.2 target):** auto-discover playbooks → one tool per playbook
- **v0.3 (v9.2 target):** SSE transport for browser-side MCP hosts
- **v0.4 (v9.2 target):** Resources surface (expose cowork sessions, files, receipts as MCP resources)
- **v1.0 (v9.3 target):** Full prompts surface + multi-tenant scoping
