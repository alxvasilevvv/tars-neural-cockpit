"""W255 -- tests for the receipt-anchored audit explorer router.

Covers:

1. ``test_timeline_reverse_chronological_order`` -- timeline returns
   receipts newest-first.
2. ``test_timeline_filter_by_kind`` -- ``kind=`` filter excludes
   other types.
3. ``test_verify_endpoint_shape`` -- /api/audit/verify on a real
   receipt returns the documented keys and signature_ok=True for a
   clean chain.
4. ``test_export_json_returns_immediate_file`` -- POST
   /api/receipts/export with format=json yields a downloadable
   file via GET /api/receipts/export/{job_id}.
5. ``test_export_pdf_succeeds_or_returns_helpful_error`` -- PDF path
   either ships a real PDF (when reportlab is installed) or returns
   a 501 with the install hint.
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
        self._tmp = tempfile.mkdtemp(prefix="tars-w255-audit-")
        os.environ["TARS_RECEIPT_DIR"] = self._tmp
        os.environ["TARS_RECEIPT_DB_PATH"] = os.path.join(self._tmp, "receipts.sqlite")
        os.environ["TARS_RECEIPT_HOST_KEY_PATH"] = os.path.join(self._tmp, "host-key.json")
        os.environ["TARS_EXPORTS_DIR"] = os.path.join(self._tmp, "exports")
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
            "TARS_EXPORTS_DIR",
            "TARS_RECEIPT_STORE",
        ):
            os.environ.pop(k, None)
        from backend.core.receipts.store import reset_store
        reset_store()

    def _emit_seq(self, kinds_actors):
        """Emit N receipts; ``kinds_actors`` is a list of ``(kind, actor)``."""
        from backend.core.receipts import record

        async def _go():
            out = []
            for i, (kind, actor) in enumerate(kinds_actors):
                r = await record(
                    type=kind,
                    actor=actor,
                    resource=f"r_{i}",
                    payload={"summary": f"step {i}", "i": i},
                )
                out.append(r)
            return out

        return _run(_go())


class TestAuditTimelineOrder(_AuditCase):
    def test_timeline_reverse_chronological_order(self) -> None:
        rs = self._emit_seq([
            ("composer", "user:alice"),
            ("composer", "user:alice"),
            ("voice", "user:alice"),
            ("composer", "user:alice"),
        ])
        self.assertTrue(all(rs))
        resp = self.client.get("/api/audit/timeline?limit=10")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body.get("ok"))
        items = body.get("items") or []
        self.assertEqual(len(items), 4)
        # ts should be non-increasing (newest first).
        for a, b in zip(items, items[1:]):
            self.assertGreaterEqual(a["ts"], b["ts"])


class TestAuditTimelineFilterByKind(_AuditCase):
    def test_timeline_filter_by_kind(self) -> None:
        self._emit_seq([
            ("composer", "user:alice"),
            ("voice", "user:alice"),
            ("composer", "user:alice"),
            ("file-drop", "user:bob"),
            ("composer", "user:bob"),
        ])
        resp = self.client.get("/api/audit/timeline?kind=composer&limit=50")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json().get("items") or []
        self.assertEqual(len(items), 3)
        for it in items:
            self.assertEqual(it["kind"], "composer")
        # Sanity: 'voice' filter returns 1.
        r2 = self.client.get("/api/audit/timeline?kind=voice&limit=50")
        self.assertEqual(len(r2.json().get("items") or []), 1)


class TestAuditVerifyShape(_AuditCase):
    def test_verify_endpoint_shape(self) -> None:
        rs = self._emit_seq([
            ("composer", "user:alice"),
            ("composer", "user:alice"),
            ("voice", "user:alice"),
        ])
        target = rs[1]
        assert target is not None
        resp = self.client.get(f"/api/audit/verify/{target.hash}")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # Documented keys present.
        for k in (
            "ok",
            "verified",
            "signature_ok",
            "merkle_proof_ok",
            "anchored",
            "day",
            "verified_at",
        ):
            self.assertIn(k, body, f"missing key {k!r} in {body!r}")
        # Clean chain -> both sig and proof must verify.
        self.assertTrue(body["signature_ok"])
        self.assertTrue(body["merkle_proof_ok"])
        self.assertTrue(body["verified"])
        # No Solana anchor in this test env so 'anchored' is False -- that's fine,
        # the explorer_url should be None / absent and solana_tx None.
        self.assertFalse(body["anchored"])


class TestAuditExportJson(_AuditCase):
    def test_export_json_returns_immediate_file(self) -> None:
        self._emit_seq([
            ("composer", "user:alice"),
            ("voice", "user:alice"),
        ])
        resp = self.client.post(
            "/api/receipts/export",
            json={"format": "json"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        j = resp.json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["format"], "json")
        self.assertEqual(j["count"], 2)
        self.assertIn("job_id", j)
        # File should be downloadable.
        dl = self.client.get(j["download_url"])
        self.assertEqual(dl.status_code, 200)
        # Content should be valid JSON with our receipts inside.
        import json as _json
        parsed = _json.loads(dl.content)
        self.assertIn("receipts", parsed)
        self.assertEqual(len(parsed["receipts"]), 2)
        # Bundle is itself signed (Ed25519 over body hash).
        self.assertIn("_signature", parsed)


class TestAuditExportPdf(_AuditCase):
    def test_export_pdf_succeeds_or_returns_helpful_error(self) -> None:
        self._emit_seq([("composer", "user:alice")])
        resp = self.client.post(
            "/api/receipts/export",
            json={"format": "pdf"},
        )
        # reportlab present -> 200 with download_url; absent -> 501 with hint.
        if resp.status_code == 200:
            j = resp.json()
            self.assertTrue(j["ok"])
            self.assertEqual(j["format"], "pdf")
            dl = self.client.get(j["download_url"])
            self.assertEqual(dl.status_code, 200)
            # PDFs start with the magic %PDF- header.
            self.assertTrue(dl.content.startswith(b"%PDF-"))
        else:
            self.assertEqual(resp.status_code, 501, resp.text)
            j = resp.json()
            self.assertFalse(j["ok"])
            self.assertEqual(j["error"], "pdf_renderer_missing")
            self.assertIn("reportlab", j["hint"].lower())


if __name__ == "__main__":
    unittest.main()
