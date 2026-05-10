"""Synthesised ``DomainPack`` that wraps a remote MCP server.

For every tool advertised by a remote MCP server, ``BridgedPack``
emits one ``ActionSpec`` whose handler proxies the call back
through the MCP client. From the cockpit's / CLI's / TARS MCP
server's point of view, a bridged tool looks indistinguishable
from a hand-written pack action.

Per-call session: each handler invocation spins up a fresh
subprocess, runs the handshake, calls the tool, closes. This
adds ~100-300ms latency per call but is dead-simple and
correct. Connection pooling can layer on top in a future
Wave M6 without changing the action surface.

Naming:

- Pack slug: ``mcp-<server_name>``.
- Action id: sanitised ``tool_name`` — MCP tool names can
  contain ``/`` and ``.`` (e.g. ``filesystem/read_file``);
  TARS action ids are ``[a-z0-9_]``. We replace anything else
  with ``_`` and lowercase the result.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Iterable, Mapping

from backend.core.domains.base import (
    ActionSpec,
    AwarenessSource,
    DomainManifest,
    DomainPack,
)
from backend.mcp.client import ClientSession, ServerConfig, StdioTransport


log = logging.getLogger(__name__)


_BRIDGE_COLOR = "#a78bfa"  # purple — visually distinct from native packs
_NAME_SANITISER = re.compile(r"[^a-z0-9_]+")


def sanitize_action_id(tool_name: str) -> str:
    """Lowercase + collapse non-``[a-z0-9_]`` runs to ``_``."""

    cleaned = _NAME_SANITISER.sub("_", tool_name.lower()).strip("_")
    return cleaned or "tool"


def _build_handler(
    server_config: ServerConfig, tool_name: str
) -> Callable[[Mapping[str, Any]], Any]:
    """Build a per-tool async handler closure. Each call opens
    a fresh transport, runs the handshake, calls the tool,
    closes. Returns the *unwrapped* MCP payload directly so
    the cockpit / CLI / TARS MCP server see the same shape
    they get from native handlers."""

    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        transport = StdioTransport(
            command=server_config.command,
            args=server_config.args,
            env=dict(server_config.env) if server_config.env else None,
            cwd=server_config.cwd,
        )
        try:
            async with ClientSession(transport) as session:
                payload = await session.call_tool(tool_name, args or {})
            if payload.pop("__remote_is_error", False):
                if "ok" not in payload:
                    payload["ok"] = False
                return payload
            if "ok" not in payload:
                payload["ok"] = True
            return payload
        except Exception as exc:  # noqa: BLE001 — surface as structured error
            log.exception(
                "mcp.bridge.handler.uncaught server=%s tool=%s",
                server_config.name,
                tool_name,
            )
            return {
                "ok": False,
                "error": "mcp_bridge_call_failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "server": server_config.name,
                "tool": tool_name,
            }

    handler.__name__ = f"bridged__{server_config.name}__{tool_name}"
    return handler


class BridgedPack(DomainPack):
    """A ``DomainPack`` synthesised from a remote MCP server's
    tool list. Pure decorator over the M3 client — no business
    logic of its own."""

    def __init__(
        self,
        server_config: ServerConfig,
        tool_descriptors: list[dict[str, Any]],
    ) -> None:
        if not server_config.name:
            raise ValueError("server_config.name must be non-empty")
        self._server_config = server_config
        self._tool_descriptors = list(tool_descriptors)
        self._actions = tuple(
            self._build_action_spec(t) for t in tool_descriptors
        )
        description = (
            server_config.description
            or f"Bridged tools from MCP server {server_config.name!r}."
        )
        self.manifest = DomainManifest(
            slug=f"mcp-{server_config.name}",
            name=f"MCP · {server_config.name}",
            short=f"Bridged from {server_config.name}",
            description=description,
            color=_BRIDGE_COLOR,
            capabilities=("mcp.bridged",),
            audience="ops",
        )

    # ------------------------------------------------------------------
    # DomainPack contract
    # ------------------------------------------------------------------

    def actions(self) -> Iterable[ActionSpec]:
        return self._actions

    def awareness(self) -> Iterable[AwarenessSource]:
        return ()

    def system_prompt(self) -> str:
        if not self._actions:
            return (
                f"Tools bridged from MCP server {self._server_config.name!r} "
                "are unavailable right now (no tools discovered)."
            )
        names = ", ".join(sorted(a.id for a in self._actions))
        return (
            f"You have access to {len(self._actions)} tools bridged from the "
            f"MCP server {self._server_config.name!r}: {names}. They behave "
            "like native actions — call them through the standard action "
            "surface. Each call spawns a fresh remote session, so prefer "
            "batched calls when the same tool will be invoked repeatedly."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_action_spec(self, tool: Mapping[str, Any]) -> ActionSpec:
        tool_name = str(tool.get("name") or "").strip()
        if not tool_name:
            raise ValueError(
                f"bridged tool from {self._server_config.name!r} missing 'name'"
            )
        description = str(tool.get("description") or tool_name)
        # Friendly display name — first 60 chars of description.
        name = description[:60] if len(description) > 60 else description
        annotations = tool.get("annotations") or {}
        destructive = bool(
            annotations.get("destructiveHint") if isinstance(annotations, Mapping) else False
        )
        schema = tool.get("inputSchema")
        if not isinstance(schema, Mapping):
            schema = {"type": "object", "properties": {}}
        return ActionSpec(
            id=sanitize_action_id(tool_name),
            name=name,
            description=description,
            handler=_build_handler(self._server_config, tool_name),
            schema=dict(schema),
            destructive=destructive,
        )

    @property
    def server_config(self) -> ServerConfig:
        return self._server_config

    @property
    def tool_descriptors(self) -> list[dict[str, Any]]:
        return list(self._tool_descriptors)
