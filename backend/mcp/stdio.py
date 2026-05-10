"""stdio transport — line-delimited JSON-RPC over stdin/stdout.

This is the canonical MCP transport for desktop AI hosts
(Claude Desktop, Cursor, Continue): the host launches us as
a child process and reads/writes JSON-RPC messages on
stdin/stdout. **Stderr is for diagnostic logging only** — the
host treats stderr as an out-of-band log surface, never as a
protocol channel.

Protocol framing: per MCP spec, each JSON-RPC message is a
single line terminated by ``\n``. We write line-delimited
JSON via ``sys.stdout.buffer`` (bytes) so we don't depend on
the OS locale for UTF-8 encoding.

Lifecycle:

1. Read one line from stdin.
2. Parse → dispatch → serialize.
3. Write one line to stdout (skip on notification).
4. Repeat until EOF on stdin (host disconnected).

EOF on stdin is the canonical "host shut us down" signal —
we exit cleanly with status 0.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from .protocol import (
    ErrorCode,
    JsonRpcResponse,
    make_error,
    parse_request,
    serialize_response,
)
from .server import McpServer


log = logging.getLogger(__name__)


async def serve_stdio(server: McpServer | None = None) -> int:
    """Run the MCP server over stdio until stdin closes.

    Returns the process exit code (0 on clean shutdown).
    """

    server = server or McpServer()
    log.info(
        "mcp.stdio.start tools=%d", len(server.registry.bindings)
    )

    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:  # EOF — host disconnected
            log.info("mcp.stdio.eof")
            return 0
        line = line.rstrip("\r\n")
        if not line:
            continue

        response = await _handle_line(server, line)
        if response is None:
            # Notification — no reply.
            continue

        _write_line(serialize_response(response))


async def _handle_line(server: McpServer, raw: str) -> JsonRpcResponse | None:
    try:
        request = parse_request(raw)
    except ValueError as exc:
        return make_error(
            request_id=None,
            code=ErrorCode.PARSE_ERROR,
            message=f"parse error: {exc}",
        )
    return await server.dispatch(request)


def _write_line(text: str) -> None:
    """Write one JSON-RPC line to stdout. Bytes-level write
    keeps us portable on Windows hosts where text-mode stdout
    rewrites \n to \r\n (which would break the framing)."""

    payload = (text + "\n").encode("utf-8")
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
