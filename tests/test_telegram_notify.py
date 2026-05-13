"""Wave 161 — coverage for backend.core.notifications.telegram.

Sibling to test_imessage.py. Tests use mocked urllib so no
actual Telegram API call leaves the test process.

Cases (~13):
  - is_configured False without env, True with env
  - send_telegram empty text → text_required
  - send_telegram text > 4096 → text_too_long
  - send_telegram without token → token_missing
  - send_telegram empty chat_id → chat_id_required
  - send_telegram success path (200 ok=true)
  - send_telegram with parse_mode passes through
  - send_telegram with HTTPError → http_error + status code
  - send_telegram with URLError → transport_error
  - send_telegram with ok=false body → telegram_api_error
  - send_telegram with bad JSON → bad_response
  - fanout_doctor_change without chat_id → chat_id_required + hint
  - fanout_doctor_change emits formatted text via send_telegram
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from backend.core.notifications import telegram as tg


class _IsolatedTg(unittest.TestCase):
    def setUp(self) -> None:
        for k in ("TELEGRAM_BOT_TOKEN", "TARS_DOCTOR_ALERT_CHAT_ID"):
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k in ("TELEGRAM_BOT_TOKEN", "TARS_DOCTOR_ALERT_CHAT_ID"):
            os.environ.pop(k, None)


# ─── is_configured ─────────────────────────────────────────────────


class TestIsConfigured(_IsolatedTg):
    def test_false_when_unset(self) -> None:
        self.assertFalse(tg.is_configured())

    def test_true_when_env_set(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "12345:abc"
        self.assertTrue(tg.is_configured())


# ─── send_telegram validation ──────────────────────────────────────


class TestSendValidation(_IsolatedTg):
    def test_empty_text(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        self.assertEqual(tg.send_telegram(1, "")["error"], "text_required")
        self.assertEqual(tg.send_telegram(1, "   ")["error"], "text_required")

    def test_text_too_long(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        out = tg.send_telegram(1, "a" * 5000)
        self.assertEqual(out["error"], "text_too_long")
        self.assertEqual(out["limit"], 4096)

    def test_token_missing(self) -> None:
        out = tg.send_telegram(1, "hi")
        self.assertEqual(out["error"], "token_missing")
        self.assertIn("hint", out)

    def test_chat_id_required(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        out = tg.send_telegram("", "hi")
        self.assertEqual(out["error"], "chat_id_required")


# ─── HTTP path ─────────────────────────────────────────────────────


def _mock_urlopen(body: dict, *, status: int = 200):
    raw = json.dumps(body).encode("utf-8")
    fake_resp = MagicMock()
    fake_resp.read.return_value = raw
    fake_resp.__enter__ = lambda self: fake_resp
    fake_resp.__exit__ = lambda *a: False
    return fake_resp


class TestSendHttp(_IsolatedTg):
    def test_success_path(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "12345:test"
        resp = _mock_urlopen({
            "ok": True,
            "result": {"message_id": 42, "chat": {"id": 1}},
        })
        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   return_value=resp) as mock:
            out = tg.send_telegram(1, "Hello world")
        self.assertTrue(out["ok"])
        self.assertEqual(out["message_id"], 42)
        self.assertEqual(out["text_len"], len("Hello world"))
        # Verify Bot API URL was hit
        args, _ = mock.call_args
        req = args[0]
        self.assertIn("api.telegram.org", req.full_url)
        self.assertIn("/sendMessage", req.full_url)

    def test_parse_mode_passes_through(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "12345:test"
        resp = _mock_urlopen({"ok": True, "result": {"message_id": 1}})
        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   return_value=resp) as mock:
            tg.send_telegram(1, "*bold*", parse_mode="Markdown",
                             disable_web_page_preview=True)
        args, _ = mock.call_args
        req = args[0]
        body = req.data.decode("utf-8")
        self.assertIn("parse_mode=Markdown", body)
        self.assertIn("disable_web_page_preview=true", body)

    def test_http_error(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"

        def _raise(*a, **kw):
            raise urllib.error.HTTPError(
                url="https://api.telegram.org/bot/sendMessage",
                code=403, msg="Forbidden",
                hdrs=None, fp=io.BytesIO(b'{"description":"bot blocked"}'),
            )

        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   side_effect=_raise):
            out = tg.send_telegram(1, "hi")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "http_error")
        self.assertEqual(out["status"], 403)
        self.assertIn("bot blocked", out["detail"])

    def test_url_error(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"

        def _raise(*a, **kw):
            raise urllib.error.URLError("dns fail")

        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   side_effect=_raise):
            out = tg.send_telegram(1, "hi")
        self.assertEqual(out["error"], "transport_error")
        self.assertIn("dns fail", out["detail"])

    def test_telegram_api_error(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        resp = _mock_urlopen({
            "ok": False,
            "description": "Bad Request: chat not found",
            "error_code": 400,
        })
        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   return_value=resp):
            out = tg.send_telegram(999999, "hi")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "telegram_api_error")
        self.assertEqual(out["code"], 400)
        self.assertIn("chat not found", out["detail"])

    def test_bad_response(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        # Resp returns non-dict JSON
        fake = MagicMock()
        fake.read.return_value = b"\"not a dict\""
        fake.__enter__ = lambda self: fake
        fake.__exit__ = lambda *a: False
        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   return_value=fake):
            out = tg.send_telegram(1, "hi")
        self.assertEqual(out["error"], "bad_response")


# ─── fanout_doctor_change ──────────────────────────────────────────


class TestFanoutDoctorChange(_IsolatedTg):
    def test_no_chat_id_returns_hint(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        out = tg.fanout_doctor_change({"slug": "daemon", "from": "ok", "to": "fail"})
        self.assertEqual(out["error"], "chat_id_required")
        self.assertIn("hint", out)

    def test_fanout_formats_alert(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        os.environ["TARS_DOCTOR_ALERT_CHAT_ID"] = "42"
        captured: dict = {}
        resp = _mock_urlopen({"ok": True, "result": {"message_id": 7}})
        with patch("backend.core.notifications.telegram.urllib.request.urlopen",
                   return_value=resp) as mock:
            out = tg.fanout_doctor_change({
                "slug": "mcp",
                "from": "ok",
                "to": "fail",
                "summary": "registry failed",
            })
        self.assertTrue(out["ok"])
        # Verify the text formatting
        args, _ = mock.call_args
        req = args[0]
        body = req.data.decode("utf-8")
        # urlencoded; check key parts
        self.assertIn("chat_id=42", body)
        self.assertIn("mcp", body)
        self.assertIn("ok", body)
        self.assertIn("fail", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
