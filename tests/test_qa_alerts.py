"""Wave 117 — tests for scripts.qa_agent.alerts."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts.qa_agent import alerts as alerts_mod
from scripts.qa_agent.alerts import (
    DEFAULT_THRESHOLD,
    load_history,
    record_run,
    save_history,
    send_alert,
    should_alert,
)


class TestShouldAlert(unittest.TestCase):
    def test_below_threshold_returns_false(self):
        self.assertFalse(should_alert(["fail", "fail"], threshold=3))

    def test_at_threshold_returns_true(self):
        self.assertTrue(should_alert(["fail", "fail", "fail"], threshold=3))

    def test_streak_resets_after_success(self):
        # Even though there are 3 fails in the history, the most-recent
        # entry is a pass, so the streak is broken.
        self.assertFalse(
            should_alert(["fail", "fail", "fail", "pass"], threshold=3)
        )

    def test_pass_inside_window_breaks_streak(self):
        self.assertFalse(
            should_alert(["fail", "pass", "fail", "fail"], threshold=3)
        )

    def test_warn_does_not_count_as_fail(self):
        self.assertFalse(
            should_alert(["fail", "warn", "fail"], threshold=3)
        )

    def test_empty_history(self):
        self.assertFalse(should_alert([], threshold=3))

    def test_default_threshold(self):
        self.assertEqual(DEFAULT_THRESHOLD, 3)
        self.assertTrue(should_alert(["fail"] * DEFAULT_THRESHOLD))


class TestHistoryRoundTrip(unittest.TestCase):
    def test_record_and_persist(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "hist.json"
            history = load_history(path)
            record_run(history, "p.alpha", "pass")
            record_run(history, "p.alpha", "fail")
            record_run(history, "p.beta", "fail")
            self.assertTrue(save_history(history, path))
            loaded = load_history(path)
            self.assertEqual(loaded["probes"]["p.alpha"], ["pass", "fail"])
            self.assertEqual(loaded["probes"]["p.beta"], ["fail"])

    def test_corrupt_file_returns_skeleton(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "hist.json"
            path.write_text("{not json")
            loaded = load_history(path)
            self.assertEqual(loaded["probes"], {})

    def test_per_probe_cap(self):
        with TemporaryDirectory() as td:
            history = {"version": 1, "probes": {}, "updated_at": 0}
            for _ in range(20):
                record_run(history, "p.x", "pass")
            self.assertEqual(
                len(history["probes"]["p.x"]),
                alerts_mod.HISTORY_MAX_PER_PROBE,
            )


class TestSendAlert(unittest.TestCase):
    def setUp(self):
        # Reset KNOWN_FLAKY before each test.
        alerts_mod.KNOWN_FLAKY.clear()

    def test_no_token_is_no_op(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OPERATOR_CHAT_ID")}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(alerts_mod, "_emit_webhook", return_value={"ok": False}):
                out = send_alert("p.test", "synthetic failure")
        self.assertFalse(out["telegram"]["ok"])
        self.assertEqual(out["telegram"]["reason"], "no_token")

    def test_token_set_calls_telegram(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "test:abc",
            "TELEGRAM_OPERATOR_CHAT_ID": "12345",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(
                alerts_mod, "_emit_webhook", return_value={"ok": False}
            ):
                # Block the rich-client import path so we hit the urllib fallback.
                with mock.patch.dict("sys.modules", {"backend.core.connectors.telegram": None}):
                    fake_resp = mock.MagicMock()
                    fake_resp.status = 200
                    fake_resp.__enter__ = lambda self: fake_resp
                    fake_resp.__exit__ = lambda *a: False
                    with mock.patch("urllib.request.urlopen", return_value=fake_resp) as urlopen:
                        out = send_alert("p.test", "synthetic failure")
                        urlopen.assert_called_once()
        self.assertTrue(out["telegram"]["ok"])
        self.assertEqual(out["telegram"]["via"], "urllib")

    def test_known_flaky_short_circuits(self):
        alerts_mod.KNOWN_FLAKY.add("p.flaky")
        try:
            out = send_alert("p.flaky", "ignored")
            self.assertEqual(out, {"ok": True, "skipped": "flaky"})
        finally:
            alerts_mod.KNOWN_FLAKY.clear()


if __name__ == "__main__":
    unittest.main()
