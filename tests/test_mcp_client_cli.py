"""CLI entry tests for the MCP client.

Drive ``main(argv)`` directly via capsys. Server-touching
verbs (`list-tools`, `call-tool`, `ping`) point at a
temporary ``servers.json`` whose entry spawns the local mock
server, so we get end-to-end coverage of the registry +
session integration without touching the real
``$TARS_HOME``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from backend.mcp.client.__main__ import main
from backend.mcp.client import reset_client_registry


@pytest.fixture
def isolated_registry(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("TARS_HOME", str(tmp_path))
    monkeypatch.setenv("TARS_ALGOTRADE_HOME", str(tmp_path))
    reset_client_registry()
    yield tmp_path
    reset_client_registry()


def _seed_mock_server(home: Path) -> None:
    cfg_dir = home / "mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "servers.json").write_text(
        json.dumps(
            {
                "mock": {
                    "command": sys.executable,
                    "args": ["-m", "tests.mcp_fixtures.mock_mcp_server"],
                    "description": "in-test mock",
                }
            }
        )
    )


# ---------------------------------------------------------------------
# Parser / no-command behaviour
# ---------------------------------------------------------------------


def test_no_command_prints_help_and_returns_2(capsys, isolated_registry) -> None:
    rc = main([])
    assert rc == 2
    err = capsys.readouterr().err
    assert "tars-mcp-client" in err


# ---------------------------------------------------------------------
# list-servers
# ---------------------------------------------------------------------


def test_list_servers_empty_registry(capsys, isolated_registry) -> None:
    rc = main(["list-servers"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "servers": [], "count": 0}


def test_list_servers_one_entry(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["list-servers"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["servers"][0]["name"] == "mock"
    assert out["servers"][0]["command"] == sys.executable


# ---------------------------------------------------------------------
# list-tools
# ---------------------------------------------------------------------


def test_list_tools_unknown_server_returns_rc1(capsys, isolated_registry) -> None:
    rc = main(["list-tools", "ghost"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "server_not_in_registry"


def test_list_tools_against_mock_server(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["list-tools", "mock"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["server_info"]["name"] == "mock-mcp"
    names = sorted(t["name"] for t in out["tools"])
    assert names == ["boom", "echo"]


# ---------------------------------------------------------------------
# call-tool
# ---------------------------------------------------------------------


def test_call_tool_happy_path(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["call-tool", "mock", "echo", '{"value": "hi"}'])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert out["result"]["echo"] == {"value": "hi"}


def test_call_tool_remote_error_returns_rc1(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["call-tool", "mock", "boom", "{}"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["ok"] is False
    assert out["result"]["error"] == "boom"


def test_call_tool_invalid_json_arguments_returns_rc1(
    capsys, isolated_registry
) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["call-tool", "mock", "echo", "not-json"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_arguments_json"


def test_call_tool_non_object_arguments_returns_rc1(
    capsys, isolated_registry
) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["call-tool", "mock", "echo", "[1,2]"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_arguments_type"


# ---------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------


def test_ping_against_mock_server(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["ping", "mock"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert isinstance(out["ping_ms"], (int, float))
    assert out["server_info"]["name"] == "mock-mcp"


# ---------------------------------------------------------------------
# servers add / remove / show
# ---------------------------------------------------------------------


def test_servers_add_then_show(capsys, isolated_registry) -> None:
    rc = main([
        "servers-add", "demo",
        "--command", "/usr/bin/true",
        # `--arg=-x` form so argparse does not eat the leading dash
        # as the next flag. Operators hit the same constraint.
        "--arg=-x",
        "--arg", "value",
        "--env", "API=key",
        "--description", "demo entry",
    ])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["added"]["name"] == "demo"
    assert body["added"]["args"] == ["-x", "value"]
    assert body["added"]["env"] == {"API": "key"}
    assert body["added"]["description"] == "demo entry"

    rc = main(["servers-show", "demo"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["server"]["command"] == "/usr/bin/true"


def test_servers_add_rejects_invalid_env_pair(capsys, isolated_registry) -> None:
    rc = main(["servers-add", "x", "--command", "y", "--env", "no-equals"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_env_pair"


def test_servers_remove_returns_1_when_missing(capsys, isolated_registry) -> None:
    rc = main(["servers-remove", "ghost"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "server_not_in_registry"


def test_servers_remove_round_trip(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["servers-remove", "mock"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["removed"] == "mock"
    rc = main(["list-servers"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["count"] == 0


def test_servers_show_unknown_returns_1(capsys, isolated_registry) -> None:
    rc = main(["servers-show", "ghost"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "server_not_in_registry"


# ---------------------------------------------------------------------
# bridge-bootstrap / bridge-list / bridge-unregister
# ---------------------------------------------------------------------


def test_bridge_bootstrap_registers_packs(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main(["bridge-bootstrap", "--discovery-timeout", "10"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["registered"] == ["mcp-mock"]
    assert out["result"]["discovered"] == ["mock"]


def test_bridge_list_after_bootstrap_shows_packs(
    capsys, isolated_registry
) -> None:
    _seed_mock_server(isolated_registry)
    main(["bridge-bootstrap", "--discovery-timeout", "10"])
    capsys.readouterr()  # discard bootstrap output
    rc = main(["bridge-list"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] == 1
    assert out["packs"][0]["slug"] == "mcp-mock"
    assert sorted(out["packs"][0]["actions"]) == ["boom", "echo"]


def test_bridge_unregister_clears_packs(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    main(["bridge-bootstrap", "--discovery-timeout", "10"])
    capsys.readouterr()
    rc = main(["bridge-unregister"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["removed"] == 1
    rc = main(["bridge-list"])
    listing = json.loads(capsys.readouterr().out)
    assert listing["count"] == 0


def test_bridge_bootstrap_with_failed_server_returns_rc1(
    capsys, isolated_registry
) -> None:
    """Configure one good server and one bad — bootstrap returns
    rc=1 because at least one server failed, but the good one
    still registers."""

    _seed_mock_server(isolated_registry)
    main([
        "servers-add", "ghost",
        "--command", "/no/such/binary-please",
    ])
    capsys.readouterr()
    rc = main(["bridge-bootstrap", "--discovery-timeout", "2"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["result"]["registered"] == ["mcp-mock"]
    failed_names = [f["server"] for f in out["result"]["failed"]]
    assert failed_names == ["ghost"]


def test_bridge_bootstrap_only_filter_restricts(
    capsys, isolated_registry
) -> None:
    main([
        "servers-add", "alpha",
        "--command", "/usr/bin/true",
    ])
    main([
        "servers-add", "beta",
        "--command", "/usr/bin/true",
    ])
    capsys.readouterr()
    rc = main(["bridge-bootstrap", "--only", "alpha", "--discovery-timeout", "2"])
    out = json.loads(capsys.readouterr().out)
    # Both will fail (binaries are not MCP servers), but we should
    # only see attempts for alpha.
    seen = {f["server"] for f in out["result"]["failed"]}
    assert seen == {"alpha"}


# ---------------------------------------------------------------------
# bridge-cache list / delete
# ---------------------------------------------------------------------


def test_bridge_cache_list_after_bootstrap(
    capsys, isolated_registry
) -> None:
    _seed_mock_server(isolated_registry)
    main(["bridge-bootstrap", "--discovery-timeout", "10"])
    capsys.readouterr()
    rc = main(["bridge-cache-list"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] == 1
    assert out["cache"][0]["server"] == "mock"
    assert out["cache"][0]["fresh"] is True


def test_bridge_cache_list_show_tools(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    main(["bridge-bootstrap", "--discovery-timeout", "10"])
    capsys.readouterr()
    rc = main(["bridge-cache-list", "--show-tools"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    row = out["cache"][0]
    assert row["tool_count"] == 2
    assert sorted(row["tool_names"]) == ["boom", "echo"]


def test_bridge_cache_delete_round_trip(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    main(["bridge-bootstrap", "--discovery-timeout", "10"])
    capsys.readouterr()
    rc = main(["bridge-cache-delete", "mock"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["deleted"] == "mock"
    rc = main(["bridge-cache-delete", "mock"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "cache_entry_not_found"


# ---------------------------------------------------------------------
# bridge-pool-bench — Wave M6
# ---------------------------------------------------------------------


def test_bridge_pool_bench_reports_cold_warm_speedup(
    capsys, isolated_registry
) -> None:
    _seed_mock_server(isolated_registry)
    rc = main([
        "bridge-pool-bench",
        "mock",
        "echo",
        "--arguments", '{"value":"hi"}',
        "--iterations", "3",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["server"] == "mock"
    assert out["tool"] == "echo"
    assert out["cold_payload_ok"] is True
    assert isinstance(out["cold_ms"], float)
    assert isinstance(out["warm_avg_ms"], float)
    assert len(out["warm_calls"]) == 3
    # Subprocess spawn vs reuse — speedup must be > 1
    # even on a slow CI runner. Mock server is fast enough
    # that warm calls are sub-ms; we expect >= 2x.
    assert out["speedup_vs_cold"] is None or out["speedup_vs_cold"] >= 2.0
    # Stats snapshot is taken before pool.close_all(), so it
    # shows the live session that served the warm calls.
    assert out["pool_stats"]["count"] == 1
    assert out["pool_stats"]["sessions"][0]["name"] == "mock"


def test_bridge_pool_bench_invalid_json_args(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main([
        "bridge-pool-bench",
        "mock",
        "echo",
        "--arguments", "{not valid",
    ])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_arguments_json"


def test_bridge_pool_bench_unknown_server(capsys, isolated_registry) -> None:
    rc = main([
        "bridge-pool-bench",
        "ghost",
        "echo",
    ])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "server_not_in_registry"


def test_bridge_pool_bench_unknown_tool(capsys, isolated_registry) -> None:
    _seed_mock_server(isolated_registry)
    rc = main([
        "bridge-pool-bench",
        "mock",
        "no-such-tool",
        "--iterations", "1",
    ])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "bench_failed"
    assert "not in mcp-mock" in err["detail"]


# ---------------------------------------------------------------------
# bridge-pool-stats / bridge-pool-sweeper / bridge-pool-cap — Wave M7
# ---------------------------------------------------------------------


def test_bridge_pool_stats_returns_snapshot(capsys, isolated_registry) -> None:
    """Default pool starts empty; stats should still surface a
    stable shape including the sweeper status block."""

    from backend.core.mcp_bridge import reset_default_pool

    reset_default_pool()
    rc = main(["bridge-pool-stats"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    snap = out["pool"]
    assert snap["count"] == 0
    assert snap["sessions"] == []
    assert snap["sweeper"]["running"] is False
    assert snap["default_max_concurrency"] is None


def test_bridge_pool_sweeper_run_once_returns_zero(
    capsys, isolated_registry
) -> None:
    """Empty pool → sweeper run-once evicts nothing, exits 0."""

    from backend.core.mcp_bridge import reset_default_pool

    reset_default_pool()
    rc = main(["bridge-pool-sweeper", "run-once", "--max-idle", "1.0"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert out["action"] == "run-once"
    assert out["evicted"] == 0


def test_bridge_pool_sweeper_stop_when_not_running(
    capsys, isolated_registry
) -> None:
    """Stop on a non-running sweeper should be a no-op,
    not an error."""

    from backend.core.mcp_bridge import reset_default_pool

    reset_default_pool()
    rc = main(["bridge-pool-sweeper", "stop"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["was_running"] is False


def test_bridge_pool_cap_set_then_clear(capsys, isolated_registry) -> None:
    from backend.core.mcp_bridge import get_default_pool, reset_default_pool

    reset_default_pool()

    rc = main(["bridge-pool-cap", "filesystem", "4"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["concurrency_limit"] == 4
    assert get_default_pool().get_concurrency_limit("filesystem") == 4

    rc = main(["bridge-pool-cap", "filesystem", "off"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["concurrency_limit"] is None
    assert get_default_pool().get_concurrency_limit("filesystem") is None


def test_bridge_pool_cap_rejects_invalid_limit(capsys, isolated_registry) -> None:
    from backend.core.mcp_bridge import reset_default_pool

    reset_default_pool()
    rc = main(["bridge-pool-cap", "fs", "many"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_limit"

    rc = main(["bridge-pool-cap", "fs", "0"])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "invalid_limit"


def test_bridge_pool_sweeper_rejects_zero_interval(capsys, isolated_registry) -> None:
    from backend.core.mcp_bridge import reset_default_pool

    reset_default_pool()
    rc = main([
        "bridge-pool-sweeper",
        "start",
        "--interval", "0",
        "--max-idle", "1",
    ])
    err = json.loads(capsys.readouterr().err)
    assert rc == 1
    assert err["error"] == "sweeper_failed"
