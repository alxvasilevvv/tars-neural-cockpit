"""W211 — tests for /api/briefing/today and /api/digest/*.

Both new routers must:
- Return 200 even when backend stores are unavailable (fault-tolerant
  is part of the contract — cockpit shows whatever section succeeded).
- Have a stable response shape so the cockpit's KV renderer doesn't
  break when individual sections error.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestBriefingRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        self._tmp = tempfile.mkdtemp(prefix="tars-w211-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._orig_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self._home)

        from web_extras.routers.briefing import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            os.environ.pop("HOME", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_today_returns_200_with_sections(self) -> None:
        r = self.client.get("/api/briefing/today")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("headline", body)
        self.assertIn("sections", body)
        for key in ("health", "activity", "reflection", "agents"):
            self.assertIn(key, body["sections"], f"section {key!r} missing")

    def test_today_reflection_picks_up_persisted_file(self) -> None:
        d = self._home / ".tars"
        d.mkdir()
        (d / "reflection_latest.json").write_text(
            json.dumps({"generated_at": 1234567890, "summary": "test reflection"})
        )
        body = self.client.get("/api/briefing/today").json()
        refl = body["sections"]["reflection"]
        self.assertTrue(refl["ok"])
        self.assertEqual(refl["summary"], "test reflection")
        self.assertEqual(refl["generated_at"], 1234567890)

    def test_today_headline_is_string(self) -> None:
        body = self.client.get("/api/briefing/today").json()
        self.assertIsInstance(body["headline"], str)
        self.assertGreater(len(body["headline"]), 5)


class TestDigestRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        self._tmp = tempfile.mkdtemp(prefix="tars-w211-digest-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._orig_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self._home)

        from web_extras.routers.digest import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            os.environ.pop("HOME", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_latest_returns_no_file_state(self) -> None:
        r = self.client.get("/api/digest/latest")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["exists"])
        self.assertIn("hint", body)

    def test_run_returns_summary_with_text(self) -> None:
        r = self.client.post("/api/digest/run", json={})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("digest_text", body)
        self.assertIsInstance(body["digest_text"], str)
        self.assertIn("TARS", body["digest_text"])
        self.assertIn("sections", body)
        self.assertIn("fanout", body)

    def test_run_then_latest_returns_persisted(self) -> None:
        self.client.post("/api/digest/run", json={})
        r = self.client.get("/api/digest/latest")
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["exists"])
        self.assertIn("summary", body)

    def test_run_with_no_channels_returns_attempted_false(self) -> None:
        # Strip TARS_DIGEST_CHANNELS so fanout branch is "not attempted".
        os.environ.pop("TARS_DIGEST_CHANNELS", None)
        body = self.client.post("/api/digest/run", json={}).json()
        self.assertFalse(body["fanout"]["attempted"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
