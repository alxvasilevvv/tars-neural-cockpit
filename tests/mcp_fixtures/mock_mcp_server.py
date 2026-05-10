"""Tiny stdlib-only mock MCP server used by client e2e tests.

Speaks just enough of the MCP protocol to exercise the
client's handshake / tools/list / tools/call code paths:

- ``initialize`` — replies with pinned protocol version +
  serverInfo.
- ``notifications/initialized`` — silent.
- ``ping`` — empty result.
- ``tools/list`` — returns two tools: ``echo`` (returns its
  arguments) and ``boom`` (returns ``isError: true``).
- ``tools/call`` — dispatches to the two tools, returns
  ``method_not_found`` for anything else.
- Unknown method — ``-32601 method_not_found``.

Behaviours the test suite enables via env vars:

- ``MOCK_MCP_LOG_TO_STDERR=1`` — emit one stderr line on
  startup so the stderr-capture test has something to read.
- ``MOCK_MCP_DELAY_MS`` — sleep this many ms before
  replying to ``ping`` (used by the timeout test).
- ``MOCK_MCP_FAIL_HANDSHAKE=1`` — return JSON-RPC error
  on ``initialize`` (used by the handshake-failure test).
- ``MOCK_MCP_CRASH_AFTER=N`` — write N replies, then exit
  (used by the EOF-mid-session test).
"""

from __future__ import annotations

import json
import os
import sys
import time


def _send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _tool_text(payload: dict, *, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
        "isError": is_error,
    }


def main() -> int:
    if os.environ.get("MOCK_MCP_LOG_TO_STDERR"):
        sys.stderr.write("mock-mcp: started\n")
        sys.stderr.flush()

    delay_ms = int(os.environ.get("MOCK_MCP_DELAY_MS") or "0")
    fail_handshake = bool(os.environ.get("MOCK_MCP_FAIL_HANDSHAKE"))
    crash_after = int(os.environ.get("MOCK_MCP_CRASH_AFTER") or "0")

    replies = 0
    while True:
        line = sys.stdin.readline()
        if not line:
            return 0
        line = line.rstrip("\r\n")
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        rid = req.get("id")
        params = req.get("params") or {}

        if method == "initialize":
            if fail_handshake:
                _send(_err(rid, -32603, "mock initialize failure"))
            else:
                _send(_ok(rid, {
                    "protocolVersion": "2025-06-18",
                    "serverInfo": {"name": "mock-mcp", "version": "0.0.1"},
                    "capabilities": {
                        "tools": {"listChanged": False, "_count": 2},
                        "prompts": {"listChanged": False},
                        "resources": {"listChanged": False},
                    },
                }))
            replies += 1

        elif method == "notifications/initialized":
            continue

        elif method == "ping":
            if delay_ms:
                time.sleep(delay_ms / 1000.0)
            _send(_ok(rid, {}))
            replies += 1

        elif method == "tools/list":
            _send(_ok(rid, {"tools": [
                {
                    "name": "echo",
                    "description": "Echo the arguments back as JSON.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                    },
                    "annotations": {
                        "title": "echo",
                        "readOnlyHint": True,
                        "destructiveHint": False,
                    },
                },
                {
                    "name": "boom",
                    "description": "Always returns isError=true.",
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": {
                        "title": "boom",
                        "readOnlyHint": False,
                        "destructiveHint": True,
                    },
                },
            ]}))
            replies += 1

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments") or {}
            if tool_name == "echo":
                _send(_ok(rid, _tool_text(
                    {"ok": True, "echo": args}, is_error=False
                )))
            elif tool_name == "boom":
                _send(_ok(rid, _tool_text(
                    {"ok": False, "error": "boom"}, is_error=True
                )))
            else:
                _send(_ok(rid, _tool_text(
                    {"ok": False, "error": "tool_not_found", "name": tool_name},
                    is_error=True,
                )))
            replies += 1

        elif method and method.startswith("notifications/"):
            continue

        else:
            _send(_err(rid, -32601, f"method not implemented: {method!r}"))
            replies += 1

        if crash_after and replies >= crash_after:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
