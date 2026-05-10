"""Bridge from TARS ``ActionSpec`` → MCP ``Tool``.

Single source of truth: we walk the domain pack registry,
expose every ``ActionSpec`` as one MCP tool. Tool names are
``"<pack_slug>.<action_id>"`` so the MCP audit trail aligns
1-to-1 with the cockpit / CLI / HTTP audit log.

We never re-implement business logic — ``invoke_tool`` calls
the canonical async handler the cockpit calls. Errors from
the handler are translated into MCP tool-call results with
``isError: true`` so MCP hosts (Claude Desktop, Cursor)
display them inline instead of bubbling JSON-RPC errors that
abort the whole request chain.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from .protocol import Tool, ToolCallResult


log = logging.getLogger(__name__)


# Names of action ids we **never** expose through MCP, even if the
# pack registers them. Today this list is empty — every algotrade
# verb is safe for MCP — but we keep the hook so an operator can
# block a single id (e.g. a future ``algotrade.purge_audit``)
# without unregistering it from the pack.
DENY_TOOL_IDS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ToolBinding:
    """Internal record: MCP-facing ``Tool`` + the canonical
    handler it routes to."""

    tool: Tool
    handler: Callable[[Mapping[str, Any]], Any]


@dataclass
class ToolRegistry:
    """In-memory map ``tool_name → ToolBinding``. Built once at
    server start by walking the domain pack registry."""

    bindings: dict[str, ToolBinding] = field(default_factory=dict)

    def list_tools(self) -> list[Tool]:
        return [b.tool for _, b in sorted(self.bindings.items())]

    def get(self, name: str) -> ToolBinding | None:
        return self.bindings.get(name)


def _ensure_packs_loaded() -> None:
    """Import the canonical pack roster so ``all_packs()``
    returns something useful. Idempotent — calling twice is a
    no-op."""

    importlib.import_module("backend.core.domains.packs")


def build_tool_registry() -> ToolRegistry:
    """Walk every registered pack and build a ``ToolRegistry``."""

    _ensure_packs_loaded()
    from backend.core.domains.registry import all_packs

    registry = ToolRegistry()
    for pack in all_packs():
        slug = pack.manifest.slug
        for action in pack.actions():
            if action.id in DENY_TOOL_IDS:
                log.debug("mcp.tool.denied: %s.%s", slug, action.id)
                continue
            tool_name = f"{slug}.{action.id}"
            tool = Tool(
                name=tool_name,
                description=_compose_description(pack.manifest.name, action),
                input_schema=action.schema or {"type": "object", "properties": {}},
                destructive=bool(action.destructive),
            )
            registry.bindings[tool_name] = ToolBinding(
                tool=tool, handler=action.handler
            )
    log.info("mcp.tools.registered: %d tools", len(registry.bindings))
    return registry


def _compose_description(pack_name: str, action) -> str:
    """Glue the pack name onto each action description so the
    Claude Desktop tool list shows ``[Algotrade] Run a backtest…``
    instead of bare ``Run a backtest…``. Hosts truncate long
    descriptions; we keep the pack tag short."""

    base = action.description or action.name
    return f"[{pack_name}] {base}"


# ---------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------


async def invoke_tool(
    registry: ToolRegistry,
    name: str,
    arguments: Mapping[str, Any] | None,
) -> ToolCallResult:
    """Look the tool up, call its handler, wrap the payload as
    an MCP ``ToolCallResult``. Never raises — every failure
    path is encoded as a structured payload with ``isError``."""

    binding = registry.get(name)
    if binding is None:
        return ToolCallResult(
            payload={
                "ok": False,
                "error": "tool_not_found",
                "detail": (
                    f"No tool named {name!r}. Call tools/list to see "
                    "the available tools."
                ),
            },
            is_error=True,
        )

    args = dict(arguments or {})

    handler = binding.handler
    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(args)
        else:
            result = handler(args)
            if inspect.isawaitable(result):
                result = await result
    except Exception as exc:  # noqa: BLE001 — surface, never crash
        log.exception("mcp.tool.uncaught: %s", name)
        return ToolCallResult(
            payload={
                "ok": False,
                "error": "handler_uncaught",
                "detail": f"{type(exc).__name__}: {exc}",
            },
            is_error=True,
        )

    if not isinstance(result, Mapping):
        # Hand it through anyway, but flag the contract violation
        # so the operator sees something actionable.
        return ToolCallResult(
            payload={
                "ok": True,
                "warning": "handler_returned_non_mapping",
                "value": result,
            },
            is_error=False,
        )

    is_error = result.get("ok") is False
    return ToolCallResult(payload=dict(result), is_error=is_error)
