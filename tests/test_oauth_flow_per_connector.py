"""Wave 123 — per-connector OAuth happy-path tests (slack/gmail/calendar/telegram).

Wave 122 audit noted only the registry tests covered connector
OAuth flow. This file fills the gap by exercising:

- get_auth_url returns URL with required scopes/state
- exchange_code with mocked HTTP returns token shape
- token_storage at expected path with mode 0o600 (Unix)
- is_configured returns True/False per env state
- has_token reflects on-disk state

All HTTP calls are mocked via ``unittest.mock.patch`` against the
module-private ``_http_post`` / ``_http_request`` helpers so no
network is hit. Telegram differs (bot-token style) — adapted accordingly.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


class _IsolatedConnectors(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w123-conn-")
        os.environ["TARS_CONNECTORS_DIR"] = self._tmp

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        os.environ.pop("TARS_CONNECTORS_DIR", None)


# ----- Slack ------------------------------------------------------------


class TestSlackOAuth(_IsolatedConnectors):
    def setUp(self) -> None:
        super().setUp()
        os.environ["SLACK_CLIENT_ID"] = "test-client-id"
        os.environ["SLACK_CLIENT_SECRET"] = "test-client-secret"
        os.environ["SLACK_REDIRECT_URI"] = "https://app/example/cb"

    def tearDown(self) -> None:
        for k in ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"):
            os.environ.pop(k, None)
        super().tearDown()

    def test_is_configured(self) -> None:
        from backend.core.connectors import slack
        self.assertTrue(slack.is_configured())

    def test_is_configured_false_without_env(self) -> None:
        os.environ.pop("SLACK_CLIENT_ID", None)
        from backend.core.connectors import slack
        self.assertFalse(slack.is_configured())

    def test_get_auth_url_contains_scopes_and_state(self) -> None:
        from backend.core.connectors import slack
        url = slack.get_auth_url(state="abc123")
        self.assertIn("client_id=test-client-id", url)
        self.assertIn("state=abc123", url)
        self.assertIn("channels%3Aread", url)
        self.assertIn("redirect_uri=", url)

    def test_exchange_code_persists_token(self) -> None:
        from backend.core.connectors import slack, _storage
        fake_resp = {
            "ok": True,
            "access_token": "xoxb-token-123",
            "team": {"id": "T1"},
            "authed_user": {"id": "U1", "access_token": "xoxp-user"},
        }
        with patch.object(slack, "_http_post", return_value=fake_resp):
            token = slack.exchange_code("auth-code-abc")
        self.assertEqual(token["access_token"], "xoxb-token-123")
        self.assertTrue(slack.has_token())
        # Persisted blob can be loaded back.
        blob = _storage.load_token("slack")
        self.assertIsNotNone(blob)
        self.assertEqual(blob["access_token"], "xoxb-token-123")

    def test_exchange_code_failure_raises(self) -> None:
        from backend.core.connectors import slack, ConnectorAuthError
        with patch.object(
            slack, "_http_post",
            return_value={"ok": False, "error": "invalid_code"},
        ):
            with self.assertRaises(ConnectorAuthError):
                slack.exchange_code("bad-code")

    def test_token_file_mode_0600(self) -> None:
        if os.name != "posix":
            self.skipTest("file mode assertion only meaningful on POSIX")
        from backend.core.connectors import slack, _storage
        fake_resp = {"ok": True, "access_token": "xoxb-A"}
        with patch.object(slack, "_http_post", return_value=fake_resp):
            slack.exchange_code("c")
        path = _storage._token_path("slack")
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)


# ----- Gmail (Google) ---------------------------------------------------


class TestGmailOAuth(_IsolatedConnectors):
    def setUp(self) -> None:
        super().setUp()
        os.environ["GOOGLE_CLIENT_ID"] = "g-client"
        os.environ["GOOGLE_CLIENT_SECRET"] = "g-secret"
        os.environ["GOOGLE_REDIRECT_URI"] = "https://app/example/google/cb"

    def tearDown(self) -> None:
        for k in (
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
        ):
            os.environ.pop(k, None)
        super().tearDown()

    def test_is_configured(self) -> None:
        from backend.core.connectors import gmail
        self.assertTrue(gmail.is_configured())

    def test_is_configured_false_without_env(self) -> None:
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        from backend.core.connectors import gmail
        self.assertFalse(gmail.is_configured())

    def test_get_auth_url_contains_scope_and_offline(self) -> None:
        from backend.core.connectors import gmail
        url = gmail.get_auth_url(state="state-x")
        self.assertIn("client_id=g-client", url)
        self.assertIn("state=state-x", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)

    def test_exchange_code_persists_token(self) -> None:
        from backend.core.connectors import gmail, _storage
        fake_resp = {
            "access_token": "ya29.token",
            "refresh_token": "rt-123",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        with patch.object(gmail, "_http_post", return_value=fake_resp):
            token = gmail.exchange_code("g-code")
        self.assertEqual(token["access_token"], "ya29.token")
        self.assertIn("expires_at", token)
        self.assertTrue(gmail.has_token())
        blob = _storage.load_token("google")
        self.assertEqual(blob["refresh_token"], "rt-123")

    def test_exchange_code_failure_raises(self) -> None:
        from backend.core.connectors import gmail, ConnectorAuthError
        with patch.object(
            gmail, "_http_post",
            return_value={"error": "invalid_grant"},
        ):
            with self.assertRaises(ConnectorAuthError):
                gmail.exchange_code("bad")


# ----- Google Calendar (piggybacks on Google OAuth) ---------------------


class TestCalendarOAuth(_IsolatedConnectors):
    def setUp(self) -> None:
        super().setUp()
        os.environ["GOOGLE_CLIENT_ID"] = "g-client"
        os.environ["GOOGLE_CLIENT_SECRET"] = "g-secret"
        os.environ["GOOGLE_REDIRECT_URI"] = "https://app/example/google/cb"

    def tearDown(self) -> None:
        for k in (
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
        ):
            os.environ.pop(k, None)
        super().tearDown()

    def test_is_configured_true_when_google_env_set(self) -> None:
        from backend.core.connectors import calendar
        self.assertTrue(calendar.is_configured())

    def test_is_configured_false_when_google_env_missing(self) -> None:
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        from backend.core.connectors import calendar
        self.assertFalse(calendar.is_configured())

    def test_calendar_auth_url_reuses_gmail_auth(self) -> None:
        from backend.core.connectors import calendar
        url = calendar.get_auth_url(state="cal-state")
        self.assertIn("state=cal-state", url)
        self.assertIn("client_id=g-client", url)

    def test_calendar_exchange_code_delegates(self) -> None:
        from backend.core.connectors import calendar, gmail
        fake_resp = {
            "access_token": "cal-tok",
            "refresh_token": "cal-rt",
            "expires_in": 3600,
        }
        with patch.object(gmail, "_http_post", return_value=fake_resp):
            token = calendar.exchange_code("c-code")
        self.assertEqual(token["access_token"], "cal-tok")
        # Calendar uses the shared "google" storage key.
        self.assertTrue(calendar.has_token())


# ----- Telegram (bot-token style — no OAuth) ---------------------------


class TestTelegramConnect(_IsolatedConnectors):
    def setUp(self) -> None:
        super().setUp()
        # Make sure no env token leaks in.
        for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID"):
            os.environ.pop(k, None)

    def test_is_configured_false_without_token(self) -> None:
        from backend.core.connectors import telegram
        self.assertFalse(telegram.is_configured())

    def test_is_configured_true_with_env_token(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "12345:fake-bot-token"
        from backend.core.connectors import telegram
        try:
            self.assertTrue(telegram.is_configured())
        finally:
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)

    def test_get_auth_url_returns_botfather(self) -> None:
        from backend.core.connectors import telegram
        url = telegram.get_auth_url()
        self.assertIn("BotFather", url)

    def test_exchange_code_validates_via_get_me_and_persists(self) -> None:
        from backend.core.connectors import telegram, _storage
        fake_get_me = {
            "id": 99,
            "username": "tars_test_bot",
            "first_name": "TARS Test",
        }
        with patch.object(telegram, "_bot_get_me", return_value=fake_get_me):
            out = telegram.exchange_code("12345:fake-bot-token")
        self.assertTrue(out["ok"])
        self.assertEqual(out["bot_id"], 99)
        blob = _storage.load_token("telegram")
        self.assertIsNotNone(blob)
        self.assertEqual(blob["bot_token"], "12345:fake-bot-token")
        self.assertEqual(blob["bot_username"], "tars_test_bot")

    def test_exchange_code_rejects_empty(self) -> None:
        from backend.core.connectors import telegram, ConnectorAuthError
        with self.assertRaises(ConnectorAuthError):
            telegram.exchange_code("")
        with self.assertRaises(ConnectorAuthError):
            telegram.exchange_code("   ")

    def test_health_check_when_not_configured(self) -> None:
        from backend.core.connectors import telegram
        out = telegram.health_check()
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "not_configured")


# ----- Storage layer per-token ----------------------------------------


class TestStorageHelpers(_IsolatedConnectors):
    def test_save_load_delete_roundtrip(self) -> None:
        from backend.core.connectors import _storage
        path = _storage.save_token("foo", {"k": "v"})
        self.assertTrue(path.is_file())
        blob = _storage.load_token("foo")
        self.assertEqual(blob["k"], "v")
        self.assertIn("stored_at", blob)
        self.assertTrue(_storage.delete_token("foo"))
        self.assertIsNone(_storage.load_token("foo"))

    def test_load_token_returns_none_for_missing(self) -> None:
        from backend.core.connectors import _storage
        self.assertIsNone(_storage.load_token("does-not-exist"))
        self.assertFalse(_storage.has_token("does-not-exist"))

    def test_token_age_s_after_save(self) -> None:
        from backend.core.connectors import _storage
        _storage.save_token("aged", {"x": 1})
        age = _storage.token_age_s("aged")
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
