"""MCP / JSON-RPC 2.0 message types and serialisation.

Stdlib-only. The MCP spec is layered on top of JSON-RPC 2.0
(https://www.jsonrpc.org/specification, https://modelcontextprotocol.io)
and we implement just the slice TARS needs:

- ``initialize`` — handshake, server capabilities.
- ``notifications/initialized`` — client says "handshake done".
- ``ping`` — health check.
- ``tools/list`` — list available tools.
- ``tools/call`` — invoke a tool.
- ``prompts/list``, ``resources/list`` — return empty (we
  don't ship prompt templates / static resources today).

Standard JSON-RPC error codes we use:

- -32700 parse error
- -32600 invalid request
- -32601 method not found
- -32602 invalid params
- -32603 internal error

MCP-specific (per spec §6 errors): we use the numeric range
-32000 to -32099 ("server error reserved"):

- -32000 — operator/user error (handler returned ok=False).
- -32001 — tool not found.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


PROTOCOL_VERSION = "2025-06-18"  # MCP spec version we implement against.
SERVER_NAME = "tars-mcp"
SERVER_VERSION = "0.1.0"


# ---------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------


class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    HANDLER_ERROR = -32000  # action handler returned ok=False
    TOOL_NOT_FOUND = -32001


# ---------------------------------------------------------------------
# JSON-RPC envelope dataclasses
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class JsonRpcError:
    code: int
    message: str
    data: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            out["data"] = self.data
        return out


@dataclass(frozen=True)
class JsonRpcRequest:
    method: str
    params: Mapping[str, Any] | None = None
    id: int | str | None = None  # None ⇒ notification (no response expected)

    @property
    def is_notification(self) -> bool:
        return self.id is None


@dataclass(frozen=True)
class JsonRpcResponse:
    id: int | str | None
    result: Any | None = None
    error: JsonRpcError | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            out["error"] = self.error.to_dict()
        else:
            out["result"] = self.result if self.result is not None else {}
        return out


# ---------------------------------------------------------------------
# MCP Tool definition + call result
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    """An MCP tool advertised through ``tools/list``.

    ``name`` is the unique tool identifier the client uses in
    ``tools/call``. We mint it as ``"<pack>.<action_id>"`` so
    operators can grep the audit log by the same name they see in
    the cockpit / CLI.

    ``input_schema`` is a JSON Schema object — TARS ``ActionSpec``
    schemas are already JSON-Schema-compatible so we forward them
    as-is.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any]
    destructive: bool = False

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": dict(self.input_schema)
            if self.input_schema
            else {"type": "object", "properties": {}},
        }
        if self.destructive:
            # MCP optional ``annotations`` block — tells well-behaved
            # hosts (Claude Desktop, Cursor) to surface a confirm
            # dialog before invoking. Spec §3.4.
            out["annotations"] = {
                "title": self.name,
                "destructiveHint": True,
                "readOnlyHint": False,
                "openWorldHint": False,
            }
        else:
            out["annotations"] = {
                "title": self.name,
                "destructiveHint": False,
                "readOnlyHint": True,
                "openWorldHint": False,
            }
        return out


@dataclass(frozen=True)
class ToolCallResult:
    """Wraps the action handler's payload as MCP tool content.

    MCP expects ``content: [{"type": "text", "text": "..."}]``.
    We serialize the dict to pretty JSON so the host can render
    it readably and the operator can read it inline in Claude
    Desktop's tool-call UI.
    """

    payload: Mapping[str, Any]
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        text = json.dumps(self.payload, indent=2, ensure_ascii=False, sort_keys=True)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": self.is_error,
        }


# ---------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------


def parse_request(raw: str) -> JsonRpcRequest:
    """Parse one JSON-RPC request line. Raises ``ValueError`` on
    a structural problem so the dispatcher can wrap it into a
    PARSE_ERROR or INVALID_REQUEST response."""

    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"json parse failed: {exc}") from exc

    if not isinstance(body, Mapping):
        raise ValueError("request must be a JSON object")
    if body.get("jsonrpc") != "2.0":
        raise ValueError("missing or wrong jsonrpc version (need '2.0')")
    method = body.get("method")
    if not isinstance(method, str) or not method:
        raise ValueError("method must be a non-empty string")
    params = body.get("params")
    if params is not None and not isinstance(params, Mapping):
        raise ValueError("params must be an object when present")
    raw_id = body.get("id")
    if raw_id is not None and not isinstance(raw_id, (int, str)):
        raise ValueError("id must be int, str, or omitted")

    return JsonRpcRequest(method=method, params=params, id=raw_id)


def serialize_response(response: JsonRpcResponse) -> str:
    """One JSON-RPC response → one stdout line. No trailing
    newline; the transport layer adds it."""

    return json.dumps(response.to_dict(), ensure_ascii=False)


def make_error(
    request_id: int | str | None,
    code: int,
    message: str,
    data: Any | None = None,
) -> JsonRpcResponse:
    return JsonRpcResponse(
        id=request_id,
        error=JsonRpcError(code=code, message=message, data=data),
    )


# ---------------------------------------------------------------------
# Server-side capability advertisement (used in `initialize` reply)
# ---------------------------------------------------------------------


def server_info() -> dict[str, Any]:
    return {"name": SERVER_NAME, "version": SERVER_VERSION}


def server_capabilities(*, tool_count: int) -> dict[str, Any]:
    """Capabilities the client should expect us to honour. We
    declare ``tools`` (always) and empty ``prompts`` /
    ``resources`` so the client doesn't probe us for what we
    don't have. ``listChanged: false`` because the tool surface
    is fixed at server start (one process = one pack registry)."""

    return {
        "tools": {"listChanged": False, "_count": tool_count},
        "prompts": {"listChanged": False},
        "resources": {"listChanged": False, "subscribe": False},
        "logging": {},
    }
