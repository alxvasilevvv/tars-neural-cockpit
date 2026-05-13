"""Wave 157 — coverage for backend.core.daemon.doctor_watch.

The watcher is the glue between Background daemon (W152/153) and
the doctor (W154-156): every Nth tick it runs run_all() + diffs
against the previous tick's statuses + emits a webhook event on
any drift.

Tests focus on:
  - Enable / disable via TARS_DAEMON_DOCTOR_ENABLED
  - Tick scheduling via TARS_DAEMON_DOCTOR_EVERY_N
  - diff_statuses: first-time slug = no change reported
  - diff_statuses: same status = no change
  - diff_statuses: ok → warn = change with from/to
  - run_once respects disabled mode
  - run_once with a forced cache transition emits the webhook
  - The webhook payload shape is correct
  - The watcher swallows exceptions in run_all
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.core.daemon import doctor_watch
from backend.core.doctor.checks import CheckResult


def _run(coro):
    return asyncio.run(coro)


class _IsolatedWatch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w157-watch-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)
        for k in ("TARS_DAEMON_DOCTOR_ENABLED", "TARS_DAEMON_DOCTOR_EVERY_N"):
            os.environ.pop(k, None)
        doctor_watch._reset_for_tests()

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        doctor_watch._reset_for_tests()


# ─── env / scheduling ──────────────────────────────────────────────


class TestEnableFlag(_IsolatedWatch):
    def test_disabled_by_default(self) -> None:
        self.assertFalse(doctor_watch.is_enabled())

    def test_enabled_via_env(self) -> None:
        os.environ["TARS_DAEMON_DOCTOR_ENABLED"] = "1"
        self.assertTrue(doctor_watch.is_enabled())
        os.environ["TARS_DAEMON_DOCTOR_ENABLED"] = "yes"
        self.assertTrue(doctor_watch.is_enabled())
        os.environ["TARS_DAEMON_DOCTOR_ENABLED"] = "0"
        self.assertFalse(doctor_watch.is_enabled())


class TestTickScheduling(_IsolatedWatch):
    def test_should_run_when_disabled_returns_false(self) -> None:
        self.assertFalse(doctor_watch.should_run_this_tick(1))
        self.assertFalse(doctor_watch.should_run_this_tick(100))

    def test_should_run_every_tick_by_default(self) -> None:
        os.environ["TARS_DAEMON_DOCTOR_ENABLED"] = "1"
        for n in (1, 2, 5, 10):
            self.assertTrue(doctor_watch.should_run_this_tick(n))

    def test_should_run_every_n(self) -> None:
        os.environ["TARS_DAEMON_DOCTOR_ENABLED"] = "1"
        os.environ["TARS_DAEMON_DOCTOR_EVERY_N"] = "5"
        # 5, 10, 15… fire; 1, 2, 3, 4 don't.
        self.assertFalse(doctor_watch.should_run_this_tick(1))
        self.assertFalse(doctor_watch.should_run_this_tick(4))
        self.assertTrue(doctor_watch.should_run_this_tick(5))
        self.assertTrue(doctor_watch.should_run_this_tick(10))
        self.assertFalse(doctor_watch.should_run_this_tick(11))


# ─── diff_statuses ─────────────────────────────────────────────────


class TestDiffStatuses(_IsolatedWatch):
    def _mk(self, slug: str, status: str, summary: str = "") -> CheckResult:
        return CheckResult(slug=slug, label=slug, status=status, summary=summary)

    def test_first_time_slug_is_not_a_change(self) -> None:
        results = [self._mk("a", "ok"), self._mk("b", "warn")]
        changes = doctor_watch.diff_statuses(results, cached={})
        self.assertEqual(changes, [])

    def test_same_status_no_change(self) -> None:
        results = [self._mk("a", "ok")]
        changes = doctor_watch.diff_statuses(results, cached={"a": "ok"})
        self.assertEqual(changes, [])

    def test_ok_to_warn_is_reported(self) -> None:
        results = [self._mk("a", "warn", "heartbeat stale")]
        changes = doctor_watch.diff_statuses(results, cached={"a": "ok"})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["slug"], "a")
        self.assertEqual(changes[0]["from"], "ok")
        self.assertEqual(changes[0]["to"], "warn")
        self.assertEqual(changes[0]["summary"], "heartbeat stale")

    def test_multiple_transitions(self) -> None:
        results = [
            self._mk("a", "fail"),
            self._mk("b", "ok"),
            self._mk("c", "warn"),
        ]
        cached = {"a": "ok", "b": "warn", "c": "warn"}
        changes = doctor_watch.diff_statuses(results, cached=cached)
        # a: ok→fail, b: warn→ok, c: no change.
        self.assertEqual(len(changes), 2)
        slugs = {c["slug"] for c in changes}
        self.assertEqual(slugs, {"a", "b"})


# ─── run_once ──────────────────────────────────────────────────────


class TestRunOnce(_IsolatedWatch):
    def test_disabled_run_short_circuits(self) -> None:
        out = _run(doctor_watch.run_once())
        self.assertFalse(out["ran"])
        self.assertEqual(out["reason"], "disabled")

    def test_forced_run_with_no_changes(self) -> None:
        # First call: cache empty, so no transitions reported.
        out = _run(doctor_watch.run_once(force=True))
        self.assertTrue(out["ran"])
        self.assertEqual(out["changes"], [])
        self.assertFalse(out["emitted"])
        # State updated.
        s = doctor_watch.get_state()
        self.assertEqual(s.runs, 1)
        self.assertGreater(len(s.last_status_by_slug), 0)

    def test_forced_run_with_transition_emits(self) -> None:
        # Pre-load the cache with statuses that differ from what
        # run_all will return; then force-run and check the emitter
        # was called.
        s = doctor_watch.get_state()
        # Use 'vault' which we know is registered.
        s.last_status_by_slug["vault"] = "ok"  # missing dir → warn now

        mock_emit = AsyncMock(return_value=None)
        with patch("backend.core.webhooks.emit", new=mock_emit, create=True):
            out = _run(doctor_watch.run_once(force=True))

        self.assertTrue(out["ran"])
        # vault is missing in the temp home → status is 'warn' → transition.
        self.assertTrue(any(c["slug"] == "vault" for c in out["changes"]))
        # emit() should have been awaited at least once.
        self.assertTrue(mock_emit.await_count >= 1)
        # Payload shape: event_type='doctor.status_changed' + data dict.
        call_kwargs = mock_emit.await_args.kwargs
        self.assertEqual(call_kwargs.get("event_type"), "doctor.status_changed")
        data = call_kwargs.get("data", {})
        self.assertIn("changes", data)
        self.assertIn("summary", data)
        self.assertIn("results", data)
        self.assertIn("fired_at", data)

    def test_emit_failure_swallowed(self) -> None:
        s = doctor_watch.get_state()
        s.last_status_by_slug["vault"] = "ok"

        mock_emit = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("backend.core.webhooks.emit", new=mock_emit, create=True):
            out = _run(doctor_watch.run_once(force=True))

        # Watcher still reports 'ran=True' + 'emitted=False'.
        self.assertTrue(out["ran"])
        self.assertFalse(out["emitted"])

    def test_run_all_failure_handled(self) -> None:
        with patch("backend.core.doctor.run_all", side_effect=RuntimeError("doc fail")):
            out = _run(doctor_watch.run_once(force=True))
        self.assertFalse(out["ran"])
        self.assertIn("run_all_failed", out.get("error", ""))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
