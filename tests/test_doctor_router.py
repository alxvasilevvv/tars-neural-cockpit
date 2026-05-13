"""Wave 155 — HTTP endpoint coverage for tars-doctor.

These tests use FastAPI's TestClient to hit the router directly,
so they validate the full request/response shape, not just the
underlying doctor module (which has its own tests in
``tests/test_doctor.py``).

Cases (~6):
  - GET /api/doctor returns 200 + {ok, summary, results}
  - The summary counters match the results array
  - results array has one entry per registered check
  - GET /api/doctor/<known-slug> returns 200 + {ok, result}
  - GET /api/doctor/<unknown-slug> returns 404 with known list
  - GET /api/doctor/registry returns slug+label list with no side effects
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestDoctorRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w155-doctor-router-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available in this environment")
            return

        from web_extras.routers.doctor import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    def test_doctor_all_returns_ok_and_summary(self) -> None:
        r = self.client.get("/api/doctor")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("ok", body)
        self.assertIn("summary", body)
        self.assertIn("results", body)
        self.assertIsInstance(body["results"], list)
        self.assertGreater(len(body["results"]), 0)

    def test_summary_counters_match_results(self) -> None:
        body = self.client.get("/api/doctor").json()
        totals = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
        for row in body["results"]:
            totals[row["status"]] = totals.get(row["status"], 0) + 1
        self.assertEqual(body["summary"], totals)

    def test_each_result_has_required_fields(self) -> None:
        body = self.client.get("/api/doctor").json()
        for row in body["results"]:
            self.assertIn("slug", row)
            self.assertIn("label", row)
            self.assertIn("status", row)
            self.assertIn("summary", row)
            self.assertIn("elapsed_ms", row)
            self.assertIn(row["status"], {"ok", "warn", "fail", "skip"})

    def test_single_check_known_slug(self) -> None:
        # 'vault' is always registered; missing dir → warn status
        r = self.client.get("/api/doctor/vault")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["result"]["slug"], "vault")

    def test_single_check_unknown_slug_returns_404(self) -> None:
        r = self.client.get("/api/doctor/nonexistent-xyz")
        self.assertEqual(r.status_code, 404)
        detail = r.json()["detail"]
        self.assertEqual(detail["error"], "unknown_check")
        self.assertEqual(detail["slug"], "nonexistent-xyz")
        self.assertIn("known", detail)
        self.assertIn("vault", detail["known"])

    def test_registry_endpoint(self) -> None:
        r = self.client.get("/api/doctor/registry")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertGreater(body["count"], 0)
        slugs = {e["slug"] for e in body["checks"]}
        # Sanity-check a couple of slugs we know are registered.
        self.assertIn("daemon", slugs)
        self.assertIn("vault", slugs)

    def test_html_page_renders(self) -> None:
        r = self.client.get("/api/doctor/page")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))
        body = r.text
        self.assertIn("<!doctype html>", body.lower())
        self.assertIn("TARS doctor", body)
        # The page fetches /api/doctor in JS
        self.assertIn("/api/doctor", body)
        # And handles the status palette
        self.assertIn("ok", body)
        self.assertIn("warn", body)
        self.assertIn("fail", body)

    # ─── Wave 167 — fix endpoint ───────────────────────────────────

    def test_fix_all_returns_summary(self) -> None:
        r = self.client.post("/api/doctor/fix")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("ok", body)
        self.assertIn("summary", body)
        self.assertIn("results", body)
        # summary fields sum to results length
        s = body["summary"]
        self.assertEqual(
            s["applied"] + s["skipped"] + s["failed"],
            len(body["results"]),
        )

    def test_fix_one_known_slug(self) -> None:
        # vault is a real fixable slug; mkdir will succeed in the
        # test home directory.
        r = self.client.post("/api/doctor/fix/vault")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("result", body)
        self.assertEqual(body["result"]["slug"], "vault")

    def test_fix_unknown_slug_404(self) -> None:
        r = self.client.post("/api/doctor/fix/nonexistent-xyz")
        self.assertEqual(r.status_code, 404)
        detail = r.json()["detail"]
        self.assertEqual(detail["error"], "unknown_check")
        self.assertEqual(detail["slug"], "nonexistent-xyz")
        self.assertIn("fixable", detail)
        # vault should appear in the fixable list
        self.assertIn("vault", detail["fixable"])

    def test_fix_skip_only_slug_still_returns_200(self) -> None:
        # daemon fixer always skips with manual_action_required —
        # that's not a failure, so endpoint should return 200 with
        # ok=True.
        r = self.client.post("/api/doctor/fix/daemon")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["result"]["skipped"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
