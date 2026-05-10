"""TARS unified receipt ledger (Wave 95).

Hash-chained, ed25519-signed, append-only event ledger with optional
daily Merkle root + Solana memo anchoring. Replaces the scattered
receipt emitters that lived in ``wallet/audit.py`` (signed wallet
events) and ``meeet/store.py`` (unsigned event mirror) — one
verifiable trail for B2B compliance.

See ``docs/contracts/RECEIPTS.md`` for the public contract.

Public surface:

- :mod:`.models`   — :class:`Receipt`, :class:`MerkleRoot` dataclasses.
- :mod:`.chain`    — hash + sign + verify + chain-walk primitives.
- :mod:`.merkle`   — daily Merkle root + proof generation.
- :mod:`.store`    — :class:`ReceiptStore` (NDJSON + SQLite index).
- :mod:`.anchor`   — optional Solana memo anchoring.
- :mod:`.dispatch` — :func:`record` (best-effort, never throws).

Hot-path callers should ONLY use :func:`record`. Never bypass to the
store directly — that breaks the ``TARS_RECEIPT_STORE=disabled``
opt-out and the never-throw guarantee other modules depend on.

Contract version: 1.0.
"""

from __future__ import annotations

from .chain import (
    compute_hash,
    sign,
    verify,
    verify_chain,
)
from .dispatch import record
from .merkle import compute_root, daily_root, proof, verify_proof
from .models import CONTRACT_VERSION, MerkleRoot, Receipt, new_receipt_id
from .store import ReceiptStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "MerkleRoot",
    "Receipt",
    "ReceiptStore",
    "compute_hash",
    "compute_root",
    "daily_root",
    "get_store",
    "new_receipt_id",
    "proof",
    "record",
    "reset_store",
    "sign",
    "verify",
    "verify_chain",
    "verify_proof",
]
