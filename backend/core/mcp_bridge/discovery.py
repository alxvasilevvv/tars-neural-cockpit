"""Discover what tools a remote MCP server exposes.

Async helper that spins up a one-shot MCP client session
against a configured remote server, runs the handshake,
calls ``tools/list``, and returns the list of tool
descriptors. Used at boot to learn what actions a
``BridgedPack`` should advertise.

Discovery is deliberately one-shot — we open the transport,
list, close. Long-lived connections live in a future Wave
M6 (connection pooling). For workshops + interactive use
the per-call cost is in the 100-300ms range, dominated by
the subprocess spawn time of the remote server.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.mcp.client import ClientSession, ServerConfig, StdioTransport
from backend.mcp.client.transport import RemoteRpcError


log = logging.getLogger(__name__)


class DiscoveryError(Exception):
    """Raised when discovery fails for any reason — subprocess
    failed to start, handshake rejected, list timed out, etc.
    The bootstrap loop catches it and skips the offending
    server with a warning so one bad config does not break
    the entire bridge."""

    def __init__(self, server_name: str, reason: str) -> None:
        self.server_name = server_name
        self.reason = reason
        super().__init__(f"discovery failed for {server_name!r}: {reason}")


async def discover_remote_tools(
    config: ServerConfig,
    *,
    timeout: float = 30.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Connect to ``config``, return (tool_descriptors, server_info).

    ``tool_descriptors`` are the raw dicts the remote server
    returned through ``tools/list`` — same shape an MCP host
    would see. ``server_info`` is the ``serverInfo`` block
    from the ``initialize`` reply.

    Never raises ``ClientSession`` lifecycle exceptions
    directly — wraps them in :class:`DiscoveryError` so the
    bootstrap loop can centralise handling.
    """

    transport = StdioTransport(
        command=config.command,
        args=config.args,
        env=dict(config.env) if config.env else None,
        cwd=config.cwd,
    )
    try:
        async with asyncio.timeout(timeout):
            async with ClientSession(transport) as session:
                tools = await session.list_tools(timeout=timeout)
                return tools, dict(session.server_info)
    except asyncio.TimeoutError:
        raise DiscoveryError(
            config.name, f"timed out after {timeout:.1f}s"
        ) from None
    except RemoteRpcError as exc:
        raise DiscoveryError(
            config.name, f"remote rpc error [{exc.code}] {exc.message}"
        ) from exc
    except (ConnectionError, FileNotFoundError, OSError) as exc:
        raise DiscoveryError(
            config.name, f"transport error: {type(exc).__name__}: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — last-line surface
        log.exception("mcp.bridge.discovery.uncaught: %s", config.name)
        raise DiscoveryError(
            config.name, f"uncaught: {type(exc).__name__}: {exc}"
        ) from exc
