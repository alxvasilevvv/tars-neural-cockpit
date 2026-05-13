"""Wave 154 — coverage for backend.core.doctor.

The doctor's job is to surface health across every TARS subsystem
in a single command. Tests focus on:
  - Each individual check returns a well-formed CheckResult
  - The check never raises (broken-import branches return 'skip',
    not exceptions)
  - run_all returns one result per registered check
  - JSON output mode is parseable
  - Human output table renders in the expected shape
  - Exit codes: ok-only → 0; with warn → 1; with fail → 2
  - --list lists the registered slugs
  - Unknown --check slug returns a 'fail' row
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core.doctor import (
    CheckResult,
    REGISTRY,
    run_all,
    run_check,
)


class _IsolatedDoctor(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w154-doctor-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)
        # Drop env toggles
        for k in ("CLONE_STORE", "TARS_SCHEDULER_ENABLED", "TARS_VAULT_DIR"):
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass


# ─── individual checks ─────────────────────────────────────────────


class TestIndividualChecks(_IsolatedDoctor):
    def test_each_check_returns_check_result(self) -> None:
        for slug, fn in REGISTRY:
            with self.subTest(slug=slug):
                result = run_check(slug)
                self.assertIsInstance(result, CheckResult)
                self.assertEqual(result.slug, slug)
                self.assertIn(result.status, {"ok", "warn", "fail", "skip"})
                self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_check_never_raises_even_on_broken_module(self) -> None:
        # The REGISTRY is a list of (slug, fn) tuples. Replace one
        # entry's fn with an exploder and verify run_check converts
        # the raised exception to a 'fail' CheckResult.
        import backend.core.doctor.checks as ch

        def _explode(_t):
            raise RuntimeError("simulated import failure")

        original = ch.REGISTRY[:]
        try:
            ch.REGISTRY[:] = [("exploder", _explode)]
            r = ch.run_check("exploder")
        finally:
            ch.REGISTRY[:] = original
        self.assertEqual(r.slug, "exploder")
        self.assertEqual(r.status, "fail")
        self.assertIn("simulated import failure", r.summary)

    def test_unknown_check_slug(self) -> None:
        r = run_check("nonexistent-slug-xyz")
        self.assertEqual(r.status, "fail")
        self.assertIn("unknown check", r.summary)


class TestDaemonCheck(_IsolatedDoctor):
    def test_no_heartbeat_returns_warn(self) -> None:
        from backend.core.doctor.checks import check_background_daemon
        r = check_background_daemon(5.0)
        self.assertEqual(r.status, "warn")
        self.assertIn("heartbeat", r.summary.lower())
        self.assertTrue(r.suggestion)

    def test_fresh_heartbeat_returns_ok(self) -> None:
        # Write a fresh heartbeat manually.
        import json as _json
        import time
        hb_dir = self._home / ".tars"
        hb_dir.mkdir()
        (hb_dir / "daemon.heartbeat").write_text(_json.dumps({
            "pid": 12345,
            "started_at": time.time() - 60,
            "last_tick": time.time() - 5,
            "tick_count": 7,
            "last_status": "running",
            "error_count": 0,
            "last_error": None,
            "contract_version": "0.1.0",
        }))
        # Reload runner so HEARTBEAT_PATH picks up new HOME.
        import importlib
        from backend.core.daemon import runner as _rmod
        importlib.reload(_rmod)
        from backend.core.doctor.checks import check_background_daemon
        r = check_background_daemon(5.0)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.details["pid"], 12345)
        self.assertEqual(r.details["tick_count"], 7)


class TestMcpCheck(_IsolatedDoctor):
    def test_mcp_check_finds_tools(self) -> None:
        from backend.core.doctor.checks import check_mcp_server
        r = check_mcp_server(5.0)
        # If mcp is importable, we should see ≥5 tools (W150 ships 5 builtins);
        # otherwise the check skips cleanly.
        self.assertIn(r.status, {"ok", "warn", "skip", "fail"})
        if r.status == "ok":
            self.assertGreaterEqual(r.details["tool_count"], 5)


class TestVaultCheck(_IsolatedDoctor):
    def test_vault_missing_dir_is_warn(self) -> None:
        from backend.core.doctor.checks import check_vault
        r = check_vault(5.0)
        # Vault dir at $HOME/.tars/vault doesn't exist in our temp home.
        self.assertEqual(r.status, "warn")
        self.assertIn("missing", r.summary)

    def test_vault_present_is_ok(self) -> None:
        vault = self._home / ".tars" / "vault"
        vault.mkdir(parents=True)
        (vault / "dummy.key").write_text("test")
        from backend.core.doctor.checks import check_vault
        r = check_vault(5.0)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.details["file_count"], 1)


# ─── Wave 173 — new checks ────────────────────────────────────────


class TestLlmProviderCheck(_IsolatedDoctor):
    def test_no_keys_returns_warn(self) -> None:
        for k in ("TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
                  "TARS_OPENAI_API_KEY", "OPENAI_API_KEY",
                  "TARS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "warn")
        self.assertIn("LLM provider", r.summary)
        self.assertFalse(r.details["anthropic_set"])
        self.assertFalse(r.details["openai_set"])
        self.assertFalse(r.details["openrouter_set"])

    def test_anthropic_only_is_ok(self) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-abc123long-secret-value"
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "ok")
        self.assertIn("Anthropic", r.summary)
        # Redacted preview shouldn't leak the secret
        self.assertIn("…", r.details["anthropic_preview"])
        self.assertNotIn("secret", r.details["anthropic_preview"])
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_openrouter_only_is_ok(self) -> None:
        # W174: OpenRouter joins as a third recognised provider
        for k in ("TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
                  "TARS_OPENAI_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(k, None)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-longsecretvalue123"
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "ok")
        self.assertIn("OpenRouter", r.summary)
        self.assertTrue(r.details["openrouter_set"])
        self.assertIn("…", r.details["openrouter_preview"])
        os.environ.pop("OPENROUTER_API_KEY", None)

    def test_tars_prefixed_openrouter_var(self) -> None:
        for k in ("TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
                  "TARS_OPENAI_API_KEY", "OPENAI_API_KEY",
                  "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["TARS_OPENROUTER_API_KEY"] = "sk-or-prefixed-variant"
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "ok")
        self.assertIn("OpenRouter", r.summary)
        os.environ.pop("TARS_OPENROUTER_API_KEY", None)

    def test_both_keys_set(self) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-xxx"
        os.environ["OPENAI_API_KEY"] = "sk-oai-yyy"
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "ok")
        self.assertIn("Anthropic + OpenAI", r.summary)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_all_three_keys_set(self) -> None:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-xxx"
        os.environ["OPENAI_API_KEY"] = "sk-oai-yyy"
        os.environ["OPENROUTER_API_KEY"] = "sk-or-zzz"
        from backend.core.doctor.checks import check_llm_provider
        r = check_llm_provider(5.0)
        self.assertEqual(r.status, "ok")
        self.assertIn("Anthropic", r.summary)
        self.assertIn("OpenAI", r.summary)
        self.assertIn("OpenRouter", r.summary)
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)


class TestDiskSpaceCheck(_IsolatedDoctor):
    def test_returns_ok_or_warn(self) -> None:
        from backend.core.doctor.checks import check_disk_space
        r = check_disk_space(5.0)
        self.assertIn(r.status, {"ok", "warn", "fail"})
        self.assertIn("free_gb", r.details)
        self.assertIn("probe_dir", r.details)


class TestLogFreshnessCheck(_IsolatedDoctor):
    def test_no_log_returns_skip(self) -> None:
        from backend.core.doctor.checks import check_log_freshness
        r = check_log_freshness(5.0)
        self.assertEqual(r.status, "skip")
        self.assertIn("no daemon log", r.summary)

    def test_fresh_log_returns_ok(self) -> None:
        log_dir = self._home / ".tars"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / "daemon.out.log"
        log.write_text("recent entry")
        from backend.core.doctor.checks import check_log_freshness
        r = check_log_freshness(5.0)
        self.assertEqual(r.status, "ok")
        self.assertLess(r.details["age_s"], 60)

    def test_stale_log_returns_fail(self) -> None:
        import os as _os
        log_dir = self._home / ".tars"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / "daemon.out.log"
        log.write_text("old entry")
        # Set mtime to 2 hours ago
        old = time.time() - (2 * 3600)
        _os.utime(log, (old, old))
        from backend.core.doctor.checks import check_log_freshness
        r = check_log_freshness(5.0)
        self.assertEqual(r.status, "fail")
        self.assertIn("hours", r.summary)


# ─── run_all + __main__ ────────────────────────────────────────────


class TestRunAll(_IsolatedDoctor):
    def test_run_all_returns_one_per_registry_entry(self) -> None:
        results = run_all()
        self.assertEqual(len(results), len(REGISTRY))
        slugs = {r.slug for r in results}
        registry_slugs = {s for s, _ in REGISTRY}
        self.assertEqual(slugs, registry_slugs)


class TestCliExitCodes(_IsolatedDoctor):
    def _capture(self, argv):
        from backend.core.doctor import __main__ as dm
        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            rc = dm.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_json_output_is_parseable(self) -> None:
        rc, out, _ = self._capture(["--json"])
        self.assertIn(rc, {0, 1, 2})
        parsed = json.loads(out)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), len(REGISTRY))
        for row in parsed:
            self.assertIn("slug", row)
            self.assertIn("status", row)

    def test_human_output_contains_summary(self) -> None:
        rc, out, _ = self._capture([])
        self.assertIn("Summary:", out)
        self.assertIn("ok", out)

    def test_list_subcommand(self) -> None:
        rc, out, _ = self._capture(["--list"])
        self.assertEqual(rc, 0)
        for slug, _ in REGISTRY:
            self.assertIn(slug, out)

    def test_exit_code_warn_when_no_heartbeat(self) -> None:
        # No daemon heartbeat → at least one warn → rc=1 (or 2 if anything fails).
        rc, _, _ = self._capture([])
        self.assertIn(rc, {1, 2})

    def test_exit_code_with_only_ok_and_skip(self) -> None:
        # Mock run_all to return one ok + one skip → rc=0
        from backend.core.doctor import __main__ as dm
        from backend.core.doctor.checks import CheckResult as _CR

        fake = [
            _CR(slug="a", label="A", status="ok", summary="fine"),
            _CR(slug="b", label="B", status="skip", summary="not configured"),
        ]
        out = io.StringIO()
        with patch("backend.core.doctor.__main__.run_all", return_value=fake), \
             patch("sys.stdout", out):
            rc = dm.main([])
        self.assertEqual(rc, 0)

    def test_exit_code_with_fail_returns_two(self) -> None:
        from backend.core.doctor import __main__ as dm
        from backend.core.doctor.checks import CheckResult as _CR

        fake = [_CR(slug="x", label="X", status="fail", summary="broken")]
        out = io.StringIO()
        with patch("backend.core.doctor.__main__.run_all", return_value=fake), \
             patch("sys.stdout", out):
            rc = dm.main([])
        self.assertEqual(rc, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
