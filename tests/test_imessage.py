"""Wave 160 — coverage for backend.core.notifications.imessage.

Closes the last W148 reality-audit honesty drift (task #66).

Send path tests use ``unittest.mock`` to patch
``subprocess.run`` + ``shutil.which`` — we don't actually call
osascript. Read path tests construct a synthetic chat.db with
the same schema Apple uses (message + handle tables) and verify
the SELECT works end-to-end.

Cases (~14):
  - is_supported() True on darwin, False elsewhere
  - send_imessage handle/text validation (empty, too long, bad shape)
  - send_imessage when not on darwin → not_supported_on_platform
  - send_imessage with osascript missing → osascript_not_found
  - send_imessage success path with mocked osascript
  - send_imessage with osascript returning non-zero → osascript_failed
  - send_imessage with osascript timeout
  - recent_messages when not on darwin
  - recent_messages with missing db → db_not_found + hint
  - recent_messages with synthetic db → parses rows
  - Cocoa timestamp conversion (seconds + nanoseconds)
  - _looks_like_handle: emails, phones, junk
  - AppleScript escaping of backslash + quotes
  - Module is importable on all platforms without raising
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core.notifications import imessage as im


def _make_synthetic_db(path: Path) -> None:
    """Build a tiny chat.db that mirrors Apple's schema shape."""

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                handle_id INTEGER,
                is_from_me INTEGER,
                date INTEGER,
                service TEXT
            )
        """)
        conn.execute(
            "INSERT INTO handle (ROWID, id) VALUES (1, '+15551234567')"
        )
        conn.execute(
            "INSERT INTO handle (ROWID, id) VALUES (2, 'friend@example.com')"
        )
        # Cocoa-epoch seconds for 2024-01-15 12:00 UTC ≈ 727099200
        conn.execute(
            "INSERT INTO message (text, handle_id, is_from_me, date, service) "
            "VALUES ('Hello there', 1, 0, 727099200, 'iMessage')"
        )
        # Big Sur+ nanosecond format
        conn.execute(
            "INSERT INTO message (text, handle_id, is_from_me, date, service) "
            "VALUES ('From me', 2, 1, 727099200000000000, 'iMessage')"
        )
        conn.commit()
    finally:
        conn.close()


class TestIsSupported(unittest.TestCase):
    def test_supported_on_darwin(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            self.assertTrue(im.is_supported())

    def test_not_supported_elsewhere(self) -> None:
        for plat in ("linux", "win32", "freebsd13"):
            with self.subTest(platform=plat):
                with patch.object(im.sys, "platform", plat):
                    self.assertFalse(im.is_supported())


class TestLooksLikeHandle(unittest.TestCase):
    def test_phone_shapes_accepted(self) -> None:
        for s in ("+15551234567", "15551234567", "+1 555 123 4567", "555-123-4567"):
            with self.subTest(handle=s):
                self.assertTrue(im._looks_like_handle(s))

    def test_email_shapes_accepted(self) -> None:
        for s in ("a@b.co", "alien@example.com", "name.surname@host.tld"):
            with self.subTest(handle=s):
                self.assertTrue(im._looks_like_handle(s))

    def test_junk_rejected(self) -> None:
        for s in ("", "abc", "@hostonly", "no-at-no-dot", "+", "12"):
            with self.subTest(handle=s):
                self.assertFalse(im._looks_like_handle(s))


class TestAppleScriptEscape(unittest.TestCase):
    def test_backslash_doubled(self) -> None:
        self.assertEqual(im._escape_for_applescript("a\\b"), "a\\\\b")

    def test_quote_escaped(self) -> None:
        self.assertEqual(im._escape_for_applescript('hi "you"'), 'hi \\"you\\"')


class TestSendImessage(unittest.TestCase):
    def test_blocked_on_non_darwin(self) -> None:
        with patch.object(im.sys, "platform", "linux"):
            out = im.send_imessage("+15551234567", "hi")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "not_supported_on_platform")

    def test_handle_required(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            out = im.send_imessage("", "hi")
        self.assertEqual(out["error"], "handle_required")

    def test_text_required(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            out = im.send_imessage("+15551234567", "")
        self.assertEqual(out["error"], "text_required")

    def test_handle_shape_validated(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            out = im.send_imessage("not-a-real-handle", "hi")
        self.assertEqual(out["error"], "handle_invalid_shape")

    def test_text_too_long(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            out = im.send_imessage("+15551234567", "x" * 9000)
        self.assertEqual(out["error"], "text_too_long")

    def test_osascript_missing(self) -> None:
        with patch.object(im.sys, "platform", "darwin"), \
             patch("backend.core.notifications.imessage.shutil.which", return_value=None):
            out = im.send_imessage("+15551234567", "hi")
        self.assertEqual(out["error"], "osascript_not_found")

    def test_send_success_path(self) -> None:
        fake = subprocess.CompletedProcess(
            args=["osascript"], returncode=0, stdout="", stderr=""
        )
        with patch.object(im.sys, "platform", "darwin"), \
             patch("backend.core.notifications.imessage.shutil.which", return_value="/usr/bin/osascript"), \
             patch("backend.core.notifications.imessage.subprocess.run", return_value=fake):
            out = im.send_imessage("alien@example.com", "Test 🚀")
        self.assertTrue(out["ok"])
        self.assertEqual(out["handle"], "alien@example.com")
        self.assertEqual(out["text_len"], len("Test 🚀"))

    def test_send_osascript_failed(self) -> None:
        fake = subprocess.CompletedProcess(
            args=["osascript"], returncode=1, stdout="",
            stderr="Messages got an error: No buddy found",
        )
        with patch.object(im.sys, "platform", "darwin"), \
             patch("backend.core.notifications.imessage.shutil.which", return_value="/usr/bin/osascript"), \
             patch("backend.core.notifications.imessage.subprocess.run", return_value=fake):
            out = im.send_imessage("+15551234567", "hi")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "osascript_failed")
        self.assertIn("No buddy found", out["stderr"])

    def test_send_timeout(self) -> None:
        def _raise(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=["osascript"], timeout=15.0)
        with patch.object(im.sys, "platform", "darwin"), \
             patch("backend.core.notifications.imessage.shutil.which", return_value="/usr/bin/osascript"), \
             patch("backend.core.notifications.imessage.subprocess.run", side_effect=_raise):
            out = im.send_imessage("+15551234567", "hi")
        self.assertEqual(out["error"], "osascript_timeout")


class TestRecentMessages(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w160-imsg-")
        self._db = Path(self._tmp) / "chat.db"
        os.environ["TARS_IMESSAGE_DB_PATH"] = str(self._db)

    def tearDown(self) -> None:
        try:
            import shutil as _sh
            _sh.rmtree(self._tmp)
        except Exception:
            pass
        os.environ.pop("TARS_IMESSAGE_DB_PATH", None)

    def test_blocked_on_non_darwin(self) -> None:
        with patch.object(im.sys, "platform", "linux"):
            out = im.recent_messages(limit=10)
        self.assertEqual(out["error"], "not_supported_on_platform")

    def test_missing_db_returns_hint(self) -> None:
        with patch.object(im.sys, "platform", "darwin"):
            out = im.recent_messages(limit=10)
        self.assertEqual(out["error"], "db_not_found")
        self.assertIn("hint", out)

    def test_reads_synthetic_db(self) -> None:
        _make_synthetic_db(self._db)
        with patch.object(im.sys, "platform", "darwin"):
            out = im.recent_messages(limit=10)
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 2)
        # Newest first → 'From me' (handle 2) should be index 0
        self.assertEqual(out["messages"][0]["handle"], "friend@example.com")
        self.assertTrue(out["messages"][0]["is_from_me"])
        # Cocoa timestamp converted to unix
        self.assertGreater(out["messages"][0]["sent_at"], 1_700_000_000)
        # 'Hello there' second
        self.assertEqual(out["messages"][1]["text"], "Hello there")
        self.assertFalse(out["messages"][1]["is_from_me"])


class TestCocoaConversion(unittest.TestCase):
    def test_seconds_format(self) -> None:
        # Cocoa epoch = 2001-01-01 UTC = unix 978307200
        out = im._cocoa_to_unix(0)
        self.assertEqual(out, 0.0)  # zero is treated as "unknown"
        # 1 second after Cocoa epoch
        out = im._cocoa_to_unix(1)
        self.assertEqual(out, 978307201.0)

    def test_nanoseconds_format(self) -> None:
        # Big Sur+: 1 second after Cocoa epoch in nanoseconds
        out = im._cocoa_to_unix(1_000_000_000)
        # 1_000_000_000 is BELOW the 1e15 threshold → treated as seconds
        # So this would be ~31.6 years after Cocoa epoch (2032)
        self.assertGreater(out, 978307200)
        # Real big-sur nanosecond value (> 1e15)
        ns = 2 * 10**18  # 2_000_000_000 seconds in nano
        out2 = im._cocoa_to_unix(ns)
        self.assertAlmostEqual(out2, 2_000_000_000 + 978307200, places=1)


class TestModuleImportEverywhere(unittest.TestCase):
    def test_module_imports_on_all_platforms(self) -> None:
        # The module itself shouldn't crash on non-darwin — public
        # functions return error dicts. Re-import to verify.
        import importlib
        from backend.core import notifications
        importlib.reload(notifications)
        self.assertTrue(hasattr(notifications, "send_imessage"))
        self.assertTrue(hasattr(notifications, "recent_messages"))
        self.assertEqual(notifications.CONTRACT_VERSION, "0.1.0")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
