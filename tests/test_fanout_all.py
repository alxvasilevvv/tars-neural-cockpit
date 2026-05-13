"""Wave 162 — coverage for backend.core.notifications.fanout_all
and the daemon doctor_watch auto fan-out integration.

Cases (~10):
  - fanout_all with empty channel list returns []
  - fanout_all reads TARS_DAEMON_FANOUT_CHANNELS env when channels=None
  - fanout_all unknown channel → result with error='unknown_channel'
  - fanout_all telegram channel routes to telegram fanout
  - fanout_all imessage channel routes to imessage fanout
  - imessage_fanout_doctor_change without handle → handle_required + hint
  - imessage_fanout_doctor_change formats text including slug + transition
  - doctor_watch._emit_changes calls fanout_all when env set
  - doctor_watch._emit_changes skips fanout when env unset
  - fan-out exception doesn't demote webhook emit success
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from backend.core.notifications import fanout_all
from backend.core.notifications import imessage as imsg
from backend.core.daemon import doctor_watch
from backend.core.doctor.checks import CheckResult


def _run(coro):
    return asyncio.run(coro)


class _IsolatedFanout(unittest.TestCase):
    def setUp(self) -> None:
        for k in (
            "TARS_DAEMON_FANOUT_CHANNELS",
            "TELEGRAM_BOT_TOKEN",
            "TARS_DOCTOR_ALERT_CHAT_ID",
            "TARS_DOCTOR_ALERT_IMESSAGE_HANDLE",
        ):
            os.environ.pop(k, None)
        doctor_watch._reset_for_tests()

    def tearDown(self) -> None:
        for k in (
            "TARS_DAEMON_FANOUT_CHANNELS",
            "TELEGRAM_BOT_TOKEN",
            "TARS_DOCTOR_ALERT_CHAT_ID",
            "TARS_DOCTOR_ALERT_IMESSAGE_HANDLE",
        ):
            os.environ.pop(k, None)
        doctor_watch._reset_for_tests()


# ─── fanout_all ────────────────────────────────────────────────────


class TestFanoutAll(_IsolatedFanout):
    def test_empty_channels_returns_empty(self) -> None:
        self.assertEqual(fanout_all({"slug": "x", "from": "ok", "to": "warn"}, channels=[]), [])

    def test_env_var_supplies_channels(self) -> None:
        os.environ["TARS_DAEMON_FANOUT_CHANNELS"] = "telegram,unknown"
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"  # avoid token_missing for telegram
        change = {"slug": "x", "from": "ok", "to": "fail", "summary": "test"}
        # Telegram will fail on chat_id since we didn't set it,
        # but the dispatcher should still return both rows in order.
        results = fanout_all(change)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["channel"], "telegram")
        self.assertEqual(results[1]["channel"], "unknown")
        self.assertEqual(results[1]["error"], "unknown_channel")

    def test_telegram_channel_routes_to_telegram(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        os.environ["TARS_DOCTOR_ALERT_CHAT_ID"] = "42"

        called = {}

        def _spy(change, *, chat_id=None, token=None):
            called["change"] = change
            return {"ok": True, "message_id": 1}

        with patch("backend.core.notifications.telegram_fanout_doctor_change", new=_spy):
            results = fanout_all(
                {"slug": "a", "from": "ok", "to": "fail"},
                channels=["telegram"],
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["channel"], "telegram")
        self.assertTrue(results[0]["ok"])
        self.assertEqual(called["change"]["slug"], "a")

    def test_imessage_channel_routes_to_imessage(self) -> None:
        called = {}

        def _spy(change, *, handle=None):
            called["change"] = change
            return {"ok": True, "handle": handle, "text_len": 10}

        with patch("backend.core.notifications.imessage_fanout_doctor_change", new=_spy):
            results = fanout_all(
                {"slug": "b", "from": "ok", "to": "warn"},
                channels=["imessage"],
            )
        self.assertEqual(results[0]["channel"], "imessage")
        self.assertTrue(results[0]["ok"])


# ─── imessage_fanout_doctor_change ─────────────────────────────────


class TestImessageFanout(_IsolatedFanout):
    def test_no_handle_returns_hint(self) -> None:
        out = imsg.fanout_doctor_change({"slug": "x", "from": "ok", "to": "fail"})
        self.assertEqual(out["error"], "handle_required")
        self.assertIn("hint", out)

    def test_text_formatted_with_glyph(self) -> None:
        os.environ["TARS_DOCTOR_ALERT_IMESSAGE_HANDLE"] = "+15551234567"
        captured = {}

        def _spy(handle, text):
            captured["handle"] = handle
            captured["text"] = text
            return {"ok": True, "handle": handle, "text_len": len(text)}

        with patch("backend.core.notifications.imessage.send_imessage", new=_spy):
            imsg.fanout_doctor_change({
                "slug": "daemon",
                "from": "ok",
                "to": "fail",
                "summary": "heartbeat stale",
            })
        self.assertEqual(captured["handle"], "+15551234567")
        self.assertIn("daemon", captured["text"])
        self.assertIn("ok", captured["text"])
        self.assertIn("fail", captured["text"])
        self.assertIn("FAIL", captured["text"])  # glyph
        self.assertIn("heartbeat stale", captured["text"])


# ─── doctor_watch._emit_changes integration ────────────────────────


class TestDoctorWatchFanout(_IsolatedFanout):
    def _mk_results(self):
        return [
            CheckResult(slug="mcp", label="MCP", status="fail",
                        summary="registry failed"),
            CheckResult(slug="vault", label="Vault", status="ok",
                        summary="2 entries"),
        ]

    def test_fanout_called_when_env_set(self) -> None:
        os.environ["TARS_DAEMON_FANOUT_CHANNELS"] = "telegram"
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        os.environ["TARS_DOCTOR_ALERT_CHAT_ID"] = "42"

        changes = [{"slug": "mcp", "from": "ok", "to": "fail", "summary": "test"}]
        results = self._mk_results()

        mock_emit = AsyncMock(return_value=None)
        fanout_calls: list = []

        def _spy(change, channels=None):
            fanout_calls.append((change, channels))
            return [{"channel": "telegram", "ok": True, "message_id": 1}]

        with patch("backend.core.webhooks.emit", new=mock_emit, create=True), \
             patch("backend.core.notifications.fanout_all", new=_spy):
            ok = _run(doctor_watch._emit_changes(changes, results))

        self.assertTrue(ok)
        # fanout_all was called once per change
        self.assertEqual(len(fanout_calls), 1)
        self.assertEqual(fanout_calls[0][0]["slug"], "mcp")

    def test_fanout_skipped_when_env_unset(self) -> None:
        changes = [{"slug": "mcp", "from": "ok", "to": "fail"}]
        results = self._mk_results()

        mock_emit = AsyncMock(return_value=None)
        fanout_called = False

        def _spy(*a, **kw):
            nonlocal fanout_called
            fanout_called = True
            return []

        with patch("backend.core.webhooks.emit", new=mock_emit, create=True), \
             patch("backend.core.notifications.fanout_all", new=_spy):
            _run(doctor_watch._emit_changes(changes, results))

        self.assertFalse(fanout_called)

    def test_fanout_exception_doesnt_demote_emit(self) -> None:
        os.environ["TARS_DAEMON_FANOUT_CHANNELS"] = "telegram"
        changes = [{"slug": "mcp", "from": "ok", "to": "fail"}]
        results = self._mk_results()

        mock_emit = AsyncMock(return_value=None)

        def _explode(*a, **kw):
            raise RuntimeError("fan-out boom")

        with patch("backend.core.webhooks.emit", new=mock_emit, create=True), \
             patch("backend.core.notifications.fanout_all", new=_explode):
            ok = _run(doctor_watch._emit_changes(changes, results))

        # Webhook emit succeeded → ok=True even though fan-out blew up
        self.assertTrue(ok)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
