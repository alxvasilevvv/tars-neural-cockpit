# TARS MCP server — operator + integration manual

> Wave M4. Stdlib-only **Model Context Protocol** server that
> exposes every TARS action handler as an MCP tool. Same
> handlers the cockpit / HTTP layer / `tars` CLI call, so the
> audit log, risk gate, and council voices stay unified across
> all four transports.

## What is MCP and why is this here?

**MCP** ([Model Context Protocol](https://modelcontextprotocol.io)) is
an open spec from Anthropic that lets AI hosts (Claude Desktop,
Cursor, Continue, custom clients) plug into local tools through a
standard JSON-RPC interface. By shipping TARS as an MCP server, we
get three properties for free:

1. **Native to AI hosts.** Claude Desktop and Cursor speak MCP out
   of the box. No bespoke API key plumbing, no per-host adapter.
2. **Zero network surface.** stdio transport — the host launches us
   as a subprocess and talks JSON-RPC over stdin/stdout. Operators
   get the same trust model they already give Claude Desktop.
3. **Same audit log.** Every `tools/call` invocation routes through
   the canonical action handler, so the trail is identical whether
   the operator drives from the cockpit, the CLI, or an MCP host.

## Run the server

The server ships at `backend/mcp/`. Two ways to launch:

```bash
# Direct: works from a clone of the repo with no setup.
python3 -m backend.mcp

# Via the CLI (after Wave M2 PR #174 merges):
tars mcp serve
```

There's no daemon and no port — the host launches one process per
session, talks to it over stdin/stdout, and reaps it on disconnect.

## Wire it into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS (or the equivalent path on Windows/Linux):

```json
{
  "mcpServers": {
    "tars": {
      "command": "python3",
      "args": ["-m", "backend.mcp"],
      "cwd": "/absolute/path/to/tars-neural-cockpit",
      "env": {
        "TARS_HOME": "/Users/you/.tars",
        "TARS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Restart Claude Desktop. The TARS tools appear in the tool picker
under `tars`, prefixed by pack slug (`algotrade.list_recipes`,
`algotrade.backtest`, `algotrade.lab_create_workshop`, …).

## Wire it into Cursor

Cursor speaks the same MCP dialect. Edit your Cursor settings:

```json
{
  "mcp.servers": {
    "tars": {
      "command": "python3",
      "args": ["-m", "backend.mcp"],
      "cwd": "/absolute/path/to/tars-neural-cockpit"
    }
  }
}
```

## Tool naming & discovery

Tool names are minted as `<pack_slug>.<action_id>` so the MCP
audit trail aligns 1-to-1 with the cockpit / CLI / HTTP surfaces.
A representative slice (the full set grows with each pack):

| Tool name                         | What it does                                                         |
| --------------------------------- | -------------------------------------------------------------------- |
| `algotrade.list_recipes`          | Bundled starter strategies.                                          |
| `algotrade.backtest`              | Run a backtest (recipe / fingerprint / IR; CSV or Binance bars).     |
| `algotrade.register_strategy`     | Persist a strategy to the local registry.                            |
| `algotrade.start_paper_session`   | Open a paper trading session under a risk policy.                    |
| `algotrade.start_live_session`    | **Destructive.** Open a Binance Spot session (testnet by default).   |
| `algotrade.session_report`        | Render the W3-PR2 markdown report for a session.                     |
| `algotrade.council_review`        | Run the W3-PR3 trading council voices.                               |
| `algotrade.lab_create_workshop`   | Create a workshop bucket (W4-PR2).                                   |
| `algotrade.lab_enroll_attendee`   | Enroll an attendee into a workshop.                                  |
| `algotrade.lab_leaderboard`       | Compute the leaderboard from disk.                                   |
| `algotrade.lab_workshop_debrief`  | Render the W4-PR3 debrief bundle.                                    |
| `business.morning_brief`          | Daily morning briefing (pack-cross verb).                            |
| `traders.summarize_market`        | Trader pack market summary.                                          |
| `wallet.anchor_memo`              | Anchor a memo on Solana / EVM / TON.                                 |

Call `tools/list` from the host to see the full live catalog —
everything in the registered domain pack roster is exposed.

## Destructive vs read-only

Each tool carries an MCP `annotations` block:

```json
{
  "annotations": {
    "destructiveHint": true,
    "readOnlyHint": false
  }
}
```

These come straight from `ActionSpec.destructive`. Well-behaved
hosts (Claude Desktop, Cursor) surface a confirm dialog for tools
with `destructiveHint: true` — that's how `algotrade.start_live_session`
gets a "this touches real money" confirmation in the host before
the call leaves the wire.

## Protocol details

We implement MCP spec version `2025-06-18`. Methods we honour:

| Method                        | Notes                                                  |
| ----------------------------- | ------------------------------------------------------ |
| `initialize`                  | Returns server capabilities + protocol version.        |
| `notifications/initialized`   | Marks session ready. No reply.                         |
| `ping`                        | Empty `{}` result — useful for host liveness probes.   |
| `tools/list`                  | Full tool catalog.                                     |
| `tools/call`                  | Invokes a tool with `arguments`.                       |
| `prompts/list`                | Empty (we don't ship prompt templates).                |
| `resources/list`              | Empty (no static resources).                           |
| `resources/templates/list`    | Empty.                                                 |
| `logging/setLevel`            | Accepted, no-op (we already log to stderr).            |

### Error envelope

Three places errors can surface:

1. **JSON-RPC envelope errors** (parse, invalid request, method
   not found, invalid params). Standard JSON-RPC 2.0 codes:
   `-32700` / `-32600` / `-32601` / `-32602` / `-32603`.
2. **Handler errors** that the action handler returned as
   `{"ok": false, "error": "..."}`. Wrapped as a `tools/call`
   result with `isError: true` and the original payload as text
   content. The MCP host renders these inline.
3. **Uncaught exceptions** in a handler. Same shape as #2 —
   `{"ok": false, "error": "handler_uncaught", "detail": "..."}` —
   so the host never sees the JSON-RPC channel fault.

The dispatcher never raises. Operators see structured payloads,
not stack traces.

## Environment variables

| Variable                | Default       | Purpose                                                  |
| ----------------------- | ------------- | -------------------------------------------------------- |
| `TARS_HOME`             | `~/.tars`     | Root for on-disk state.                                  |
| `TARS_ALGOTRADE_HOME`   | `$TARS_HOME`  | Override just the algotrade data dir.                    |
| `TARS_MCP_LOG_LEVEL`    | `INFO`        | Stderr log verbosity (`DEBUG` / `INFO` / `WARNING`).     |

All `TARS_*` env vars the underlying packs honour propagate
unchanged because the MCP server hosts the same packs.

## Smoke test by hand

```bash
# Send a few JSON-RPC frames and watch the responses come back.
python3 -m backend.mcp <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"smoke","version":"0"},"capabilities":{}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"algotrade.list_recipes","arguments":{}}}
EOF
```

Expected: four lines on stdout — initialize result, tools list,
tool call result. Stderr carries any log output.

## Testing

`tests/test_mcp_*.py` — **53 cases** across four files:

- `test_mcp_protocol.py` — JSON-RPC envelope parsing, error codes,
  Tool / ToolCallResult serialization (22 cases).
- `test_mcp_tools.py` — ActionSpec → Tool bridge: registry build,
  destructive flag propagation, async + sync handler dispatch,
  uncaught exceptions, non-mapping returns (10 cases).
- `test_mcp_server.py` — Dispatcher: handshake, ping, unknown
  method, tools/list, tools/call happy + error paths, optional
  list endpoints, end-to-end strategy flow (16 cases).
- `test_mcp_stdio.py` — stdio transport: line framing, parse
  error envelope, notification skip, end-to-end three-frame
  dialog with EOF shutdown (5 cases).

All tests drive the dispatcher in-process — no subprocess spawning
— so the suite runs in <500ms.

## What's next (Wave M3)

The next milestone is the **MCP client** so TARS itself can drive
external MCP servers (filesystem, GitHub, Postgres, etc.). The
server you're reading about is the natural integration test
target: M3 will use this very server as a smoke fixture.
