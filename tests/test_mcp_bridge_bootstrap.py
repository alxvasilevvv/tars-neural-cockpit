"""End-to-end tests for the bootstrap loop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from backend.core.domains.registry import _REGISTRY, get_pack
from backend.core.mcp_bridge import (
    BridgeBootResult,
    ToolCache,
    boot_mcp_bridges,
    unregister_bridges,
)
from backend.mcp.client.registry import ClientRegistry, ServerConfig


@pytest.fixture
def isolated_registry(tmp_path: Path):
    """Provide a fresh ClientRegistry + ToolCache rooted at
    ``tmp_path``. Wipes any pre-existing bridge packs from
    the global registry on entry + exit so test ordering
    can never leak."""

    unregister_bridges()
    yield (
        ClientRegistry(tmp_path / "servers.json"),
        ToolCache(tmp_path / "cache"),
        tmp_path,
    )
    unregister_bridges()


def _add_mock(reg: ClientRegistry, name: str = "mock", **env: str) -> None:
    reg.add(
        ServerConfig(
            name=name,
            command=sys.executable,
            args=("-m", "tests.mcp_fixtures.mock_mcp_server"),
            env=env,
        )
    )


# ---------------------------------------------------------------------
# Empty registry
# ---------------------------------------------------------------------


def test_boot_returns_empty_result_when_no_servers(isolated_registry) -> None:
    reg, cache, _ = isolated_registry
    result = boot_mcp_bridges(client_registry=reg, cache=cache)
    assert isinstance(result, BridgeBootResult)
    assert result.registered == ()
    assert result.failed == ()
    assert result.cache_hits == ()


# ---------------------------------------------------------------------
# Happy path — discovery + cache write + global registry effect
# ---------------------------------------------------------------------


def test_boot_discovers_and_registers_bridge_pack(isolated_registry) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg)
    result = boot_mcp_bridges(client_registry=reg, cache=cache)

    assert len(result.registered) == 1
    pack = result.registered[0]
    assert pack.manifest.slug == "mcp-mock"
    assert result.discovered == ("mock",)
    assert result.cache_hits == ()

    same = get_pack("mcp-mock")
    assert same is pack
    actions = sorted(a.id for a in pack.actions())
    assert actions == ["boom", "echo"]


def test_boot_writes_cache_after_discovery(isolated_registry) -> None:
    reg, cache, tmp = isolated_registry
    _add_mock(reg)
    boot_mcp_bridges(client_registry=reg, cache=cache)
    assert (tmp / "cache" / "mock.json").exists()


# ---------------------------------------------------------------------
# Cache hit on second boot
# ---------------------------------------------------------------------


def test_second_boot_hits_cache(isolated_registry) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg)
    boot_mcp_bridges(client_registry=reg, cache=cache)
    unregister_bridges()
    result2 = boot_mcp_bridges(client_registry=reg, cache=cache)
    assert result2.cache_hits == ("mock",)
    assert result2.discovered == ()
    assert len(result2.registered) == 1


def test_refresh_forces_rediscovery_even_with_fresh_cache(
    isolated_registry,
) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg)
    boot_mcp_bridges(client_registry=reg, cache=cache)
    unregister_bridges()
    result = boot_mcp_bridges(client_registry=reg, cache=cache, refresh=True)
    assert result.discovered == ("mock",)
    assert result.cache_hits == ()


# ---------------------------------------------------------------------
# Failure path — discovery fails AND no cache → server skipped
# ---------------------------------------------------------------------


def test_failed_discovery_without_cache_appends_to_failed(
    isolated_registry,
) -> None:
    reg, cache, _ = isolated_registry
    reg.add(
        ServerConfig(name="ghost", command="/no/such/binary-please")
    )
    result = boot_mcp_bridges(
        client_registry=reg, cache=cache, discovery_timeout=2.0
    )
    assert result.registered == ()
    assert result.failed
    failed_name, failed_reason = result.failed[0]
    assert failed_name == "ghost"
    assert "transport" in failed_reason
    assert get_pack("mcp-ghost") is None


# ---------------------------------------------------------------------
# Failure with stale cache → falls back to cached descriptors
# ---------------------------------------------------------------------


def test_discovery_failure_falls_back_to_stale_cache(
    isolated_registry, tmp_path
) -> None:
    reg, cache, _ = isolated_registry
    # Pre-seed a (stale) cache entry the bootstrap can fall back to.
    cache.write(
        "ghost",
        server_info={"name": "ghost", "version": "0"},
        tools=[
            {
                "name": "echo",
                "description": "stale entry",
                "inputSchema": {},
            }
        ],
    )
    # Manually backdate the on-disk timestamp so it's NOT fresh,
    # forcing the discovery attempt before fallback.
    cache_file = tmp_path / "cache" / "ghost.json"
    body = json.loads(cache_file.read_text())
    body["discovered_at"] = "2020-01-01T00:00:00Z"
    cache_file.write_text(json.dumps(body))

    reg.add(
        ServerConfig(name="ghost", command="/no/such/binary-please")
    )
    result = boot_mcp_bridges(
        client_registry=reg, cache=cache, discovery_timeout=2.0
    )
    assert len(result.registered) == 1
    assert result.cache_hits == ("ghost",)  # fell back even though stale
    assert result.failed == ()


# ---------------------------------------------------------------------
# `only=` restrictor
# ---------------------------------------------------------------------


def test_only_filter_restricts_to_named_servers(isolated_registry) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg, name="mock_a")
    _add_mock(reg, name="mock_b")
    result = boot_mcp_bridges(
        client_registry=reg, cache=cache, only=["mock_a"]
    )
    slugs = [p.manifest.slug for p in result.registered]
    assert slugs == ["mcp-mock_a"]


# ---------------------------------------------------------------------
# Empty tool list → skipped, not failed
# ---------------------------------------------------------------------


def test_server_with_no_tools_is_skipped(isolated_registry, tmp_path) -> None:
    reg, cache, _ = isolated_registry
    # Pre-seed an empty fresh cache entry so discovery doesn't run.
    cache.write("empty", server_info={"name": "empty"}, tools=[])
    reg.add(ServerConfig(name="empty", command="x"))
    result = boot_mcp_bridges(client_registry=reg, cache=cache)
    assert result.registered == ()
    assert any("empty_tool_list" in r for _, r in result.skipped)


# ---------------------------------------------------------------------
# unregister_bridges removes only mcp-* packs
# ---------------------------------------------------------------------


def test_unregister_bridges_only_touches_mcp_prefixed_slugs(
    isolated_registry,
) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg)
    boot_mcp_bridges(client_registry=reg, cache=cache)
    snapshot_before = set(_REGISTRY.keys())
    removed = unregister_bridges()
    snapshot_after = set(_REGISTRY.keys())
    diff = snapshot_before - snapshot_after
    assert removed == 1
    assert diff == {"mcp-mock"}
    assert all(not s.startswith("mcp-") for s in snapshot_after)


# ---------------------------------------------------------------------
# Boot result serialisation
# ---------------------------------------------------------------------


def test_boot_result_to_dict_shape(isolated_registry) -> None:
    reg, cache, _ = isolated_registry
    _add_mock(reg)
    result = boot_mcp_bridges(client_registry=reg, cache=cache)
    body = result.to_dict()
    assert body["registered"] == ["mcp-mock"]
    assert body["discovered"] == ["mock"]
    assert body["total"] == 1
    assert body["failed"] == []
