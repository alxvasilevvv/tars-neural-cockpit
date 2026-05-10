"""Tests for the ActionSpec → MCP Tool bridge."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

from backend.mcp.tools import (
    ToolBinding,
    ToolRegistry,
    build_tool_registry,
    invoke_tool,
)
from backend.mcp.protocol import Tool


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------
# Registry build (real packs)
# ---------------------------------------------------------------------


def test_registry_includes_algotrade_pack() -> None:
    reg = build_tool_registry()
    names = set(reg.bindings.keys())
    # Verbs guaranteed on main from W1.
    assert "algotrade.list_recipes" in names
    assert "algotrade.backtest" in names
    assert "algotrade.register_strategy" in names


def test_registry_tool_names_are_pack_dot_action() -> None:
    reg = build_tool_registry()
    for name in reg.bindings:
        assert "." in name, f"tool {name!r} missing pack prefix"


def test_registry_list_tools_is_sorted_by_name() -> None:
    reg = build_tool_registry()
    names = [t.name for t in reg.list_tools()]
    assert names == sorted(names)


def test_registry_destructive_actions_carry_flag() -> None:
    reg = build_tool_registry()
    # `register_strategy` writes to the local strategy registry —
    # destructive on disk, so the flag must propagate.
    binding = reg.get("algotrade.register_strategy")
    assert binding is not None
    assert binding.tool.destructive is True
    # Read-only verb stays non-destructive.
    listing = reg.get("algotrade.list_recipes")
    assert listing is not None
    assert listing.tool.destructive is False


# ---------------------------------------------------------------------
# invoke_tool — async + sync handlers, error paths
# ---------------------------------------------------------------------


def _registry_with(bindings: dict[str, ToolBinding]) -> ToolRegistry:
    return ToolRegistry(bindings=bindings)


def test_invoke_tool_unknown_returns_isError() -> None:
    reg = _registry_with({})
    res = _run(invoke_tool(reg, "x.y", {}))
    assert res.is_error is True
    assert res.payload["error"] == "tool_not_found"


def test_invoke_tool_async_handler_payload() -> None:
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True, "echo": dict(args)}

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", {"a": 1}))
    assert res.is_error is False
    assert res.payload == {"ok": True, "echo": {"a": 1}}


def test_invoke_tool_sync_handler_payload() -> None:
    def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True, "n": len(args)}

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", {"a": 1, "b": 2}))
    assert res.is_error is False
    assert res.payload == {"ok": True, "n": 2}


def test_invoke_tool_handler_returning_ok_false_marks_isError() -> None:
    async def handler(_args: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": "oops"}

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", {}))
    assert res.is_error is True
    assert res.payload["error"] == "oops"


def test_invoke_tool_handler_uncaught_exception_is_caught() -> None:
    async def handler(_args: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", {}))
    assert res.is_error is True
    assert res.payload["error"] == "handler_uncaught"
    assert "RuntimeError" in res.payload["detail"]
    assert "boom" in res.payload["detail"]


def test_invoke_tool_handler_returning_non_mapping_warns() -> None:
    async def handler(_args: Mapping[str, Any]) -> Any:
        return [1, 2, 3]

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", {}))
    # Non-mapping is a contract violation but not an error per se —
    # we surface it so the operator can fix the handler.
    assert res.is_error is False
    assert res.payload.get("warning") == "handler_returned_non_mapping"
    assert res.payload["value"] == [1, 2, 3]


def test_invoke_tool_none_arguments_treated_as_empty() -> None:
    captured: dict[str, Any] = {}

    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        captured["args"] = dict(args)
        return {"ok": True}

    reg = _registry_with(
        {
            "x.y": ToolBinding(
                tool=Tool(name="x.y", description="d", input_schema={}),
                handler=handler,
            )
        }
    )
    res = _run(invoke_tool(reg, "x.y", None))
    assert res.is_error is False
    assert captured["args"] == {}
