"""High-level MCP client session.

Wraps a ``StdioTransport`` with MCP-specific semantics:
``initialize`` handshake, ``ping``, ``list_tools``, and
``call_tool`` with the standard text-content unwrapping logic.

A ``ClientSession`` is the unit operators / playbooks should
hold — it knows whether the handshake succeeded, what the
remote server's protocol version is, and which tools are
exposed.

Use as an async context manager so the subprocess is reaped
even when an exception bubbles up:

    async with ClientSession(StdioTransport("python3", ("-m", "backend.mcp"))) as s:
        tools = await s.list_tools()
        result = await s.call_tool("algotrade.list_recipes")
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from .transport import RemoteRpcError, StdioTransport


log = logging.getLogger(__name__)


CLIENT_NAME = "tars-mcp-client"
CLIENT_VERSION = "0.1.0"
CLIENT_PROTOCOL_VERSION = "2025-06-18"


class RemoteToolError(Exception):
    """Raised when a ``tools/call`` returned ``isError: true``.

    Carries the parsed payload so callers can branch on
    ``error.payload.get("error") == "recipe_not_found"`` etc.
    instead of stringly-typed regex parsing.
    """

    def __init__(self, tool_name: str, payload: Mapping[str, Any]) -> None:
        self.tool_name = tool_name
        self.payload = dict(payload)
        super().__init__(
            f"remote tool {tool_name!r} returned isError=true: "
            f"{payload.get('error', 'unknown_error')}"
        )


@dataclass
class ClientSession:
    transport: StdioTransport
    server_info: dict[str, Any] = field(default_factory=dict)
    server_capabilities: dict[str, Any] = field(default_factory=dict)
    protocol_version: str | None = None
    initialized: bool = False

    async def __aenter__(self) -> "ClientSession":
        await self.transport.start()
        await self.initialize()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        try:
            await self.transport.close()
        except Exception:  # noqa: BLE001
            log.exception("mcp.client.session.close_failed")

    # ------------------------------------------------------------------
    # MCP methods
    # ------------------------------------------------------------------

    async def initialize(self, *, timeout: float = 30.0) -> dict[str, Any]:
        """Handshake. Per MCP spec: send ``initialize`` first,
        then ``notifications/initialized`` to tell the server
        the client is ready to receive tool calls."""

        result = await self.transport.request(
            "initialize",
            params={
                "protocolVersion": CLIENT_PROTOCOL_VERSION,
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
                "capabilities": {},
            },
            timeout=timeout,
        )
        if not isinstance(result, Mapping):
            raise ValueError(
                f"initialize returned non-object result: {result!r}"
            )
        self.server_info = dict(result.get("serverInfo") or {})
        self.server_capabilities = dict(result.get("capabilities") or {})
        self.protocol_version = result.get("protocolVersion")

        # Per spec the client must follow up with the
        # `notifications/initialized` notification before issuing
        # any tool calls.
        await self.transport.notify("notifications/initialized")
        self.initialized = True
        log.info(
            "mcp.client.session.initialized server=%s/%s tools_count=%s",
            self.server_info.get("name"),
            self.server_info.get("version"),
            self.server_capabilities.get("tools", {}).get("_count", "?"),
        )
        return dict(result)

    async def ping(self, *, timeout: float = 5.0) -> dict[str, Any]:
        result = await self.transport.request("ping", timeout=timeout)
        return dict(result) if isinstance(result, Mapping) else {}

    async def list_tools(self, *, timeout: float = 30.0) -> list[dict[str, Any]]:
        self._require_initialized()
        result = await self.transport.request("tools/list", timeout=timeout)
        if not isinstance(result, Mapping):
            return []
        tools = result.get("tools") or []
        return [dict(t) for t in tools if isinstance(t, Mapping)]

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        timeout: float = 60.0,
        raise_on_remote_error: bool = False,
    ) -> dict[str, Any]:
        """Call a remote tool. Returns the *unwrapped* payload —
        we collapse ``content: [{"type":"text","text":"..."}]``
        into the parsed JSON if it parses, else into a string.

        When the remote server sets ``isError: true`` (handler
        rejected the input), we either:

        - return the payload alongside ``__remote_is_error: True``
          (default — caller branches on it), or
        - raise ``RemoteToolError`` (when
          ``raise_on_remote_error=True``).
        """

        self._require_initialized()
        result = await self.transport.request(
            "tools/call",
            params={
                "name": name,
                "arguments": dict(arguments) if arguments else {},
            },
            timeout=timeout,
        )
        if not isinstance(result, Mapping):
            return {"__remote_raw": result}

        payload = _unwrap_content(result)
        is_error = bool(result.get("isError"))
        if isinstance(payload, dict):
            out = dict(payload)
        else:
            out = {"value": payload}
        if is_error:
            if raise_on_remote_error:
                raise RemoteToolError(name, out)
            out["__remote_is_error"] = True
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError(
                "ClientSession.initialize() must be called before MCP "
                "operations (or use the session as an async context "
                "manager)"
            )


def _unwrap_content(result: Mapping[str, Any]) -> Any:
    """Collapse the ``content: [{type, text}, …]`` wire shape into
    the underlying payload. We assume one text block per result —
    that is what every TARS handler emits, and what the spec
    recommends for structured tool replies."""

    content = result.get("content")
    if not isinstance(content, list) or not content:
        return result.get("structuredContent", {})
    first = content[0]
    if not isinstance(first, Mapping):
        return content
    if first.get("type") == "text" and isinstance(first.get("text"), str):
        text = first["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return first
