"""Wave 91 -- structural tests for the connectors registry.

Stdlib unittest only -- no network, no live OAuth. We exercise:

* the registry surface (3 connectors, expected env vars)
* ``get_status`` shape under both unconfigured and configured-but-no-token
* ``health_check`` returns ``ok=False`` cleanly when not configured
* OAuth scaffolding (auth-url shape, ConnectorNotConfigured raise path)
* token storage round-trip
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.core.connectors import (
    ConnectorNotConfigured,
    _storage,
    calendar as calendar_conn,
    gmail as gmail_conn,
    registry,
    slack as slack_conn,
    telegram as telegram_conn,
)


class _IsolateStorage:
    """Context manager: TARS_CONNECTORS_DIR -> tempdir for the test."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("TARS_CONNECTORS_DIR")
        os.environ["TARS_CONNECTORS_DIR"] = self._tmp.name
        return Path(self._tmp.name)

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("TARS_CONNECTORS_DIR", None)
        else:
            os.environ["TARS_CONNECTORS_DIR"] = self._prev
        self._tmp.cleanup()


def _clear_env(*names: str) -> dict[str, str | None]:
    saved = {n: os.environ.pop(n, None) for n in names}
    return saved


def _restore_env(saved: dict[str, str | None]) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class TestRegistryStructure(unittest.TestCase):
    def test_four_connectors_registered(self):
        # Wave 108 — Telegram joins slack/gmail/calendar.
        names = registry.list_connectors()
        self.assertEqual(set(names), {"slack", "gmail", "calendar", "telegram"})

    def test_each_spec_has_required_fields(self):
        for name in registry.list_connectors():
            spec = registry.get(name)
            self.assertEqual(spec.name, name)
            self.assertIsInstance(spec.label, str)
            self.assertGreater(len(spec.env_vars), 0)
            self.assertTrue(callable(spec.is_configured))
            self.assertTrue(callable(spec.has_token))
            self.assertTrue(callable(spec.get_auth_url))
            self.assertTrue(callable(spec.exchange_code))
            self.assertTrue(callable(spec.disconnect))
            self.assertTrue(callable(spec.health_check))

    def test_unknown_name_raises(self):
        with self.assertRaises(KeyError):
            registry.get("does-not-exist")

    def test_slack_env_vars_match_module(self):
        spec = registry.get("slack")
        self.assertEqual(
            spec.env_vars,
            ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"),
        )

    def test_gmail_and_calendar_share_google_env(self):
        gmail_env = registry.get("gmail").env_vars
        cal_env = registry.get("calendar").env_vars
        self.assertEqual(gmail_env, cal_env)
        self.assertIn("GOOGLE_CLIENT_ID", gmail_env)


class TestStatusShape(unittest.TestCase):
    def test_status_returns_expected_shape(self):
        saved = _clear_env(
            "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI",
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID",
        )
        try:
            with _IsolateStorage():
                status = registry.get_status()
            self.assertTrue(status["ok"])
            self.assertIsInstance(status["as_of"], int)
            self.assertEqual(len(status["connectors"]), 4)
            for entry in status["connectors"]:
                self.assertIn("name", entry)
                self.assertIn("label", entry)
                self.assertIn("env_vars", entry)
                self.assertIn("configured", entry)
                self.assertIn("connected", entry)
                self.assertFalse(entry["configured"])  # env was cleared
                self.assertFalse(entry["connected"])
        finally:
            _restore_env(saved)


class TestHealthCheckUnconfigured(unittest.TestCase):
    def test_health_returns_not_configured_error(self):
        saved = _clear_env(
            "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI",
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID",
        )
        try:
            with _IsolateStorage():
                for name in ("slack", "gmail", "calendar", "telegram"):
                    result = registry.health_check(name)
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["error"], "not_configured")
        finally:
            _restore_env(saved)


class TestSlackOAuthShape(unittest.TestCase):
    def test_get_auth_url_raises_when_not_configured(self):
        saved = _clear_env(
            "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"
        )
        try:
            with self.assertRaises(ConnectorNotConfigured):
                slack_conn.get_auth_url(state="abc")
        finally:
            _restore_env(saved)

    def test_get_auth_url_includes_client_id_and_redirect(self):
        saved = _clear_env(
            "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"
        )
        try:
            os.environ["SLACK_CLIENT_ID"] = "test-client-id"
            os.environ["SLACK_CLIENT_SECRET"] = "test-secret"
            os.environ["SLACK_REDIRECT_URI"] = "http://localhost/cb"
            url = slack_conn.get_auth_url(state="xyz")
            self.assertIn("client_id=test-client-id", url)
            self.assertIn("redirect_uri=http", url)
            self.assertIn("state=xyz", url)
            self.assertTrue(url.startswith("https://slack.com/oauth/v2/authorize"))
        finally:
            _restore_env(saved)


class TestGoogleOAuthShape(unittest.TestCase):
    def test_get_auth_url_includes_offline_access(self):
        saved = _clear_env(
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"
        )
        try:
            os.environ["GOOGLE_CLIENT_ID"] = "g-cid"
            os.environ["GOOGLE_CLIENT_SECRET"] = "g-sec"
            os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost/g"
            url = gmail_conn.get_auth_url()
            self.assertIn("access_type=offline", url)
            self.assertIn("client_id=g-cid", url)
            # both gmail.readonly and calendar.readonly should be in scope
            self.assertIn("gmail.readonly", url)
            self.assertIn("calendar.readonly", url)
        finally:
            _restore_env(saved)

    def test_calendar_reuses_google_env(self):
        saved = _clear_env(
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"
        )
        try:
            self.assertFalse(calendar_conn.is_configured())
            os.environ["GOOGLE_CLIENT_ID"] = "g"
            os.environ["GOOGLE_CLIENT_SECRET"] = "s"
            os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost/cb"
            self.assertTrue(calendar_conn.is_configured())
        finally:
            _restore_env(saved)


class TestTokenStorage(unittest.TestCase):
    def test_save_load_delete_roundtrip(self):
        with _IsolateStorage():
            self.assertFalse(_storage.has_token("slack"))
            _storage.save_token("slack", {"access_token": "xoxp-test"})
            self.assertTrue(_storage.has_token("slack"))
            blob = _storage.load_token("slack")
            self.assertIsNotNone(blob)
            self.assertEqual(blob["access_token"], "xoxp-test")
            self.assertIn("stored_at", blob)
            self.assertTrue(_storage.delete_token("slack"))
            self.assertFalse(_storage.has_token("slack"))

    def test_load_returns_none_when_missing(self):
        with _IsolateStorage():
            self.assertIsNone(_storage.load_token("slack"))


class TestIcsParser(unittest.TestCase):
    def test_parse_minimal_vevent(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:abc123\n"
            "SUMMARY:Test Event\n"
            "DTSTART:20260510T100000Z\n"
            "DTEND:20260510T110000Z\n"
            "LOCATION:Office\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        events = calendar_conn.IcsCalendarSource.parse_events(ics)
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt["uid"], "abc123")
        self.assertEqual(evt["summary"], "Test Event")
        self.assertEqual(evt["location"], "Office")
        self.assertTrue(evt["start"].startswith("2026-05-10"))


class TestTelegramConnector(unittest.TestCase):
    """Wave 108 -- TelegramClient + save-self + send-self surface."""

    def test_not_configured_when_env_and_blob_missing(self):
        saved = _clear_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID")
        try:
            with _IsolateStorage():
                self.assertFalse(telegram_conn.is_configured())
                self.assertFalse(telegram_conn.has_token())
                # health_check stays well-formed even when not configured.
                hc = telegram_conn.health_check()
                self.assertFalse(hc["ok"])
                self.assertEqual(hc["error"], "not_configured")
                # get_auth_url returns the BotFather bootstrap URL.
                self.assertEqual(
                    telegram_conn.get_auth_url(state="x"),
                    "https://t.me/BotFather",
                )
                # send_message_to_self raises ConnectorNotConfigured when
                # the operator hasn't saved a chat id.
                client = telegram_conn.TelegramClient("test-tok")
                # No env / blob chat_id -> raises.
                with self.assertRaises(ConnectorNotConfigured):
                    client.send_message_to_self("hi")
        finally:
            _restore_env(saved)

    def test_save_self_chat_id_persists(self):
        saved = _clear_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID")
        try:
            with _IsolateStorage():
                # Need a token first to anchor the blob.
                os.environ["TELEGRAM_BOT_TOKEN"] = "12345:ABC"
                self.assertTrue(telegram_conn.is_configured())
                self.assertIsNone(telegram_conn.get_self_chat_id())
                result = telegram_conn.save_self_chat_id(987654)
                self.assertTrue(result["ok"])
                self.assertEqual(result["self_chat_id"], 987654)
                self.assertEqual(telegram_conn.get_self_chat_id(), 987654)
                # Env override wins over blob.
                os.environ["TELEGRAM_OPERATOR_CHAT_ID"] = "111"
                self.assertEqual(telegram_conn.get_self_chat_id(), 111)
        finally:
            _restore_env(saved)

    def test_send_message_to_self_calls_send_message(self):
        """send_message_to_self resolves chat_id and forwards to send_message."""

        saved = _clear_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID")
        try:
            with _IsolateStorage():
                os.environ["TELEGRAM_BOT_TOKEN"] = "12345:ABC"
                telegram_conn.save_self_chat_id(42)

                client = telegram_conn.TelegramClient("12345:ABC")
                with mock.patch.object(
                    client, "send_message", return_value={"message_id": 7, "chat": {"id": 42}}
                ) as patched:
                    out = client.send_message_to_self("hello world")
                self.assertEqual(out["message_id"], 7)
                patched.assert_called_once()
                # Positional chat_id should be the saved 42.
                args, kwargs = patched.call_args
                self.assertEqual(args[0], 42)
                self.assertEqual(args[1], "hello world")
                self.assertEqual(kwargs.get("parse_mode"), "Markdown")
        finally:
            _restore_env(saved)


if __name__ == "__main__":
    unittest.main()
