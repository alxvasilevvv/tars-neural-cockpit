"""stdio transport tests.

We avoid spawning a real subprocess (`python -m backend.mcp`)
in these unit tests — that's covered by the
``docs/MCP.md`` smoke walkthrough and a separate manual
acceptance check. Here we drive ``serve_stdio`` directly with
``contextlib.redirect_stdout`` / monkeypatched ``sys.stdin``
so the suite stays fast and deterministic.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys

import pytest

from backend.mcp.server import McpServer
from backend.mcp.stdio import _handle_line, _write_line, serve_stdio


def test_handle_line_dispatches_ping() -> None:
    server = McpServer()
    line = '{"jsonrpc":"2.0","id":7,"method":"ping"}'
    resp = asyncio.run(_handle_line(server, line))
    assert resp is not None
    body = resp.to_dict()
    assert body["id"] == 7
    assert body["result"] == {}


def test_handle_line_returns_parse_error_on_garbage() -> None:
    server = McpServer()
    resp = asyncio.run(_handle_line(server, "not-json{"))
    assert resp is not None
    body = resp.to_dict()
    assert body["error"]["code"] == -32700
    assert body["id"] is None


def test_handle_line_returns_none_for_notification() -> None:
    server = McpServer()
    line = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    resp = asyncio.run(_handle_line(server, line))
    assert resp is None
    assert server.initialized is True


def test_serve_stdio_processes_lines_then_exits_on_eof(
    monkeypatch, capfdbinary
) -> None:
    """End-to-end: feed three lines + EOF on stdin, capture
    stdout, assert exactly three responses come back in order."""

    payloads = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "algotrade.list_recipes", "arguments": {}},
        },
    ]
    stdin_text = "\n".join(json.dumps(p) for p in payloads) + "\n"

    fake_stdin = io.StringIO(stdin_text)
    monkeypatch.setattr(sys, "stdin", fake_stdin)

    rc = asyncio.run(serve_stdio(McpServer()))
    out, _err = capfdbinary.readouterr()
    lines = [ln for ln in out.decode("utf-8").splitlines() if ln.strip()]

    assert rc == 0
    # Two responses: ping + tools/call. The notification produces no reply.
    assert len(lines) == 2
    bodies = [json.loads(ln) for ln in lines]
    assert bodies[0]["id"] == 1
    assert bodies[0]["result"] == {}
    assert bodies[1]["id"] == 2
    assert bodies[1]["result"]["isError"] is False


def test_write_line_uses_lf_framing(monkeypatch, capfdbinary) -> None:
    """Bytes-level write to stdout — no CRLF rewrite even on
    Windows-style hosts. We assert the framing is exactly one
    \\n at the end."""

    _write_line('{"hello":"world"}')
    out, _err = capfdbinary.readouterr()
    assert out == b'{"hello":"world"}\n'
