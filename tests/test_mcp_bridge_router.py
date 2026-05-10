"""HTTP surface tests for ``/api/mcp/bridge/*`` (Wave M6
cockpit panel).

Two coverage layers:

1. **Degradation tests** — run on every branch, including
   ``main`` where ``backend.mcp`` and ``backend.core.mcp_bridge``
   don't exist yet. Verify the router never raises 5xx and
   returns ``{ok: true, available: false, reason: ...}`` so
   the cockpit can render a friendly empty state.
2. **Happy-path tests** — auto-skip when the M3/M5/M6 modules
   aren't importable. Once Wave M3 (#177), M5 (#178), and M6
   (#180) merge, these light up automatically and exercise
   the real bridge bootstrap + pool stats.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


try:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    _CLIENT: TestClient | None = TestClient(app)
except Exception:  # pragma: no cover — FastAPI not installed
    _CLIENT = None


def _has_mcp_modules() -> bool:
    try:
        importlib.import_module("backend.mcp.client")
        importlib.import_module("backend.core.mcp_bridge")
    except ImportError:
        return False
    return True


def _skip_if_no_client() -> None:
    if _CLIENT is None:
        raise unittest.SkipTest("fastapi.TestClient unavailable")


def _seed_servers_json(home: Path, payload: dict) -> None:
    cfg_dir = home / "mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "servers.json").write_text(json.dumps(payload))


# ---------------------------------------------------------------------
# Degradation — run on every branch
# ---------------------------------------------------------------------


class DegradationEndpointTests(unittest.TestCase):
    """Verify the router behaves cleanly when the M3/M5/M6
    modules don't exist (i.e. on plain ``main``)."""

    def setUp(self) -> None:
        _skip_if_no_client()

    def test_status_returns_envelope_even_without_mcp_modules(self) -> None:
        assert _CLIENT is not None
        resp = _CLIENT.get("/api/mcp/bridge/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIn("as_of", body)
        if _has_mcp_modules():
            self.assertTrue(body["available"])
        else:
            self.assertFalse(body["available"])
            self.assertIn("mcp_bridge_unavailable", body["reason"])

    def test_servers_returns_envelope_even_without_mcp_modules(self) -> None:
        assert _CLIENT is not None
        resp = _CLIENT.get("/api/mcp/bridge/servers")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        if not _has_mcp_modules():
            self.assertFalse(body["available"])
            self.assertIn("reason", body)

    def test_refresh_returns_503_when_mcp_modules_missing(self) -> None:
        if _has_mcp_modules():
            self.skipTest("Wave M3+ available — happy-path covers this")
        assert _CLIENT is not None
        resp = _CLIENT.post("/api/mcp/bridge/refresh", json={})
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        # Unified error envelope wraps the detail.
        self.assertIn("mcp_bridge_unavailable", json.dumps(body))

    def test_refresh_rejects_too_high_timeout(self) -> None:
        assert _CLIENT is not None
        resp = _CLIENT.post(
            "/api/mcp/bridge/refresh", json={"discovery_timeout": 999}
        )
        self.assertEqual(resp.status_code, 422)

    def test_router_is_mounted_under_expected_prefix(self) -> None:
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        self.assertIn("/api/mcp/bridge/status", paths)
        self.assertIn("/api/mcp/bridge/servers", paths)
        self.assertIn("/api/mcp/bridge/refresh", paths)


# ---------------------------------------------------------------------
# Happy path — runs only when Wave M3+ modules are importable
# ---------------------------------------------------------------------


@unittest.skipUnless(
    _has_mcp_modules(),
    "Wave M3+ modules not present on this branch",
)
class HappyPathEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _skip_if_no_client()
        self._tmp = TemporaryDirectory()
        self._home = Path(self._tmp.name)
        self._old_home = os.environ.get("TARS_HOME")
        os.environ["TARS_HOME"] = str(self._home)
        from backend.mcp.client import reset_client_registry

        reset_client_registry()

    def tearDown(self) -> None:
        from backend.mcp.client import reset_client_registry

        reset_client_registry()
        if self._old_home is None:
            os.environ.pop("TARS_HOME", None)
        else:
            os.environ["TARS_HOME"] = self._old_home
        self._tmp.cleanup()

    def test_status_with_no_servers_configured_returns_empty_envelope(self) -> None:
        assert _CLIENT is not None
        body = _CLIENT.get("/api/mcp/bridge/status").json()
        self.assertTrue(body["available"])
        self.assertEqual(body["servers"], [])
        self.assertEqual(body["registered"], [])
        self.assertEqual(body["cache"], [])

    def test_status_lists_configured_servers(self) -> None:
        assert _CLIENT is not None
        _seed_servers_json(
            self._home,
            {
                "demo": {
                    "command": sys.executable,
                    "args": ["-m", "tests.mcp_fixtures.mock_mcp_server"],
                    "description": "in-test mock",
                }
            },
        )
        body = _CLIENT.get("/api/mcp/bridge/status").json()
        names = [s["name"] for s in body["servers"]]
        self.assertEqual(names, ["demo"])
        self.assertEqual(body["servers"][0]["command"], sys.executable)


if __name__ == "__main__":
    unittest.main()
