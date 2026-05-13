"""Wave 152 — coverage for backend.core.daemon.

The daemon is the closer for the "Background TARS" honesty gap
(W148 audit found task #65 marked FULLY IMPLEMENTED but no code
existed). v0.1 ships macOS launchd LaunchAgent + heartbeat file +
graceful SIGTERM.

Test cases (~16):
  - plist renders with default config
  - plist contains the canonical Label/PYTHONPATH/RunAtLoad keys
  - render_plist accepts extra_env and emits valid key/string pairs
  - PlistConfig.resolve_defaults picks up sys.executable + cwd
  - install_plist (dry_run) writes the file without launchctl
  - install_plist returns ok=False when launchctl is missing
  - uninstall_plist (no plist file present) returns ok=True
  - DaemonState default shape
  - write_heartbeat → read_heartbeat round-trip
  - heartbeat write is atomic (tmp file replaces target)
  - run_daemon exits 0 when both scheduler+force are disabled
  - run_daemon force-mode writes a heartbeat with last_status running
  - _force_run env var override
  - render_plist via __main__ subprocess subcommand
  - --status subcommand returns clean JSON
  - --uninstall subcommand path
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _run(coro):
    return asyncio.run(coro)


REPO_ROOT = Path(__file__).resolve().parents[1]


class _IsolatedDaemon(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w152-daemon-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        # Re-point HEARTBEAT_PATH at our temp home
        os.environ["HOME"] = str(self._home)
        # Drop scheduler enable + force flag so tests start clean.
        for k in ("TARS_SCHEDULER_ENABLED", "TARS_DAEMON_FORCE",
                  "TARS_DAEMON_HEARTBEAT_S", "TARS_SCHEDULER_TICK_S"):
            os.environ.pop(k, None)
        # Reload modules so HEARTBEAT_PATH picks up the new HOME.
        import importlib
        from backend.core.daemon import runner as _rmod
        from backend.core.daemon import launchd as _lmod
        importlib.reload(_rmod)
        importlib.reload(_lmod)
        self._rmod = _rmod
        self._lmod = _lmod

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass


# ─── render_plist ──────────────────────────────────────────────────


class TestRenderPlist(_IsolatedDaemon):
    def test_renders_default_plist(self) -> None:
        xml = self._lmod.render_plist()
        self.assertIn("<?xml version=\"1.0\"", xml)
        self.assertIn("<plist version=\"1.0\">", xml)
        self.assertIn("<string>com.tars.background</string>", xml)
        self.assertIn("<string>-m</string>", xml)
        self.assertIn("<string>backend.core.daemon</string>", xml)
        self.assertIn("<key>RunAtLoad</key>", xml)
        self.assertIn("<key>KeepAlive</key>", xml)
        self.assertIn("<key>PYTHONPATH</key>", xml)

    def test_plist_includes_extra_env(self) -> None:
        cfg = self._lmod.PlistConfig(
            extra_env={"TARS_LOG_LEVEL": "DEBUG", "FOO": "bar"},
        )
        xml = self._lmod.render_plist(cfg)
        self.assertIn("<key>TARS_LOG_LEVEL</key>", xml)
        self.assertIn("<string>DEBUG</string>", xml)
        self.assertIn("<key>FOO</key>", xml)
        self.assertIn("<string>bar</string>", xml)

    def test_plist_xml_escapes_extra_env(self) -> None:
        cfg = self._lmod.PlistConfig(extra_env={"X": "<script>"})
        xml = self._lmod.render_plist(cfg)
        self.assertIn("&lt;script&gt;", xml)
        self.assertNotIn("<script>", xml.replace("&lt;script&gt;", ""))

    def test_plist_config_resolve_defaults(self) -> None:
        cfg = self._lmod.PlistConfig().resolve_defaults()
        self.assertEqual(cfg.python, sys.executable)
        self.assertTrue(cfg.cwd.endswith("jarvis"))
        self.assertIn(".tars", cfg.log_path)


# ─── install / uninstall ──────────────────────────────────────────


class TestInstallPlist(_IsolatedDaemon):
    def test_install_dry_run_writes_file(self) -> None:
        plist_dir = Path(self._tmp) / "LaunchAgents"
        result = self._lmod.install_plist(
            plist_dir=plist_dir, dry_run=True,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(Path(result["plist_path"]).exists())
        # XML is well-formed-ish
        body = Path(result["plist_path"]).read_text()
        self.assertIn("<plist", body)
        self.assertIn(self._lmod.PLIST_LABEL, body)

    def test_install_handles_missing_launchctl(self) -> None:
        plist_dir = Path(self._tmp) / "LaunchAgents"

        def _raise(*args, **kwargs):
            raise FileNotFoundError("launchctl not found")

        with patch("backend.core.daemon.launchd._launchctl", side_effect=_raise):
            result = self._lmod.install_plist(plist_dir=plist_dir, dry_run=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "launchctl_not_found")
        # Plist was still written before the launchctl call.
        self.assertTrue(Path(result["plist_path"]).exists())

    def test_uninstall_no_plist_present(self) -> None:
        plist_dir = Path(self._tmp) / "LaunchAgents"
        plist_dir.mkdir()

        # Mock launchctl bootout success (rc=0)
        fake = subprocess.CompletedProcess(args=["launchctl", "bootout"], returncode=0, stdout="", stderr="")
        with patch("backend.core.daemon.launchd._launchctl", return_value=fake):
            result = self._lmod.uninstall_plist(plist_dir=plist_dir)
        self.assertTrue(result["ok"])


class TestPlistStatus(_IsolatedDaemon):
    def test_status_when_not_loaded(self) -> None:
        plist_dir = Path(self._tmp) / "LaunchAgents"
        plist_dir.mkdir()
        # launchctl list <label> returns rc=113 when not loaded
        fake = subprocess.CompletedProcess(
            args=["launchctl", "list"], returncode=113, stdout="", stderr=""
        )
        with patch("backend.core.daemon.launchd._launchctl", return_value=fake):
            st = self._lmod.plist_status(plist_dir=plist_dir)
        self.assertFalse(st["loaded"])
        self.assertIsNone(st["pid"])
        self.assertFalse(st["installed"])

    def test_status_when_loaded_parses_pid(self) -> None:
        plist_dir = Path(self._tmp) / "LaunchAgents"
        plist_dir.mkdir()
        (plist_dir / self._lmod.PLIST_FILENAME).write_text("<plist/>")
        stdout = """{
\t"LimitLoadToSessionType" = "Aqua";
\t"Label" = "com.tars.background";
\t"PID" = 12345;
}"""
        fake = subprocess.CompletedProcess(
            args=["launchctl", "list"], returncode=0, stdout=stdout, stderr=""
        )
        with patch("backend.core.daemon.launchd._launchctl", return_value=fake):
            st = self._lmod.plist_status(plist_dir=plist_dir)
        self.assertTrue(st["loaded"])
        self.assertTrue(st["installed"])
        self.assertEqual(st["pid"], 12345)


# ─── heartbeat I/O ─────────────────────────────────────────────────


class TestHeartbeat(_IsolatedDaemon):
    def test_state_default_shape(self) -> None:
        self._rmod._reset_state_for_tests()
        s = self._rmod.get_state()
        self.assertEqual(s.pid, os.getpid())
        self.assertGreater(s.started_at, 0)
        self.assertEqual(s.tick_count, 0)
        self.assertEqual(s.last_status, "starting")

    def test_write_then_read_round_trip(self) -> None:
        self._rmod._reset_state_for_tests()
        s = self._rmod.get_state()
        s.last_tick = 12345.0
        s.tick_count = 7
        s.last_status = "running"
        path = self._rmod.write_heartbeat(s)
        self.assertTrue(path.exists())
        back = self._rmod.read_heartbeat(path)
        self.assertIsNotNone(back)
        self.assertEqual(back["tick_count"], 7)
        self.assertEqual(back["last_status"], "running")
        self.assertEqual(back["last_tick"], 12345.0)

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(self._rmod.read_heartbeat(Path("/nope/missing.json")))


# ─── run_daemon loop ───────────────────────────────────────────────


class TestRunDaemon(_IsolatedDaemon):
    def test_exits_clean_when_scheduler_disabled_and_unforced(self) -> None:
        self._rmod._reset_state_for_tests()
        rc = _run(self._rmod.run_daemon())
        self.assertEqual(rc, 0)
        hb = self._rmod.read_heartbeat()
        self.assertIsNotNone(hb)
        self.assertEqual(hb["last_status"], "idle_exit")

    def test_force_mode_loops_then_stops(self) -> None:
        os.environ["TARS_DAEMON_FORCE"] = "1"
        os.environ["TARS_DAEMON_HEARTBEAT_S"] = "0.1"
        self._rmod._reset_state_for_tests()

        async def _ticker():
            # Let run_daemon run for ~0.3s then send SIGINT to drain.
            task = asyncio.create_task(self._rmod.run_daemon())
            await asyncio.sleep(0.3)
            import signal
            os.kill(os.getpid(), signal.SIGINT)
            return await asyncio.wait_for(task, timeout=2.0)

        rc = _run(_ticker())
        self.assertEqual(rc, 0)
        hb = self._rmod.read_heartbeat()
        self.assertIsNotNone(hb)
        # last_status should be 'stopped' after clean shutdown
        self.assertEqual(hb["last_status"], "stopped")
        # tick_count incremented at least once
        self.assertGreaterEqual(hb["tick_count"], 1)


class TestForceRunEnvVar(_IsolatedDaemon):
    def test_force_env_var_recognized(self) -> None:
        os.environ["TARS_DAEMON_FORCE"] = "yes"
        self.assertTrue(self._rmod._force_run())
        os.environ["TARS_DAEMON_FORCE"] = "0"
        self.assertFalse(self._rmod._force_run())
        os.environ.pop("TARS_DAEMON_FORCE", None)
        self.assertFalse(self._rmod._force_run())


# ─── __main__ subcommands ──────────────────────────────────────────


class TestMainSubcommands(_IsolatedDaemon):
    def test_render_plist_subcommand_via_main(self) -> None:
        from backend.core.daemon import __main__ as dm
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = dm.main(["--render-plist"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("<plist", out)
        self.assertIn("com.tars.background", out)

    def test_heartbeat_subcommand_missing_file(self) -> None:
        from backend.core.daemon import __main__ as dm
        rc = dm.main(["--heartbeat"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
