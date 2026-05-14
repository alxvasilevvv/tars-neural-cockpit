"""Wave 238 — pytest coverage for the MCP servers panel router.

Each case is env-isolated via a temporary ``$HOME`` so the auto-seed
on first run is exercised cleanly and the persisted JSON never
leaks across tests.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestMcpPanelRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w238-mcp-panel-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers.mcp_panel import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.config_path = self._home / ".tars" / "mcp_servers.json"

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    def test_first_run_auto_seeds_example(self) -> None:
        """Empty home → /servers returns the seeded example record + writes config file."""

        self.assertFalse(self.config_path.exists())
        r = self.client.get("/api/mcp/servers")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)
        seed = body[0]
        self.assertEqual(seed["name"], "anthropic-filesystem")
        self.assertFalse(seed["enabled"])
        self.assertEqual(seed["status"], "stopped")
        self.assertIn("env_keys_set", seed)
        self.assertNotIn("env", seed)  # value side never leaks
        # File now exists and is valid JSON
        self.assertTrue(self.config_path.exists())
        raw = json.loads(self.config_path.read_text())
        self.assertIsInstance(raw, list)
        self.assertEqual(len(raw), 1)

    def test_post_adds_server_then_get_returns_it(self) -> None:
        payload = {
            "name": "my-mcp",
            "command": "python3",
            "args": ["-m", "my_server"],
            "env": {"API_KEY": "secret-value"},
        }
        r = self.client.post("/api/mcp/servers", json=payload)
        self.assertEqual(r.status_code, 200)
        created = r.json()
        self.assertEqual(created["name"], "my-mcp")
        self.assertEqual(created["command"], "python3")
        self.assertEqual(created["args"], ["-m", "my_server"])
        # Public projection: env *names* only
        self.assertEqual(created["env_keys_set"], ["API_KEY"])
        self.assertNotIn("env", created)
        new_id = created["id"]

        # GET reflects the new server alongside the seed.
        all_rows = self.client.get("/api/mcp/servers").json()
        names = [r["name"] for r in all_rows]
        self.assertIn("my-mcp", names)
        ids = [r["id"] for r in all_rows]
        self.assertIn(new_id, ids)

    def test_put_toggles_enabled_and_persists(self) -> None:
        # Use the auto-seeded record (starts disabled).
        seed = self.client.get("/api/mcp/servers").json()[0]
        sid = seed["id"]
        self.assertFalse(seed["enabled"])

        # Toggle on
        r = self.client.put(f"/api/mcp/servers/{sid}", json={"enabled": True})
        self.assertEqual(r.status_code, 200)
        updated = r.json()
        self.assertTrue(updated["enabled"])
        self.assertEqual(updated["status"], "enabled")
        # Persisted on disk
        raw = json.loads(self.config_path.read_text())
        row = [x for x in raw if x["id"] == sid][0]
        self.assertTrue(row["enabled"])
        self.assertEqual(row["status"], "enabled")

        # Toggle off
        r2 = self.client.put(f"/api/mcp/servers/{sid}", json={"enabled": False})
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["enabled"])
        self.assertEqual(r2.json()["status"], "stopped")

    def test_delete_removes_server(self) -> None:
        seed = self.client.get("/api/mcp/servers").json()[0]
        sid = seed["id"]

        r = self.client.delete(f"/api/mcp/servers/{sid}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

        # Subsequent GET no longer contains it
        after = self.client.get("/api/mcp/servers").json()
        # NB: the auto-seed only fires when the file is missing entirely.
        # After delete the file still exists (empty list), so seeds do *not*
        # re-appear — that's the desired behaviour.
        self.assertEqual([r["id"] for r in after], [])

        # 404 on second delete
        r404 = self.client.delete(f"/api/mcp/servers/{sid}")
        self.assertEqual(r404.status_code, 404)

    def test_status_endpoint_shape(self) -> None:
        # Add a server, toggle it on, then ask for its status.
        created = self.client.post(
            "/api/mcp/servers",
            json={"name": "status-test", "command": "echo", "args": [], "env": {}},
        ).json()
        sid = created["id"]

        # Disabled → "stopped"
        s1 = self.client.get(f"/api/mcp/servers/{sid}/status").json()
        self.assertEqual(s1["id"], sid)
        self.assertEqual(s1["status"], "stopped")
        self.assertIsNone(s1["uptime_sec"])
        self.assertIn("last_message_at", s1)
        self.assertIn("error", s1)

        # Enable → "running"
        self.client.put(f"/api/mcp/servers/{sid}", json={"enabled": True})
        s2 = self.client.get(f"/api/mcp/servers/{sid}/status").json()
        self.assertEqual(s2["status"], "running")
        # uptime is 0 or a small positive int
        self.assertIsInstance(s2["uptime_sec"], int)
        self.assertGreaterEqual(s2["uptime_sec"], 0)
        # 404 on unknown id
        r404 = self.client.get("/api/mcp/servers/does-not-exist/status")
        self.assertEqual(r404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
