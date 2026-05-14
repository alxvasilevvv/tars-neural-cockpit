"""W258 — tests for managed launchd agents.

These tests run on any platform: the macOS-specific launchctl
calls are bypassed via ``dry_run=True`` (register) and module-
level patches (``is_supported``). The actual XML render, plist
write/read, and id validation are exercised everywhere.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestLaunchdRender(unittest.TestCase):
    def setUp(self) -> None:
        from backend.core.bg_agents import launchd as bg
        self.bg = bg

    def test_render_minimal_plist_has_required_keys(self) -> None:
        spec = self.bg.AgentSpec(
            id="alpha",
            command=["/usr/bin/python3", "-m", "my_pkg"],
        )
        xml = self.bg.render_agent_plist(spec)
        self.assertIn("<key>Label</key>", xml)
        self.assertIn("world.meeet.tars.agent.alpha", xml)
        self.assertIn("<key>ProgramArguments</key>", xml)
        self.assertIn("<string>/usr/bin/python3</string>", xml)
        self.assertIn("<key>StandardOutPath</key>", xml)
        self.assertIn("<key>StandardErrorPath</key>", xml)
        self.assertIn("<key>RunAtLoad</key>", xml)
        # No EnvironmentVariables when empty.
        self.assertNotIn("<key>EnvironmentVariables</key>", xml)

    def test_render_with_env_and_schedule(self) -> None:
        spec = self.bg.AgentSpec(
            id="beta",
            command=["/bin/echo", "hi"],
            schedule="15 9 * * *",   # 09:15 every day
            env={"FOO": "bar", "BAZ": "qux"},
            keep_alive=True,
        )
        xml = self.bg.render_agent_plist(spec)
        self.assertIn("<key>EnvironmentVariables</key>", xml)
        self.assertIn("<key>FOO</key>", xml)
        self.assertIn("<string>bar</string>", xml)
        self.assertIn("<key>StartCalendarInterval</key>", xml)
        self.assertIn("<key>Minute</key>", xml)
        self.assertIn("<integer>15</integer>", xml)
        self.assertIn("<integer>9</integer>", xml)
        self.assertIn("<key>KeepAlive</key>", xml)
        # cron set → RunAtLoad omitted (StartCalendarInterval owns scheduling).
        self.assertNotIn("<key>RunAtLoad</key>", xml)

    def test_cron_invalid_falls_back_to_runatload(self) -> None:
        spec = self.bg.AgentSpec(
            id="gamma",
            command=["/bin/echo"],
            schedule="*/5 * * * *",   # steps not supported
        )
        xml = self.bg.render_agent_plist(spec)
        self.assertNotIn("<key>StartCalendarInterval</key>", xml)
        self.assertIn("<key>RunAtLoad</key>", xml)

    def test_xml_escape_in_env_values(self) -> None:
        spec = self.bg.AgentSpec(
            id="delta",
            command=["/bin/echo"],
            env={"X": "a & b < c > d"},
        )
        xml = self.bg.render_agent_plist(spec)
        self.assertIn("a &amp; b &lt; c &gt; d", xml)

    def test_id_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.bg.register(agent_id="../evil", command=["/bin/sh"])
        with self.assertRaises(ValueError):
            self.bg.register(agent_id="", command=["/bin/sh"])
        with self.assertRaises(ValueError):
            self.bg.register(agent_id="-bad", command=["/bin/sh"])


class TestRegisterUnregisterRoundTrip(unittest.TestCase):
    """Exercise the file-write path with dry_run=True so we never
    actually shell out to launchctl."""

    def setUp(self) -> None:
        from backend.core.bg_agents import launchd as bg
        self.bg = bg
        self.tmp = Path(tempfile.mkdtemp(prefix="tars-w258-"))
        # Override LOG_DIR so the tests don't pollute ~/.tars/.
        self._orig_log = bg.LOG_DIR
        bg.LOG_DIR = self.tmp / "logs"

    def tearDown(self) -> None:
        self.bg.LOG_DIR = self._orig_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_register_writes_plist(self) -> None:
        result = self.bg.register(
            agent_id="trader",
            command=["/usr/bin/python3", "-m", "trader_bot"],
            schedule="0 9 * * 1",
            env={"DRY_RUN": "1"},
            plist_dir=self.tmp,
            dry_run=True,
        )
        self.assertTrue(result["dry_run"])
        plist = Path(result["plist_path"])
        self.assertTrue(plist.exists())
        body = plist.read_text()
        self.assertIn("world.meeet.tars.agent.trader", body)
        self.assertIn("trader_bot", body)
        self.assertIn("<key>DRY_RUN</key>", body)
        self.assertEqual(result["action"], "installed")

        # Re-register → action flips to "updated".
        second = self.bg.register(
            agent_id="trader",
            command=["/usr/bin/python3", "-m", "trader_bot", "--v2"],
            plist_dir=self.tmp,
            dry_run=True,
        )
        self.assertEqual(second["action"], "updated")
        body2 = Path(second["plist_path"]).read_text()
        self.assertIn("--v2", body2)

    def test_register_rejects_empty_command(self) -> None:
        result = self.bg.register(
            agent_id="empty",
            command=[],
            plist_dir=self.tmp,
            dry_run=True,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "command_required")

    def test_unregister_removes_plist(self) -> None:
        self.bg.register(
            agent_id="todelete",
            command=["/bin/echo", "x"],
            plist_dir=self.tmp,
            dry_run=True,
        )
        target = self.tmp / f"{self.bg.AGENT_LABEL_PREFIX}todelete.plist"
        self.assertTrue(target.exists())

        result = self.bg.unregister(
            agent_id="todelete",
            plist_dir=self.tmp,
        )
        self.assertTrue(result["ok"])
        self.assertFalse(target.exists())

    def test_list_managed_finds_only_our_prefix(self) -> None:
        self.bg.register(
            agent_id="one",
            command=["/bin/echo", "1"],
            plist_dir=self.tmp,
            dry_run=True,
        )
        self.bg.register(
            agent_id="two",
            command=["/bin/echo", "2"],
            plist_dir=self.tmp,
            dry_run=True,
        )
        # Drop a non-TARS plist into the same dir — should be ignored.
        (self.tmp / "com.someone.else.plist").write_text("<plist/>")

        # is_supported() being False on Linux is fine; list_managed should
        # still find the files, just with error on status rows.
        rows = self.bg.list_managed(plist_dir=self.tmp)
        ids = sorted(r["agent_id"] for r in rows)
        self.assertEqual(ids, ["one", "two"])


class TestTailLogs(unittest.TestCase):
    def setUp(self) -> None:
        from backend.core.bg_agents import launchd as bg
        self.bg = bg
        self.tmp = Path(tempfile.mkdtemp(prefix="tars-w258-logs-"))
        self._orig_log = bg.LOG_DIR
        bg.LOG_DIR = self.tmp

    def tearDown(self) -> None:
        self.bg.LOG_DIR = self._orig_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tail_logs_missing_file_returns_empty(self) -> None:
        out = self.bg.tail_logs(agent_id="nope", tail=50)
        self.assertEqual(out["agent_id"], "nope")
        self.assertEqual(out["out"], "")
        self.assertEqual(out["err"], "")

    def test_tail_logs_returns_trailing_lines(self) -> None:
        out_path = self.tmp / "alpha.out.log"
        lines = [f"line {i}" for i in range(200)]
        out_path.write_text("\n".join(lines) + "\n")
        out = self.bg.tail_logs(agent_id="alpha", tail=10)
        got = out["out"].splitlines()
        self.assertEqual(got[-1], "line 199")
        self.assertEqual(len(got), 10)


class TestNonDarwinFallback(unittest.TestCase):
    """When ``is_supported()`` is False the helpers should still
    return structured payloads rather than raising."""

    def setUp(self) -> None:
        from backend.core.bg_agents import launchd as bg
        self.bg = bg
        self.tmp = Path(tempfile.mkdtemp(prefix="tars-w258-linux-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_register_without_dry_run_on_linux_reports_unsupported(self) -> None:
        with mock.patch.object(self.bg, "is_supported", return_value=False):
            result = self.bg.register(
                agent_id="linuxguy",
                command=["/bin/echo"],
                plist_dir=self.tmp,
                dry_run=False,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "launchd_not_supported_on_platform")
            # The plist *was* still written so the operator can copy it
            # over to a Mac if they want.
            self.assertTrue(Path(result["plist_path"]).exists())

    def test_status_unsupported(self) -> None:
        with mock.patch.object(self.bg, "is_supported", return_value=False):
            st = self.bg.status(agent_id="anything")
            self.assertFalse(st["loaded"])
            self.assertEqual(st["error"], "launchd_not_supported_on_platform")


class TestHTTPRouter(unittest.TestCase):
    """Smoke-test the FastAPI surface — only the happy path that
    doesn't require launchctl."""

    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers import bg_agents as bg_router

        app = FastAPI()
        app.include_router(bg_router.managed_router)
        self.client = TestClient(app)
        self._tmp = Path(tempfile.mkdtemp(prefix="tars-w258-http-"))

        # Redirect plist dir + log dir to the temp area for this test.
        from backend.core.bg_agents import launchd as bg
        self._bg = bg
        self._orig_plist_dir = bg.DEFAULT_AGENT_PLIST_DIR
        self._orig_log_dir = bg.LOG_DIR
        bg.DEFAULT_AGENT_PLIST_DIR = self._tmp / "LaunchAgents"
        bg.LOG_DIR = self._tmp / "logs"
        bg.DEFAULT_AGENT_PLIST_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._bg.DEFAULT_AGENT_PLIST_DIR = self._orig_plist_dir
        self._bg.LOG_DIR = self._orig_log_dir
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_list_returns_supported_flag(self) -> None:
        r = self.client.get("/api/bg-agents")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("supported", body)
        self.assertIn("agents", body)
        self.assertIsInstance(body["agents"], list)

    def test_register_then_list_then_delete(self) -> None:
        r = self.client.post(
            "/api/bg-agents/register",
            json={
                "id": "httpkid",
                "command": ["/bin/echo", "hello"],
                "dry_run": True,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["dry_run"])

        listed = self.client.get("/api/bg-agents").json()
        ids = [a["agent_id"] for a in listed["agents"]]
        self.assertIn("httpkid", ids)

        r2 = self.client.delete("/api/bg-agents/httpkid")
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertTrue(r2.json()["ok"])

    def test_register_rejects_bad_id(self) -> None:
        r = self.client.post(
            "/api/bg-agents/register",
            json={"id": "../evil", "command": ["/bin/sh"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_logs_endpoint(self) -> None:
        # Pre-populate a log file under the redirected LOG_DIR.
        (self._bg.LOG_DIR).mkdir(parents=True, exist_ok=True)
        (self._bg.LOG_DIR / "logagent.out.log").write_text("hello-from-test\n")
        r = self.client.get("/api/bg-agents/logagent/logs?tail=10")
        self.assertEqual(r.status_code, 200)
        self.assertIn("hello-from-test", r.json()["out"])


if __name__ == "__main__":
    unittest.main()
