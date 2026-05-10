"""``python -m backend.mcp.client`` — operator CLI.

Useful for inspecting a remote MCP server from the terminal
without writing Python:

    # List configured remote servers
    python -m backend.mcp.client list-servers

    # List tools on one server
    python -m backend.mcp.client list-tools tars-self

    # Call a tool with JSON arguments
    python -m backend.mcp.client call-tool tars-self \
        algotrade.list_recipes '{}'

Output is always JSON (machine-readable). Error envelope is
``{"ok": false, "error": "...", "detail": "..."}`` on stderr
plus exit code 1.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .registry import (
    ClientRegistry,
    ServerConfig,
    get_client_registry,
)
from .session import ClientSession
from .transport import RemoteRpcError, StdioTransport


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tars-mcp-client",
        description=(
            "Inspect + call tools on remote MCP servers configured "
            "in $TARS_HOME/mcp/servers.json."
        ),
    )
    sub = p.add_subparsers(dest="command", metavar="<verb>")

    sub.add_parser("list-servers", help="List configured remote servers.")

    lt = sub.add_parser(
        "list-tools",
        help="Connect to a server, return its tools/list output.",
    )
    lt.add_argument("server", help="Server name from the registry.")

    ct = sub.add_parser(
        "call-tool", help="Connect to a server and invoke one tool."
    )
    ct.add_argument("server")
    ct.add_argument("tool")
    ct.add_argument(
        "arguments",
        nargs="?",
        default="{}",
        help="JSON object for the tool arguments (default: {}).",
    )
    ct.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds (default: 60).",
    )

    pn = sub.add_parser("ping", help="Connect, ping, return latency-ish.")
    pn.add_argument("server")

    return p


def _load_server(name: str) -> ServerConfig | None:
    return get_client_registry().get(name)


def _print(payload: Any, *, file=None) -> None:
    # Resolve `sys.stdout` at call time, not at module-import time —
    # otherwise pytest's `capsys` fixture (which monkeypatches
    # sys.stdout) doesn't see the bytes.
    target = file if file is not None else sys.stdout
    target.write(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    target.write("\n")
    target.flush()


def _err(error: str, detail: str = "") -> int:
    _print({"ok": False, "error": error, "detail": detail}, file=sys.stderr)
    return 1


async def _list_servers() -> int:
    reg = get_client_registry()
    rows = [s.to_dict() for s in reg.list()]
    _print({"ok": True, "servers": rows, "count": len(rows)})
    return 0


async def _list_tools(server_name: str) -> int:
    cfg = _load_server(server_name)
    if cfg is None:
        return _err("server_not_in_registry", server_name)
    transport = StdioTransport(
        command=cfg.command, args=cfg.args, env=cfg.env, cwd=cfg.cwd
    )
    try:
        async with ClientSession(transport) as s:
            tools = await s.list_tools()
            _print(
                {
                    "ok": True,
                    "server": server_name,
                    "server_info": s.server_info,
                    "tools": tools,
                    "count": len(tools),
                }
            )
            return 0
    except (TimeoutError, ConnectionError, RemoteRpcError) as exc:
        return _err(type(exc).__name__, str(exc))


async def _call_tool(
    server_name: str, tool_name: str, raw_args: str, timeout: float
) -> int:
    cfg = _load_server(server_name)
    if cfg is None:
        return _err("server_not_in_registry", server_name)
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError as exc:
        return _err("invalid_arguments_json", str(exc))
    if not isinstance(args, dict):
        return _err("invalid_arguments_type", "must be a JSON object")
    transport = StdioTransport(
        command=cfg.command, args=cfg.args, env=cfg.env, cwd=cfg.cwd
    )
    try:
        async with ClientSession(transport) as s:
            result = await s.call_tool(tool_name, args, timeout=timeout)
            ok = not result.pop("__remote_is_error", False)
            _print({"ok": ok, "server": server_name, "tool": tool_name, "result": result})
            return 0 if ok else 1
    except (TimeoutError, ConnectionError, RemoteRpcError) as exc:
        return _err(type(exc).__name__, str(exc))


async def _ping(server_name: str) -> int:
    cfg = _load_server(server_name)
    if cfg is None:
        return _err("server_not_in_registry", server_name)
    transport = StdioTransport(
        command=cfg.command, args=cfg.args, env=cfg.env, cwd=cfg.cwd
    )
    try:
        import time

        async with ClientSession(transport) as s:
            t0 = time.perf_counter()
            await s.ping()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _print(
                {
                    "ok": True,
                    "server": server_name,
                    "ping_ms": round(elapsed_ms, 3),
                    "server_info": s.server_info,
                }
            )
            return 0
    except (TimeoutError, ConnectionError, RemoteRpcError) as exc:
        return _err(type(exc).__name__, str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    level_name = (os.environ.get("TARS_MCP_CLIENT_LOG_LEVEL") or "WARNING").upper()
    logging.basicConfig(
        stream=sys.stderr,
        level=getattr(logging, level_name, logging.WARNING),
        format="[%(levelname)s] %(name)s — %(message)s",
    )

    if args.command is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        if args.command == "list-servers":
            return asyncio.run(_list_servers())
        if args.command == "list-tools":
            return asyncio.run(_list_tools(args.server))
        if args.command == "call-tool":
            return asyncio.run(
                _call_tool(args.server, args.tool, args.arguments, args.timeout)
            )
        if args.command == "ping":
            return asyncio.run(_ping(args.server))
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
