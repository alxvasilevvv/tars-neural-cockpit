"""On-disk cache of remote MCP tool listings.

Discovery is expensive — it spawns a subprocess and runs a
full handshake just to learn the tool catalog. Most remote
servers' tool lists are stable across runs (filesystem
server: same 5 verbs for months, GitHub server: same 20
verbs). Cache the descriptors so the second + boot is
instant.

Cache files live at ``$TARS_HOME/mcp/cache/<server>.json``.
Schema:

    {
      "server": "filesystem",
      "discovered_at": "2026-05-10T22:00:00Z",
      "server_info": {"name": "...", "version": "..."},
      "tools": [<tools/list dicts>]
    }

A cache entry is **fresh** for ``max_age_seconds`` (default
24h). Anything older triggers a re-discovery on next boot,
falling back to the cached entry if discovery fails (so a
temporarily-down server doesn't strand the bridge).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)

DEFAULT_MAX_AGE_SECONDS = 86_400  # 1 day


@dataclass(frozen=True)
class CachedDiscovery:
    server_name: str
    discovered_at: str  # ISO-8601, UTC
    server_info: dict[str, Any]
    tools: list[dict[str, Any]]

    def age_seconds(self, *, now: float | None = None) -> float:
        try:
            ts = datetime.fromisoformat(self.discovered_at.replace("Z", "+00:00"))
        except ValueError:
            return float("inf")
        now_ts = now if now is not None else time.time()
        return max(0.0, now_ts - ts.timestamp())

    def is_fresh(self, *, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> bool:
        return self.age_seconds() <= max_age_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server_name,
            "discovered_at": self.discovered_at,
            "server_info": dict(self.server_info),
            "tools": list(self.tools),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CachedDiscovery":
        if not isinstance(raw, dict):
            raise ValueError("cache entry must be a JSON object")
        for key in ("server", "discovered_at", "tools"):
            if key not in raw:
                raise ValueError(f"cache entry missing {key!r}")
        if not isinstance(raw.get("tools"), list):
            raise ValueError("cache entry 'tools' must be a list")
        return cls(
            server_name=str(raw["server"]),
            discovered_at=str(raw["discovered_at"]),
            server_info=dict(raw.get("server_info") or {}),
            tools=list(raw["tools"]),
        )


@dataclass
class ToolCache:
    """File-backed cache. ``root`` is the directory that
    contains one ``<server>.json`` file per cached server."""

    root: Path

    def _path(self, server_name: str) -> Path:
        # Normalise server names so a slug containing "/" or
        # ".." can never escape the cache root.
        safe = "".join(
            c if c.isalnum() or c in {"-", "_"} else "_" for c in server_name
        )
        return self.root / f"{safe}.json"

    def read(self, server_name: str) -> CachedDiscovery | None:
        path = self._path(server_name)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.warning(
                "mcp.bridge.cache.parse_failed: %s — %s (treating as miss)",
                path,
                exc,
            )
            return None
        try:
            return CachedDiscovery.from_dict(raw)
        except ValueError as exc:
            log.warning(
                "mcp.bridge.cache.invalid_entry: %s — %s", path, exc
            )
            return None

    def write(
        self,
        server_name: str,
        *,
        server_info: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> CachedDiscovery:
        entry = CachedDiscovery(
            server_name=server_name,
            discovered_at=datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            server_info=dict(server_info),
            tools=list(tools),
        )
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(server_name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(entry.to_dict(), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(path)
        log.info(
            "mcp.bridge.cache.write %s tools=%d", server_name, len(tools)
        )
        return entry

    def delete(self, server_name: str) -> bool:
        path = self._path(server_name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_servers(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.stem for p in self.root.glob("*.json"))
