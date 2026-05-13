"""MCP server main loop (Wave 150).

Reads newline-delimited JSON-RPC requests from stdin, dispatches to
handlers, writes responses to stdout. stderr is left for diagnostics
(MCP hosts surface it to the operator).

Spawn via:
  python3 -m backend.core.mcp                       # stdio server
  python3 -m backend.core.mcp --probe               # local self-test
  python3 -m backend.core.mcp --list-tools          # print tool catalog

Wiring into Claude Desktop / Cursor: see `docs/contracts/MCP.md`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Awaitable, Callable

from .protocol import (
    JSONRPC_INTERNAL_ERROR,
    JSONRPC_INVALID_PARAMS,
    MCP_PROTOCOL_VERSION,
    JsonRpcError,
    JsonRpcMethodNotFound,
    JsonRpcRequest,
    JsonRpcResponse,
    decode_message,
    encode_message,
    make_error_response,
)
from .tools import ToolRegistry, registry

logger = logging.getLogger(__name__)


# ─── Server ────────────────────────────────────────────────────────────────


class MCPServer:
    """JSON-RPC dispatcher over a tool registry.

    Stateless across requests except for the `initialized` flag —
    spec requires a handshake before `tools/*` calls.
    """

    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools or registry()
        self._initialized = False
        self._handlers: dict[str, Callable[[JsonRpcRequest], Awaitable[Any]]] = {
            "initialize": self._on_initialize,
            "notifications/initialized": self._on_initialized_notification,
            "ping": self._on_ping,
            "tools/list": self._on_tools_list,
            "tools/call": self._on_tools_call,
            "shutdown": self._on_shutdown,
        }

    # ---- core dispatch -----------------------------------------------------

    async def handle(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """Dispatch one request. Returns None for notifications."""

        handler = self._handlers.get(request.method)
        if handler is None:
            if request.is_notification:
                # Silently drop unknown notifications per spec.
                logger.debug("MCP: ignoring unknown notification %s", request.method)
                return None
            raise JsonRpcMethodNotFound(request.method)

        try:
            result = await handler(request)
        except JsonRpcError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("MCP handler %s crashed", request.method)
            raise JsonRpcError(
                JSONRPC_INTERNAL_ERROR,
                f"Handler error: {type(exc).__name__}: {exc}",
            ) from exc

        if request.is_notification:
            return None
        return JsonRpcResponse(id=request.id, result=result)

    # ---- handshake ---------------------------------------------------------

    async def _on_initialize(self, request: JsonRpcRequest) -> dict[str, Any]:
        # Spec: server MUST respond before host sends notifications/initialized.
        self._initialized = False  # not yet — wait for the notification
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {},
                "resources": {},
                "logging": {},
            },
            "serverInfo": {
                "name": "tars-mcp",
                "version": "0.1.0",
            },
        }

    async def _on_initialized_notification(self, _request: JsonRpcRequest) -> None:
        self._initialized = True
        logger.info("MCP server initialized — ready for tool calls")
        return None  # notification — no response

    async def _on_ping(self, _request: JsonRpcRequest) -> dict[str, Any]:
        # Ping is technically optional in MCP but most hosts use it for
        # connectivity health.
        return {}

    # ---- tools -------------------------------------------------------------

    async def _on_tools_list(self, _request: JsonRpcRequest) -> dict[str, Any]:
        return self.tools.manifest()

    async def _on_tools_call(self, request: JsonRpcRequest) -> dict[str, Any]:
        name = request.params.get("name")
        if not isinstance(name, str) or not name:
            raise JsonRpcError(
                JSONRPC_INVALID_PARAMS, "tools/call requires 'name'"
            )
        arguments = request.params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(
                JSONRPC_INVALID_PARAMS, "tools/call 'arguments' must be an object"
            )
        tool = self.tools.get(name)
        if tool is None:
            raise JsonRpcError(
                JSONRPC_INVALID_PARAMS,
                f"Unknown tool: {name}",
                {"available": [t.name for t in self.tools.all()]},
            )

        try:
            output = await tool.handler(arguments)
        except Exception as exc:  # noqa: BLE001
            # Tool errors come back as `isError: true` per MCP spec —
            # the host still gets a successful response envelope, just
            # with an error flag inside.
            logger.warning("MCP tool %s raised: %s", name, exc)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool {name} failed: {type(exc).__name__}: {exc}",
                    }
                ],
                "isError": True,
            }

        # Coerce output to MCP content envelope. Tools may return dict
        # (we JSON-stringify), str (passed through), or already-shaped
        # content list.
        if isinstance(output, list) and all(
            isinstance(item, dict) and "type" in item for item in output
        ):
            content = output
        elif isinstance(output, str):
            content = [{"type": "text", "text": output}]
        else:
            content = [
                {
                    "type": "text",
                    "text": json.dumps(output, ensure_ascii=False, indent=2),
                }
            ]
        return {"content": content, "isError": False}

    # ---- shutdown ---------------------------------------------------------

    async def _on_shutdown(self, _request: JsonRpcRequest) -> dict[str, Any]:
        logger.info("MCP server shutdown requested")
        return {}


# ─── stdio main loop ───────────────────────────────────────────────────────


async def run_stdio(server: MCPServer | None = None) -> None:
    """Run the MCP server reading stdin / writing stdout.

    Per spec, each message is one JSON object on one line. We use
    asyncio's stream readers to avoid blocking the event loop on
    stdin reads.
    """

    server = server or MCPServer()
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    # Write helper — flushes per-line.
    def write_line(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()

    logger.info("MCP server listening on stdio")
    while True:
        try:
            raw = await reader.readline()
        except (BrokenPipeError, ConnectionResetError):
            logger.info("MCP server stdin closed — exiting")
            return
        if not raw:
            # EOF — host closed the pipe.
            logger.info("MCP server stdin EOF — exiting")
            return

        line = raw.decode("utf-8", errors="replace")
        try:
            request = decode_message(line)
        except JsonRpcError as e:
            err = make_error_response(None, e.code, e.message, e.data)
            write_line(encode_message(err))
            continue

        try:
            response = await server.handle(request)
        except JsonRpcMethodNotFound as e:
            response = make_error_response(request.id, e.code, e.message, e.data)
        except JsonRpcError as e:
            response = make_error_response(request.id, e.code, e.message, e.data)

        if response is not None:
            write_line(encode_message(response))


# ─── CLI entry point ───────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m backend.core.mcp`."""

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = argv if argv is not None else sys.argv[1:]

    if "--list-tools" in args:
        from .tools import registry as _reg

        for tool in _reg().all():
            print(f"  {tool.name:30s}  {tool.description[:80]}")
        return 0

    if "--probe" in args:
        return _run_probe()

    asyncio.run(run_stdio())
    return 0


def _run_probe() -> int:
    """Quick in-process self-test: list tools + version-tool call."""

    async def go() -> None:
        server = MCPServer()
        from .protocol import JsonRpcRequest

        # initialize
        r = await server.handle(JsonRpcRequest(id=1, method="initialize"))
        print("[initialize]", json.dumps(r.to_dict(), indent=2))

        # tools/list
        r = await server.handle(JsonRpcRequest(id=2, method="tools/list"))
        print("[tools/list]", json.dumps(r.to_dict(), indent=2))

        # tools/call tars.version
        r = await server.handle(
            JsonRpcRequest(
                id=3,
                method="tools/call",
                params={"name": "tars.version", "arguments": {}},
            )
        )
        print("[tars.version]", json.dumps(r.to_dict(), indent=2))

    asyncio.run(go())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
