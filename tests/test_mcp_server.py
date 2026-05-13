"""Tests for the MCP server bridge (Wave 150).

Stdlib unittest only. Covers:
  - protocol decoding (valid/invalid messages)
  - JSON-RPC dispatch (initialize, tools/list, tools/call, error paths)
  - tool registry behaviour
  - built-in tool envelope shapes (tars.version is the smoke probe)
"""

from __future__ import annotations

import asyncio
import json
import unittest

from backend.core.mcp.protocol import (
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INVALID_REQUEST,
    JSONRPC_METHOD_NOT_FOUND,
    JSONRPC_PARSE_ERROR,
    JsonRpcError,
    JsonRpcRequest,
    decode_message,
    encode_message,
)
from backend.core.mcp.server import MCPServer
from backend.core.mcp.tools import (
    Tool,
    ToolRegistry,
    builtin_tools,
)


def _run(coro):
    return asyncio.run(coro)


# ---------- protocol -------------------------------------------------------


class TestProtocolDecode(unittest.TestCase):
    def test_decode_valid_request(self) -> None:
        line = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}'
        req = decode_message(line)
        self.assertEqual(req.id, 1)
        self.assertEqual(req.method, "ping")
        self.assertEqual(req.params, {})
        self.assertFalse(req.is_notification)

    def test_decode_notification_has_no_id(self) -> None:
        line = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
        req = decode_message(line)
        self.assertIsNone(req.id)
        self.assertTrue(req.is_notification)

    def test_decode_rejects_non_object(self) -> None:
        with self.assertRaises(JsonRpcError) as cm:
            decode_message("[1,2,3]")
        self.assertEqual(cm.exception.code, JSONRPC_INVALID_REQUEST)

    def test_decode_rejects_missing_jsonrpc(self) -> None:
        with self.assertRaises(JsonRpcError) as cm:
            decode_message('{"id":1,"method":"x"}')
        self.assertEqual(cm.exception.code, JSONRPC_INVALID_REQUEST)

    def test_decode_rejects_bad_method(self) -> None:
        with self.assertRaises(JsonRpcError) as cm:
            decode_message('{"jsonrpc":"2.0","id":1,"method":""}')
        self.assertEqual(cm.exception.code, JSONRPC_INVALID_REQUEST)

    def test_decode_rejects_parse_error(self) -> None:
        with self.assertRaises(JsonRpcError) as cm:
            decode_message("{not json")
        self.assertEqual(cm.exception.code, JSONRPC_PARSE_ERROR)

    def test_decode_rejects_empty_line(self) -> None:
        with self.assertRaises(JsonRpcError):
            decode_message("\n")


class TestProtocolEncode(unittest.TestCase):
    def test_encode_result_response(self) -> None:
        from backend.core.mcp.protocol import JsonRpcResponse

        line = encode_message(JsonRpcResponse(id=42, result={"ok": True}))
        self.assertTrue(line.endswith("\n"))
        body = json.loads(line)
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["id"], 42)
        self.assertEqual(body["result"], {"ok": True})
        self.assertNotIn("error", body)


# ---------- registry -------------------------------------------------------


class TestToolRegistry(unittest.TestCase):
    def test_registry_register_and_get(self) -> None:
        reg = ToolRegistry()

        async def noop(_params):
            return {"hi": 1}

        reg.register(
            Tool(name="x.noop", description="noop", input_schema={}, handler=noop)
        )
        self.assertIsNotNone(reg.get("x.noop"))
        self.assertIsNone(reg.get("missing"))
        self.assertEqual(len(reg.all()), 1)

    def test_registry_manifest_shape(self) -> None:
        reg = ToolRegistry()

        async def noop(_params):
            return {}

        reg.register(
            Tool(
                name="x.a",
                description="A",
                input_schema={"type": "object"},
                handler=noop,
            )
        )
        m = reg.manifest()
        self.assertIn("tools", m)
        self.assertEqual(m["tools"][0]["name"], "x.a")
        self.assertEqual(m["tools"][0]["description"], "A")
        self.assertEqual(m["tools"][0]["inputSchema"], {"type": "object"})

    def test_builtin_tools_present(self) -> None:
        names = {t.name for t in builtin_tools()}
        expected = {
            "tars.version",
            "tars.list_playbooks",
            "tars.run_playbook",
            "tars.recent_events",
            "tars.cowork_session",
        }
        self.assertEqual(names, expected)


# ---------- server dispatch ------------------------------------------------


class TestServerDispatch(unittest.TestCase):
    def test_initialize_returns_protocol_version(self) -> None:
        server = MCPServer()
        r = _run(server.handle(JsonRpcRequest(id=1, method="initialize")))
        assert r is not None
        self.assertEqual(r.id, 1)
        self.assertIn("protocolVersion", r.result)
        self.assertEqual(r.result["serverInfo"]["name"], "tars-mcp")

    def test_initialized_notification_returns_none(self) -> None:
        server = MCPServer()
        r = _run(
            server.handle(
                JsonRpcRequest(id=None, method="notifications/initialized")
            )
        )
        self.assertIsNone(r)  # notification — no response

    def test_unknown_method_for_request_raises(self) -> None:
        server = MCPServer()
        with self.assertRaises(JsonRpcError) as cm:
            _run(server.handle(JsonRpcRequest(id=1, method="bogus")))
        self.assertEqual(cm.exception.code, JSONRPC_METHOD_NOT_FOUND)

    def test_unknown_method_for_notification_is_silent(self) -> None:
        server = MCPServer()
        r = _run(server.handle(JsonRpcRequest(id=None, method="bogus.event")))
        self.assertIsNone(r)


class TestServerToolsList(unittest.TestCase):
    def test_tools_list_returns_builtin_count(self) -> None:
        server = MCPServer()
        r = _run(server.handle(JsonRpcRequest(id=1, method="tools/list")))
        assert r is not None
        self.assertIn("tools", r.result)
        self.assertEqual(len(r.result["tools"]), 5)


class TestServerToolsCall(unittest.TestCase):
    def test_call_tars_version_success(self) -> None:
        server = MCPServer()
        r = _run(
            server.handle(
                JsonRpcRequest(
                    id=1,
                    method="tools/call",
                    params={"name": "tars.version", "arguments": {}},
                )
            )
        )
        assert r is not None
        self.assertFalse(r.result["isError"])
        # version handler returns JSON-stringified text
        text = r.result["content"][0]["text"]
        body = json.loads(text)
        self.assertTrue(body["ok"])
        self.assertIn("tars", body)
        self.assertIn("mcp_contract", body)

    def test_call_missing_name_raises_invalid_params(self) -> None:
        server = MCPServer()
        with self.assertRaises(JsonRpcError) as cm:
            _run(
                server.handle(
                    JsonRpcRequest(
                        id=1,
                        method="tools/call",
                        params={"arguments": {}},
                    )
                )
            )
        self.assertEqual(cm.exception.code, JSONRPC_INVALID_PARAMS)

    def test_call_unknown_tool_raises_with_available_list(self) -> None:
        server = MCPServer()
        with self.assertRaises(JsonRpcError) as cm:
            _run(
                server.handle(
                    JsonRpcRequest(
                        id=1,
                        method="tools/call",
                        params={"name": "tars.does_not_exist", "arguments": {}},
                    )
                )
            )
        self.assertEqual(cm.exception.code, JSONRPC_INVALID_PARAMS)
        self.assertIn("available", cm.exception.data)
        self.assertIn("tars.version", cm.exception.data["available"])

    def test_call_tool_handler_failure_returns_isError_envelope(self) -> None:
        """Tool that raises → response with isError:true, NOT a JSON-RPC error.

        Per MCP spec, tool-level errors are surfaced inside the success
        envelope so the host can show them to the user without
        treating it as a transport failure.
        """

        server = MCPServer()

        async def boom(_params):
            raise RuntimeError("intentional boom")

        # Add a failing tool to the global registry for this test
        # (tests run in isolated process so global state is fine).
        from backend.core.mcp.tools import _REGISTRY  # noqa: SLF001

        _REGISTRY.register(
            Tool(name="x.boom", description="boom", input_schema={}, handler=boom)
        )

        r = _run(
            server.handle(
                JsonRpcRequest(
                    id=1,
                    method="tools/call",
                    params={"name": "x.boom", "arguments": {}},
                )
            )
        )
        assert r is not None
        self.assertTrue(r.result["isError"])
        self.assertIn("boom", r.result["content"][0]["text"])
        # Clean up so other tests don't see this tool.
        _REGISTRY._tools.pop("x.boom", None)  # noqa: SLF001


# ---------- built-in tool: tars.version ------------------------------------


class TestVersionTool(unittest.TestCase):
    def test_version_tool_returns_ok_shape(self) -> None:
        from backend.core.mcp.tools import _handle_version  # noqa: SLF001

        out = _run(_handle_version({}))
        self.assertTrue(out["ok"])
        self.assertIn("tars", out)
        self.assertIn("mcp_contract", out)
        self.assertIn("timestamp", out)


if __name__ == "__main__":
    unittest.main()
