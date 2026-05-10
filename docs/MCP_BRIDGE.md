# TARS MCP bridge — external MCP tools as DomainPack actions

> Wave M5. Closes the round-trip:
>
> ```
> Claude Desktop / Cursor (MCP host)
>           ↓ MCP protocol
>    TARS MCP server (Wave M4)
>           ↓ DomainPack action surface
>    BridgedPack (this module)
>           ↓ MCP client (Wave M3)
>    External MCP server (filesystem, GitHub, Postgres, …)
> ```

Result: every MCP server out there in the wider ecosystem
becomes a **first-class TARS action**. Cockpit, CLI, HTTP,
TARS MCP server — all see them. Audit log, risk gate, and
council voices treat them like any other action. Composition
works in both directions:

- **Inbound**: an MCP host (Claude Desktop) calls
  `mcp-filesystem.read_file` through the TARS MCP server,
  which routes through the `BridgedPack` action, which
  proxies via the M3 client to the actual filesystem MCP
  server. Same audit trail.
- **Outbound**: a TARS playbook calls `mcp-github.list_issues`
  directly through the action surface; the MCP host never
  has to know there's a remote server behind it.

## Boot the bridge

The bridge is **opt-in** at boot — `packs/__init__.py` does
not auto-call it because cold-boot for unit tests should
not touch the network/filesystem servers the operator may
have configured.

Production hosts (HTTP server, MCP server, CLI) explicitly
call the bootstrap:

```python
from backend.core.mcp_bridge import boot_mcp_bridges

result = boot_mcp_bridges()
log.info("MCP bridge: %d packs registered, %d failed",
         len(result.registered), len(result.failed))
```

`boot_mcp_bridges()` is **tolerant** — one bad server
config does not break the others. Each server is processed
independently:

1. **Cache check.** If `$TARS_HOME/mcp/cache/<server>.json`
   is fresh (default: ≤ 24h old), use it.
2. **Discovery.** Otherwise, run `discover_remote_tools`
   with a per-server `discovery_timeout` (default 10s).
   On success, write the cache.
3. **Stale fallback.** If discovery fails AND a stale cache
   exists, fall back to it. Better to expose tools that
   may have drifted than to lose the bridge entirely
   when the remote is temporarily down.
4. **Skip.** If discovery fails and there's no cache,
   skip the server (logged warning + `failed` entry).
5. **Register.** Build a `BridgedPack` from the descriptors,
   call `register(pack)`. Slug is `mcp-<server_name>`.

The function returns a structured `BridgeBootResult` with
`registered` / `cache_hits` / `discovered` / `failed` /
`skipped` lists so the caller can surface what happened in
a cockpit "domain pack status" panel.

## Configure remote servers

Same `$TARS_HOME/mcp/servers.json` the M3 client reads (see
`docs/MCP_CLIENT.md`):

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem",
             "/Users/me/Documents"],
    "description": "Anthropic reference filesystem MCP"
  },
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."}
  },
  "tars-self": {
    "command": "python3",
    "args": ["-m", "backend.mcp"],
    "cwd": "/path/to/tars-neural-cockpit"
  }
}
```

After boot, those become:

| Bridged pack       | Tools available                                      |
| ------------------ | ---------------------------------------------------- |
| `mcp-filesystem`   | `read_file`, `write_file`, `list_directory`, ...    |
| `mcp-github`       | `list_issues`, `create_issue`, `get_pull_request`, ... |
| `mcp-tars-self`    | The full TARS pack catalog (composition!)            |

Tool ids are sanitised — MCP tool names can contain `/`
and `.` (e.g. `filesystem/read_file`); TARS action ids are
`[a-z0-9_]`. The bridge replaces anything else with `_`
and lowercases the result.

## Per-call session model (MVP)

Every bridged action call spawns a **fresh** subprocess,
runs the handshake, calls the tool, closes. Adds ~100-300ms
latency per call but is dead-simple and correct. No state
leaks between calls; the bridge can run for weeks without
accumulating zombie subprocesses.

Connection pooling is a future Wave M6 — when it lands,
`BridgedPack` will not need to change because the action
handler signature stays identical.

## Cache layout

Default location: `$TARS_HOME/mcp/cache/<server>.json`.
One file per remote server, atomically written via
`*.tmp` + `replace`:

```json
{
  "server": "filesystem",
  "discovered_at": "2026-05-10T22:00:00Z",
  "server_info": {"name": "filesystem", "version": "1.0.0"},
  "tools": [
    {"name": "read_file", "description": "...", "inputSchema": {...}},
    ...
  ]
}
```

Cache freshness defaults to 24h. Pass
`max_age_seconds=` to `boot_mcp_bridges()` to tune.

The cache file name is **sanitised** — a server name
containing `..` or `/` cannot escape the cache root.

## Destructive actions

The bridge propagates `annotations.destructiveHint` from
the remote tool descriptor onto the synthesised
`ActionSpec.destructive` flag. So a remote tool that says
"this writes to the filesystem" gets flagged destructive in
TARS too — risk gate / cockpit confirmation dialogs apply
the same way they do for native pack actions.

When the bridged action is re-exposed through the TARS MCP
server, the same flag flows back into the MCP `annotations`
block, so an upstream Claude Desktop sees the destructive
warning too. End-to-end consistent.

## Testing

`tests/test_mcp_bridge_*.py` — **50 cases** across four files:

- `test_mcp_bridge_pack.py` (12) — `sanitize_action_id`
  matrix, manifest generation, action spec build, name
  truncation, validation, system prompt, awareness empty,
  handler round-trip against mock server, remote `isError`
  propagation, subprocess failure → structured error.
- `test_mcp_bridge_cache.py` (15) — `CachedDiscovery` round-
  trip, freshness, missing-key validation, file ops
  (read missing, write/read round-trip, atomic write,
  filename sanitisation, parse-failure miss, schema-failure
  miss, delete, list_servers).
- `test_mcp_bridge_discovery.py` (4) — happy path,
  handshake failure → `DiscoveryError`, command-not-found
  → `DiscoveryError`, timeout → `DiscoveryError` (using a
  self-contained hang-fixture script).
- `test_mcp_bridge_bootstrap.py` (10) — empty registry,
  discover + register + cache write, second-boot cache hit,
  `refresh=True` forces re-discovery, failed discovery
  without cache, stale-cache fallback after failed
  discovery, `only=` filter, empty-tool-list skipped,
  `unregister_bridges` only touches `mcp-*` slugs,
  `BridgeBootResult.to_dict` shape.

All e2e tests spawn the same `tests/mcp_fixtures/mock_mcp_server`
fixture from M3 — no in-process mocking shortcut. Suite
runs in <1s total.

## What's next

- **Wave M6 — connection pooling.** Long-lived
  `ClientSession` per server, shared across handler calls.
  Strips the per-call subprocess overhead. Keeps the
  action surface unchanged.
- **`tars mcp bridge ...` CLI verbs.** `bootstrap`,
  `refresh <server>`, `list`, `unregister <server>`. Will
  layer onto the M2 CLI (#174) once it merges.
- **Cockpit panel.** Surface `BridgeBootResult` in the
  domain-pack status UI so operators can see at a glance
  which remote servers loaded, which fell back to stale
  cache, and which failed.
