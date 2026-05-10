"""Dataclasses for the unified receipt ledger (Wave 95).

Two records:

- :class:`Receipt` — a single hash-chained, signed event in the
  tamper-evident ledger. Each record links to the previous one via
  ``prev_hash``; the ``hash`` field is the canonical sha256 over the
  ordered (prev_hash, ts, type, actor, resource, payload) tuple, hex
  encoded. ``signature`` is ed25519 over the hash (base64). The
  signing ``public_key`` is embedded in every receipt so verifiers
  don't need out-of-band key distribution.

- :class:`MerkleRoot` — daily aggregation. Once UTC midnight passes,
  the ledger computes a Merkle root over all receipt hashes for the
  prior day. Optionally, the operator can anchor the root on Solana
  via a memo transaction; ``solana_signature`` records the txid.

Contract version: 1.0 (see ``docs/contracts/RECEIPTS.md``).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


def new_receipt_id() -> str:
    """Generate a short, sortable receipt id."""

    return f"rcpt_{uuid.uuid4().hex[:18]}"


@dataclass
class Receipt:
    """A single hash-chained signed event in the ledger.

    The ``hash`` and ``signature`` fields are populated by
    :mod:`backend.core.receipts.chain`. ``prev_hash`` is the hash of
    the previous receipt in the chain (or the empty string for the
    very first receipt). ``public_key`` is the ed25519 verify key
    that produced ``signature``, base64 encoded.
    """

    id: str
    ts: float
    type: str
    actor: str
    resource: str | None
    payload: dict[str, Any]
    prev_hash: str
    hash: str
    signature: str
    public_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "type": self.type,
            "actor": self.actor,
            "resource": self.resource,
            "payload": dict(self.payload),
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "signature": self.signature,
            "public_key": self.public_key,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Receipt":
        return cls(
            id=str(d["id"]),
            ts=float(d["ts"]),
            type=str(d["type"]),
            actor=str(d["actor"]),
            resource=(None if d.get("resource") is None else str(d["resource"])),
            payload=dict(d.get("payload") or {}),
            prev_hash=str(d.get("prev_hash") or ""),
            hash=str(d.get("hash") or ""),
            signature=str(d.get("signature") or ""),
            public_key=str(d.get("public_key") or ""),
        )


@dataclass
class MerkleRoot:
    """A daily Merkle-root anchor record.

    ``day_iso`` is ``YYYY-MM-DD`` (UTC). ``root_hex`` is the 64-char
    hex sha256 root over the ordered list of receipt hashes for the
    day. ``leaf_count`` is the number of receipts the root covers.
    ``anchored_at`` and ``solana_signature`` are populated only when
    the operator opts into Solana memo anchoring.
    """

    id: str
    day_iso: str
    root_hex: str
    leaf_count: int
    anchored_at: float | None = None
    solana_signature: str | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "day_iso": self.day_iso,
            "root_hex": self.root_hex,
            "leaf_count": self.leaf_count,
            "anchored_at": self.anchored_at,
            "solana_signature": self.solana_signature,
            "created_at": self.created_at,
        }
