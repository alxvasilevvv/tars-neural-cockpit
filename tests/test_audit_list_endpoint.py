"""Wave 123 — tests for GET /api/audit/list.

W122 found the FE Compliance page polled `/api/audit/list` while no
backend router served it (graceful FE 404 fallback was masking the
gap). This wave wires the route into receipts.py as `audit_router`.

Cases:
- empty_returns_count_zero: store is empty -> {ok, count:0, items:[]}
- contains_recorded_receipts: emit N receipts -> count == N
- filtered_by_actor: actor=alice excludes bob's receipts
- pagination_limit_respected: limit=2 returns at most 2
- sig_verified_field_present_per_row: every row has the field
- sig_verified_true_for_clean_chain: signed receipts verify True
- type_filter_excludes_others: type=foo only returns foo
- 503_when_store_disabled: TARS_RECEIPT_STORE=disabled -> 503
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient


def _run(coro):
    return asyncio.run(coro)


class _AuditCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w123-audit-")
        os.environ["TARS_RECEIPT_DIR"] = self._tmp
        os.environ["TARS_RECEIPT_DB_PATH"] = os.path.join(
            self._tmp, "receipts.sqlite"
        )
        os.environ["TARS_RECEIPT_HOST_KEY_PATH"] = os.path.join(
            self._tmp, "host-key.json"
        )
        os.environ.pop("TARS_RECEIPT_STORE", None)
        from backend.core.receipts.store import reset_store
        reset_store()
        from web_extras.app import app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        for k in (
            "TARS_RECEIPT_DIR",
            "TARS_RECEIPT_DB_PATH",
            "TARS_RECEIPT_HOST_KEY_PATH",
            "TARS_RECEIPT_STORE",
        ):
            os.environ.pop(k, None)
        from backend.core.receipts.store import reset_store
        reset_store()

    def _emit(self, n: int, *, actor: str = "user:alice", type: str = "test.event") -> None:
        from backend.core.receipts import record

        async def _go():
            for i in range(n):
                await record(
                    type=type, actor=actor, resource=f"r_{i}",
                    payload={"impact": i},
                )

        _run(_go())


class TestAuditListEmpty(_AuditCase):
    def test_empty_returns_count_zero(self) -> None:
        resp = self.client.get("/api/audit/list")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["items"], [])


class TestAuditListContent(_AuditCase):
    def test_contains_recorded_receipts(self) -> None:
        self._emit(3)
        resp = self.client.get("/api/audit/list")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(len(body["items"]), 3)
        # Required fields per row.
        for item in body["items"]:
            for k in ("id", "ts", "type", "actor", "resource",
                      "impact", "sig_verified"):
                self.assertIn(k, item)


class TestAuditFilters(_AuditCase):
    def test_filtered_by_actor(self) -> None:
        self._emit(2, actor="user:alice")
        self._emit(2, actor="user:bob")
        resp = self.client.get(
            "/api/audit/list", params={"actor": "user:alice"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["count"], 2)
        for item in body["items"]:
            self.assertEqual(item["actor"], "user:alice")

    def test_type_filter_excludes_others(self) -> None:
        self._emit(2, type="foo.bar")
        self._emit(3, type="baz.qux")
        resp = self.client.get(
            "/api/audit/list", params={"type": "foo.bar"},
        )
        body = resp.json()
        self.assertEqual(body["count"], 2)
        for item in body["items"]:
            self.assertEqual(item["type"], "foo.bar")


class TestAuditPagination(_AuditCase):
    def test_pagination_limit_respected(self) -> None:
        self._emit(5)
        resp = self.client.get("/api/audit/list", params={"limit": 2})
        body = resp.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["items"]), 2)


class TestAuditSigVerified(_AuditCase):
    def test_sig_verified_field_present_per_row(self) -> None:
        self._emit(2)
        resp = self.client.get("/api/audit/list")
        body = resp.json()
        for item in body["items"]:
            self.assertIn("sig_verified", item)
            self.assertIsInstance(item["sig_verified"], bool)

    def test_sig_verified_true_on_clean_chain(self) -> None:
        self._emit(2)
        resp = self.client.get("/api/audit/list")
        body = resp.json()
        # Freshly recorded receipts have valid host-key signatures.
        for item in body["items"]:
            self.assertTrue(item["sig_verified"], item)


class TestAuditDisabled(unittest.TestCase):
    def test_503_when_store_disabled(self) -> None:
        os.environ["TARS_RECEIPT_STORE"] = "disabled"
        try:
            from backend.core.receipts.store import reset_store
            reset_store()
            from web_extras.app import app
            client = TestClient(app)
            resp = client.get("/api/audit/list")
            self.assertEqual(resp.status_code, 503)
            self.assertEqual(resp.json().get("detail"), "receipts_disabled")
        finally:
            os.environ.pop("TARS_RECEIPT_STORE", None)
            from backend.core.receipts.store import reset_store
            reset_store()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
