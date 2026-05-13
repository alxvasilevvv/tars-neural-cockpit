"""Wave 163 — coverage for backend.core.notifications.email.

Tests use ``unittest.mock`` to patch ``smtplib.SMTP`` /
``smtplib.SMTP_SSL`` — no real SMTP traffic leaves the test
process.

Cases (~14):
  - is_configured False without env, True with HOST + FROM
  - send_email empty 'to' → to_required
  - send_email empty subject → subject_required
  - send_email empty body → body_required
  - send_email missing host → host_missing + hint
  - send_email missing from → from_missing + hint
  - send_email comma-separated 'to' string parses to list
  - send_email starttls path calls smtp.starttls()
  - send_email ssl path uses SMTP_SSL
  - send_email plain path skips both
  - send_email login called when user+password set
  - send_email login skipped when user missing
  - send_email SMTPAuthenticationError → auth_failed
  - send_email transport error → transport_error
  - fanout_doctor_change without env → to_required + hint
  - fanout_doctor_change formats subject + body
  - fanout_all 'email' channel routes to email
"""

from __future__ import annotations

import os
import smtplib
import unittest
from unittest.mock import MagicMock, patch

from backend.core.notifications import email as em
from backend.core.notifications import fanout_all


class _IsolatedEmail(unittest.TestCase):
    def setUp(self) -> None:
        for k in (
            "TARS_SMTP_HOST", "TARS_SMTP_PORT", "TARS_SMTP_USER",
            "TARS_SMTP_PASSWORD", "TARS_SMTP_FROM", "TARS_SMTP_TLS",
            "TARS_DOCTOR_ALERT_EMAIL",
        ):
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k in (
            "TARS_SMTP_HOST", "TARS_SMTP_PORT", "TARS_SMTP_USER",
            "TARS_SMTP_PASSWORD", "TARS_SMTP_FROM", "TARS_SMTP_TLS",
            "TARS_DOCTOR_ALERT_EMAIL",
        ):
            os.environ.pop(k, None)


class TestIsConfigured(_IsolatedEmail):
    def test_false_when_unset(self) -> None:
        self.assertFalse(em.is_configured())

    def test_true_with_host_and_from(self) -> None:
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        os.environ["TARS_SMTP_FROM"] = "alien@example.com"
        self.assertTrue(em.is_configured())

    def test_false_when_only_host(self) -> None:
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        self.assertFalse(em.is_configured())


class TestSendValidation(_IsolatedEmail):
    def _env_set(self):
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        os.environ["TARS_SMTP_FROM"] = "alien@example.com"

    def test_empty_to(self) -> None:
        self._env_set()
        self.assertEqual(em.send_email("", "s", "b")["error"], "to_required")
        self.assertEqual(em.send_email([], "s", "b")["error"], "to_required")

    def test_empty_subject(self) -> None:
        self._env_set()
        self.assertEqual(em.send_email("a@b.co", "", "b")["error"], "subject_required")

    def test_empty_body(self) -> None:
        self._env_set()
        self.assertEqual(em.send_email("a@b.co", "s", "")["error"], "body_required")

    def test_host_missing(self) -> None:
        os.environ["TARS_SMTP_FROM"] = "alien@example.com"
        out = em.send_email("a@b.co", "s", "body")
        self.assertEqual(out["error"], "host_missing")
        self.assertIn("hint", out)

    def test_from_missing(self) -> None:
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        out = em.send_email("a@b.co", "s", "body")
        self.assertEqual(out["error"], "from_missing")

    def test_comma_separated_to_string(self) -> None:
        self._env_set()
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            out = em.send_email("a@b.co, c@d.co", "Hello", "Body")
        self.assertTrue(out["ok"])
        self.assertEqual(out["to"], ["a@b.co", "c@d.co"])


class TestSendTransport(_IsolatedEmail):
    def setUp(self) -> None:
        super().setUp()
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        os.environ["TARS_SMTP_FROM"] = "alien@example.com"

    def test_starttls_path(self) -> None:
        os.environ["TARS_SMTP_TLS"] = "starttls"
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            out = em.send_email("a@b.co", "s", "b")
        self.assertTrue(out["ok"])
        smtp_mock.starttls.assert_called_once()
        smtp_mock.send_message.assert_called_once()

    def test_ssl_path(self) -> None:
        os.environ["TARS_SMTP_TLS"] = "ssl"
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP_SSL",
                   return_value=smtp_mock) as ssl_cls:
            out = em.send_email("a@b.co", "s", "b")
        self.assertTrue(out["ok"])
        ssl_cls.assert_called_once()
        smtp_mock.send_message.assert_called_once()
        # starttls NOT called on SSL path
        self.assertFalse(getattr(smtp_mock.starttls, "called", False))

    def test_plain_path(self) -> None:
        os.environ["TARS_SMTP_TLS"] = "plain"
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            out = em.send_email("a@b.co", "s", "b")
        self.assertTrue(out["ok"])
        # plain → no starttls + no SSL
        self.assertFalse(getattr(smtp_mock.starttls, "called", False))

    def test_login_called_when_credentials_present(self) -> None:
        os.environ["TARS_SMTP_USER"] = "alien@example.com"
        os.environ["TARS_SMTP_PASSWORD"] = "secret"
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            em.send_email("a@b.co", "s", "b")
        smtp_mock.login.assert_called_once_with("alien@example.com", "secret")

    def test_login_skipped_anonymous(self) -> None:
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            em.send_email("a@b.co", "s", "b")
        self.assertFalse(getattr(smtp_mock.login, "called", False))

    def test_auth_error(self) -> None:
        os.environ["TARS_SMTP_USER"] = "x"
        os.environ["TARS_SMTP_PASSWORD"] = "y"

        def _raise(*a, **kw):
            raise smtplib.SMTPAuthenticationError(535, b"auth fail")

        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False
        smtp_mock.login = _raise

        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            out = em.send_email("a@b.co", "s", "b")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "auth_failed")

    def test_transport_error(self) -> None:
        def _raise(*a, **kw):
            raise TimeoutError("dns timed out")

        with patch("backend.core.notifications.email.smtplib.SMTP",
                   side_effect=_raise):
            out = em.send_email("a@b.co", "s", "b")
        self.assertEqual(out["error"], "transport_error")


class TestFanoutDoctorChange(_IsolatedEmail):
    def test_no_target_returns_hint(self) -> None:
        out = em.fanout_doctor_change({"slug": "x", "from": "ok", "to": "fail"})
        self.assertEqual(out["error"], "to_required")
        self.assertIn("hint", out)

    def test_formats_subject_and_body(self) -> None:
        os.environ["TARS_SMTP_HOST"] = "smtp.example.com"
        os.environ["TARS_SMTP_FROM"] = "alien@example.com"
        os.environ["TARS_DOCTOR_ALERT_EMAIL"] = "ops@example.com"

        captured: dict = {}
        smtp_mock = MagicMock()
        smtp_mock.__enter__ = lambda s: smtp_mock
        smtp_mock.__exit__ = lambda *a: False

        def _capture(msg):
            captured["subject"] = msg["Subject"]
            captured["body"] = msg.get_content()
            captured["to"] = msg["To"]

        smtp_mock.send_message = _capture

        with patch("backend.core.notifications.email.smtplib.SMTP",
                   return_value=smtp_mock):
            out = em.fanout_doctor_change({
                "slug": "daemon", "from": "ok", "to": "fail",
                "summary": "heartbeat stale",
            })

        self.assertTrue(out["ok"])
        self.assertIn("daemon", captured["subject"])
        self.assertIn("FAIL", captured["subject"])
        self.assertIn("ok", captured["body"])
        self.assertIn("fail", captured["body"])
        self.assertIn("heartbeat stale", captured["body"])
        self.assertIn("ops@example.com", captured["to"])


class TestFanoutAllEmailRoute(_IsolatedEmail):
    def test_email_channel_dispatched(self) -> None:
        called = {}

        def _spy(change, *, to=None):
            called["change"] = change
            return {"ok": True, "message_id": "<x@y>"}

        with patch("backend.core.notifications.email_fanout_doctor_change", new=_spy):
            results = fanout_all(
                {"slug": "z", "from": "warn", "to": "fail"},
                channels=["email"],
            )
        self.assertEqual(results[0]["channel"], "email")
        self.assertTrue(results[0]["ok"])
        self.assertEqual(called["change"]["slug"], "z")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
