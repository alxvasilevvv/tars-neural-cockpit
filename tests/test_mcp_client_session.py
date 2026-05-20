"""End-to-end MCP client session tests against the mock server.

Tests spawn the tiny `tests.mcp_fixtures.mock_mcp_server` as a
subprocess and drive the full handshake / tools / call flow
through the public ``ClientSession`` surface.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from backend.core.mcp.client_pkg import ClientSession, RemoteToolError, StdioTransport
from backend.core.mcp.client_pkg.transport import RemoteRpcError


def _mock_transport(**env_overrides: str) -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=("-m", "tests.mcp_fixtures.mock_mcp_server"),
        env=env_overrides or None,
    )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------


def test_initialize_populates_server_info_and_capabilities() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            assert s.initialized is True
            assert s.protocol_version == "2025-06-18"
            assert s.server_info["name"] == "mock-mcp"
            assert s.server_capabilities["tools"]["_count"] == 2
    _run(go())


def test_initialize_failure_propagates_as_remote_rpc_error() -> None:
    async def go():
        transport = _mock_transport(MOCK_MCP_FAIL_HANDSHAKE="1")
        session = ClientSession(transport)
        await transport.start()
        try:
            with pytest.raises(RemoteRpcError) as excinfo:
                await session.initialize()
            assert excinfo.value.code == -32603
            assert "mock initialize failure" in excinfo.value.message
        finally:
            await transport.close()
    _run(go())


def test_session_must_be_initialized_before_list_tools() -> None:
    async def go():
        transport = _mock_transport()
        session = ClientSession(transport)
        await transport.start()
        try:
            with pytest.raises(RuntimeError, match="initialize"):
                await session.list_tools()
        finally:
            await transport.close()
    _run(go())


# ---------------------------------------------------------------------
# tools/list
# ---------------------------------------------------------------------


def test_list_tools_returns_known_two_tools() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            tools = await s.list_tools()
            names = sorted(t["name"] for t in tools)
            assert names == ["boom", "echo"]
            echo = next(t for t in tools if t["name"] == "echo")
            assert echo["description"].startswith("Echo")
            assert echo["annotations"]["readOnlyHint"] is True
            boom = next(t for t in tools if t["name"] == "boom")
            assert boom["annotations"]["destructiveHint"] is True
    _run(go())


# ---------------------------------------------------------------------
# tools/call — happy + error paths
# ---------------------------------------------------------------------


def test_call_tool_unwraps_text_content_into_payload() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            res = await s.call_tool("echo", {"value": "hello"})
            assert res["ok"] is True
            assert res["echo"] == {"value": "hello"}
            assert "__remote_is_error" not in res
    _run(go())


def test_call_tool_boom_marks_remote_is_error_in_payload() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            res = await s.call_tool("boom")
            assert res["__remote_is_error"] is True
            assert res["ok"] is False
            assert res["error"] == "boom"
    _run(go())


def test_call_tool_raises_when_raise_on_remote_error_set() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            with pytest.raises(RemoteToolError) as excinfo:
                await s.call_tool("boom", raise_on_remote_error=True)
            assert excinfo.value.tool_name == "boom"
            assert excinfo.value.payload["error"] == "boom"
    _run(go())


def test_call_unknown_tool_returns_remote_tool_not_found_envelope() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            res = await s.call_tool("not.a.real.tool")
            assert res["__remote_is_error"] is True
            assert res["error"] == "tool_not_found"
            assert res["name"] == "not.a.real.tool"
    _run(go())


# ---------------------------------------------------------------------
# ping + timeouts + lifecycle
# ---------------------------------------------------------------------


def test_ping_returns_empty_dict() -> None:
    async def go():
        async with ClientSession(_mock_transport()) as s:
            assert await s.ping() == {}
    _run(go())


def test_ping_timeout_aborts_with_timeout_error() -> None:
    async def go():
        async with ClientSession(_mock_transport(MOCK_MCP_DELAY_MS="500")) as s:
            with pytest.raises(TimeoutError):
                await s.ping(timeout=0.05)
    _run(go())


def test_request_after_close_raises_connection_error() -> None:
    async def go():
        transport = _mock_transport()
        session = ClientSession(transport)
        await transport.start()
        await session.initialize()
        await transport.close()
        with pytest.raises(ConnectionError):
            await session.list_tools()
    _run(go())


def test_unknown_method_yields_method_not_found() -> None:
    async def go():
        transport = _mock_transport()
        await transport.start()
        try:
            with pytest.raises(RemoteRpcError) as excinfo:
                await transport.request("not/a/real/method")
            assert excinfo.value.code == -32601
        finally:
            await transport.close()
    _run(go())


# ---------------------------------------------------------------------
# stderr forwarding
# ---------------------------------------------------------------------


def test_stderr_lines_routed_through_callback() -> None:
    async def go():
        captured: list[str] = []
        transport = _mock_transport(MOCK_MCP_LOG_TO_STDERR="1")
        transport.on_stderr = captured.append
        async with ClientSession(transport) as s:
            # Round-trip a request so the stderr loop has time to
            # drain at least the startup line.
            await s.ping()
            await asyncio.sleep(0.05)
        assert any("mock-mcp" in line for line in captured), captured
    _run(go())
