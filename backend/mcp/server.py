"""MCP server core — request dispatcher.

Transport-agnostic: the dispatcher takes parsed
``JsonRpcRequest`` objects and emits ``JsonRpcResponse``
objects. The stdio transport (``backend.mcp.stdio``) wraps
these calls in an asyncio loop reading from stdin / writing
to stdout.

Methods we implement (MCP spec §3 + tools, prompts, resources
extensions):

| Method                      | Notes                                  |
| --------------------------- | -------------------------------------- |
| ``initialize``              | Handshake. Returns server capabilities. |
| ``notifications/initialized`` | Client says handshake done. No reply. |
| ``ping``                    | Health check. Empty result.            |
| ``tools/list``              | Returns the full tool catalog.         |
| ``tools/call``              | Invokes a tool by name.                |
| ``prompts/list``            | Empty list (no prompt templates).      |
| ``resources/list``          | Empty list (no static resources).      |
| ``resources/templates/list``| Empty list.                            |
| ``logging/setLevel``        | Accepted, but no-op (we honour stderr).|

Notifications are detected by ``request.id is None``; the
dispatcher returns ``None`` for them so the transport can
skip the write.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from .protocol import (
    ErrorCode,
    JsonRpcRequest,
    JsonRpcResponse,
    PROTOCOL_VERSION,
    make_error,
    server_capabilities,
    server_info,
)
from .tools import ToolRegistry, build_tool_registry, invoke_tool


log = logging.getLogger(__name__)


@dataclass
class McpServer:
    registry: ToolRegistry = field(default_factory=build_tool_registry)
    initialized: bool = False
    client_info: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Public entry — dispatch one parsed request
    # ------------------------------------------------------------------

    async def dispatch(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """Handle one JSON-RPC request. Returns ``None`` for
        notifications (request.id is None). Never raises."""

        method = request.method
        params = request.params or {}

        try:
            if method == "initialize":
                return self._on_initialize(request, params)
            if method == "notifications/initialized":
                self.initialized = True
                log.info("mcp.session.initialized client=%s", self.client_info)
                return None
            if method == "ping":
                return JsonRpcResponse(id=request.id, result={})
            if method == "tools/list":
                return self._on_tools_list(request)
            if method == "tools/call":
                return await self._on_tools_call(request, params)
            if method == "prompts/list":
                return JsonRpcResponse(
                    id=request.id, result={"prompts": []}
                )
            if method == "resources/list":
                return JsonRpcResponse(
                    id=request.id, result={"resources": []}
                )
            if method == "resources/templates/list":
                return JsonRpcResponse(
                    id=request.id, result={"resourceTemplates": []}
                )
            if method == "logging/setLevel":
                # Accept silently — we already log to stderr.
                return JsonRpcResponse(id=request.id, result={})
            if method.startswith("notifications/"):
                # Unknown notification → spec says "ignore silently"
                return None
            return make_error(
                request.id,
                ErrorCode.METHOD_NOT_FOUND,
                f"method not implemented: {method!r}",
            )
        except Exception as exc:  # noqa: BLE001 — never crash the loop
            log.exception("mcp.dispatch.uncaught method=%s", method)
            return make_error(
                request.id,
                ErrorCode.INTERNAL_ERROR,
                f"internal error: {type(exc).__name__}: {exc}",
            )

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    def _on_initialize(
        self, request: JsonRpcRequest, params: Mapping[str, Any]
    ) -> JsonRpcResponse:
        # We accept whatever protocolVersion the client offers — the
        # spec allows the server to pick its own and the client must
        # negotiate. We always reply with our pinned version.
        client_info = params.get("clientInfo") or {}
        if isinstance(client_info, Mapping):
            self.client_info = dict(client_info)
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": server_capabilities(
                tool_count=len(self.registry.bindings)
            ),
            "serverInfo": server_info(),
            # Free-form, but Claude Desktop / Cursor render this as a
            # hint above the tool picker. Useful to distinguish
            # multiple TARS sessions.
            "instructions": (
                "TARS MCP server. Every tool routes through the same "
                "action handler the cockpit drives, so audit log, risk "
                "gate, and council voices stay unified. Destructive "
                "tools are flagged via annotations.destructiveHint."
            ),
        }
        return JsonRpcResponse(id=request.id, result=result)

    def _on_tools_list(self, request: JsonRpcRequest) -> JsonRpcResponse:
        return JsonRpcResponse(
            id=request.id,
            result={"tools": [t.to_dict() for t in self.registry.list_tools()]},
        )

    async def _on_tools_call(
        self, request: JsonRpcRequest, params: Mapping[str, Any]
    ) -> JsonRpcResponse:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return make_error(
                request.id,
                ErrorCode.INVALID_PARAMS,
                "tools/call requires a non-empty `name` string",
            )
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            return make_error(
                request.id,
                ErrorCode.INVALID_PARAMS,
                "tools/call `arguments` must be an object",
            )
        result = await invoke_tool(self.registry, name, arguments)
        return JsonRpcResponse(id=request.id, result=result.to_dict())
