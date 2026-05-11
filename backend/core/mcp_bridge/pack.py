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
from typing import Any, Callable, Iterable, Mapping, TYPE_CHECKING

from backend.core.domains.base import (
    ActionSpec,
    AwarenessSource,
    DomainManifest,
    DomainPack,
)
from backend.mcp.client import ClientSession, ServerConfig, StdioTransport

if TYPE_CHECKING:
    from .pool import SessionPool


log = logging.getLogger(__name__)


_BRIDGE_COLOR = "#a78bfa"  # purple — visually distinct from native packs
_NAME_SANITISER = re.compile(r"[^a-z0-9_]+")


def sanitize_action_id(tool_name: str) -> str:
    """Lowercase + collapse non-``[a-z0-9_]`` runs to ``_``."""

    cleaned = _NAME_SANITISER.sub("_", tool_name.lower()).strip("_")
    return cleaned or "tool"


def _build_handler(
    server_config: ServerConfig,
    tool_name: str,
    *,
    pool: "SessionPool | None" = None,
) -> Callable[[Mapping[str, Any]], Any]:
    """Build a per-tool async handler closure.

    When ``pool`` is ``None`` (M5 default), each call opens a
    fresh transport, runs the handshake, calls the tool,
    closes. Simple but ~100-300ms per call.

    When ``pool`` is provided (Wave M6), each call reuses the
    long-lived ``ClientSession`` cached by the pool. On
    transient transport errors (remote crashed, EOF), the
    handler evicts the dead entry and retries once with a
    fresh session — operators see at most one failed call
    per remote crash.

    Returns the *unwrapped* MCP payload directly so the
    cockpit / CLI / TARS MCP server see the same shape they
    get from native handlers.
    """

    if pool is None:
        return _build_per_call_handler(server_config, tool_name)
    return _build_pooled_handler(server_config, tool_name, pool)


def _build_per_call_handler(
    server_config: ServerConfig, tool_name: str
) -> Callable[[Mapping[str, Any]], Any]:
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
            return _normalise_payload(payload)
        except Exception as exc:  # noqa: BLE001 — surface as structured error
            log.exception(
                "mcp.bridge.handler.uncaught server=%s tool=%s",
                server_config.name,
                tool_name,
            )
            return _failure_envelope(server_config.name, tool_name, exc)

    handler.__name__ = f"bridged__{server_config.name}__{tool_name}"
    return handler


def _build_pooled_handler(
    server_config: ServerConfig,
    tool_name: str,
    pool: "SessionPool",
) -> Callable[[Mapping[str, Any]], Any]:
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        try:
            session = await pool.get_or_create(server_config)
            # Wave M7 — gate every call_tool through the pool's
            # per-server semaphore so a misbehaving caller can't
            # flood one MCP server with concurrent requests. The
            # context manager is a no-op when no cap is set.
            async with pool.acquire_slot(server_config):
                try:
                    payload = await session.call_tool(tool_name, args or {})
                except (ConnectionError, BrokenPipeError) as exc:
                    # The pooled session died mid-call. Evict it,
                    # reconnect, retry once. After that, surface
                    # the failure to the caller.
                    log.warning(
                        "mcp.bridge.pooled.retry server=%s tool=%s reason=%s",
                        server_config.name,
                        tool_name,
                        exc,
                    )
                    await pool.evict(server_config.name)
                    session = await pool.get_or_create(server_config)
                    payload = await session.call_tool(tool_name, args or {})
            return _normalise_payload(payload)
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "mcp.bridge.handler.uncaught server=%s tool=%s",
                server_config.name,
                tool_name,
            )
            return _failure_envelope(server_config.name, tool_name, exc)

    handler.__name__ = f"bridged_pooled__{server_config.name}__{tool_name}"
    return handler


def _normalise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the cockpit-facing ``ok``/``isError`` collapsing.
    Shared by the per-call and pooled handlers so both flavours
    return the same shape."""

    if payload.pop("__remote_is_error", False):
        if "ok" not in payload:
            payload["ok"] = False
        return payload
    if "ok" not in payload:
        payload["ok"] = True
    return payload


def _failure_envelope(
    server_name: str, tool_name: str, exc: BaseException
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "mcp_bridge_call_failed",
        "detail": f"{type(exc).__name__}: {exc}",
        "server": server_name,
        "tool": tool_name,
    }


class BridgedPack(DomainPack):
    """A ``DomainPack`` synthesised from a remote MCP server's
    tool list. Pure decorator over the M3 client — no business
    logic of its own."""

    def __init__(
        self,
        server_config: ServerConfig,
        tool_descriptors: list[dict[str, Any]],
        *,
        pool: "SessionPool | None" = None,
    ) -> None:
        if not server_config.name:
            raise ValueError("server_config.name must be non-empty")
        self._server_config = server_config
        self._tool_descriptors = list(tool_descriptors)
        self._pool = pool
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
            handler=_build_handler(
                self._server_config, tool_name, pool=self._pool
            ),
            schema=dict(schema),
            destructive=destructive,
        )

    @property
    def server_config(self) -> ServerConfig:
        return self._server_config

    @property
    def tool_descriptors(self) -> list[dict[str, Any]]:
        return list(self._tool_descriptors)

    @property
    def pooled(self) -> bool:
        return self._pool is not None
