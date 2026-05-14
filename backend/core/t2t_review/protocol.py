"""W260 — signed envelope protocol for T2T code review handoff.

Wire shapes:

- :class:`ReviewRequest` — TARS A -> TARS B. Carries the composer
  plan body + diff bundle + optional comment.
- :class:`ReviewResponse` — TARS B -> TARS A. Approval or rejection
  with optional comment.

Both payloads get wrapped in a *signed envelope*:

    {
      "version": 1,
      "type": "t2t.review.request" | "t2t.review.response",
      "sender_tars_id": "<host_id of the sender>",
      "sender_public_key": "<base64 ed25519 pubkey, 44 chars>",
      "ts": 1715000000.0,
      "body": { ... ReviewRequest|ReviewResponse fields ... },
      "signature": "<base64 ed25519 sig over canonical bytes>"
    }

The canonical bytes are the JSON-serialised envelope WITHOUT the
``signature`` key, using ``sort_keys=True`` and
``separators=(',', ':')`` — same shape the W67 receipt chain uses.

Signing leans on the W67 host key (``~/.tars/host-key.json``,
loaded via :mod:`backend.core.receipts.store`) so TARS already has
exactly one identity for both receipt emission and peer handshake.
That keeps the W82 mental model intact: a single ed25519 keypair per
TARS instance, the peer's ``sender_tars_id`` is the SHA-256 prefix
of its pubkey, and a peer's identity is verifiable from the embedded
public_key alone.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


# Bump this when the canonical-bytes shape or the body schema
# changes incompatibly. Receivers reject envelopes with a higher
# version than they understand.
ENVELOPE_VERSION = 1

REQUEST_TYPE = "t2t.review.request"
RESPONSE_TYPE = "t2t.review.response"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReviewRequest:
    """Payload TARS A sends to TARS B asking for a code-review pass.

    - ``review_id`` is the stable id both sides reference. Minted by
      the sender; the receiver echoes it on the response so the
      outbox-poll loop can match the pair without depending on a
      symmetric ack channel.
    - ``plan`` is the full :class:`ComposerPlan.to_dict()` payload —
      diff strings included — so the recipient renders the review
      without ever calling back to the sender.
    - ``recipient_tars_id`` is informational on the wire (the
      receiver already knows who it is); useful for logging and for
      the outbox so the sender can list outgoing reviews per peer.
    """

    review_id: str
    sender_tars_id: str
    recipient_tars_id: str
    plan: dict[str, Any]
    comment: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewRequest":
        return cls(
            review_id=str(data.get("review_id") or ""),
            sender_tars_id=str(data.get("sender_tars_id") or ""),
            recipient_tars_id=str(data.get("recipient_tars_id") or ""),
            plan=dict(data.get("plan") or {}),
            comment=data.get("comment"),
            created_at=float(data.get("created_at") or time.time()),
        )


@dataclass
class ReviewResponse:
    """Payload TARS B sends back to TARS A. ``decision`` is either
    ``approve`` or ``reject``. Carries an optional reviewer comment
    in both cases (rejection reason is required by the API layer,
    but the protocol stores it as an optional field so a fuzzed
    payload still parses cleanly).
    """

    review_id: str
    decision: str  # "approve" | "reject"
    reviewer_tars_id: str
    comment: str | None = None
    reason: str | None = None
    decided_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewResponse":
        decision = str(data.get("decision") or "").lower()
        if decision not in ("approve", "reject"):
            raise ValueError(
                f"decision must be approve|reject, got {decision!r}"
            )
        return cls(
            review_id=str(data.get("review_id") or ""),
            decision=decision,
            reviewer_tars_id=str(data.get("reviewer_tars_id") or ""),
            comment=data.get("comment"),
            reason=data.get("reason"),
            decided_at=float(data.get("decided_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def new_review_id() -> str:
    return "rev_" + secrets.token_hex(8)


def tars_id_from_pubkey(public_key_b64: str) -> str:
    """Derive the 12-hex-char ``tars_id`` from an ed25519 pubkey.

    Same trick the pairing module uses for fingerprints — short
    enough to fit on a status pill in the cockpit, long enough to
    avoid first-byte collisions across realistic peer counts.
    """

    try:
        raw = base64.b64decode(public_key_b64.encode("ascii"))
    except Exception:  # noqa: BLE001
        return "unknown"
    return hashlib.sha256(raw).hexdigest()[:12]


def canonical_bytes(envelope: dict[str, Any]) -> bytes:
    """Deterministic byte encoding of an envelope WITHOUT signature.

    Used as the signing + verification target.
    """

    body = {k: v for k, v in envelope.items() if k != "signature"}
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_envelope(
    *,
    envelope_type: str,
    body: dict[str, Any],
    sender_tars_id: str,
    sender_priv_seed: bytes,
) -> dict[str, Any]:
    """Build + sign a full envelope.

    ``sender_priv_seed`` is the raw 32-byte ed25519 seed (the same
    shape the W67 receipt store persists).
    """

    if envelope_type not in (REQUEST_TYPE, RESPONSE_TYPE):
        raise ValueError(f"unknown envelope type {envelope_type!r}")
    if len(sender_priv_seed) != 32:
        raise ValueError(
            f"ed25519 seed must be 32 bytes, got {len(sender_priv_seed)}"
        )

    sk = Ed25519PrivateKey.from_private_bytes(sender_priv_seed)
    pub_b64 = base64.b64encode(
        sk.public_key().public_bytes_raw()
    ).decode("ascii")

    envelope: dict[str, Any] = {
        "version": ENVELOPE_VERSION,
        "type": envelope_type,
        "sender_tars_id": sender_tars_id,
        "sender_public_key": pub_b64,
        "ts": round(time.time(), 6),
        "body": body,
    }
    sig = sk.sign(canonical_bytes(envelope))
    envelope["signature"] = base64.b64encode(sig).decode("ascii")
    return envelope


def verify_envelope(envelope: dict[str, Any]) -> bool:
    """Return True iff the envelope's signature checks against
    ``sender_public_key`` and the version is supported.

    Defensive: never raises. A malformed envelope is just ``False``.
    """

    if not isinstance(envelope, dict):
        return False
    try:
        version = int(envelope.get("version") or 0)
    except (TypeError, ValueError):
        return False
    if version != ENVELOPE_VERSION:
        return False
    sig_b64 = envelope.get("signature")
    pub_b64 = envelope.get("sender_public_key")
    if not sig_b64 or not pub_b64:
        return False
    try:
        pub_raw = base64.b64decode(pub_b64.encode("ascii"))
        sig_raw = base64.b64decode(sig_b64.encode("ascii"))
    except Exception:  # noqa: BLE001
        return False
    if len(pub_raw) != 32:
        return False
    try:
        vk = Ed25519PublicKey.from_public_bytes(pub_raw)
        vk.verify(sig_raw, canonical_bytes(envelope))
    except (InvalidSignature, ValueError, TypeError):
        return False
    # Sender id should match the pubkey-derived id so a malicious
    # peer can't claim someone else's identity even with a valid sig.
    claimed = str(envelope.get("sender_tars_id") or "")
    if claimed and claimed != tars_id_from_pubkey(pub_b64):
        return False
    return True
