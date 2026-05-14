"""W246 -- pytest coverage for the Cmd+K palette v2 aggregator router.

Each case is env-isolated via a temporary ``$HOME`` so the MCP
auto-seed (W238) and notepad SQLite live in a throwaway path and
never leak across tests.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestPaletteRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w246-palette-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        # Reroute both HOME and TARS_HOME so notepads.sqlite + mcp_servers.json
        # land here and don't bleed in real user state.
        self._prev_home = os.environ.get("HOME")
        self._prev_tars_home = os.environ.get("TARS_HOME")
        os.environ["HOME"] = str(self._home)
        os.environ["TARS_HOME"] = str(self._home / ".tars")

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        # Drop any cached notepad-store singleton from a previous test.
        try:
            import backend.core.notepads as nb

            if hasattr(nb, "_STORE"):
                nb._STORE = None
            if hasattr(nb, "_store"):
                nb._store = None
        except Exception:
            pass

        from web_extras.routers.palette import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        if self._prev_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._prev_home
        if self._prev_tars_home is None:
            os.environ.pop("TARS_HOME", None)
        else:
            os.environ["TARS_HOME"] = self._prev_tars_home

    def test_returns_categorized_actions(self) -> None:
        """GET /api/palette/actions returns the documented envelope."""

        r = self.client.get("/api/palette/actions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertIn("categories", body)
        self.assertIn("actions", body)
        self.assertIn("count", body)
        self.assertIsInstance(body["categories"], list)
        self.assertIsInstance(body["actions"], list)
        self.assertEqual(len(body["actions"]), body["count"])

        # Required category labels appear in the categories list.
        cats = body["categories"]
        for required in ("Quick actions", "Agents", "Notepads",
                         "MCP servers", "Mentions", "Recent"):
            self.assertIn(required, cats, f"missing category {required!r}")

        # Every action carries the documented shape.
        for a in body["actions"]:
            for required in ("id", "category", "label"):
                self.assertIn(required, a, f"action missing key {required!r}: {a}")

    def test_quick_actions_present(self) -> None:
        """At least one Quick action (e.g. Reload) is always served."""

        r = self.client.get("/api/palette/actions")
        body = r.json()
        actions = body["actions"]
        quick = [a for a in actions if a.get("category") == "Quick actions"]
        self.assertTrue(quick, "expected at least one Quick action")

        labels = {a.get("label") for a in quick}
        # Reload is the canonical anchor entry.
        self.assertIn("Reload", labels)

        # Quick actions carry a stable id prefix.
        for a in quick:
            self.assertTrue(a["id"].startswith("quick."))
            # Each is independently executable -- payload says how.
            self.assertIn("payload", a)
            self.assertIn("kind", a["payload"])

    def test_missing_notepads_returns_empty_section_gracefully(self) -> None:
        """No notepads seeded -> Notepads section is empty, not an error."""

        # Ensure the notepads DB file does not exist (fresh TARS_HOME).
        npath = self._home / ".tars" / "notepads.sqlite"
        if npath.exists():
            npath.unlink()

        r = self.client.get("/api/palette/actions")
        self.assertEqual(r.status_code, 200)
        body = r.json()

        notepads = [a for a in body["actions"] if a.get("category") == "Notepads"]
        # Zero notepads is the expected outcome on a fresh home.
        self.assertEqual(len(notepads), 0)
        # The category still appears in the header list for the dropdown.
        self.assertIn("Notepads", body["categories"])


if __name__ == "__main__":
    unittest.main()
