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

## Per-call session model (M5 default)

When `boot_mcp_bridges()` is called **without** a `pool=`
argument, every bridged action call spawns a **fresh**
subprocess, runs the handshake, calls the tool, closes.
Adds ~100-300ms latency per call but is dead-simple and
correct. No state leaks between calls; the bridge can run
for weeks without accumulating zombie subprocesses.

Use this mode for one-shot CLI commands, scheduled
playbooks, and anything else where you don't care about
sub-second latency.

## Pooled session model (Wave M6)

For long-lived hosts — HTTP server, MCP server, cockpit
backend, workshop session driver — pass a `SessionPool`
to the bootstrap:

```python
from backend.core.mcp_bridge import (
    SessionPool, aboot_mcp_bridges, get_default_pool,
)

# At process startup
pool = get_default_pool()  # process-scoped singleton
result = await aboot_mcp_bridges(pool=pool)

# At process shutdown
await pool.close_all()
```

What changes:

- **One subprocess per remote server**, kept alive across
  every bridged action call.
- **First call ("cold")** still pays the spawn + handshake
  cost (~15-300ms depending on the remote server).
- **Subsequent calls ("warm")** typically run in <1ms
  end-to-end because there is no process spawn, no JSON-RPC
  handshake, and no `tools/list` round trip — only the
  `tools/call` itself.
- Bench output from the in-test mock server: **194x speedup**
  on warm calls vs cold (15.8ms cold → 0.08ms warm).
- **Concurrent calls** on the same pooled session run truly
  in parallel; the JSON-RPC layer correlates replies by id.
- **Failure recovery**: if a pooled subprocess dies (remote
  crashed, stdin closed), the bridge handler detects the
  `ConnectionError` on the next call, evicts the dead entry,
  reconnects, retries the call once. Operators see at most
  one failed call per remote crash.
- **Idle eviction** is opt-in via `pool.evict_idle(max_idle_seconds=...)`.
  Long-lived hosts can call this from a periodic task.
- **Always close** with `await pool.close_all()` at process
  shutdown so no zombie subprocesses leak.

The `BridgedPack` action handler signature is identical in
both modes — code that imports a bridged action does not
need to know whether it's pool-backed.

### Async vs sync entry

There are two bootstrap entry points:

- `boot_mcp_bridges(...)` — sync, calls `asyncio.run()`
  internally. Use from CLI / tests / synchronous scripts.
- `aboot_mcp_bridges(...)` — async, safe to call from
  inside an already-running event loop. Use from HTTP /
  MCP server startup hooks where the loop is up.

Both accept the same arguments, including `pool=`.

### CLI bench

Operators can sanity-check the pool benefit on a real
configured server:

```bash
python -m backend.mcp.client bridge-pool-bench filesystem read_file \
    --arguments '{"path": "/tmp/x.txt"}' --iterations 10
```

Output is one JSON envelope with `cold_ms`, `warm_calls`,
`warm_avg_ms`, `speedup_vs_cold`, and the live `pool_stats`
snapshot — useful for sizing how many concurrent workshop
attendees one pool can handle.

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

`tests/test_mcp_bridge_*.py` — **68 cases** across five files:

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
- `test_mcp_bridge_pool.py` (18, **Wave M6**) — pool basic
  reuse, separate-server isolation, concurrent
  `get_or_create` race serialisation, `close_all` count +
  idempotency, `evict` happy/missing, idle eviction sweep,
  pool stats round-trip, cross-loop guard, default-pool
  singleton + reset, `pooled` flag on `BridgedPack`,
  pooled-handler reuse across calls, automatic reconnect
  after pool eviction, subprocess failure → structured
  envelope, `aboot_mcp_bridges` runs inside an existing
  loop, pool=None falls back to per-call.

All e2e tests spawn the same `tests/mcp_fixtures/mock_mcp_server`
fixture from M3 — no in-process mocking shortcut. Suite
runs in <1s total.

## Pool lifecycle (Wave M7)

Wave M7 ships two opt-in mechanisms that close the pool's
"long-running host" gap. Both are no-overhead-when-disabled
so existing M5 / M6 callers see no behavioural change.

### Background idle-eviction sweeper

```python
pool = get_default_pool()
await pool.start_sweeper(interval_seconds=60.0, max_idle_seconds=300.0)
# … host runs …
await pool.stop_sweeper()
```

Spawns a coroutine that calls `pool.evict_idle()` on a fixed
interval. Errors inside `evict_idle` are logged and the loop
continues — the sweeper is best-effort and never crashes the
host. Stats land on `pool.stats()["sweeper"]`:

```jsonc
{
  "running": true,
  "interval_seconds": 60.0,
  "max_idle_seconds": 300.0,
  "runs_total": 14,
  "sessions_evicted_total": 3,
  "last_run_evicted": 0,
  "uptime_seconds": 842.1,
  "seconds_since_last_run": 12.3
}
```

CLI (one-shot operator commands; the CLI cannot keep a
sweeper alive past process exit — wire `start_sweeper` into
the host lifespan for that):

```bash
tars-mcp-client bridge-pool-sweeper run-once --max-idle 300
tars-mcp-client bridge-pool-stats        # live snapshot
```

### Per-server concurrency caps

Some remote servers can't take 50 in-flight requests. Cap them
at the pool level — the bridge handler holds a slot before
issuing `tools/call`, so callers are transparently serialised:

Static (in `~/.tars/mcp/servers.json`):

```jsonc
{
  "filesystem": {
    "command": "uv",
    "args": ["run", "fs-mcp"],
    "max_concurrency": 4
  }
}
```

Or set / clear at runtime:

```python
pool.set_concurrency_limit("filesystem", 4)
pool.set_concurrency_limit("filesystem", None)  # clear cap
```

CLI:

```bash
tars-mcp-client bridge-pool-cap filesystem 4
tars-mcp-client bridge-pool-cap filesystem off
```

The pool also accepts a process-wide default:

```python
pool = SessionPool(default_max_concurrency=8)  # for every server unless overridden
```

`pool.stats()["sessions"][i]` carries `in_flight`,
`in_flight_peak`, `calls_total`, and `concurrency_limit`
per server so the cockpit panel can render "filesystem:
2/4 in flight, 137 calls".

## What's next

- **Cockpit panel.** Surface `BridgeBootResult` and the
  live `pool.stats()` (incl. sweeper + concurrency) in the
  domain-pack status UI. Already partly addressed by
  PR #182 (`MCPBridgePanel`); the M7 fields slot into the
  same envelope without UI changes.
- **Per-tool concurrency caps.** Today the cap is per
  *server*; a noisy tool on a quiet server can still
  starve siblings. The follow-up is a tool-level semaphore
  on top of the per-server one.
- **Sweeper-driven liveness probe.** Have the sweeper also
  send a cheap `tools/list` to each session every N runs;
  a failed probe pre-empts a real `call_tool` ConnectionError.
