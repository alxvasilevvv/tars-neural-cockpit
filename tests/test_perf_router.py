"""Wave 108 -- /api/perf router shape tests.

We exercise the router via stdlib unittest. fastapi.TestClient is
imported lazily; if FastAPI isn't installed (e.g. minimal CI image)
the cases skip gracefully so the suite still runs.

Coverage:

1. ``/api/perf/summary`` returns the expected top-level keys.
2. The latency block contains all 4 tracked ops.
3. ``/api/perf/latency?op=council`` exposes percentile + histogram.
4. ``/api/perf/latency`` rejects bad ``window`` values with 400.
5. Histogram bucket counts match the recorded sample distribution.
6. ``/api/perf/health/connectors`` returns 4 connectors with the
   Wave 108 surface (slack/gmail/calendar/telegram).
"""

from __future__ import annotations

import os
import unittest

from backend.core.observability import latency as latency_mod


try:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    _CLIENT: TestClient | None = TestClient(app)
except Exception:  # pragma: no cover -- fastapi not installed
    _CLIENT = None


def _skip_if_no_client() -> None:
    if _CLIENT is None:
        raise unittest.SkipTest("fastapi.TestClient unavailable in this environment")


class _PerfBase(unittest.TestCase):
    def setUp(self) -> None:
        _skip_if_no_client()
        # Hermetic: clear any leftover samples from earlier tests.
        latency_mod.reset()
        # Prevent the perf summary code from accidentally hitting any
        # disabled-but-stateful side modules.
        os.environ.setdefault("TARS_RECEIPT_STORE", "disabled")
        os.environ.setdefault("TARS_SCHEDULER_STORE", "disabled")
        os.environ.setdefault("TARS_WEBHOOKS_DB_PATH", "/tmp/tars-perf-test.sqlite")

    def tearDown(self) -> None:
        latency_mod.reset()


class SummaryShapeTests(_PerfBase):
    def test_summary_top_level_keys(self) -> None:
        resp = _CLIENT.get("/api/perf/summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        for key in ("as_of", "window_s", "latency", "connectors", "webhooks", "receipts", "jobs", "resources"):
            self.assertIn(key, body)
        self.assertIsInstance(body["latency"], dict)

    def test_summary_includes_all_tracked_ops(self) -> None:
        resp = _CLIENT.get("/api/perf/summary?window=1h")
        body = resp.json()
        for op in ("council", "backtest", "webhook", "connector"):
            self.assertIn(op, body["latency"])
            self.assertIn("count", body["latency"][op])


class LatencyEndpointTests(_PerfBase):
    def test_latency_for_known_op(self) -> None:
        for ms in (10, 25, 50, 100, 200, 400, 800, 1600):
            latency_mod.record("council", ms)
        resp = _CLIENT.get("/api/perf/latency?op=council&window=24h")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["op"], "council")
        self.assertEqual(body["summary"]["count"], 8)
        # P50 of [10..1600] doubling sequence -> middle of 100/200
        self.assertGreater(body["summary"]["p95"], body["summary"]["p50"])
        self.assertEqual(body["summary"]["max"], 1600)
        self.assertIn("buckets", body["histogram"])

    def test_latency_rejects_bad_window(self) -> None:
        resp = _CLIENT.get("/api/perf/latency?op=council&window=abc")
        self.assertEqual(resp.status_code, 400)

    def test_histogram_bucket_counts_match_samples(self) -> None:
        # Buckets default to ..1/5/10/25/50/100/250/500/1000/2500/5000/10000/30000/+inf
        for ms in (3, 7, 15, 60, 800, 50000):
            latency_mod.record("backtest", ms)
        resp = _CLIENT.get("/api/perf/latency?op=backtest")
        body = resp.json()
        buckets = {b["label"]: b["count"] for b in body["histogram"]["buckets"]}
        self.assertEqual(buckets["<=5ms"], 1)        # 3
        self.assertEqual(buckets["<=10ms"], 1)       # 7
        self.assertEqual(buckets["<=25ms"], 1)       # 15
        self.assertEqual(buckets["<=100ms"], 1)      # 60
        self.assertEqual(buckets["<=1000ms"], 1)     # 800
        self.assertEqual(buckets["+inf"], 1)         # 50000


class ConnectorHealthTests(_PerfBase):
    def test_lists_all_four_connectors(self) -> None:
        resp = _CLIENT.get("/api/perf/health/connectors")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        names = {c["name"] for c in body["connectors"]}
        self.assertEqual(names, {"slack", "gmail", "calendar", "telegram"})


class LatencyModuleTests(unittest.TestCase):
    """Module-level tests that don't require FastAPI -- always run.

    Pin the maths the router relies on so a regression in the
    recorder shows up before the integration tests skip.
    """

    def setUp(self) -> None:
        latency_mod.reset()

    def tearDown(self) -> None:
        latency_mod.reset()

    def test_summary_empty_when_no_samples(self) -> None:
        s = latency_mod.summary("council")
        self.assertEqual(s["count"], 0)
        self.assertIsNone(s["p50"])
        self.assertIsNone(s["max"])

    def test_percentile_and_summary_against_known_dataset(self) -> None:
        for ms in (10, 25, 50, 100, 200, 400, 800, 1600):
            latency_mod.record("council", ms)
        s = latency_mod.summary("council")
        self.assertEqual(s["count"], 8)
        self.assertEqual(s["max"], 1600)
        self.assertGreater(s["p99"], s["p95"])
        self.assertGreater(s["p95"], s["p50"])

    def test_histogram_buckets_match_samples(self) -> None:
        for ms in (3, 7, 15, 60, 800, 50000):
            latency_mod.record("backtest", ms)
        h = latency_mod.histogram("backtest")
        labels = {b["label"]: b["count"] for b in h["buckets"]}
        self.assertEqual(labels["<=5ms"], 1)
        self.assertEqual(labels["<=10ms"], 1)
        self.assertEqual(labels["<=25ms"], 1)
        self.assertEqual(labels["<=100ms"], 1)
        self.assertEqual(labels["<=1000ms"], 1)
        self.assertEqual(labels["+inf"], 1)
        self.assertEqual(h["total"], 6)


if __name__ == "__main__":
    unittest.main()
