"""Wave 203 — pytest coverage for the new /api/vision router.

Validates the request/response shapes the new cockpit Vision tab depends
on, without requiring real LLM keys or pytesseract on the test box.
"""

from __future__ import annotations

import os
import unittest


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

    # ─── /health ─────────────────────────────────────────────────────────
    def test_health_returns_capability_dict(self) -> None:
        r = self.client.get("/api/vision/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        caps = body["capabilities"]
        for key in (
            "ocr_local",
            "image_metadata",
            "llm_vision_anthropic",
            "llm_vision_openai",
            "llm_vision_openrouter",
            "llm_vision_any",
        ):
            self.assertIn(key, caps)
            self.assertIsInstance(caps[key], bool)

    # ─── /analyze ────────────────────────────────────────────────────────
    def test_analyze_rejects_bad_data_url(self) -> None:
        r = self.client.post(
            "/api/vision/analyze",
            json={"image_data_url": "not-a-data-url", "prompt": "describe"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "bad_image_data_url")
        self.assertIn("hint", body)

    def test_analyze_without_keys_returns_honest_error(self) -> None:
        # Strip any LLM keys for this test so we hit the "no key" branch.
        snapshot = {}
        for k in (
            "TARS_ANTHROPIC_API_KEY",
            "ANTHROPIC_API_KEY",
            "TARS_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ):
            snapshot[k] = os.environ.pop(k, None)
        try:
            r = self.client.post(
                "/api/vision/analyze",
                json={
                    "image_data_url": "data:image/png;base64,iVBORw0KGgo=",
                    "prompt": "what is this",
                },
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"], "no_llm_key_with_vision")
            self.assertIn("hint", body)
        finally:
            for k, v in snapshot.items():
                if v is not None:
                    os.environ[k] = v

    def test_analyze_accepts_jpeg_and_webp(self) -> None:
        for mime in ("jpeg", "jpg", "webp"):
            r = self.client.post(
                "/api/vision/analyze",
                json={
                    "image_data_url": f"data:image/{mime};base64,Zm9v",
                    "prompt": "describe",
                },
            )
            self.assertEqual(r.status_code, 200)
            body = r.json()
            # Either no key (expected on test box) or actual upstream error —
            # but must NOT be bad_image_data_url for valid mime types.
            self.assertNotEqual(body.get("error"), "bad_image_data_url")

    def test_analyze_missing_body_returns_422(self) -> None:
        r = self.client.post("/api/vision/analyze", json={})
        # Pydantic v2: missing required `image_data_url` → 422
        self.assertEqual(r.status_code, 422)

    # ─── /ocr ────────────────────────────────────────────────────────────
    def test_ocr_without_pytesseract_returns_honest_error(self) -> None:
        # If pytesseract IS installed, this becomes a different code path —
        # we just confirm the endpoint accepts multipart and returns 200.
        files = {"file": ("test.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        r = self.client.post("/api/vision/ocr", files=files)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Either ocr_unavailable (no pytesseract) or ok=true (pytesseract present)
        # or ok=false ocr_failed (bad PNG). All acceptable as long as not 500.
        self.assertIn("ok", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
