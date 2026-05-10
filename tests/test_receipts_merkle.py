"""Merkle root + proof generation + proof verification tests for the
unified receipt ledger (Wave 95).

Stdlib unittest only.
"""

from __future__ import annotations

import hashlib
import unittest

from backend.core.receipts.merkle import (
    compute_root,
    proof,
    verify_proof,
)


def _hexes(n: int) -> list[str]:
    """Generate ``n`` deterministic 64-char hex hashes."""

    return [hashlib.sha256(f"leaf-{i}".encode()).hexdigest() for i in range(n)]


class TestComputeRoot(unittest.TestCase):
    def test_empty_returns_empty_string(self):
        self.assertEqual(compute_root([]), "")

    def test_single_leaf_root_is_leaf(self):
        h = hashlib.sha256(b"single").hexdigest()
        self.assertEqual(compute_root([h]), h)

    def test_two_leaves_root_matches_manual(self):
        leaves = _hexes(2)
        manual = hashlib.sha256(
            bytes.fromhex(leaves[0]) + bytes.fromhex(leaves[1])
        ).hexdigest()
        self.assertEqual(compute_root(leaves), manual)

    def test_three_leaves_duplicates_last(self):
        leaves = _hexes(3)
        # level 1: H(h0||h1), H(h2||h2)
        l1 = [
            hashlib.sha256(bytes.fromhex(leaves[0]) + bytes.fromhex(leaves[1])).digest(),
            hashlib.sha256(bytes.fromhex(leaves[2]) + bytes.fromhex(leaves[2])).digest(),
        ]
        manual = hashlib.sha256(l1[0] + l1[1]).hexdigest()
        self.assertEqual(compute_root(leaves), manual)

    def test_root_changes_when_leaf_changes(self):
        leaves = _hexes(4)
        r1 = compute_root(leaves)
        leaves[2] = hashlib.sha256(b"different").hexdigest()
        r2 = compute_root(leaves)
        self.assertNotEqual(r1, r2)


class TestProof(unittest.TestCase):
    def test_proof_for_single_leaf_is_empty_path(self):
        leaf = hashlib.sha256(b"single").hexdigest()
        p = proof([leaf], 0)
        self.assertEqual(p["leaf"], leaf)
        self.assertEqual(p["path"], [])
        self.assertEqual(p["root"], leaf)

    def test_proof_verifies_for_each_index(self):
        leaves = _hexes(7)  # odd -> exercises duplicate-last logic
        root = compute_root(leaves)
        for i in range(7):
            p = proof(leaves, i)
            self.assertEqual(p["root"], root)
            self.assertTrue(verify_proof(p["leaf"], p["path"], p["root"]))

    def test_invalid_proof_does_not_verify(self):
        leaves = _hexes(4)
        p = proof(leaves, 1)
        # Corrupt one sibling.
        p["path"][0]["sibling"] = "0" * 64
        self.assertFalse(verify_proof(p["leaf"], p["path"], p["root"]))


if __name__ == "__main__":
    unittest.main()
