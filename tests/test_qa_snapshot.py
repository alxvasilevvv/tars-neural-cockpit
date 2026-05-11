"""Wave 126 — tests for scripts.qa_agent.snapshot."""

from __future__ import annotations

import json
import re
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.qa_agent.snapshot import (
    SNAPSHOT_VERSION,
    aggregate_incidents,
    build_snapshot,
    load_snapshot,
    maybe_commit_snapshot,
    should_commit_snapshot,
    write_snapshot,
)


@dataclass
class _ProbeStub:
    """Lightweight stand-in for ``probes.Probe`` — only the attrs the
    snapshot writer reads (``name``, ``status``)."""

    name: str
    status: str
    detail: str = ""
    duration_ms: int = 0
    category: str = "test"
    evidence: dict = field(default_factory=dict)


class BuildSnapshotShape(unittest.TestCase):
    def test_produces_expected_top_level_shape(self):
        probes = [
            _ProbeStub("a", "pass"),
            _ProbeStub("b", "pass"),
        ]
        history = {"probes": {"a": ["pass", "pass"], "b": ["pass"]}}
        now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        snap = build_snapshot(probes, history, now=now)

        self.assertEqual(snap["version"], SNAPSHOT_VERSION)
        self.assertEqual(snap["overall_status"], "green")
        self.assertEqual(snap["generated_at"], "2026-05-11T12:00:00+00:00")
        self.assertEqual(len(snap["probes"]), 2)
        # Each public probe row has the documented keys.
        for row in snap["probes"]:
            for key in (
                "name",
                "status",
                "last_status",
                "last_success_at",
                "last_failure_at",
                "failure_count_24h",
                "uptime_7d_pct",
            ):
                self.assertIn(key, row)
        # No fails → no incidents.
        self.assertEqual(snap["incidents"], [])

    def test_iso8601_generated_at(self):
        snap = build_snapshot([_ProbeStub("a", "pass")])
        # Must round-trip through fromisoformat.
        parsed = datetime.fromisoformat(snap["generated_at"])
        self.assertIsNotNone(parsed.tzinfo, "generated_at must be tz-aware")
        # And must have second precision (no microseconds).
        self.assertNotIn(".", snap["generated_at"])

    def test_overall_red_when_any_probe_fails(self):
        probes = [
            _ProbeStub("a", "pass"),
            _ProbeStub("b", "fail"),
            _ProbeStub("c", "warn"),
        ]
        snap = build_snapshot(probes)
        self.assertEqual(snap["overall_status"], "red")

    def test_overall_yellow_when_only_warns(self):
        probes = [_ProbeStub("a", "pass"), _ProbeStub("b", "warn")]
        snap = build_snapshot(probes)
        self.assertEqual(snap["overall_status"], "yellow")

    def test_skip_does_not_taint_overall(self):
        # Skipped probes (e.g. DNS not yet propagated) shouldn't paint
        # the public dashboard yellow/red — they're a "we didn't try"
        # signal, not a failure.
        probes = [_ProbeStub("a", "pass"), _ProbeStub("b", "skip")]
        snap = build_snapshot(probes)
        self.assertEqual(snap["overall_status"], "green")
        # Skip rows project to green bucket but preserve raw last_status
        # so the FE can still distinguish in tooltips.
        skip_row = next(r for r in snap["probes"] if r["name"] == "b")
        self.assertEqual(skip_row["status"], "green")
        self.assertEqual(skip_row["last_status"], "skip")


class UptimeAndFailureCounts(unittest.TestCase):
    def test_uptime_pct_from_history(self):
        # 8 of 10 entries are pass → 80% uptime.
        series = ["pass"] * 8 + ["fail", "fail"]
        history = {"probes": {"x": series}}
        snap = build_snapshot([_ProbeStub("x", "pass")], history)
        row = snap["probes"][0]
        self.assertEqual(row["uptime_7d_pct"], 80.0)
        self.assertEqual(row["failure_count_24h"], 2)

    def test_skips_excluded_from_uptime(self):
        # Skips don't count either way — pure pass/fail/warn ratio.
        series = ["pass", "skip", "skip", "pass"]
        history = {"probes": {"x": series}}
        snap = build_snapshot([_ProbeStub("x", "pass")], history)
        self.assertEqual(snap["probes"][0]["uptime_7d_pct"], 100.0)


class AggregateIncidents(unittest.TestCase):
    def test_no_incidents_when_all_green(self):
        rows = [{"name": "a", "status": "green"}]
        self.assertEqual(aggregate_incidents(rows), [])

    def test_incident_emitted_when_any_red(self):
        rows = [
            {"name": "a", "status": "green"},
            {"name": "http.route/workshop", "status": "red"},
            {"name": "bundle.imports", "status": "red"},
        ]
        now = datetime(2026, 5, 10, 9, 30, 0, tzinfo=timezone.utc)
        out = aggregate_incidents(rows, now=now)
        self.assertEqual(len(out), 1)
        inc = out[0]
        # Affected list is sorted and includes only red probes.
        self.assertEqual(inc["probes_affected"], ["bundle.imports", "http.route/workshop"])
        # Stable id derived from date + first-affected so the FE can
        # de-dupe successive 5-min runs of the same outage.
        self.assertTrue(inc["id"].startswith("incident-2026-05-10-"))
        self.assertIsNone(inc["resolved_at"])
        self.assertIn("2 probes failing", inc["summary"])


class CommitDecision(unittest.TestCase):
    def _snap(self, status: str, ts: str, red_names=()):
        return {
            "version": 1,
            "generated_at": ts,
            "overall_status": status,
            "probes": [{"name": n, "status": "red"} for n in red_names],
            "incidents": [],
        }

    def test_first_snapshot_always_commits(self):
        snap = self._snap("green", "2026-05-11T12:00:00+00:00")
        commit, reason = should_commit_snapshot(snap, prev_snapshot=None)
        self.assertTrue(commit)
        self.assertEqual(reason, "first_snapshot")

    def test_status_change_commits(self):
        prev = self._snap("green", "2026-05-11T11:55:00+00:00")
        new = self._snap("red", "2026-05-11T12:00:00+00:00", red_names=("a",))
        commit, reason = should_commit_snapshot(new, prev)
        self.assertTrue(commit)
        self.assertIn("status_change", reason)

    def test_no_change_within_interval_skips(self):
        prev = self._snap("green", "2026-05-11T11:58:00+00:00")
        new = self._snap("green", "2026-05-11T12:00:00+00:00")
        now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        commit, reason = should_commit_snapshot(new, prev, now=now, interval_s=30 * 60)
        self.assertFalse(commit)
        self.assertEqual(reason, "no_change_within_interval")

    def test_interval_elapsed_commits(self):
        prev = self._snap("green", "2026-05-11T11:00:00+00:00")
        new = self._snap("green", "2026-05-11T12:00:00+00:00")
        now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        commit, reason = should_commit_snapshot(new, prev, now=now, interval_s=30 * 60)
        self.assertTrue(commit)
        self.assertEqual(reason, "interval")

    def test_red_probe_set_change_commits(self):
        # Same overall_status but different failing probe → still
        # interesting enough to publish.
        prev = self._snap("red", "2026-05-11T11:58:00+00:00", red_names=("a",))
        new = self._snap("red", "2026-05-11T12:00:00+00:00", red_names=("b",))
        now = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        commit, reason = should_commit_snapshot(new, prev, now=now, interval_s=30 * 60)
        self.assertTrue(commit)
        self.assertEqual(reason, "probes_changed")


class RoundTrip(unittest.TestCase):
    def test_write_then_load_returns_same_dict(self):
        snap = build_snapshot([_ProbeStub("a", "pass")])
        with TemporaryDirectory() as td:
            path = Path(td) / "qa-snapshot.json"
            self.assertTrue(write_snapshot(snap, path))
            loaded = load_snapshot(path)
            self.assertEqual(loaded, snap)

    def test_load_returns_none_on_missing_file(self):
        with TemporaryDirectory() as td:
            self.assertIsNone(load_snapshot(Path(td) / "nope.json"))

    def test_maybe_commit_writes_and_signals_first(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "qa-snapshot.json"
            snap = build_snapshot([_ProbeStub("a", "pass")])
            outcome = maybe_commit_snapshot(snap, snapshot_path=path)
            self.assertTrue(outcome["written"])
            self.assertTrue(outcome["commit"])
            self.assertEqual(outcome["reason"], "first_snapshot")
            # Second call with identical snapshot but old timestamp —
            # should NOT commit (no change, within interval).
            now = datetime.fromisoformat(snap["generated_at"]) + timedelta(minutes=1)
            outcome2 = maybe_commit_snapshot(
                snap, snapshot_path=path, now=now, interval_s=30 * 60
            )
            self.assertFalse(outcome2["commit"])


if __name__ == "__main__":
    unittest.main()
