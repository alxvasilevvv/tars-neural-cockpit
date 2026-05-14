"""W220 — pytest coverage for /api/voice/command dispatcher.

Four cases (per spec):
  • doctor regex
  • agents regex
  • today regex
  • llm fallback (with the provider call monkey-patched so the test is
    hermetic — no live API hits)

Reuses the env-isolated tempfile HOME pattern from
``tests/test_auth_meeet_router.py``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class TestVoiceCommandRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w220-voice-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        self._orig_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self._home)

        # Strip every LLM-provider key from the env so the fallback
        # branch is deterministic. Tests that need an LLM monkey-patch
        # the module's _llm_fallback directly.
        self._stashed_keys = {}
        for k in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "TARS_ANTHROPIC_API_KEY",
            "TARS_OPENAI_API_KEY",
            "TARS_OPENROUTER_API_KEY",
        ):
            self._stashed_keys[k] = os.environ.pop(k, None)

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

    def tearDown(self) -> None:
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            os.environ.pop("HOME", None)
        for k, v in self._stashed_keys.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # ─── regex intents ──────────────────────────────────────────────
    def test_doctor_regex_matches(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "TARS, запусти доктор", "lang": "ru-RU"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["action"], "run_doctor")
        self.assertEqual(body["engine"], "regex")
        # Reply must be in Russian since lang=ru-RU.
        self.assertTrue(any(ch in body["reply"] for ch in "абвгдежзиклмн"))

    def test_agents_regex_matches(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "Покажи мне агентов", "lang": "ru-RU"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["action"], "open_tab:agents")
        self.assertEqual(body["engine"], "regex")

    def test_today_regex_matches(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "What's the briefing for today?", "lang": "en-US"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["action"], "show_today")
        self.assertEqual(body["engine"], "regex")
        # English reply for en-US.
        self.assertIn("today", body["reply"].lower())

    def test_reload_regex_matches(self) -> None:
        r = self.client.post(
            "/api/voice/command",
            json={"transcript": "Перезагрузи интерфейс", "lang": "ru-RU"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["action"], "reload")

    # ─── LLM fallback ──────────────────────────────────────────────
    def test_llm_fallback_called_when_no_intent_matches(self) -> None:
        """Mock the LLM hook, hand it a non-matching transcript,
        confirm the router returns engine=llm with the mocked reply."""
        from web_extras.routers import voice_command as mod

        mock_reply = "Я могу подсказать дальше, если уточнишь задачу."
        with patch.object(
            mod, "_llm_fallback", new=AsyncMock(return_value=mock_reply)
        ):
            r = self.client.post(
                "/api/voice/command",
                json={
                    "transcript": "что такое квантовая запутанность",
                    "lang": "ru-RU",
                },
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIsNone(body["action"])
        self.assertEqual(body["engine"], "llm")
        self.assertEqual(body["reply"], mock_reply)

    def test_llm_fallback_empty_returns_graceful_default(self) -> None:
        """If no LLM key is configured (and the fallback returns ""),
        the router must still return a friendly canned reply."""
        from web_extras.routers import voice_command as mod

        with patch.object(mod, "_llm_fallback", new=AsyncMock(return_value="")):
            r = self.client.post(
                "/api/voice/command",
                json={
                    "transcript": "tell me a joke about kuiper belt",
                    "lang": "en-US",
                },
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["engine"], "fallback")
        self.assertIn("Sorry", body["reply"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
