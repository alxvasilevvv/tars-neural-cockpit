"""File-backed registry of remote MCP servers.

Operators wire up the external servers they want TARS to drive
by editing ``$TARS_HOME/mcp/servers.json``:

    {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem",
                 "/Users/me/Documents"]
      },
      "tars-self": {
        "command": "python3",
        "args": ["-m", "backend.core.mcp"],
        "cwd": "/path/to/tars-neural-cockpit",
        "env": {"TARS_HOME": "/Users/me/.tars"}
      }
    }

Once registered by name, playbooks / agents / the CLI can
address them with that name instead of repeating the full
spawn config.

The registry is **lazily loaded** — the file is re-read on
every ``get`` call. That means an operator can edit it
without restarting TARS and the next ``get`` picks it up.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


log = logging.getLogger(__name__)


def _root() -> Path:
    home = (
        os.environ.get("TARS_HOME")
        or os.environ.get("TARS_ALGOTRADE_HOME")
        or str(Path.home() / ".tars")
    )
    return Path(home).expanduser() / "mcp"


@dataclass(frozen=True)
class ServerConfig:
    """Describes how to spawn one remote MCP server."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "command": self.command,
            "args": list(self.args),
        }
        if self.env:
            out["env"] = dict(self.env)
        if self.cwd:
            out["cwd"] = self.cwd
        if self.description:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, name: str, raw: Mapping[str, Any]) -> "ServerConfig":
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"server {name!r} config must be an object, got {type(raw).__name__}"
            )
        cmd = raw.get("command")
        if not isinstance(cmd, str) or not cmd:
            raise ValueError(
                f"server {name!r} missing required 'command' string"
            )
        args = raw.get("args") or []
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(
                f"server {name!r} 'args' must be a list of strings"
            )
        env_raw = raw.get("env") or {}
        if not isinstance(env_raw, Mapping) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in env_raw.items()
        ):
            raise ValueError(
                f"server {name!r} 'env' must be a string→string object"
            )
        cwd = raw.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"server {name!r} 'cwd' must be a string")
        description = raw.get("description") or ""
        if not isinstance(description, str):
            raise ValueError(f"server {name!r} 'description' must be a string")
        return cls(
            name=name,
            command=cmd,
            args=tuple(args),
            env=dict(env_raw),
            cwd=cwd,
            description=description,
        )


@dataclass
class ClientRegistry:
    """In-memory map ``server_name → ServerConfig``. Always
    re-reads the on-disk roster file to pick up live edits."""

    path: Path

    def list(self) -> list[ServerConfig]:
        data = self._read()
        return sorted(data.values(), key=lambda s: s.name)

    def get(self, name: str) -> ServerConfig | None:
        return self._read().get(name)

    def add(self, config: ServerConfig) -> None:
        data = self._read()
        data[config.name] = config
        self._write(data)

    def remove(self, name: str) -> bool:
        data = self._read()
        if name not in data:
            return False
        del data[name]
        self._write(data)
        return True

    def _read(self) -> dict[str, ServerConfig]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.warning(
                "mcp.client.registry.parse_failed: %s — returning empty",
                exc,
            )
            return {}
        if not isinstance(raw, Mapping):
            log.warning("mcp.client.registry.bad_root: not an object")
            return {}
        out: dict[str, ServerConfig] = {}
        for name, body in raw.items():
            try:
                out[name] = ServerConfig.from_dict(name, body)
            except ValueError as exc:
                log.warning("mcp.client.registry.skip %s: %s", name, exc)
        return out

    def _write(self, data: Mapping[str, ServerConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            name: {
                "command": cfg.command,
                "args": list(cfg.args),
                **({"env": dict(cfg.env)} if cfg.env else {}),
                **({"cwd": cfg.cwd} if cfg.cwd else {}),
                **({"description": cfg.description} if cfg.description else {}),
            }
            for name, cfg in sorted(data.items())
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self.path)


def load_servers_file(path: Path | str) -> list[ServerConfig]:
    """Standalone helper — read a servers.json file from any path
    and return the parsed list. Used by tests + the CLI for
    one-shot inspection without going through the singleton."""

    p = Path(path).expanduser()
    return sorted(ClientRegistry(p)._read().values(), key=lambda s: s.name)


_SINGLETON: ClientRegistry | None = None


def get_client_registry() -> ClientRegistry:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ClientRegistry(_root() / "servers.json")
    return _SINGLETON


def reset_client_registry() -> None:
    """Test helper — clear the singleton so the next ``get_*``
    call re-reads ``$TARS_HOME``."""

    global _SINGLETON
    _SINGLETON = None
