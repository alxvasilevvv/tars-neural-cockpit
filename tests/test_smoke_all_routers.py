"""W227 — comprehensive per-router smoke pytest.

One test method per endpoint introduced in W203-W225 plus a sanity baseline
for /api/health. Mirrors the style of ``tests/test_accessibility_router.py``:
each test imports a single router, mounts it on a fresh FastAPI app,
and verifies a minimal-valid request returns a sensible status code.

This file is intentionally *broad and shallow* — deep correctness checks
live in the per-router test modules. The goal here is "every router still
loads + every endpoint still responds".
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path


# ─── /api/vision (W203) ────────────────────────────────────────────────


class TestVisionRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.vision import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_vision_health_200(self) -> None:
        r = self.client.get("/api/vision/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("capabilities", body)

    def test_vision_ocr_multipart_no_500(self) -> None:
        files = {"file": ("smoke.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        r = self.client.post("/api/vision/ocr", files=files)
        # 200 on graceful degrade, 400 on real OCR fail — never 500.
        self.assertIn(r.status_code, (200, 400))

    def test_vision_analyze_returns_envelope(self) -> None:
        body = {
            "image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII=",
            "prompt": "smoke",
        }
        r = self.client.post("/api/vision/analyze", json=body)
        self.assertEqual(r.status_code, 200)
        self.assertIn("ok", r.json())


# ─── /api/auth/meeet (W203 + W219) ─────────────────────────────────────


class TestAuthMeeetRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w227-auth-")
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

    def test_meeet_status_200(self) -> None:
        r = self.client.get("/api/auth/meeet/status")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_meeet_exchange_200(self) -> None:
        r = self.client.post(
            "/api/auth/meeet/exchange",
            json={"token": "smoke-test-token-12345678"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_meeet_disconnect_200(self) -> None:
        # disconnect should be idempotent — succeeds even if no token.
        r = self.client.delete("/api/auth/meeet/disconnect")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_meeet_magic_link_start_envelope(self) -> None:
        r = self.client.post(
            "/api/auth/meeet/magic-link-start",
            json={"email": "smoke@test.local"},
        )
        # 200 with ok=true (sent) or ok=false (meeet_unreachable in tests).
        self.assertEqual(r.status_code, 200)
        self.assertIn("ok", r.json())

    def test_meeet_oauth_google_start_200(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/google/start")
        self.assertEqual(r.status_code, 200)
        self.assertIn("redirect_url", r.json())

    def test_meeet_oauth_apple_start_200(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/apple/start")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["provider"], "apple")

    def test_meeet_oauth_unknown_provider_400(self) -> None:
        r = self.client.get("/api/auth/meeet/oauth/facebook/start")
        self.assertEqual(r.status_code, 400)


# ─── /api/public/proof (W204) ──────────────────────────────────────────


class TestPublicProofRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.public_proof import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_public_proof_health_200(self) -> None:
        r = self.client.get("/api/public/proof/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "tars.public_proof")

    def test_public_proof_anchor_lookup_responds(self) -> None:
        root = "0" * 64
        r = self.client.get(f"/api/public/proof/anchor/{root}")
        # 200 with ok=False (root_not_found) is the happy path on a fresh box.
        # 503 = store unavailable in this test env. Either is acceptable.
        self.assertIn(r.status_code, (200, 503))

    def test_public_proof_anchor_bad_root_400(self) -> None:
        r = self.client.get("/api/public/proof/anchor/not-hex")
        self.assertEqual(r.status_code, 400)

    def test_public_proof_verify_envelope(self) -> None:
        body = {
            "leaf_hex": "0" * 64,
            "path": [],
            "root_hex": "0" * 64,
        }
        r = self.client.post("/api/public/proof/verify", json=body)
        self.assertEqual(r.status_code, 200)
        self.assertIn("valid", r.json())


# ─── /api/briefing (W206) ──────────────────────────────────────────────


class TestBriefingRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.briefing import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_briefing_today_200(self) -> None:
        r = self.client.get("/api/briefing/today")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("headline", body)
        self.assertIn("sections", body)


# ─── /api/digest (W209) ────────────────────────────────────────────────


class TestDigestRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.digest import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_digest_run_post_empty_body_200(self) -> None:
        r = self.client.post("/api/digest/run", json={})
        # Best-effort generate — should not crash, returns envelope.
        self.assertEqual(r.status_code, 200)

    def test_digest_latest_200(self) -> None:
        r = self.client.get("/api/digest/latest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ok", r.json())


# ─── /api/a11y (W217) ──────────────────────────────────────────────────


class TestA11yRouterSmoke(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.accessibility import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_a11y_health_200(self) -> None:
        r = self.client.get("/api/a11y/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_a11y_ocr_speak_no_500(self) -> None:
        files = {"file": ("smoke.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        r = self.client.post("/api/a11y/ocr_speak", files=files)
        self.assertIn(r.status_code, (200, 400))

    def test_a11y_speak_200(self) -> None:
        r = self.client.post("/api/a11y/speak", json={"text": "smoke test"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])


# ─── /api/voice (W220) ─────────────────────────────────────────────────


class TestVoiceCommandRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return
        from web_extras.routers.voice_command import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_voice_command_regex_intent_200(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "проверка", "lang": "ru-RU"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("reply", body)

    def test_voice_command_doctor_intent_routes(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "запусти доктора", "lang": "ru-RU"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["action"], "run_doctor")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
