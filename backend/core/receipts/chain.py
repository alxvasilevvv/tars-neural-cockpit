"""Hash chain + ed25519 signature primitives for the receipt ledger
(Wave 95).

The chain uses a deterministic JSON canonicalisation: ``json.dumps``
with ``sort_keys=True`` and ``separators=(',', ':')`` — same shape
the wallet, webhooks, and pairing modules already lean on. The
hashed input is the ordered tuple
``(prev_hash, ts, type, actor, resource, payload)``, packed as a
small JSON list so insertion order is preserved without depending on
Python dict ordering. The output is sha256 hex, 64 chars (32 bytes).

Signatures are ed25519 over the *hash bytes* (not the JSON), encoded
base64. We sign the hash (rather than the canonical JSON) so a
verifier can re-hash the receipt body and confirm both the chain
linkage and the signature in one shot.

Uses :mod:`cryptography` for ed25519 primitives (rather than pynacl
elsewhere in the codebase) so the receipts module has zero coupling
to the wallet / pairing layer's libsodium dependency. Both libraries
emit RFC-8032-compliant signatures, so cross-verification with
pynacl-based tools is preserved.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .models import Receipt


def _canonical_payload(receipt: Receipt) -> bytes:
    """Build the deterministic byte string we hash + sign."""

    body = [
        receipt.prev_hash,
        round(float(receipt.ts), 6),
        receipt.type,
        receipt.actor,
        receipt.resource,
        receipt.payload,
    ]
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_hash(receipt: Receipt) -> str:
    """Sha256 (hex, 64 chars) over the canonical receipt body."""

    return hashlib.sha256(_canonical_payload(receipt)).hexdigest()


def sign(receipt: Receipt, host_ed25519_priv: bytes) -> str:
    """Sign ``receipt.hash`` with the host's ed25519 private key.

    ``host_ed25519_priv`` is the raw 32-byte seed. Returns
    base64-encoded signature.
    """

    if not receipt.hash:
        raise ValueError("receipt.hash must be populated before signing")
    if len(host_ed25519_priv) != 32:
        raise ValueError(
            f"ed25519 seed must be 32 bytes, got {len(host_ed25519_priv)}"
        )
    sk = Ed25519PrivateKey.from_private_bytes(host_ed25519_priv)
    sig = sk.sign(bytes.fromhex(receipt.hash))
    return base64.b64encode(sig).decode("ascii")


def verify(receipt: Receipt, host_ed25519_pub: bytes | None = None) -> bool:
    """Verify ``receipt.signature`` against the embedded public key.

    ``host_ed25519_pub`` is optional — when provided we check that
    the embedded key matches it (defends against spoofed receipts
    that supply a valid sig over a hostile pubkey). When omitted,
    only the embedded-key signature is verified.
    """

    if not receipt.signature or not receipt.public_key:
        return False
    if not receipt.hash:
        return False
    try:
        embedded_pub = base64.b64decode(receipt.public_key)
    except (ValueError, TypeError):
        return False
    if host_ed25519_pub is not None and embedded_pub != host_ed25519_pub:
        return False
    try:
        vk = Ed25519PublicKey.from_public_bytes(embedded_pub)
        sig = base64.b64decode(receipt.signature)
        vk.verify(sig, bytes.fromhex(receipt.hash))
    except (InvalidSignature, ValueError, TypeError):
        return False
    # Re-hash to make sure the body wasn't tampered with after signing.
    if compute_hash(receipt) != receipt.hash:
        return False
    return True


def verify_chain(receipts: list[Receipt]) -> dict[str, Any]:
    """Walk the receipt list end-to-end, returning the first break.

    Result shape:

        {"ok": True,  "count": N}                                        all good
        {"ok": False, "broken_at_index": i,
         "expected": "<sha>", "actual": "<sha>", "reason": "..."}        chain or sig break

    For each receipt we re-derive the hash, verify the signature, and
    confirm ``prev_hash`` matches the previous receipt's ``hash``.
    """

    prev_hash = ""
    for i, r in enumerate(receipts):
        actual = compute_hash(r)
        if r.hash != actual:
            return {
                "ok": False,
                "broken_at_index": i,
                "expected": actual,
                "actual": r.hash,
                "reason": "hash_mismatch",
            }
        if r.prev_hash != prev_hash:
            return {
                "ok": False,
                "broken_at_index": i,
                "expected": prev_hash,
                "actual": r.prev_hash,
                "reason": "prev_hash_mismatch",
            }
        if not verify(r):
            return {
                "ok": False,
                "broken_at_index": i,
                "expected": "valid_signature",
                "actual": "invalid_signature",
                "reason": "signature_invalid",
            }
        prev_hash = r.hash
    return {"ok": True, "count": len(receipts)}


# ----- helpers used by the store ----------------------------------------


def derive_public_key(host_ed25519_priv: bytes) -> bytes:
    """Return the 32-byte ed25519 public key for a given seed."""

    sk = Ed25519PrivateKey.from_private_bytes(host_ed25519_priv)
    pub = sk.public_key().public_bytes_raw()
    return pub


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh ed25519 keypair. Returns (priv_seed_32, pub_32)."""

    sk = Ed25519PrivateKey.generate()
    priv = sk.private_bytes_raw()
    pub = sk.public_key().public_bytes_raw()
    return priv, pub
