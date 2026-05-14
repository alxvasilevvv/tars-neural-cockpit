"""W241 — pytest coverage for the background-agents tray router.

Five cases mirror the spec:

1. Empty list — no tasks created, ``GET /api/bg_agents`` returns ``[]``.
2. ``POST /start`` creates a row that ``GET /api/bg_agents`` surfaces.
3. ``POST /{id}/cancel`` transitions the row to ``cancelled``.
4. ``update_task_status`` persists arbitrary state transitions across
   list + single GET (round-trip through SQLite, not just in-mem).
5. ``GET /api/bg_agents/{id}`` returns the full event log.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestBgAgentsRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w241-bg-agents-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        # Point the bg-agents store at a clean per-test SQLite file.
        self._db = self._home / ".tars" / "bg_agents.sqlite"
        os.environ["HOME"] = str(self._home)
        os.environ["TARS_BG_AGENTS_DB_PATH"] = str(self._db)
        os.environ.pop("TARS_BG_AGENTS_STORE", None)

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers import bg_agents as bg

        bg.reset_singleton_for_tests()
        self._bg_module = bg

        app = FastAPI()
        app.include_router(bg.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            self._bg_module.reset_singleton_for_tests()
        except Exception:
            pass
        os.environ.pop("TARS_BG_AGENTS_DB_PATH", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # ---- 1: empty list -----------------------------------------------------

    def test_empty_list(self) -> None:
        r = self.client.get("/api/bg_agents")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)
        self.assertEqual(body, [])

    # ---- 2: start creates a row -------------------------------------------

    def test_start_creates_row(self) -> None:
        payload = {
            "agent_id": "agt-alpha",
            "pack": "research",
            "instructions": "Summarise the meeet.world litepaper.",
            "params": {"depth": "shallow"},
        }
        r = self.client.post("/api/bg_agents/start", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"])
        tid = body["task_id"]
        self.assertTrue(tid)
        # Task row visible via list
        listing = self.client.get("/api/bg_agents").json()
        ids = [row["id"] for row in listing]
        self.assertIn(tid, ids)
        row = next(r for r in listing if r["id"] == tid)
        self.assertEqual(row["agent_id"], "agt-alpha")
        self.assertEqual(row["pack"], "research")
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["progress_pct"], 0)
        self.assertIsNotNone(row["trace_id"])

    # ---- 3: cancel transitions ---------------------------------------------

    def test_cancel_transitions_to_cancelled(self) -> None:
        created = self.client.post(
            "/api/bg_agents/start",
            json={
                "agent_id": "agt-beta",
                "pack": "advisor",
                "instructions": "draft daily summary",
            },
        ).json()
        tid = created["task_id"]
        r = self.client.post(f"/api/bg_agents/{tid}/cancel")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["task"]["status"], "cancelled")
        # Second cancel → 409 (terminal)
        r2 = self.client.post(f"/api/bg_agents/{tid}/cancel")
        self.assertEqual(r2.status_code, 409)
        # Single GET also reflects the terminal state
        single = self.client.get(f"/api/bg_agents/{tid}").json()
        self.assertEqual(single["status"], "cancelled")

    # ---- 4: state transitions persist -------------------------------------

    def test_state_transitions_persist(self) -> None:
        import asyncio

        created = self.client.post(
            "/api/bg_agents/start",
            json={
                "agent_id": "agt-gamma",
                "pack": "scraper",
                "instructions": "scrape today's HN front page",
            },
        ).json()
        tid = created["task_id"]

        store = self._bg_module.get_bg_store()
        # Push it through running → awaiting_input → running → done
        asyncio.run(store.update_task_status(
            tid, progress_pct=30, current_step="fetching",
            event={"kind": "step", "step": "fetching", "pct": 30},
        ))
        asyncio.run(store.update_task_status(
            tid, status="awaiting_input", current_step="confirm",
            event={"kind": "hil", "step": "confirm"},
        ))
        asyncio.run(store.update_task_status(
            tid, status="running", current_step="parsing", progress_pct=70,
            event={"kind": "step", "step": "parsing", "pct": 70},
        ))
        asyncio.run(store.update_task_status(
            tid, status="done", progress_pct=100,
            current_step="done",
            result_summary="Fetched 30 stories, 2 flagged for review.",
            event={"kind": "completed", "step": "done", "pct": 100},
        ))

        # Forget the cached singleton, re-instantiate — the row must
        # survive the SQLite round-trip.
        self._bg_module.reset_singleton_for_tests()
        listing = self.client.get("/api/bg_agents").json()
        row = next(r for r in listing if r["id"] == tid)
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["progress_pct"], 100)
        self.assertEqual(row["current_step"], "done")
        self.assertIn("30 stories", row["result_summary"])

    # ---- 5: single GET returns event log ----------------------------------

    def test_single_get_returns_event_log(self) -> None:
        import asyncio

        created = self.client.post(
            "/api/bg_agents/start",
            json={
                "agent_id": "agt-delta",
                "pack": "doc",
                "instructions": "format the Q1 OKRs as a doc",
            },
        ).json()
        tid = created["task_id"]
        store = self._bg_module.get_bg_store()
        asyncio.run(store.update_task_status(
            tid, progress_pct=50, current_step="drafting",
            event={"kind": "step", "step": "drafting", "pct": 50, "msg": "halfway"},
        ))
        asyncio.run(store.update_task_status(
            tid, status="done", progress_pct=100, current_step="done",
            result_summary="Doc ready in /tmp/q1-okrs.docx",
            event={"kind": "completed", "step": "done", "pct": 100},
        ))

        r = self.client.get(f"/api/bg_agents/{tid}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["id"], tid)
        self.assertEqual(body["status"], "done")
        self.assertIn("events", body)
        events = body["events"]
        self.assertGreaterEqual(len(events), 3)  # started + 2 updates + completed
        kinds = [e.get("kind") for e in events]
        self.assertIn("started", kinds)
        self.assertIn("step", kinds)
        self.assertIn("completed", kinds)
        # Unknown id → 404
        r404 = self.client.get("/api/bg_agents/does-not-exist")
        self.assertEqual(r404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
