"""W217 — pytest coverage for /api/a11y router."""

from __future__ import annotations

import unittest


class TestA11yRouter(unittest.TestCase):
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

    def test_health_returns_capabilities(self) -> None:
        r = self.client.get("/api/a11y/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        caps = body["capabilities"]
        for k in (
            "ocr_local",
            "tts_cloud_elevenlabs",
            "tts_cloud_openai",
            "tts_browser_fallback",
        ):
            self.assertIn(k, caps)
            self.assertIsInstance(caps[k], bool)
        # Browser fallback is always true.
        self.assertTrue(caps["tts_browser_fallback"])

    def test_speak_routes_to_browser_when_no_cloud_key(self) -> None:
        r = self.client.post("/api/a11y/speak", json={"text": "Hello world"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["use_browser_tts"])
        self.assertEqual(body["text"], "Hello world")

    def test_speak_rejects_empty_text(self) -> None:
        # Pydantic min_length=1 → 422
        r = self.client.post("/api/a11y/speak", json={"text": ""})
        self.assertEqual(r.status_code, 422)

    def test_speak_caps_long_text_at_10000_chars(self) -> None:
        # max_length=10000 → 422 on overflow
        r = self.client.post("/api/a11y/speak", json={"text": "x" * 10001})
        self.assertEqual(r.status_code, 422)

    def test_ocr_speak_degrades_gracefully_without_pytesseract(self) -> None:
        # If pytesseract isn't installed, endpoint returns ok=False
        # ocr_unavailable. If it IS installed, it'll attempt OCR on the
        # bytes and either succeed or return ocr_failed — never 500.
        files = {"file": ("test.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        r = self.client.post("/api/a11y/ocr_speak", files=files)
        # 200 on graceful failure, 400 on real OCR error. Never 500.
        self.assertIn(r.status_code, (200, 400))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
