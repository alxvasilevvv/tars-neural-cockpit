"""Unit tests for the MCP / JSON-RPC protocol layer."""

from __future__ import annotations

import json

import pytest

from backend.mcp.protocol import (
    ErrorCode,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    PROTOCOL_VERSION,
    Tool,
    ToolCallResult,
    make_error,
    parse_request,
    serialize_response,
    server_capabilities,
    server_info,
)


# ---------------------------------------------------------------------
# parse_request
# ---------------------------------------------------------------------


def test_parse_request_basic() -> None:
    req = parse_request(
        '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}'
    )
    assert req.method == "ping"
    assert req.id == 1
    assert req.params == {}
    assert not req.is_notification


def test_parse_request_notification_has_no_id() -> None:
    req = parse_request(
        '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    )
    assert req.id is None
    assert req.is_notification


def test_parse_request_string_id_allowed() -> None:
    req = parse_request('{"jsonrpc":"2.0","id":"abc","method":"ping"}')
    assert req.id == "abc"


def test_parse_request_rejects_wrong_jsonrpc_version() -> None:
    with pytest.raises(ValueError, match="jsonrpc"):
        parse_request('{"jsonrpc":"1.0","id":1,"method":"ping"}')


def test_parse_request_rejects_missing_method() -> None:
    with pytest.raises(ValueError, match="method"):
        parse_request('{"jsonrpc":"2.0","id":1}')


def test_parse_request_rejects_non_object_params() -> None:
    with pytest.raises(ValueError, match="params"):
        parse_request('{"jsonrpc":"2.0","id":1,"method":"x","params":[1,2]}')


def test_parse_request_rejects_non_object_request() -> None:
    with pytest.raises(ValueError, match="object"):
        parse_request("[1,2,3]")


def test_parse_request_rejects_invalid_id_type() -> None:
    with pytest.raises(ValueError, match="id"):
        parse_request('{"jsonrpc":"2.0","id":1.5,"method":"x"}')


def test_parse_request_rejects_garbage_json() -> None:
    with pytest.raises(ValueError, match="parse"):
        parse_request("not-json{")


# ---------------------------------------------------------------------
# Response serialisation
# ---------------------------------------------------------------------


def test_response_with_result() -> None:
    resp = JsonRpcResponse(id=1, result={"foo": "bar"})
    body = json.loads(serialize_response(resp))
    assert body == {"jsonrpc": "2.0", "id": 1, "result": {"foo": "bar"}}


def test_response_with_error() -> None:
    resp = make_error(2, ErrorCode.METHOD_NOT_FOUND, "no such method")
    body = json.loads(serialize_response(resp))
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 2
    assert body["error"]["code"] == ErrorCode.METHOD_NOT_FOUND
    assert "no such method" in body["error"]["message"]
    assert "result" not in body


def test_response_result_defaults_to_empty_object() -> None:
    """JSON-RPC requires `result` to be present on success; we
    canonicalise ``None`` → ``{}`` so the wire shape stays
    consistent for hosts that strict-check the envelope."""

    resp = JsonRpcResponse(id=3, result=None)
    body = json.loads(serialize_response(resp))
    assert body["result"] == {}


# ---------------------------------------------------------------------
# Tool / ToolCallResult
# ---------------------------------------------------------------------


def test_tool_to_dict_minimal() -> None:
    tool = Tool(
        name="x.y",
        description="desc",
        input_schema={"type": "object", "properties": {}},
    )
    d = tool.to_dict()
    assert d["name"] == "x.y"
    assert d["description"] == "desc"
    assert d["inputSchema"] == {"type": "object", "properties": {}}
    assert d["annotations"]["readOnlyHint"] is True
    assert d["annotations"]["destructiveHint"] is False


def test_tool_destructive_annotations_flip() -> None:
    tool = Tool(
        name="x.y",
        description="d",
        input_schema={},
        destructive=True,
    )
    d = tool.to_dict()
    assert d["annotations"]["destructiveHint"] is True
    assert d["annotations"]["readOnlyHint"] is False


def test_tool_empty_schema_falls_back_to_open_object() -> None:
    tool = Tool(name="x.y", description="d", input_schema={})
    d = tool.to_dict()
    assert d["inputSchema"] == {"type": "object", "properties": {}}


def test_tool_call_result_wraps_payload_as_text_content() -> None:
    res = ToolCallResult(payload={"ok": True, "n": 7}, is_error=False)
    d = res.to_dict()
    assert d["isError"] is False
    assert d["content"][0]["type"] == "text"
    body = json.loads(d["content"][0]["text"])
    assert body == {"n": 7, "ok": True}  # sort_keys=True in the renderer


def test_tool_call_result_preserves_is_error_flag() -> None:
    res = ToolCallResult(payload={"ok": False}, is_error=True)
    assert res.to_dict()["isError"] is True


# ---------------------------------------------------------------------
# server_capabilities / server_info
# ---------------------------------------------------------------------


def test_server_capabilities_advertises_listChanged_false() -> None:
    cap = server_capabilities(tool_count=42)
    assert cap["tools"]["listChanged"] is False
    assert cap["tools"]["_count"] == 42
    assert cap["prompts"]["listChanged"] is False
    assert cap["resources"]["listChanged"] is False


def test_server_info_pinned_name_and_version() -> None:
    info = server_info()
    assert info["name"] == "tars-mcp"
    assert info["version"]
    assert PROTOCOL_VERSION  # smoke
