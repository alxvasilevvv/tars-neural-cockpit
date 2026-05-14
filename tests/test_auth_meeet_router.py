"""Wave 203 — pytest coverage for /api/auth/meeet router.

Verifies the 1-click meeet.world connect flow's three endpoints —
exchange, status, disconnect — using an isolated HOME directory so the
real ``~/.tars/meeet_token`` is never touched during testing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestAuthMeeetRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w203-auth-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._orig_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self._home)

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers.auth_meeet import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            os.environ.pop("HOME", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # ─── /status ─────────────────────────────────────────────────────────
    def test_status_starts_disconnected(self) -> None:
        r = self.client.get("/api/auth/meeet/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["connected"])

    # ─── /exchange ───────────────────────────────────────────────────────
    def test_exchange_persists_token(self) -> None:
        r = self.client.post(
            "/api/auth/meeet/exchange",
            json={"token": "test-token-12345678"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("account", body)
        self.assertIn("stored_at", body)

        # File should exist at the test HOME.
        token_file = self._home / ".tars" / "meeet_token"
        self.assertTrue(token_file.exists())
        self.assertEqual(token_file.read_text(), "test-token-12345678")

        # Permissions should be 0o600 (best-effort).
        mode = token_file.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_exchange_rejects_short_token(self) -> None:
        r = self.client.post(
            "/api/auth/meeet/exchange",
            json={"token": "abc"},  # < 8 chars triggers Pydantic min_length
        )
        # Pydantic validation fires at request parsing → 422.
        self.assertEqual(r.status_code, 422)

    def test_status_after_exchange_shows_connected(self) -> None:
        self.client.post(
            "/api/auth/meeet/exchange",
            json={"token": "another-test-token"},
        )
        r = self.client.get("/api/auth/meeet/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["connected"])
        self.assertGreater(body["token_chars"], 8)

    # ─── /disconnect ─────────────────────────────────────────────────────
    def test_disconnect_wipes_token(self) -> None:
        # First, exchange.
        self.client.post(
            "/api/auth/meeet/exchange",
            json={"token": "to-be-wiped-12345"},
        )
        # Then, disconnect.
        r = self.client.delete("/api/auth/meeet/disconnect")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["disconnected"])

        token_file = self._home / ".tars" / "meeet_token"
        self.assertFalse(token_file.exists())

    def test_disconnect_when_nothing_stored_still_returns_200(self) -> None:
        # Idempotent: deleting when there's nothing to delete should not error.
        r = self.client.delete("/api/auth/meeet/disconnect")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
