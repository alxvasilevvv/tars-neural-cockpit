# TARS MCP client — drive remote MCP servers from TARS

> Wave M3. Stdlib-only async **MCP client** so TARS itself
> can drive any external MCP server: filesystem, GitHub,
> Postgres, third-party tool servers, **and the TARS MCP
> server** (Wave M4) when running TARS-as-client against
> TARS-as-server.

This is the inverse direction of the Wave M4 server.
Same protocol, same pinned spec version (`2025-06-18`),
same audit trail through whatever the remote tool exposes.

## Three layers

| Layer        | What it does                                                                                  |
| ------------ | --------------------------------------------------------------------------------------------- |
| `transport`  | Async `asyncio.create_subprocess_exec` + line-delimited JSON-RPC over stdin/stdout.           |
| `session`    | High-level `ClientSession` with `initialize` / `ping` / `list_tools` / `call_tool` / `close`. |
| `registry`   | File-backed roster of remote servers in `$TARS_HOME/mcp/servers.json`.                        |

## Configure remote servers

Edit `$TARS_HOME/mcp/servers.json` (created on first write):

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem",
             "/Users/me/Documents"],
    "description": "Anthropic reference filesystem MCP"
  },
  "tars-self": {
    "command": "python3",
    "args": ["-m", "backend.mcp"],
    "cwd": "/path/to/tars-neural-cockpit",
    "env": {"TARS_HOME": "/Users/me/.tars"},
    "description": "Self-hosted TARS MCP server (Wave M4)"
  }
}
```

The registry is **lazily re-read on every `get`** — edit the
file, save, the next call picks it up. No daemon restart.

## CLI verbs

### Inspect / call

```bash
# List configured remote servers.
python3 -m backend.mcp.client list-servers

# List tools on one server.
python3 -m backend.mcp.client list-tools tars-self

# Call a tool with JSON arguments.
python3 -m backend.mcp.client call-tool tars-self \
    algotrade.list_recipes '{}'

# Health-check a server.
python3 -m backend.mcp.client ping tars-self
```

### Manage server config (live edits to `servers.json`)

```bash
# Add or overwrite a server.
python3 -m backend.mcp.client servers-add filesystem \
    --command npx \
    --arg=-y \
    --arg @modelcontextprotocol/server-filesystem \
    --arg /Users/me/Documents \
    --description "Anthropic reference filesystem MCP"

# Show one entry's full config.
python3 -m backend.mcp.client servers-show filesystem

# Remove an entry.
python3 -m backend.mcp.client servers-remove filesystem
```

> Tip: argparse eats values starting with `-` as the next
> flag unless you use the `--arg=value` form. Use `--arg=-y`
> rather than `--arg -y`.

### M5 bridge — auto-register remote tools as TARS actions

```bash
# Boot the bridge — discover or cache-hit each configured
# server, register each as `mcp-<server>` DomainPack.
python3 -m backend.mcp.client bridge-bootstrap

# Force re-discovery (ignore fresh cache).
python3 -m backend.mcp.client bridge-bootstrap --refresh

# Restrict to a subset of servers.
python3 -m backend.mcp.client bridge-bootstrap --only filesystem

# List what's currently registered.
python3 -m backend.mcp.client bridge-list

# Unregister all `mcp-*` packs (e.g. before re-bootstrap).
python3 -m backend.mcp.client bridge-unregister

# Inspect the on-disk tool cache.
python3 -m backend.mcp.client bridge-cache-list --show-tools

# Drop one server's cache entry (forces re-discovery next boot).
python3 -m backend.mcp.client bridge-cache-delete filesystem

# Bench cold vs warm latency on a real server (Wave M6 pool).
python3 -m backend.mcp.client bridge-pool-bench filesystem read_file \
    --arguments '{"path": "/tmp/x.txt"}' --iterations 10
```

`bridge-bootstrap` exits `0` when every configured server
either succeeded or was skipped; `1` when at least one
server failed.

`bridge-pool-bench` (Wave M6) does one bridged call cold,
N calls warm, and reports the speedup. The mock server in
the test suite shows ~190x speedup; real servers usually
land in the 30-150x range depending on handshake cost.

Output is always JSON on stdout (machine-readable). Errors
land on stderr with `{"ok": false, "error": "...", "detail": "..."}`
and exit code `1`. Successful tool call where the remote
tool returned `isError: true` also exits `1` so cron jobs
fail loudly.

## Programmatic API

```python
import asyncio
import sys

from backend.mcp.client import ClientSession, StdioTransport


async def main() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=("-m", "backend.mcp"),
        env={"TARS_HOME": "/Users/me/.tars"},
    )
    async with ClientSession(transport) as session:
        # Handshake already done by the context manager.
        tools = await session.list_tools()
        print(f"{len(tools)} tools advertised")

        # Happy path — payload comes back already unwrapped.
        recipes = await session.call_tool("algotrade.list_recipes")
        print(recipes)  # {"ok": True, "recipes": [...]}

        # Error path — caller can branch on the marker.
        bogus = await session.call_tool(
            "algotrade.load_recipe", {"name": "ghost"}
        )
        if bogus.get("__remote_is_error"):
            print(f"remote rejected: {bogus['error']}")

        # Or raise instead of returning the error envelope.
        from backend.mcp.client import RemoteToolError
        try:
            await session.call_tool(
                "algotrade.load_recipe",
                {"name": "ghost"},
                raise_on_remote_error=True,
            )
        except RemoteToolError as exc:
            print(f"caught: {exc.payload['error']}")


asyncio.run(main())
```

## Error model

Three types of failures, distinct exception classes:

| Failure               | Class                                | When                                                       |
| --------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Transport             | `ConnectionError` / `TimeoutError`   | Subprocess died, stdout EOF, write to closed stdin, stuck. |
| JSON-RPC envelope     | `RemoteRpcError(code, message, data)`| `-32600` / `-32601` / etc — server returned `error` field. |
| Remote tool reject    | `RemoteToolError(tool, payload)`     | `tools/call` returned `isError: true`. **Opt-in** via `raise_on_remote_error=True`; default returns the payload with `__remote_is_error: True`. |

The transport reader task **never crashes the event loop**:
parse failures get logged at `WARNING` and dropped, EOF on
stdout fails every pending request with a clean
`ConnectionError`.

## Notifications

Server → client notifications (no `id`) are queued on the
transport and exposed via `transport.drain_notifications()`.
Today TARS doesn't use them — they're mostly for future MCP
features (resource updates, log streaming). The queue caps
implicitly at the host's memory.

## Server stderr forwarding

The remote server's stderr is read line-by-line and routed
through an `on_stderr` callable on the transport. Default
behaviour: forward each line to the `mcp.server.stderr`
logger at `INFO`, which means it appears wherever your
`logging` config sends `INFO` (stderr by default).

To pin lines to your own sink:

```python
captured: list[str] = []
transport = StdioTransport(
    command=sys.executable,
    args=("-m", "backend.mcp"),
)
transport.on_stderr = captured.append
```

## Testing

`tests/test_mcp_client_*.py` — **39 cases** across three
files, all driven against `tests/mcp_fixtures/mock_mcp_server.py`
(a tiny stdlib-only mock that responds to a fixed set of
methods, with env-var knobs for forced handshake failure /
delayed reply / mid-session crash).

- `test_mcp_client_session.py` (13) — handshake (happy +
  failure), gating before initialize, `list_tools`,
  `call_tool` (happy path / boom path / unknown tool /
  raise-on-error variant), `ping`, `ping` timeout,
  request after close, unknown method, stderr forwarding.
- `test_mcp_client_registry.py` (16) — `ServerConfig.from_dict`
  validation matrix, file missing / malformed / partial-
  valid behaviour, add / remove round-trip, atomic write
  via `*.tmp` + `replace`, `load_servers_file` standalone.
- `test_mcp_client_cli.py` (10) — every CLI verb's happy
  + error path: list-servers (empty / one entry),
  list-tools (unknown server / mock server), call-tool
  (happy / remote error / invalid JSON / non-object args),
  ping.

All e2e tests spawn the mock as a real subprocess so the
transport / session / CLI work over actual stdio framing.
Suite runs in <1s total.

## Why no `mcp` PyPI package?

Same reason as the M2 CLI and M4 server:

- **Stdlib-only.** Operators on a fresh laptop run
  `python3 -m backend.mcp.client` against a clone of the
  repo with **no `pip install`** required.
- **Cold start under 100ms.** Matters when an MCP-driven
  playbook spawns multiple connections.
- **Pinned protocol.** We control the spec version we
  speak; an upstream PyPI package upgrade can't surprise us
  in production.

The full `mcp` PyPI package is a great choice if you need
the high-level Python typings + the full MCP feature
matrix (sampling, sub-resources, etc.). For TARS we use
the slice we need and own it.

## What's next

- **Server roster bootstrap** — a `tars mcp servers add` CLI
  verb (in the M2 CLI shim) so operators don't hand-edit
  JSON. Easy follow-up; #174 stack adds the surface.
- **Bridge external tools as TARS actions** — wrap each
  remote tool as a `DomainPack` action so the cockpit's
  action picker treats them the same as built-in verbs.
  This is what closes the round-trip and makes the audit
  log cover external calls too.
