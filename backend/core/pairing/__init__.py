"""Pairing module — Phase L5 (in progress).

Pins the public surface from ``docs/contracts/L5_PAIRING_DRAFT.md``.

This first slice ships **shape-correct, mock-crypto** behaviour so:

- the cockpit can build the pairing UI against real endpoints;
- the iOS / Android L10 stubs can wire URLSession / OkHttp clients;
- the contract tests pin field names so a future agent can drop in
  XChaCha20-Poly1305 + X25519 without rewriting the wire shape.

What's mock for now:

- ``client_epk`` is accepted but **not validated** as a real X25519
  key — we just round-trip it.
- ``host_fingerprint`` is generated as a stable hex digest of
  ``host_id + pair_id`` so two parallel calls to
  ``POST /api/pairing/begin`` for the same envelope produce the same
  human-comparable string. Production swaps in a fingerprint of the
  host's long-term public key.
- ``accept_token`` is a random 32-char hex; the operator confirms it
  via ``POST /api/pairing/accept/{token}`` and the host emits
  ``pair.linked``.

When real crypto lands (Phase L5 implementation slice), only the
``begin`` / ``accept`` handlers' internals change — nothing on the
wire moves.
"""

from .store import (
    DEFAULT_PAIR_TTL,
    PairingNotFound,
    PairingState,
    PairingRecord,
    get_pairing_store,
)

__all__ = [
    "DEFAULT_PAIR_TTL",
    "PairingNotFound",
    "PairingState",
    "PairingRecord",
    "get_pairing_store",
]
