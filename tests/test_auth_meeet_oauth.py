"""W219 — pytest coverage for /api/auth/meeet OAuth + magic-link starts.

Follows the env-isolated tempfile HOME pattern in
``tests/test_auth_meeet_router.py`` so the real ``~/.tars/meeet_token``
is never touched.

Two cases minimum (per the W219 spec):
  • google redirect URL shape
  • apple redirect URL shape

Plus a few smoke cases for the magic-link-start surface so we don't
ship a 5-line endpoint with zero coverage.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestAuthMeeetOAuth(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w219-oauth-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._orig_home = os.environ.get("HOME")
        self._orig_base = os.environ.get("MEEET_BASE_URL")
        os.environ["HOME"] = str(self._home)
        os.environ["MEEET_BASE_URL"] = "https://meeet.world"

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
        if self._orig_base is not None:
            os.environ["MEEET_BASE_URL"] = self._orig_base
        else:
            os.environ.pop("MEEET_BASE_URL", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # ─── /oauth/google/start ────────────────────────────────────────
    def test_oauth_google_redirect_url_shape(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/google/start")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "google")
        self.assertIn("redirect_url", body)
        url = body["redirect_url"]
        # Must point to meeet.world's OAuth google endpoint and carry
        # the tars:// deep-link return URL.
        self.assertIn("meeet.world", url)
        self.assertIn("/api/oauth/google/start", url)
        self.assertIn("return=tars://auth", url)

    # ─── /oauth/apple/start ─────────────────────────────────────────
    def test_oauth_apple_redirect_url_shape(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/apple/start")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "apple")
        url = body["redirect_url"]
        self.assertIn("meeet.world", url)
        self.assertIn("/api/oauth/apple/start", url)
        self.assertIn("return=tars://auth", url)

    def test_oauth_unsupported_provider_rejected(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/facebook/start")
        self.assertEqual(r.status_code, 400)

    def test_oauth_custom_base_url(self) -> None:
        os.environ["MEEET_BASE_URL"] = "https://staging.meeet.world"
        r = self.client.get("/api/auth/meeet/oauth/google/start")
        self.assertEqual(r.status_code, 200)
        self.assertIn("staging.meeet.world", r.json()["redirect_url"])

    # ─── /magic-link-start ─────────────────────────────────────────
    def test_magic_link_rejects_invalid_email(self) -> None:
        # W230 — the backend now returns a friendly envelope instead of
        # raising 422, so the frontend can show a user-friendly hint
        # rather than the raw Pydantic "string did not match expected
        # pattern" message.
        r = self.client.post(
            "/api/auth/meeet/magic-link-start",
            json={"email": "not-an-email"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "invalid_email")
        self.assertIn("hint", body)

    def test_magic_link_meeet_unreachable_graceful(self) -> None:
        # Point at a definitely-unreachable base so we exercise the
        # except branch and confirm the {ok: false, error: meeet_unreachable}
        # contract that the UI's "skip — local-only mode" link depends on.
        os.environ["MEEET_BASE_URL"] = "http://127.0.0.1:1"
        r = self.client.post(
            "/api/auth/meeet/magic-link-start",
            json={"email": "alien@example.com"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "meeet_unreachable")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
