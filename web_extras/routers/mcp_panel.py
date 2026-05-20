"""HTTP surface for the desktop MCP-servers panel (Wave 238).

Companion to ``backend/core/mcp/`` (W150 — TARS's own MCP server that
exposes native skills as tools).  This router is the *other side*: a
small registry of **external** MCP servers the user wants TARS to be
aware of (Cursor-style panel in Settings → MCP servers).

Endpoints (all under ``/api/mcp``):

* ``GET    /servers``               — list registered servers
* ``POST   /servers``               — add a new server, returns it
* ``PUT    /servers/{id}``          — edit / toggle a server
* ``DELETE /servers/{id}``          — remove a server
* ``GET    /servers/{id}/status``   — live status snapshot

Persisted at ``~/.tars/mcp_servers.json`` as an array of records.  If
the file is missing on first read we auto-create it with one example
"anthropic-filesystem" entry left disabled — the user can flip the
toggle in Settings.

Spawn logic
-----------

W150 ships a real MCP **server** (it speaks JSON-RPC over stdio), but
not a *client* that spawns third-party MCP processes.  Rather than
half-implement a supervisor here, we record ``status = "enabled"`` /
``"stopped"`` / ``"error"`` as a state machine and leave actual
process supervision to a future wave (the JSON schema already has the
required fields).  This keeps the panel honest: the toggle changes
config, not running PIDs.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException


router = APIRouter(prefix="/api/mcp", tags=["mcp-panel"])


# --- Config storage ---


def _config_path() -> Path:
    """Resolve ``~/.tars/mcp_servers.json`` honouring ``$HOME`` overrides."""

    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".tars" / "mcp_servers.json"


def _example_seed() -> list:
    """Single inert example record used on first run."""

    return [
        {
            "id": str(uuid.uuid4()),
            "name": "anthropic-filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "~/Documents"],
            "env": {},
            "enabled": False,
            "status": "stopped",
            "last_seen": None,
            "error": None,
            "created_at": int(time.time()),
        }
    ]


def _read_servers() -> list:
    """Load + auto-seed.  Always returns a list (never raises on bad JSON)."""

    path = _config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        seed = _example_seed()
        path.write_text(json.dumps(seed, indent=2), encoding="utf-8")
        return seed

    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    except Exception:
        raw = []

    if not isinstance(raw, list):
        raw = []
    return raw


def _write_servers(rows: list) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


# --- Serialisation ---


def _public_view(row: dict) -> dict:
    """Public projection — never leaks env values, only key names."""

    env = row.get("env") or {}
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "command": row.get("command"),
        "args": list(row.get("args") or []),
        "env_keys_set": sorted(env.keys()) if isinstance(env, dict) else [],
        "enabled": bool(row.get("enabled", False)),
        "status": row.get("status") or ("enabled" if row.get("enabled") else "stopped"),
        "last_seen": row.get("last_seen"),
        "error": row.get("error"),
    }


def _find(rows: list, server_id: str):
    for r in rows:
        if r.get("id") == server_id:
            return r
    return None


# --- Endpoints ---


@router.get("/servers")
async def list_servers() -> list:
    rows = _read_servers()
    return [_public_view(r) for r in rows]


@router.post("/servers")
async def add_server(payload: dict = Body(default_factory=dict)) -> dict:
    name = (payload.get("name") or "").strip()
    command = (payload.get("command") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not command:
        raise HTTPException(status_code=400, detail="command is required")

    args = payload.get("args") or []
    if not isinstance(args, list):
        raise HTTPException(status_code=400, detail="args must be a list")
    env = payload.get("env") or {}
    if not isinstance(env, dict):
        raise HTTPException(status_code=400, detail="env must be an object")

    rows = _read_servers()
    new_row = {
        "id": str(uuid.uuid4()),
        "name": name,
        "command": command,
        "args": [str(a) for a in args],
        "env": {str(k): str(v) for k, v in env.items()},
        "enabled": bool(payload.get("enabled", False)),
        "status": "stopped",
        "last_seen": None,
        "error": None,
        "created_at": int(time.time()),
    }
    rows.append(new_row)
    _write_servers(rows)
    return _public_view(new_row)


@router.put("/servers/{server_id}")
async def update_server(server_id: str, payload: dict = Body(default_factory=dict)) -> dict:
    rows = _read_servers()
    row = _find(rows, server_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"server {server_id} not found")

    if "name" in payload and isinstance(payload["name"], str) and payload["name"].strip():
        row["name"] = payload["name"].strip()
    if "command" in payload and isinstance(payload["command"], str) and payload["command"].strip():
        row["command"] = payload["command"].strip()
    if "args" in payload:
        if not isinstance(payload["args"], list):
            raise HTTPException(status_code=400, detail="args must be a list")
        row["args"] = [str(a) for a in payload["args"]]
    if "env" in payload:
        if not isinstance(payload["env"], dict):
            raise HTTPException(status_code=400, detail="env must be an object")
        row["env"] = {str(k): str(v) for k, v in payload["env"].items()}

    if "enabled" in payload:
        prev = bool(row.get("enabled", False))
        new = bool(payload["enabled"])
        row["enabled"] = new
        if new and not prev:
            row["status"] = "enabled"
            row["last_seen"] = int(time.time())
            row["error"] = None
        elif (not new) and prev:
            row["status"] = "stopped"

    _write_servers(rows)
    return _public_view(row)


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str) -> dict:
    rows = _read_servers()
    keep = [r for r in rows if r.get("id") != server_id]
    if len(keep) == len(rows):
        raise HTTPException(status_code=404, detail=f"server {server_id} not found")
    _write_servers(keep)
    return {"ok": True, "id": server_id}


@router.get("/bridge/status")
async def bridge_status() -> dict:
    """Consolidated MCP bridge health (W310 MCP rewrite)."""

    try:
        from backend.core.mcp.bridge_pkg import get_default_pool  # type: ignore

        pool = get_default_pool()
        return {"ok": True, "pool": pool.stats()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:240]}


@router.get("/pool/stats")
async def pool_stats() -> dict:
    """Session pool snapshot for operators."""

    try:
        from backend.core.mcp.bridge_pkg.pool import get_default_pool  # type: ignore

        pool = get_default_pool()
        stats = pool.stats()
        return {"ok": True, **stats}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:240]}


@router.get("/servers/{server_id}/status")
async def server_status(server_id: str) -> dict:
    rows = _read_servers()
    row = _find(rows, server_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"server {server_id} not found")

    enabled = bool(row.get("enabled", False))
    last_seen = row.get("last_seen")
    status = row.get("status") or ("enabled" if enabled else "stopped")

    surfaced = status
    if row.get("error"):
        surfaced = "error"
    elif status == "enabled":
        surfaced = "running"
    elif not enabled:
        surfaced = "stopped"

    uptime_sec = None
    if surfaced == "running" and isinstance(last_seen, (int, float)):
        uptime_sec = max(0, int(time.time() - int(last_seen)))

    return {
        "id": server_id,
        "status": surfaced,
        "uptime_sec": uptime_sec,
        "last_message_at": last_seen,
        "error": row.get("error"),
    }
