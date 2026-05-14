"""W269 -- tests for the 60-sec voice-first onboarding telemetry router.

Covers the four cases called out in the wave brief:

1. ``test_event_logged_with_timing`` -- POST /api/onboarding/event
   persists a row with the right session_id + elapsed_ms.
2. ``test_stats_aggregate_correctly`` -- two sessions, one that
   completes step 5 and one that stalls at step 3, yield the
   expected completion counters + median/p95 TTFV.
3. ``test_skip_endpoint_marks_session`` -- POST /api/onboarding/skip
   writes a step=0 row, which stats() counts as skipped.
4. ``test_drop_off_recovery_triggers_re_prompt`` -- when the
   frontend reports ``meta.dropoff=True`` (the 20s pause hook), the
   row still lands and the meta carries the flag for downstream
   re-prompt analytics.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient


class _OnboardingCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w269-onb-")
        self._db = os.path.join(self._tmp, "onboarding.sqlite")
        os.environ["TARS_ONBOARDING_DB"] = self._db
        # Ensure a clean import per case -- the router pulls TARS_ONBOARDING_DB
        # at call-time inside _db_path() so a simple env swap is enough.
        from web_extras.app import app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("TARS_ONBOARDING_DB", None)
        import shutil
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # ---- helpers ------------------------------------------------

    def _row_count(self) -> int:
        if not os.path.exists(self._db):
            return 0
        with sqlite3.connect(self._db) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM onboarding_events"
            ).fetchone()[0]

    # ---- cases --------------------------------------------------

    def test_event_logged_with_timing(self) -> None:
        body = {"step": 1, "elapsed_ms": 4200, "session_id": "s-alpha"}
        r = self.client.post("/api/onboarding/event", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["session_id"], "s-alpha")
        self.assertEqual(d["step"], 1)

        # Row landed in SQLite with the elapsed_ms we sent.
        with sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT session_id, step, elapsed_ms, completed "
                "FROM onboarding_events"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ("s-alpha", 1, 4200, 0))

    def test_stats_aggregate_correctly(self) -> None:
        # Session A finishes all 5 steps in 55_000 ms total.
        for step, elapsed in [(1, 5000), (2, 12000), (3, 24000),
                              (4, 40000), (5, 55000)]:
            r = self.client.post(
                "/api/onboarding/event",
                json={
                    "step": step,
                    "elapsed_ms": elapsed,
                    "completed": True,
                    "session_id": "sess-A",
                },
            )
            self.assertEqual(r.status_code, 200, r.text)

        # Session B stalls at step 3.
        for step, elapsed in [(1, 4000), (2, 14000), (3, 26000)]:
            r = self.client.post(
                "/api/onboarding/event",
                json={
                    "step": step,
                    "elapsed_ms": elapsed,
                    "completed": True,
                    "session_id": "sess-B",
                },
            )
            self.assertEqual(r.status_code, 200, r.text)

        s = self.client.get("/api/onboarding/stats").json()
        self.assertEqual(s["total_sessions_started"], 2)
        self.assertEqual(s["total_sessions_completed"], 1)
        self.assertEqual(s["total_sessions_skipped"], 0)
        # Only Session A finished -> median == p95 == its elapsed.
        self.assertEqual(s["median_ttfv_ms"], 55000)
        self.assertEqual(s["p95_ttfv_ms"], 55000)
        # Step 1 reached by both, step 5 completed by exactly one.
        self.assertEqual(s["steps"]["1"]["reached"], 2)
        self.assertEqual(s["steps"]["5"]["completed"], 1)
        self.assertEqual(s["steps"]["3"]["reached"], 2)

    def test_skip_endpoint_marks_session(self) -> None:
        r = self.client.post(
            "/api/onboarding/skip",
            json={"session_id": "skipper", "elapsed_ms": 2200,
                  "reason": "user closed modal"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d["skipped"])
        self.assertEqual(d["session_id"], "skipper")

        # Stats counts the skip but not completion.
        s = self.client.get("/api/onboarding/stats").json()
        self.assertEqual(s["total_sessions_skipped"], 1)
        self.assertEqual(s["total_sessions_completed"], 0)
        self.assertEqual(s["total_sessions_started"], 1)

    def test_drop_off_recovery_triggers_re_prompt(self) -> None:
        # The frontend's 20s pause-watcher posts an event with
        # meta.dropoff=True so we can later compute "stalled-but-
        # recovered" funnel ratios. The router must accept that
        # opaque meta dict verbatim.
        r = self.client.post(
            "/api/onboarding/event",
            json={
                "step": 2,
                "elapsed_ms": 23000,
                "completed": False,
                "session_id": "stall-1",
                "meta": {"dropoff": True, "reprompt_count": 1},
            },
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Verify the meta JSON round-tripped intact in the DB.
        import json as _json
        with sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT meta FROM onboarding_events WHERE session_id=?",
                ("stall-1",),
            ).fetchone()
        self.assertIsNotNone(row)
        meta = _json.loads(row[0])
        self.assertTrue(meta.get("dropoff"))
        self.assertEqual(meta.get("reprompt_count"), 1)


if __name__ == "__main__":
    unittest.main()
