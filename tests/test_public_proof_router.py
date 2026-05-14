"""W204 — pytest coverage for /api/public/proof/* (no-auth verifier).

Cases:
  - /health returns the service stamp
  - /verify with a hand-constructed valid Merkle proof → valid=True
  - /verify with a tampered proof → valid=False
  - /verify with malformed leaf hex → 422 (Pydantic min_length)
  - /anchor/{root} with bad-format root → 400
  - /anchor/{root} with unknown root → 200 ok=False root_not_found
"""

from __future__ import annotations

import hashlib
import unittest
from typing import Any


def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def _make_root(leaves: list[bytes]) -> bytes:
    """Mirror backend.core.receipts.merkle's pair-hash semantics."""
    layer = list(leaves)
    if len(layer) == 1:
        return layer[0]
    # Pad to even count by duplicating last leaf (standard Merkle pad).
    if len(layer) % 2 != 0:
        layer.append(layer[-1])
    while len(layer) > 1:
        layer = [_sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


class TestPublicProofRouter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers.public_proof import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_health(self) -> None:
        r = self.client.get("/api/public/proof/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "tars.public_proof")
        self.assertGreater(len(body["endpoints"]), 0)

    def test_verify_valid_two_leaf_proof(self) -> None:
        # 2 leaves → root = sha256(L0 || L1). Proof for leaf 0 is just L1 on the right.
        leaf0 = _sha256(b"receipt-0")
        leaf1 = _sha256(b"receipt-1")
        root = _sha256(leaf0 + leaf1)
        r = self.client.post(
            "/api/public/proof/verify",
            json={
                "leaf_hex": leaf0.hex(),
                "path": [{"sibling": leaf1.hex(), "side": "right"}],
                "root_hex": root.hex(),
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["valid"])

    def test_verify_tampered_proof_returns_invalid(self) -> None:
        leaf0 = _sha256(b"receipt-0")
        leaf1 = _sha256(b"receipt-1")
        root = _sha256(leaf0 + leaf1)
        # Tamper with the leaf — claim leaf0 belongs to root, but submit a different leaf.
        tampered_leaf = _sha256(b"forged-receipt")
        r = self.client.post(
            "/api/public/proof/verify",
            json={
                "leaf_hex": tampered_leaf.hex(),
                "path": [{"sibling": leaf1.hex(), "side": "right"}],
                "root_hex": root.hex(),
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["valid"])

    def test_verify_rejects_short_leaf_hex(self) -> None:
        # leaf_hex < 64 chars → Pydantic 422
        r = self.client.post(
            "/api/public/proof/verify",
            json={"leaf_hex": "abc", "path": [], "root_hex": "0" * 64},
        )
        self.assertEqual(r.status_code, 422)

    def test_anchor_lookup_rejects_bad_root_format(self) -> None:
        r = self.client.get("/api/public/proof/anchor/not-a-valid-hex")
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertEqual(body["detail"]["error"], "bad_root_format")

    def test_anchor_lookup_unknown_root_returns_404_or_not_found(self) -> None:
        # 64-char hex that won't be in the store on a fresh test box.
        fake_root = "f" * 64
        r = self.client.get(f"/api/public/proof/anchor/{fake_root}")
        # Acceptable: either 200 with ok=False root_not_found, or 503
        # if the store is not initialized in the test environment.
        self.assertIn(r.status_code, (200, 503))
        if r.status_code == 200:
            body = r.json()
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"], "root_not_found")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
