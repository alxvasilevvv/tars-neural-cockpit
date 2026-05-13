"""Wave 166 — coverage for backend.core.doctor.fixers.

The `--fix` framework is intentionally conservative: only the
``vault`` fixer is allowed to mutate filesystem state in v0.4.
``daemon`` and ``scheduler`` fixers return ``skipped`` with a
suggestion — they can't safely auto-mutate launchctl/systemctl
state or the operator's parent shell.

Cases (~13):
  - FixResult shape (dataclass + to_dict round-trip)
  - run_fix unknown slug returns 'no_fixer_registered'
  - run_fix on a check with status='ok' → skipped + already_ok
  - run_fix on a check with status='skip' → skipped + check_skipped
  - run_fix exception path → reason=fixer_exception
  - vault fixer creates missing dir
  - vault fixer idempotent (second call also returns applied=True
    but mkdir doesn't raise)
  - vault fixer recheck after apply flips status to 'ok'
  - vault fixer handles mkdir OSError
  - daemon fixer always skips with manual_action_required
  - scheduler fixer always skips with manual_action_required
  - run_all_fixes returns one result per registry entry
  - __main__ --fix vault path runs end-to-end
  - --list output marks slugs that have fixers
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core.doctor import (
    CheckResult,
    FIX_REGISTRY,
    FixResult,
    REGISTRY,
    run_all_fixes,
    run_fix,
)
from backend.core.doctor import fixers as fmod


class _IsolatedFixer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w166-fix-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)
        os.environ.pop("TARS_VAULT_DIR", None)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        os.environ.pop("TARS_VAULT_DIR", None)


# ─── FixResult ────────────────────────────────────────────────────


class TestFixResult(_IsolatedFixer):
    def test_dataclass_round_trip(self) -> None:
        r = FixResult(slug="vault", applied=True, before_status="warn",
                      after_status="ok", detail="created")
        d = r.to_dict()
        self.assertEqual(d["slug"], "vault")
        self.assertTrue(d["applied"])
        self.assertEqual(d["before_status"], "warn")
        self.assertEqual(d["after_status"], "ok")


# ─── run_fix dispatch ─────────────────────────────────────────────


class TestRunFixDispatch(_IsolatedFixer):
    def test_unknown_slug(self) -> None:
        r = run_fix("nonexistent-xyz")
        self.assertTrue(r.skipped)
        self.assertEqual(r.reason, "no_fixer_registered")

    def test_status_ok_skipped(self) -> None:
        # Pre-create the vault dir so the check returns ok → fixer skips
        vault = self._home / ".tars" / "vault"
        vault.mkdir(parents=True)
        (vault / "marker").write_text("x")

        r = run_fix("vault")
        self.assertTrue(r.skipped)
        self.assertEqual(r.reason, "already_ok")

    def test_fixer_exception_handled(self) -> None:
        def _bad(_c):
            raise RuntimeError("boom")

        try:
            fmod.FIX_REGISTRY["__test_explode"] = _bad
            REGISTRY.append(("__test_explode", lambda _t: CheckResult(
                slug="__test_explode", label="x", status="warn"
            )))
            r = run_fix("__test_explode")
            self.assertFalse(r.applied)
            self.assertEqual(r.reason, "fixer_exception")
            self.assertIn("boom", r.detail)
        finally:
            fmod.FIX_REGISTRY.pop("__test_explode", None)
            REGISTRY[:] = [t for t in REGISTRY if t[0] != "__test_explode"]


# ─── vault fixer ──────────────────────────────────────────────────


class TestVaultFixer(_IsolatedFixer):
    def test_creates_missing_dir(self) -> None:
        vault = self._home / ".tars" / "vault"
        self.assertFalse(vault.exists())

        r = run_fix("vault")
        self.assertTrue(r.applied)
        self.assertEqual(r.before_status, "warn")
        self.assertEqual(r.after_status, "ok")
        self.assertTrue(vault.exists())

    def test_idempotent_second_call(self) -> None:
        # First call creates → after_status=ok
        r1 = run_fix("vault")
        self.assertTrue(r1.applied)
        # Second call: vault exists, check is ok, fixer skips
        r2 = run_fix("vault")
        self.assertTrue(r2.skipped)
        self.assertEqual(r2.reason, "already_ok")

    def test_mkdir_failure(self) -> None:
        # Force a mkdir failure by patching Path.mkdir
        from pathlib import Path as _P
        orig = _P.mkdir

        def _bad_mkdir(self, *a, **kw):
            raise OSError("permission denied")

        # Pre-create parent so the check status is 'warn'
        (self._home / ".tars").mkdir()
        with patch.object(_P, "mkdir", _bad_mkdir):
            r = run_fix("vault")
        self.assertFalse(r.applied)
        self.assertEqual(r.reason, "mkdir_failed")
        self.assertIn("permission denied", r.detail)


# ─── daemon + scheduler fixers (skip-only) ────────────────────────


class TestSkipOnlyFixers(_IsolatedFixer):
    def test_daemon_skip(self) -> None:
        r = run_fix("daemon")
        self.assertTrue(r.skipped)
        self.assertEqual(r.reason, "manual_action_required")
        self.assertIn("tars-daemon install", r.detail)

    def test_scheduler_skip(self) -> None:
        r = run_fix("scheduler")
        self.assertTrue(r.skipped)
        self.assertIn("TARS_SCHEDULER_ENABLED", r.detail)


# ─── run_all_fixes ────────────────────────────────────────────────


class TestRunAllFixes(_IsolatedFixer):
    def test_returns_one_per_registry_entry(self) -> None:
        results = run_all_fixes()
        self.assertEqual(len(results), len(FIX_REGISTRY))
        slugs = {r.slug for r in results}
        self.assertEqual(slugs, set(FIX_REGISTRY.keys()))


# ─── __main__ CLI integration ─────────────────────────────────────


class TestCliFixFlag(_IsolatedFixer):
    def _capture(self, argv):
        from backend.core.doctor import __main__ as dm
        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            rc = dm.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_fix_vault_e2e(self) -> None:
        rc, out, _ = self._capture(["--fix", "vault"])
        self.assertEqual(rc, 0)
        self.assertIn("vault", out)
        self.assertIn("Summary", out)

    def test_fix_unknown_slug(self) -> None:
        rc, out, _ = self._capture(["--fix", "nope-xyz"])
        # Run returns 0 because skipped, not failed
        self.assertEqual(rc, 0)
        self.assertIn("SKIP", out)

    def test_fix_all_via_bare_flag(self) -> None:
        rc, out, _ = self._capture(["--fix"])
        self.assertIn(rc, {0, 2})
        # All registered slugs appear in the output
        for slug in FIX_REGISTRY:
            self.assertIn(slug, out)

    def test_list_shows_fixer_marker(self) -> None:
        rc, out, _ = self._capture(["--list"])
        self.assertEqual(rc, 0)
        self.assertIn("[fixer]", out)

    # ─── Wave 169 — --test-notify CLI ───────────────────────────

    def test_test_notify_no_channels(self) -> None:
        # No env, no --channel → fanout_all returns [] → rc=1 with hint
        os.environ.pop("TARS_DAEMON_FANOUT_CHANNELS", None)
        rc, out, _ = self._capture(["--test-notify"])
        self.assertEqual(rc, 1)
        self.assertIn("no channels configured", out)
        self.assertIn("TARS_DAEMON_FANOUT_CHANNELS", out)

    def test_test_notify_channel_arg_unknown(self) -> None:
        # --channel bogus → fanout_all returns [unknown_channel] → rc=2
        rc, out, _ = self._capture(["--test-notify", "--channel", "bogus"])
        self.assertEqual(rc, 2)
        self.assertIn("bogus", out)
        self.assertIn("unknown_channel", out)

    def test_test_notify_json_mode(self) -> None:
        rc, out, _ = self._capture(
            ["--test-notify", "--channel", "bogus", "--json"]
        )
        parsed = json.loads(out)
        self.assertIn("ok", parsed)
        self.assertIn("results", parsed)
        self.assertFalse(parsed["ok"])

    # ─── Wave 172 — --watch mode ───────────────────────────────

    def test_watch_runs_max_ticks_and_exits(self) -> None:
        # --max-ticks 2 + interval 0.01 → runs twice quickly + exits
        rc, out, _ = self._capture(
            ["--watch", "--max-ticks", "2", "--interval", "0.01"]
        )
        self.assertEqual(rc, 0)
        self.assertIn("TARS doctor — watch mode", out)
        # First tick reports any non-ok rows (vault is missing in
        # the temp home so it's warn)
        self.assertIn("vault", out)

    def test_watch_only_prints_transitions(self) -> None:
        # Run with --max-ticks 1 → only initial non-ok rows print.
        # If we re-run with --max-ticks 2, the second tick should
        # NOT re-print rows whose status didn't change between ticks.
        rc, out, _ = self._capture(
            ["--watch", "--max-ticks", "3", "--interval", "0.01"]
        )
        # vault appears once (initial warn report), not three times
        vault_lines = [line for line in out.splitlines() if "vault" in line and "WARN" in line]
        self.assertEqual(len(vault_lines), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
