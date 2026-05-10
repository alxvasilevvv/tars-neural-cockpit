"""End-to-end MCP server tests via the in-process dispatcher.

We never spawn a subprocess — the dispatcher is a pure
async function that takes parsed ``JsonRpcRequest`` objects
and returns ``JsonRpcResponse`` objects. This keeps the suite
fast and deterministic.

A separate stdio-transport test (`test_mcp_stdio.py`) covers
the line-framing / EOF behaviour.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.mcp.protocol import (
    ErrorCode,
    JsonRpcRequest,
    PROTOCOL_VERSION,
)
from backend.mcp.server import McpServer


@pytest.fixture
def server() -> McpServer:
    return McpServer()


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------
# initialize / handshake
# ---------------------------------------------------------------------


def test_initialize_returns_capabilities_and_pinned_version(server) -> None:
    req = JsonRpcRequest(
        method="initialize",
        params={
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "pytest", "version": "0"},
            "capabilities": {},
        },
        id=1,
    )
    resp = _run(server.dispatch(req))
    body = resp.to_dict()
    assert body["id"] == 1
    assert body["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert body["result"]["serverInfo"]["name"] == "tars-mcp"
    assert body["result"]["capabilities"]["tools"]["listChanged"] is False
    # We registered at least the algotrade pack — count must be >0.
    assert body["result"]["capabilities"]["tools"]["_count"] > 0
    assert "instructions" in body["result"]
    assert server.client_info["name"] == "pytest"


def test_notifications_initialized_marks_session_ready(server) -> None:
    assert server.initialized is False
    resp = _run(
        server.dispatch(
            JsonRpcRequest(method="notifications/initialized", id=None)
        )
    )
    assert resp is None
    assert server.initialized is True


def test_unknown_notification_silently_ignored(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(method="notifications/who_knows", id=None)
        )
    )
    assert resp is None


def test_ping_returns_empty_result(server) -> None:
    resp = _run(server.dispatch(JsonRpcRequest(method="ping", id=99)))
    body = resp.to_dict()
    assert body["id"] == 99
    assert body["result"] == {}


def test_unknown_method_returns_method_not_found(server) -> None:
    resp = _run(
        server.dispatch(JsonRpcRequest(method="bogus/thing", id=10))
    )
    body = resp.to_dict()
    assert body["error"]["code"] == ErrorCode.METHOD_NOT_FOUND
    assert "bogus/thing" in body["error"]["message"]


# ---------------------------------------------------------------------
# tools/list
# ---------------------------------------------------------------------


def test_tools_list_includes_known_algotrade_verbs(server) -> None:
    resp = _run(server.dispatch(JsonRpcRequest(method="tools/list", id=1)))
    body = resp.to_dict()
    names = {t["name"] for t in body["result"]["tools"]}
    # Verbs guaranteed present on the W1 algotrade pack (the
    # only algotrade slice merged to main at the time this PR
    # opens). Stacked PRs (#166–#174) add 30+ more verbs and
    # this set will grow automatically — no test edit needed.
    assert "algotrade.list_recipes" in names
    assert "algotrade.backtest" in names
    assert "algotrade.register_strategy" in names
    assert "algotrade.get_strategy" in names


def test_tools_list_destructive_actions_carry_destructive_hint(server) -> None:
    resp = _run(server.dispatch(JsonRpcRequest(method="tools/list", id=1)))
    by_name = {
        t["name"]: t for t in resp.to_dict()["result"]["tools"]
    }
    # `register_strategy` is destructive (writes to the local
    # strategy registry on disk). Use it as the canary because
    # it's guaranteed to be on main from W1.
    register = by_name["algotrade.register_strategy"]
    assert register["annotations"]["destructiveHint"] is True
    # `list_recipes` is read-only.
    recipes = by_name["algotrade.list_recipes"]
    assert recipes["annotations"]["destructiveHint"] is False
    assert recipes["annotations"]["readOnlyHint"] is True


def test_tools_list_descriptions_carry_pack_tag(server) -> None:
    resp = _run(server.dispatch(JsonRpcRequest(method="tools/list", id=1)))
    by_name = {t["name"]: t for t in resp.to_dict()["result"]["tools"]}
    desc = by_name["algotrade.list_recipes"]["description"]
    assert desc.startswith("[")  # pack tag prefix
    assert "]" in desc


# ---------------------------------------------------------------------
# tools/call — happy + error paths
# ---------------------------------------------------------------------


def test_tools_call_happy_path_list_recipes(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="tools/call",
                params={"name": "algotrade.list_recipes", "arguments": {}},
                id=1,
            )
        )
    )
    body = resp.to_dict()
    assert body["result"]["isError"] is False
    text = body["result"]["content"][0]["text"]
    payload = json.loads(text)
    assert payload["ok"] is True
    assert "ma_cross" in payload["recipes"]


def test_tools_call_handler_error_marks_isError_true(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="tools/call",
                params={
                    "name": "algotrade.load_recipe",
                    "arguments": {"name": "totally-not-real"},
                },
                id=2,
            )
        )
    )
    body = resp.to_dict()
    assert body["result"]["isError"] is True
    payload = json.loads(body["result"]["content"][0]["text"])
    assert payload["ok"] is False
    assert payload["error"] == "recipe_not_found"


def test_tools_call_unknown_tool_returns_isError(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="tools/call",
                params={"name": "fake.thing", "arguments": {}},
                id=3,
            )
        )
    )
    body = resp.to_dict()
    assert body["result"]["isError"] is True
    payload = json.loads(body["result"]["content"][0]["text"])
    assert payload["error"] == "tool_not_found"


def test_tools_call_missing_name_returns_invalid_params(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="tools/call",
                params={"arguments": {}},
                id=4,
            )
        )
    )
    body = resp.to_dict()
    assert body["error"]["code"] == ErrorCode.INVALID_PARAMS
    assert "name" in body["error"]["message"]


def test_tools_call_non_object_arguments_returns_invalid_params(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="tools/call",
                params={"name": "algotrade.list_recipes", "arguments": [1, 2]},
                id=5,
            )
        )
    )
    body = resp.to_dict()
    assert body["error"]["code"] == ErrorCode.INVALID_PARAMS


# ---------------------------------------------------------------------
# Empty list responses we still need to honour
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,key",
    [
        ("prompts/list", "prompts"),
        ("resources/list", "resources"),
        ("resources/templates/list", "resourceTemplates"),
    ],
)
def test_optional_lists_return_empty(server, method, key) -> None:
    resp = _run(server.dispatch(JsonRpcRequest(method=method, id=1)))
    assert resp.to_dict()["result"] == {key: []}


def test_logging_set_level_is_a_silent_noop(server) -> None:
    resp = _run(
        server.dispatch(
            JsonRpcRequest(
                method="logging/setLevel",
                params={"level": "info"},
                id=1,
            )
        )
    )
    assert resp.to_dict()["result"] == {}


# ---------------------------------------------------------------------
# End-to-end: register → fork → list strategies via MCP
# ---------------------------------------------------------------------
#
# Once the W2/W3/W4 stack lands, a richer lab flow lives in
# `tests/test_algotrade_lab.py` (the same handlers, driven through
# the cockpit and CLI). The check below uses only verbs guaranteed
# on main from W1, so this test stays green regardless of stack
# merge order.


def test_end_to_end_strategy_flow_via_mcp(
    server, monkeypatch, tmp_path
) -> None:
    """Drive the W1 strategy registry flow entirely through
    ``tools/call`` — load recipe → register → list. Same handlers
    the cockpit + CLI hit, so a green test means the audit trail
    stays unified across all three transports."""

    monkeypatch.setenv("TARS_ALGOTRADE_HOME", str(tmp_path))

    def call(name, args):
        resp = _run(
            server.dispatch(
                JsonRpcRequest(
                    method="tools/call",
                    params={"name": name, "arguments": args},
                    id=42,
                )
            )
        )
        body = resp.to_dict()
        assert body["result"]["isError"] is False, body
        return json.loads(body["result"]["content"][0]["text"])

    recipes = call("algotrade.list_recipes", {})
    assert "ma_cross" in recipes["recipes"]

    registered = call(
        "algotrade.register_strategy",
        {"recipe": "ma_cross", "author": "mcp-smoke"},
    )
    fingerprint = registered.get("fingerprint") or registered.get(
        "strategy", {}
    ).get("fingerprint")
    assert fingerprint, registered

    listing = call("algotrade.list_strategies", {})
    fps = {s.get("fingerprint") for s in listing.get("strategies", [])}
    assert fingerprint in fps
