"""Unit tests for the MCP client config registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.mcp.client.registry import (
    ClientRegistry,
    ServerConfig,
    load_servers_file,
)


# ---------------------------------------------------------------------
# ServerConfig.from_dict — happy + validation
# ---------------------------------------------------------------------


def test_from_dict_minimal() -> None:
    cfg = ServerConfig.from_dict("fs", {"command": "npx", "args": ["a", "b"]})
    assert cfg.name == "fs"
    assert cfg.command == "npx"
    assert cfg.args == ("a", "b")
    assert cfg.env == {}
    assert cfg.cwd is None


def test_from_dict_full() -> None:
    cfg = ServerConfig.from_dict(
        "tars",
        {
            "command": "python3",
            "args": ["-m", "backend.mcp"],
            "env": {"TARS_HOME": "/x"},
            "cwd": "/repo",
            "description": "self-hosted TARS MCP",
        },
    )
    assert cfg.cwd == "/repo"
    assert cfg.env == {"TARS_HOME": "/x"}
    assert cfg.description == "self-hosted TARS MCP"


@pytest.mark.parametrize(
    "raw,match",
    [
        ({}, "command"),
        ({"command": ""}, "command"),
        ({"command": "x", "args": "not-a-list"}, "args"),
        ({"command": "x", "args": [1, 2]}, "args"),
        ({"command": "x", "env": {"k": 1}}, "env"),
        ({"command": "x", "cwd": 1}, "cwd"),
        ({"command": "x", "description": 1}, "description"),
    ],
)
def test_from_dict_rejects_malformed(raw, match) -> None:
    with pytest.raises(ValueError, match=match):
        ServerConfig.from_dict("name", raw)


# ---------------------------------------------------------------------
# ClientRegistry — read / list / add / remove
# ---------------------------------------------------------------------


def test_registry_returns_empty_when_file_missing(tmp_path: Path) -> None:
    reg = ClientRegistry(tmp_path / "servers.json")
    assert reg.list() == []
    assert reg.get("anything") is None


def test_registry_parse_failure_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "servers.json"
    p.write_text("not-json{")
    reg = ClientRegistry(p)
    assert reg.list() == []


def test_registry_skips_invalid_entries_logs_others(tmp_path: Path) -> None:
    p = tmp_path / "servers.json"
    p.write_text(
        json.dumps(
            {
                "good": {"command": "ok"},
                "broken": {"args": "no-command"},
            }
        )
    )
    reg = ClientRegistry(p)
    names = [s.name for s in reg.list()]
    assert names == ["good"]


def test_registry_round_trips_add_then_read(tmp_path: Path) -> None:
    reg = ClientRegistry(tmp_path / "servers.json")
    reg.add(ServerConfig(name="fs", command="npx", args=("-y", "fs-server")))
    reg.add(ServerConfig(name="tars", command="python3", args=("-m", "backend.mcp")))
    names = [s.name for s in reg.list()]
    assert names == ["fs", "tars"]
    fs = reg.get("fs")
    assert fs is not None
    assert fs.args == ("-y", "fs-server")


def test_registry_remove_returns_false_for_missing(tmp_path: Path) -> None:
    reg = ClientRegistry(tmp_path / "servers.json")
    reg.add(ServerConfig(name="x", command="c"))
    assert reg.remove("x") is True
    assert reg.remove("x") is False
    assert reg.list() == []


def test_registry_writes_atomically_via_tmp_then_replace(tmp_path: Path) -> None:
    reg = ClientRegistry(tmp_path / "servers.json")
    reg.add(ServerConfig(name="x", command="c"))
    body = json.loads((tmp_path / "servers.json").read_text())
    assert body == {"x": {"command": "c", "args": []}}
    # `*.tmp` cleanup: replace() should rename, not leave the tmp behind.
    assert not (tmp_path / "servers.json.tmp").exists()


# ---------------------------------------------------------------------
# load_servers_file standalone helper
# ---------------------------------------------------------------------


def test_load_servers_file_returns_sorted_list(tmp_path: Path) -> None:
    p = tmp_path / "servers.json"
    p.write_text(
        json.dumps(
            {
                "zeta": {"command": "z"},
                "alpha": {"command": "a"},
            }
        )
    )
    out = load_servers_file(p)
    assert [s.name for s in out] == ["alpha", "zeta"]
