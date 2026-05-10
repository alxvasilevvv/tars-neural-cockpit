"""Hash chain + ed25519 signature + chain-walk + tamper-detection
tests for the unified receipt ledger (Wave 95).

Stdlib unittest only — no fixtures, no temp DBs (this file exercises
pure primitives).
"""

from __future__ import annotations

import unittest

from backend.core.receipts.chain import (
    compute_hash,
    derive_public_key,
    generate_keypair,
    sign,
    verify,
    verify_chain,
)
from backend.core.receipts.models import Receipt, new_receipt_id


def _make_signed(
    *,
    priv: bytes,
    pub_b64: str,
    prev_hash: str,
    type: str = "test.event",
    actor: str = "op:alice",
    resource: str | None = "obj-1",
    payload: dict | None = None,
    ts: float = 1_700_000_000.0,
) -> Receipt:
    import base64

    r = Receipt(
        id=new_receipt_id(),
        ts=ts,
        type=type,
        actor=actor,
        resource=resource,
        payload=dict(payload or {}),
        prev_hash=prev_hash,
        hash="",
        signature="",
        public_key=pub_b64,
    )
    r.hash = compute_hash(r)
    r.signature = sign(r, priv)
    return r


class TestComputeHash(unittest.TestCase):
    def test_hash_is_64_hex(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        self.assertEqual(len(r.hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in r.hash))

    def test_hash_is_deterministic(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="abcd")
        h1 = r.hash
        # Recompute on a fresh dataclass with the same body.
        r2 = Receipt(
            id="other",
            ts=r.ts,
            type=r.type,
            actor=r.actor,
            resource=r.resource,
            payload=dict(r.payload),
            prev_hash=r.prev_hash,
            hash="",
            signature="",
            public_key=r.public_key,
        )
        self.assertEqual(compute_hash(r2), h1)

    def test_hash_changes_when_payload_changes(self):
        priv, pub = generate_keypair()
        r1 = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="", payload={"x": 1})
        r2 = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="", payload={"x": 2})
        self.assertNotEqual(r1.hash, r2.hash)

    def test_hash_changes_when_prev_hash_changes(self):
        priv, pub = generate_keypair()
        r1 = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="aaa")
        r2 = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="bbb")
        self.assertNotEqual(r1.hash, r2.hash)


class TestSignVerify(unittest.TestCase):
    def test_signed_receipt_verifies(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        self.assertTrue(verify(r))

    def test_signature_must_be_64_bytes(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        import base64

        sig_bytes = base64.b64decode(r.signature)
        self.assertEqual(len(sig_bytes), 64)

    def test_tampered_payload_fails_verify(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="", payload={"x": 1})
        # Tamper after signing.
        r.payload["x"] = 2
        self.assertFalse(verify(r))

    def test_tampered_signature_fails_verify(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        # Flip a base64 char.
        r.signature = "A" + r.signature[1:]
        self.assertFalse(verify(r))

    def test_pubkey_mismatch_fails_verify(self):
        priv, pub = generate_keypair()
        priv2, pub2 = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        # Caller insists pub2 was used; embedded says pub.
        self.assertFalse(verify(r, host_ed25519_pub=pub2))
        # But honest verifier (no override) accepts.
        self.assertTrue(verify(r))

    def test_empty_signature_fails(self):
        priv, pub = generate_keypair()
        r = _make_signed(priv=priv, pub_b64=_b64(pub), prev_hash="")
        r.signature = ""
        self.assertFalse(verify(r))

    def test_derive_public_key_matches_generate(self):
        priv, pub = generate_keypair()
        self.assertEqual(derive_public_key(priv), pub)


class TestVerifyChain(unittest.TestCase):
    def test_empty_chain_ok(self):
        self.assertEqual(verify_chain([]), {"ok": True, "count": 0})

    def test_three_receipt_chain_ok(self):
        priv, pub = generate_keypair()
        pub_b64 = _b64(pub)
        r1 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash="", payload={"i": 1}, ts=1.0)
        r2 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash=r1.hash, payload={"i": 2}, ts=2.0)
        r3 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash=r2.hash, payload={"i": 3}, ts=3.0)
        self.assertEqual(verify_chain([r1, r2, r3]), {"ok": True, "count": 3})

    def test_broken_prev_hash_detected(self):
        priv, pub = generate_keypair()
        pub_b64 = _b64(pub)
        r1 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash="", ts=1.0)
        r2 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash="WRONG", ts=2.0)
        out = verify_chain([r1, r2])
        self.assertFalse(out["ok"])
        self.assertEqual(out["broken_at_index"], 1)
        self.assertEqual(out["reason"], "prev_hash_mismatch")
        self.assertEqual(out["actual"], "WRONG")

    def test_tampered_payload_detected_in_chain(self):
        priv, pub = generate_keypair()
        pub_b64 = _b64(pub)
        r1 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash="", payload={"x": 1}, ts=1.0)
        r2 = _make_signed(priv=priv, pub_b64=pub_b64, prev_hash=r1.hash, payload={"x": 2}, ts=2.0)
        # Tamper r2 after signing.
        r2.payload["x"] = 999
        out = verify_chain([r1, r2])
        self.assertFalse(out["ok"])
        self.assertEqual(out["broken_at_index"], 1)
        self.assertEqual(out["reason"], "hash_mismatch")


def _b64(b: bytes) -> str:
    import base64

    return base64.b64encode(b).decode("ascii")


if __name__ == "__main__":
    unittest.main()
