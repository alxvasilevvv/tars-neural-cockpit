"""Unit tests for the MCP bridge's tool cache."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.core.mcp_bridge.cache import (
    DEFAULT_MAX_AGE_SECONDS,
    CachedDiscovery,
    ToolCache,
)


# ---------------------------------------------------------------------
# CachedDiscovery dataclass
# ---------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def test_cached_discovery_to_from_dict_round_trip() -> None:
    entry = CachedDiscovery(
        server_name="x",
        discovered_at=_now_iso(),
        server_info={"name": "x", "version": "1"},
        tools=[{"name": "t", "description": "d"}],
    )
    body = entry.to_dict()
    restored = CachedDiscovery.from_dict(body)
    assert restored == entry


def test_cached_discovery_from_dict_rejects_missing_keys() -> None:
    with pytest.raises(ValueError, match="server"):
        CachedDiscovery.from_dict({"discovered_at": "x", "tools": []})
    with pytest.raises(ValueError, match="discovered_at"):
        CachedDiscovery.from_dict({"server": "x", "tools": []})
    with pytest.raises(ValueError, match="tools"):
        CachedDiscovery.from_dict({"server": "x", "discovered_at": "x"})


def test_cached_discovery_rejects_non_list_tools() -> None:
    with pytest.raises(ValueError, match="list"):
        CachedDiscovery.from_dict(
            {"server": "x", "discovered_at": "x", "tools": "nope"}
        )


def test_cached_discovery_age_seconds_returns_inf_for_bad_timestamp() -> None:
    entry = CachedDiscovery(
        server_name="x",
        discovered_at="not-a-date",
        server_info={},
        tools=[],
    )
    assert entry.age_seconds() == float("inf")


def test_cached_discovery_is_fresh() -> None:
    fresh = CachedDiscovery(
        server_name="x",
        discovered_at=_now_iso(),
        server_info={},
        tools=[],
    )
    assert fresh.is_fresh()
    assert fresh.is_fresh(max_age_seconds=10)

    very_old = CachedDiscovery(
        server_name="x",
        discovered_at="2020-01-01T00:00:00Z",
        server_info={},
        tools=[],
    )
    assert not very_old.is_fresh()


# ---------------------------------------------------------------------
# ToolCache file ops
# ---------------------------------------------------------------------


def test_cache_read_returns_none_when_missing(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path)
    assert cache.read("nope") is None


def test_cache_write_then_read_round_trip(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path)
    entry = cache.write(
        "filesystem",
        server_info={"name": "fs", "version": "0"},
        tools=[
            {"name": "read_file", "description": "r"},
            {"name": "write_file", "description": "w"},
        ],
    )
    assert entry.server_name == "filesystem"
    assert entry.tools[0]["name"] == "read_file"

    fresh = cache.read("filesystem")
    assert fresh is not None
    assert fresh.tools == entry.tools
    assert fresh.server_info == {"name": "fs", "version": "0"}


def test_cache_atomic_write_uses_tmp_then_rename(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path)
    cache.write("x", server_info={}, tools=[])
    assert (tmp_path / "x.json").exists()
    assert not (tmp_path / "x.json.tmp").exists()


def test_cache_sanitises_server_name_to_safe_filename(tmp_path: Path) -> None:
    """A malicious server name must not escape the cache root."""

    cache = ToolCache(tmp_path)
    cache.write("../../etc/passwd", server_info={}, tools=[])
    # Anything outside the cache root would be a security bug.
    files = list(tmp_path.iterdir())
    assert all(f.parent == tmp_path for f in files)
    assert all("/" not in f.name and ".." not in f.name for f in files)


def test_cache_read_handles_invalid_json_as_miss(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("not-json{")
    cache = ToolCache(tmp_path)
    assert cache.read("broken") is None


def test_cache_read_handles_invalid_schema_as_miss(tmp_path: Path) -> None:
    (tmp_path / "shape.json").write_text(json.dumps({"server": "x"}))
    cache = ToolCache(tmp_path)
    assert cache.read("shape") is None


def test_cache_delete(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path)
    cache.write("x", server_info={}, tools=[])
    assert cache.delete("x") is True
    assert cache.delete("x") is False
    assert cache.read("x") is None


def test_cache_list_servers_returns_sorted_stems(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path)
    cache.write("zeta", server_info={}, tools=[])
    cache.write("alpha", server_info={}, tools=[])
    assert cache.list_servers() == ["alpha", "zeta"]


def test_cache_list_servers_returns_empty_when_root_missing(tmp_path: Path) -> None:
    cache = ToolCache(tmp_path / "does-not-exist-yet")
    assert cache.list_servers() == []


def test_default_max_age_is_one_day() -> None:
    assert DEFAULT_MAX_AGE_SECONDS == 86_400
