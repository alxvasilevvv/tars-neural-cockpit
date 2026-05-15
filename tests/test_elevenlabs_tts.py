"""W274 — ElevenLabs TTS endpoint tests (mocked HTTP)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestElevenLabsTTS(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        # Force tts cache into a tmp dir so the test stays hermetic.
        self._tmpdir = tempfile.TemporaryDirectory()
        self._home_override = mock.patch.dict(
            os.environ, {"HOME": self._tmpdir.name}, clear=False
        )
        self._home_override.start()
        # Refresh module-level cache resolver by re-importing.
        import importlib

        import web_extras.routers.accessibility as a11y_mod
        importlib.reload(a11y_mod)
        self.a11y_mod = a11y_mod

        app = FastAPI()
        app.include_router(a11y_mod.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            self._home_override.stop()
        except Exception:
            pass
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_speak_success_returns_audio_data_url(self) -> None:
        with mock.patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False
        ):
            with mock.patch.object(
                self.a11y_mod,
                "_elevenlabs_synthesize",
                return_value=b"FAKEMP3BYTES",
            ) as synth:
                r = self.client.post(
                    "/api/a11y/speak",
                    json={"text": "Привет, мир", "voice_id": "21m00Tcm4TlvDq8ikWAM"},
                )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["engine"], "elevenlabs")
        self.assertEqual(body["model_id"], "eleven_multilingual_v2")
        self.assertTrue(body["audio_url"].startswith("data:audio/mpeg;base64,"))
        self.assertFalse(body["cached"])
        synth.assert_called_once()

    def test_speak_missing_key_falls_back_to_browser_tts(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            r = self.client.post("/api/a11y/speak", json={"text": "Hello world"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["use_browser_tts"])
        self.assertEqual(body["engine"], "browser")
        self.assertEqual(body["text"], "Hello world")

    def test_speak_cache_hit_returns_cached_flag(self) -> None:
        with mock.patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test-key", "HOME": self._tmpdir.name}, clear=False
        ):
            with mock.patch.object(
                self.a11y_mod,
                "_elevenlabs_synthesize",
                return_value=b"FAKEMP3BYTES",
            ) as synth:
                payload = {"text": "Cache me please", "voice_id": "21m00Tcm4TlvDq8ikWAM"}
                r1 = self.client.post("/api/a11y/speak", json=payload)
                r2 = self.client.post("/api/a11y/speak", json=payload)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r1.json()["cached"])
        self.assertTrue(r2.json()["cached"])
        # API only called once — second is served from disk cache.
        self.assertEqual(synth.call_count, 1)

    def test_speak_truncates_long_text_to_5000_chars(self) -> None:
        big = "x" * 7000
        with mock.patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False
        ):
            captured: dict[str, object] = {}

            def _fake_synth(*, text: str, voice_id: str, model_id: str, api_key: str) -> bytes:
                captured["text"] = text
                return b"OK"

            with mock.patch.object(
                self.a11y_mod, "_elevenlabs_synthesize", side_effect=_fake_synth
            ):
                r = self.client.post("/api/a11y/speak", json={"text": big})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertLessEqual(len(captured["text"]), 5000)

    def test_voices_endpoint_returns_curated_six(self) -> None:
        r = self.client.get("/api/a11y/voices")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 6)
        self.assertEqual(len(body["voices"]), 6)
        # Default voice flagged.
        defaults = [v for v in body["voices"] if v.get("default")]
        self.assertEqual(len(defaults), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
