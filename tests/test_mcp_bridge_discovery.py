"""Tests for the discovery layer."""

from __future__ import annotations

import asyncio
import sys

import pytest

from backend.core.mcp_bridge.discovery import (
    DiscoveryError,
    discover_remote_tools,
)
from backend.mcp.client.registry import ServerConfig


def _mock_config(**env: str) -> ServerConfig:
    return ServerConfig(
        name="mock",
        command=sys.executable,
        args=("-m", "tests.mcp_fixtures.mock_mcp_server"),
        env=env or {},
    )


def test_discover_returns_descriptors_and_server_info() -> None:
    tools, info = asyncio.run(discover_remote_tools(_mock_config()))
    names = sorted(t["name"] for t in tools)
    assert names == ["boom", "echo"]
    assert info["name"] == "mock-mcp"
    assert info["version"] == "0.0.1"


def test_discover_handshake_failure_raises_discovery_error() -> None:
    cfg = _mock_config(MOCK_MCP_FAIL_HANDSHAKE="1")
    with pytest.raises(DiscoveryError) as excinfo:
        asyncio.run(discover_remote_tools(cfg))
    assert excinfo.value.server_name == "mock"
    assert "rpc error" in excinfo.value.reason
    assert "-32603" in excinfo.value.reason


def test_discover_command_not_found_raises_discovery_error() -> None:
    cfg = ServerConfig(name="ghost", command="/no/such/binary-please")
    with pytest.raises(DiscoveryError) as excinfo:
        asyncio.run(discover_remote_tools(cfg))
    assert excinfo.value.server_name == "ghost"
    assert "transport" in excinfo.value.reason


def test_discover_timeout_raises_discovery_error(tmp_path) -> None:
    """Spawn a subprocess that reads from stdin but never replies
    — discovery should give up after ``timeout`` and surface a
    ``DiscoveryError`` instead of blocking the test runner."""

    import textwrap

    script = tmp_path / "hang.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys
            import time

            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                time.sleep(60)
            """
        )
    )
    cfg = ServerConfig(
        name="hang", command=sys.executable, args=(str(script),)
    )
    with pytest.raises(DiscoveryError) as excinfo:
        asyncio.run(discover_remote_tools(cfg, timeout=0.5))
    assert excinfo.value.server_name == "hang"
    assert "timed out" in excinfo.value.reason
