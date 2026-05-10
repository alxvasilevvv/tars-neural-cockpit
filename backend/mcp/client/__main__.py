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
            "Inspect + call tools on remote MCP servers configured in "
            "$TARS_HOME/mcp/servers.json. Also manage server config "
            "and the M5 bridge that auto-registers remote MCP tools "
            "as TARS DomainPack actions."
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

    # ------------------------------------------------------------------
    # servers add / remove / show — live-edit servers.json
    # ------------------------------------------------------------------

    sa = sub.add_parser(
        "servers-add",
        help="Add or overwrite a remote server entry in servers.json.",
    )
    sa.add_argument("name")
    sa.add_argument("--command", required=True, dest="cmd")
    sa.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Append one CLI argument (repeat for each).",
    )
    sa.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Append one env var (repeat for each).",
    )
    sa.add_argument("--cwd", default=None)
    sa.add_argument("--description", default="")

    sr = sub.add_parser(
        "servers-remove",
        help="Remove a remote server entry from servers.json.",
    )
    sr.add_argument("name")

    ss = sub.add_parser(
        "servers-show",
        help="Print the full ServerConfig for one entry.",
    )
    ss.add_argument("name")

    # ------------------------------------------------------------------
    # bridge bootstrap / refresh / list / unregister / cache
    # ------------------------------------------------------------------

    bb = sub.add_parser(
        "bridge-bootstrap",
        help=(
            "Discover or cache-hit every configured server, register "
            "each as a `mcp-<server>` DomainPack."
        ),
    )
    bb.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-discovery even when a fresh cache exists.",
    )
    bb.add_argument(
        "--only",
        action="append",
        default=None,
        help="Restrict to a subset of server names (repeat).",
    )
    bb.add_argument(
        "--discovery-timeout",
        type=float,
        default=10.0,
        help="Per-server discovery timeout in seconds (default: 10).",
    )

    sub.add_parser(
        "bridge-list",
        help="List currently registered `mcp-<server>` packs.",
    )

    sub.add_parser(
        "bridge-unregister",
        help="Remove every `mcp-<server>` pack from the registry.",
    )

    bcl = sub.add_parser(
        "bridge-cache-list",
        help="List cached tool descriptors on disk.",
    )
    bcl.add_argument(
        "--show-tools",
        action="store_true",
        help="Include the per-server tool count in the output.",
    )

    bcd = sub.add_parser(
        "bridge-cache-delete",
        help="Delete the cached tool descriptors for one server.",
    )
    bcd.add_argument("name")

    bpb = sub.add_parser(
        "bridge-pool-bench",
        help=(
            "Boot the bridge with a SessionPool, call one tool N "
            "times, report cold/warm latency. Wave M6 — handy "
            "for sizing the pool benefit on real servers."
        ),
    )
    bpb.add_argument("server", help="Configured server name to benchmark.")
    bpb.add_argument(
        "tool",
        help=(
            "Bridged action ID (e.g. mcp-fs.read_file). Use "
            "bridge-list to see what's registered."
        ),
    )
    bpb.add_argument(
        "--arguments",
        default="{}",
        help="JSON object passed to the bridged action handler.",
    )
    bpb.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="How many warm calls to time after the cold call.",
    )

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
        if args.command == "servers-add":
            return _servers_add(args)
        if args.command == "servers-remove":
            return _servers_remove(args.name)
        if args.command == "servers-show":
            return _servers_show(args.name)
        if args.command == "bridge-bootstrap":
            return _bridge_bootstrap(
                refresh=args.refresh,
                only=args.only,
                discovery_timeout=args.discovery_timeout,
            )
        if args.command == "bridge-list":
            return _bridge_list()
        if args.command == "bridge-unregister":
            return _bridge_unregister()
        if args.command == "bridge-cache-list":
            return _bridge_cache_list(show_tools=args.show_tools)
        if args.command == "bridge-cache-delete":
            return _bridge_cache_delete(args.name)
        if args.command == "bridge-pool-bench":
            return _bridge_pool_bench(
                server=args.server,
                tool=args.tool,
                arguments=args.arguments,
                iterations=args.iterations,
            )
    except KeyboardInterrupt:
        return 130
    return 2


# ---------------------------------------------------------------------
# servers-add / servers-remove / servers-show
# ---------------------------------------------------------------------


def _servers_add(args) -> int:
    env: dict[str, str] = {}
    for raw in args.env:
        if "=" not in raw:
            return _err("invalid_env_pair", f"missing '=': {raw!r}")
        k, _, v = raw.partition("=")
        if not k:
            return _err("invalid_env_pair", f"empty key: {raw!r}")
        env[k] = v
    cfg = ServerConfig(
        name=args.name,
        command=args.cmd,
        args=tuple(args.arg),
        env=env,
        cwd=args.cwd,
        description=args.description,
    )
    get_client_registry().add(cfg)
    _print({"ok": True, "added": cfg.to_dict()})
    return 0


def _servers_remove(name: str) -> int:
    removed = get_client_registry().remove(name)
    if not removed:
        return _err("server_not_in_registry", name)
    _print({"ok": True, "removed": name})
    return 0


def _servers_show(name: str) -> int:
    cfg = get_client_registry().get(name)
    if cfg is None:
        return _err("server_not_in_registry", name)
    _print({"ok": True, "server": cfg.to_dict()})
    return 0


# ---------------------------------------------------------------------
# bridge-* verbs
# ---------------------------------------------------------------------


def _bridge_bootstrap(
    *, refresh: bool, only: list[str] | None, discovery_timeout: float
) -> int:
    from backend.core.mcp_bridge import boot_mcp_bridges

    result = boot_mcp_bridges(
        refresh=refresh,
        only=only,
        discovery_timeout=discovery_timeout,
    )
    _print({"ok": True, "result": result.to_dict()})
    return 0 if not result.failed else 1


def _bridge_list() -> int:
    from backend.core.domains.registry import all_packs

    packs = [
        {
            "slug": p.manifest.slug,
            "name": p.manifest.name,
            "actions": [a.id for a in p.actions()],
        }
        for p in all_packs()
        if p.manifest.slug.startswith("mcp-")
    ]
    _print({"ok": True, "packs": packs, "count": len(packs)})
    return 0


def _bridge_unregister() -> int:
    from backend.core.mcp_bridge import unregister_bridges

    removed = unregister_bridges()
    _print({"ok": True, "removed": removed})
    return 0


def _bridge_cache_list(*, show_tools: bool) -> int:
    from backend.core.mcp_bridge import ToolCache
    from backend.core.mcp_bridge.bootstrap import _default_cache_root

    cache = ToolCache(_default_cache_root())
    rows: list[dict[str, Any]] = []
    for name in cache.list_servers():
        entry = cache.read(name)
        if entry is None:
            rows.append({"server": name, "status": "unreadable"})
            continue
        row: dict[str, Any] = {
            "server": name,
            "discovered_at": entry.discovered_at,
            "age_seconds": round(entry.age_seconds(), 1),
            "fresh": entry.is_fresh(),
        }
        if show_tools:
            row["tool_count"] = len(entry.tools)
            row["tool_names"] = [t.get("name") for t in entry.tools]
        rows.append(row)
    _print({"ok": True, "cache": rows, "count": len(rows)})
    return 0


def _bridge_cache_delete(name: str) -> int:
    from backend.core.mcp_bridge import ToolCache
    from backend.core.mcp_bridge.bootstrap import _default_cache_root

    deleted = ToolCache(_default_cache_root()).delete(name)
    if not deleted:
        return _err("cache_entry_not_found", name)
    _print({"ok": True, "deleted": name})
    return 0


def _bridge_pool_bench(
    *, server: str, tool: str, arguments: str, iterations: int
) -> int:
    """Bench one bridged tool: cold call (subprocess spawn) vs
    warm calls (pooled session reuse). Useful for sizing the
    Wave M6 benefit on real remote servers."""

    import time

    try:
        parsed_args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return _err("invalid_arguments_json", str(exc))
    if not isinstance(parsed_args, dict):
        return _err("invalid_arguments_type", "must be a JSON object")

    cfg = get_client_registry().get(server)
    if cfg is None:
        return _err("server_not_in_registry", server)

    from backend.core.domains.registry import get_pack
    from backend.core.mcp_bridge import (
        SessionPool,
        aboot_mcp_bridges,
        unregister_bridges,
    )

    async def go() -> dict[str, Any]:
        pool = SessionPool()
        result = await aboot_mcp_bridges(
            client_registry=get_client_registry(),
            pool=pool,
            only=[server],
        )
        if result.failed:
            await pool.close_all()
            unregister_bridges()
            raise RuntimeError(
                f"bridge boot failed: {result.failed[0]}"
            )
        slug = f"mcp-{server}"
        pack = get_pack(slug)
        action_id = tool.split(".")[-1] if "." in tool else tool
        action = next((a for a in pack.actions() if a.id == action_id), None)
        if action is None:
            await pool.close_all()
            unregister_bridges()
            raise RuntimeError(
                f"action {action_id!r} not in {slug}; available: "
                f"{[a.id for a in pack.actions()]}"
            )

        try:
            t0 = time.perf_counter()
            cold_payload = await action.handler(parsed_args)
            cold_ms = (time.perf_counter() - t0) * 1000

            warm_ms: list[float] = []
            for _ in range(max(1, iterations)):
                t = time.perf_counter()
                await action.handler(parsed_args)
                warm_ms.append((time.perf_counter() - t) * 1000)

            avg_warm = sum(warm_ms) / len(warm_ms)
            return {
                "ok": True,
                "server": server,
                "tool": action_id,
                "cold_ms": round(cold_ms, 2),
                "warm_calls": [round(t, 2) for t in warm_ms],
                "warm_avg_ms": round(avg_warm, 2),
                "speedup_vs_cold": (
                    round(cold_ms / avg_warm, 1) if avg_warm > 0 else None
                ),
                "cold_payload_ok": bool(cold_payload.get("ok")),
                "pool_stats": pool.stats(),
            }
        finally:
            await pool.close_all()
            unregister_bridges()

    try:
        payload = asyncio.run(go())
    except RuntimeError as exc:
        return _err("bench_failed", str(exc))
    _print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
