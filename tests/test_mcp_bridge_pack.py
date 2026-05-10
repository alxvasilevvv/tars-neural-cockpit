"""Tests for the synthesised ``BridgedPack``."""

from __future__ import annotations

import asyncio
import sys

import pytest

from backend.core.mcp_bridge.pack import BridgedPack, sanitize_action_id
from backend.mcp.client.registry import ServerConfig


# ---------------------------------------------------------------------
# sanitize_action_id
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("read_file", "read_file"),
        ("FileSystem/Read", "filesystem_read"),
        ("api.v1.users", "api_v1_users"),
        ("dash-name", "dash_name"),
        ("UPPER", "upper"),
        ("__edges__", "edges"),
        ("", "tool"),
        ("???", "tool"),
        ("__lots___of___under__", "lots___of___under"),
    ],
)
def test_sanitize_action_id(raw, expected) -> None:
    assert sanitize_action_id(raw) == expected


# ---------------------------------------------------------------------
# Pack construction
# ---------------------------------------------------------------------


def _server() -> ServerConfig:
    return ServerConfig(
        name="example",
        command=sys.executable,
        args=("-m", "tests.mcp_fixtures.mock_mcp_server"),
        description="example bridge",
    )


def _tools() -> list[dict]:
    return [
        {
            "name": "echo",
            "description": "Echo the arguments back.",
            "inputSchema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
            },
            "annotations": {"destructiveHint": False, "readOnlyHint": True},
        },
        {
            "name": "delete_all",
            "description": "Pretend to wipe the world.",
            "inputSchema": {"type": "object", "properties": {}},
            "annotations": {"destructiveHint": True, "readOnlyHint": False},
        },
    ]


def test_pack_manifest_uses_mcp_prefix() -> None:
    pack = BridgedPack(_server(), _tools())
    assert pack.manifest.slug == "mcp-example"
    assert pack.manifest.name == "MCP · example"
    assert pack.manifest.color == "#a78bfa"
    assert pack.manifest.capabilities == ("mcp.bridged",)
    assert "example bridge" in pack.manifest.description


def test_pack_actions_proxy_remote_descriptors() -> None:
    pack = BridgedPack(_server(), _tools())
    by_id = {a.id: a for a in pack.actions()}
    assert set(by_id) == {"echo", "delete_all"}
    assert by_id["echo"].description == "Echo the arguments back."
    assert by_id["echo"].destructive is False
    assert by_id["delete_all"].destructive is True
    assert by_id["echo"].schema["properties"]["value"]["type"] == "string"


def test_pack_action_name_truncates_long_descriptions() -> None:
    long = "A" * 200
    pack = BridgedPack(
        _server(),
        [
            {
                "name": "x",
                "description": long,
                "inputSchema": {},
            }
        ],
    )
    action = next(iter(pack.actions()))
    assert action.name == "A" * 60


def test_pack_rejects_tool_descriptor_without_name() -> None:
    with pytest.raises(ValueError, match="missing 'name'"):
        BridgedPack(_server(), [{"description": "no name here"}])


def test_pack_with_zero_tools_has_friendly_system_prompt() -> None:
    pack = BridgedPack(_server(), [])
    assert "unavailable right now" in pack.system_prompt()


def test_pack_system_prompt_lists_tools() -> None:
    pack = BridgedPack(_server(), _tools())
    prompt = pack.system_prompt()
    assert "delete_all" in prompt
    assert "echo" in prompt
    assert "example" in prompt


def test_pack_awareness_is_empty() -> None:
    pack = BridgedPack(_server(), _tools())
    assert list(pack.awareness()) == []


def test_pack_rejects_empty_server_name() -> None:
    bad = ServerConfig(name="", command="x")
    with pytest.raises(ValueError, match="non-empty"):
        BridgedPack(bad, _tools())


# ---------------------------------------------------------------------
# Handler — round-trip through real subprocess (mock fixture)
# ---------------------------------------------------------------------


def test_handler_roundtrips_against_mock_server() -> None:
    pack = BridgedPack(_server(), _tools())
    handler = next(a for a in pack.actions() if a.id == "echo").handler
    result = asyncio.run(handler({"value": "hello"}))
    assert result["ok"] is True
    assert result["echo"] == {"value": "hello"}


def test_handler_remote_iserror_propagates_as_ok_false() -> None:
    """The mock's `boom` tool returns ``isError: true``. The
    bridge handler should surface that as ``ok=False`` in the
    structured payload — same shape native handlers use for
    rejections."""

    pack = BridgedPack(
        _server(),
        [
            {
                "name": "boom",
                "description": "Always errors.",
                "inputSchema": {},
                "annotations": {"destructiveHint": True},
            }
        ],
    )
    handler = next(iter(pack.actions())).handler
    result = asyncio.run(handler({}))
    assert result["ok"] is False
    assert result["error"] == "boom"


def test_handler_subprocess_failure_returns_structured_error() -> None:
    """Pointing at a binary that does not exist should yield a
    structured payload, not an unhandled exception."""

    bad_server = ServerConfig(
        name="ghost",
        command="/no/such/binary/ever-please",
        args=(),
    )
    pack = BridgedPack(
        bad_server,
        [{"name": "noop", "description": "x", "inputSchema": {}}],
    )
    handler = next(iter(pack.actions())).handler
    result = asyncio.run(handler({}))
    assert result["ok"] is False
    assert result["error"] == "mcp_bridge_call_failed"
    assert result["server"] == "ghost"
    assert result["tool"] == "noop"
