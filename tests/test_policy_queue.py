"""Tests for the Wave 101 ``/inbox`` policy queue surface.

Covers the new endpoints layered on top of the existing ``/api/policy``
router:

- ``GET  /api/policy/queue``                      — listing + filters.
- ``GET  /api/policy/queue/{id}``                 — single-row detail.
- ``POST /api/policy/deny/{id}``                  — deny w/ required reason.
- ``POST /api/policy/queue/bulk-approve``         — bulk + safety check.
- ``GET/POST /api/policy/auto-approve-threshold`` — Settings toggle.

Stdlib ``unittest`` keeps the suite buildable without pytest async
plugins on the operator's local machine.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.policy import store as _policy_store_mod


def _async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class PolicyQueueTestCase(unittest.TestCase):
    """Each test gets its own SQLite DB + fresh PolicyStore singleton."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db = Path(self._tmp.name) / "policy.sqlite"
        # Park the singleton against our temp DB.
        os.environ["MEEET_STORE_PATH"] = str(self._db)
        os.environ["TARS_RECEIPT_STORE"] = "disabled"
        _policy_store_mod._SINGLETON = _policy_store_mod.PolicyStore(str(self._db))

        # Build a minimal app that mounts only the policy router so
        # the test boot doesn't require the full web_extras lifespan
        # (meeet bridge, scheduler, etc).
        from web_extras.routers import policy as policy_router

        self._app = FastAPI()
        self._app.include_router(policy_router.router)
        self._client = TestClient(self._app)

    def tearDown(self) -> None:
        self._client.close()
        _policy_store_mod._SINGLETON = None
        self._tmp.cleanup()
        os.environ.pop("MEEET_STORE_PATH", None)
        os.environ.pop("TARS_RECEIPT_STORE", None)
        os.environ.pop("TARS_HIL_AUTO_APPROVE_USD", None)

    def _create(self, **overrides: Any) -> str:
        store = _policy_store_mod._SINGLETON
        kwargs: dict[str, Any] = dict(
            slug="wallet",
            action_id="sign_message",
            args={"resource": "0xabcd"},
            ttl_s=300.0,
            requested_by="op",
            trace_id=None,
            thread_id=None,
        )
        kwargs.update(overrides)
        return _async(store.create(**kwargs))

    # ------------------------------------------------------------------
    # 1. queue listing — empty + populated
    # ------------------------------------------------------------------

    def test_queue_empty_returns_zero(self) -> None:
        r = self._client.get("/api/policy/queue")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["items"], [])

    def test_queue_populated_returns_normalised_rows(self) -> None:
        tok = self._create(slug="outreach", action_id="send", args={"resource": "LP-Q4", "amount_usd": 0})
        r = self._client.get("/api/policy/queue")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 1)
        item = body["items"][0]
        self.assertEqual(item["id"], tok)
        self.assertEqual(item["category"], "outreach")
        self.assertEqual(item["resource"], "LP-Q4")
        # Action is the fully-qualified slug.action_id.
        self.assertEqual(item["action"], "outreach.send")

    # ------------------------------------------------------------------
    # 2. category filter
    # ------------------------------------------------------------------

    def test_queue_filter_by_category(self) -> None:
        self._create(slug="wallet", action_id="sign_message")
        self._create(slug="outreach", action_id="send")
        r = self._client.get("/api/policy/queue?type=wallet")
        body = r.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["category"], "wallet")

    # ------------------------------------------------------------------
    # 3. count_only path (Nav badge cheap mode)
    # ------------------------------------------------------------------

    def test_queue_count_only_omits_items(self) -> None:
        self._create()
        self._create()
        r = self._client.get("/api/policy/queue?count_only=true")
        body = r.json()
        self.assertEqual(body["count"], 2)
        self.assertNotIn("items", body)

    # ------------------------------------------------------------------
    # 4. detail endpoint
    # ------------------------------------------------------------------

    def test_queue_detail_returns_full_payload(self) -> None:
        tok = self._create(args={"resource": "0xabcd", "amount_usd": 1500})
        r = self._client.get(f"/api/policy/queue/{tok}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["item"]["id"], tok)
        self.assertEqual(body["item"]["dollar_impact"], 1500.0)

    def test_queue_detail_404_for_unknown(self) -> None:
        r = self._client.get("/api/policy/queue/cfm_does_not_exist")
        self.assertEqual(r.status_code, 404)

    # ------------------------------------------------------------------
    # 5. deny — reason is required
    # ------------------------------------------------------------------

    def test_deny_requires_reason(self) -> None:
        tok = self._create()
        r = self._client.post(f"/api/policy/deny/{tok}", json={})
        self.assertEqual(r.status_code, 422)
        self.assertIn("reason_required", r.json()["detail"])

    def test_deny_resolves_with_reason(self) -> None:
        tok = self._create()
        r = self._client.post(f"/api/policy/deny/{tok}", json={"reason": "wrong recipient"})
        self.assertEqual(r.status_code, 200)
        # Re-fetching now returns it under "all" but no longer under "pending".
        pend = self._client.get("/api/policy/queue?status=pending").json()
        self.assertEqual(pend["count"], 0)
        rec = self._client.get("/api/policy/queue?status=all").json()
        self.assertEqual(rec["count"], 1)
        self.assertEqual(rec["items"][0]["status"], "cancelled")

    # ------------------------------------------------------------------
    # 6. bulk approve — happy path + safety reject
    # ------------------------------------------------------------------

    def test_bulk_approve_happy_path(self) -> None:
        tok_a = self._create()
        tok_b = self._create(slug="outreach", action_id="send", args={"resource": "follow-up"})
        r = self._client.post(
            "/api/policy/queue/bulk-approve",
            json={"ids": [tok_a, tok_b], "reason": "QA sweep"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["approved_count"], 2)
        self.assertEqual(body["rejected_count"], 0)

    def test_bulk_approve_rejects_high_dollar_actions(self) -> None:
        tok_low = self._create(args={"resource": "x", "amount_usd": 500})
        tok_huge = self._create(
            slug="algotrade",
            action_id="live_promote",
            args={"resource": "ma_cross", "amount_usd": 50_000},
        )
        r = self._client.post(
            "/api/policy/queue/bulk-approve",
            json={"ids": [tok_low, tok_huge]},
        )
        body = r.json()
        self.assertEqual(body["approved_count"], 1)
        self.assertEqual(body["rejected_count"], 1)
        self.assertEqual(body["rejected"][0]["token"], tok_huge)
        self.assertEqual(body["rejected"][0]["reason"], "exceeds_bulk_ceiling")

    def test_bulk_approve_requires_ids(self) -> None:
        r = self._client.post("/api/policy/queue/bulk-approve", json={"ids": []})
        self.assertEqual(r.status_code, 422)

    # ------------------------------------------------------------------
    # 7. auto-approve threshold get / set
    # ------------------------------------------------------------------

    def test_auto_approve_threshold_default_zero(self) -> None:
        r = self._client.get("/api/policy/auto-approve-threshold")
        self.assertEqual(r.json()["threshold_usd"], 0.0)

    def test_auto_approve_threshold_round_trip(self) -> None:
        r = self._client.post(
            "/api/policy/auto-approve-threshold", json={"threshold_usd": 25}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["threshold_usd"], 25.0)
        r2 = self._client.get("/api/policy/auto-approve-threshold")
        self.assertEqual(r2.json()["threshold_usd"], 25.0)

    def test_auto_approve_threshold_rejects_negative(self) -> None:
        r = self._client.post(
            "/api/policy/auto-approve-threshold", json={"threshold_usd": -5}
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
