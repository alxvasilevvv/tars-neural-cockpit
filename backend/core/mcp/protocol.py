"""JSON-RPC 2.0 message types + stdio framing (Wave 150).

MCP wire format: newline-delimited JSON over stdin/stdout. Each
message is one JSON object on one line. Reference:
https://modelcontextprotocol.io/specification

Subset we implement in v0.1:
  - initialize          (handshake)
  - notifications/initialized
  - tools/list          (announce available tools)
  - tools/call          (invoke a tool)
  - shutdown            (graceful close)

Not yet supported:
  - prompts/*           (v9.2)
  - resources/*         (v9.2)
  - logging             (v9.2 — for now MCP host's stderr passthrough is enough)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "0.1.0"  # TARS-side version — MCP protocol itself is unversioned
MCP_PROTOCOL_VERSION = "2024-11-05"  # MCP spec version we conform to

# Error codes per JSON-RPC 2.0 spec + MCP extensions.
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


# ---------- Exceptions -----------------------------------------------------


class JsonRpcError(Exception):
    """Raised when a tool handler wants to return a structured error."""

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


class JsonRpcMethodNotFound(JsonRpcError):
    def __init__(self, method: str) -> None:
        super().__init__(
            JSONRPC_METHOD_NOT_FOUND,
            f"Method not found: {method}",
            {"method": method},
        )


# ---------- Message types --------------------------------------------------


@dataclass
class JsonRpcRequest:
    """Inbound message: {jsonrpc:'2.0', id, method, params}.

    Notifications (no id) also represented here with id=None — the server
    skips sending a response for those.
    """

    id: int | str | None
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.id is None


@dataclass
class JsonRpcResponse:
    """Outbound message — either result or error, never both."""

    id: int | str | None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            out["error"] = self.error
        else:
            out["result"] = self.result if self.result is not None else {}
        return out


# ---------- Framing helpers ------------------------------------------------


def decode_message(line: str) -> JsonRpcRequest:
    """Parse one newline-delimited JSON line into a JsonRpcRequest.

    Raises :class:`JsonRpcError` (parse / invalid request) with the
    appropriate JSON-RPC error code; the caller turns that into a
    response with `id=None` per spec.
    """

    stripped = line.strip()
    if not stripped:
        raise JsonRpcError(JSONRPC_PARSE_ERROR, "Empty message")
    try:
        msg = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise JsonRpcError(JSONRPC_PARSE_ERROR, f"Invalid JSON: {exc}") from exc

    if not isinstance(msg, dict):
        raise JsonRpcError(JSONRPC_INVALID_REQUEST, "Message must be an object")
    if msg.get("jsonrpc") != "2.0":
        raise JsonRpcError(JSONRPC_INVALID_REQUEST, "jsonrpc must be '2.0'")
    method = msg.get("method")
    if not isinstance(method, str) or not method:
        raise JsonRpcError(JSONRPC_INVALID_REQUEST, "method must be a non-empty string")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        raise JsonRpcError(JSONRPC_INVALID_PARAMS, "params must be an object")

    return JsonRpcRequest(
        id=msg.get("id"),
        method=method,
        params=params,
        raw=msg,
    )


def encode_message(response: JsonRpcResponse) -> str:
    """Encode a response as one newline-delimited JSON line.

    Always emits a trailing newline — that's the stdio frame delimiter.
    """

    return json.dumps(response.to_dict(), ensure_ascii=False) + "\n"


def make_error_response(
    id: int | str | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JsonRpcResponse:
    """Convenience: build an error-shape response."""

    err: dict[str, Any] = {"code": code, "message": message}
    if data:
        err["data"] = data
    return JsonRpcResponse(id=id, error=err)
