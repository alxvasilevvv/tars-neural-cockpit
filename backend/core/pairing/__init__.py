"""Pairing module — Phase L5 v1 (real crypto shipped).

Pins the public surface from ``docs/contracts/L5_PAIRING_DRAFT.md`` and
plumbs real X25519 keys end-to-end. The matching encryption envelope
lives in :mod:`backend.core.crypto.envelope` (XChaCha20-Poly1305 + X25519
sealed boxes per recipient); the host vault lives in
:mod:`backend.core.vault`.

What ships today:

- ``client_epk`` is **validated** as a 32-byte base64-encoded X25519
  public key on every ``POST /api/pairing/begin`` call (see
  ``_validate_b64_pubkey`` in :mod:`.store`). Malformed keys fail fast
  before the store takes any state.
- ``host_public_key`` is the host's vault-persisted X25519 long-term
  public key — emitted in every pairing record so clients can pin it
  on first contact.
- ``host_fingerprint`` stays a 12-char string in 4-4-4 groups for
  human comparison on QR-pair (e.g. ``QXr7-8MB9-NJ2L``); current
  digest is over ``host_id + pair_id``. Future Phase L5.2 slice
  swaps the input to the host pubkey itself so a rotated identity
  yields a fresh fingerprint without touching the wire format.
- ``accept_token`` is a 32-char hex; the operator confirms it via
  ``POST /api/pairing/accept/{token}`` and the host promotes the
  client_epk into a long-lived per-device :class:`DeviceKey`.
- The host vault (``backend.core.vault.KeyringVault``) persists the
  long-term host identity across restarts (default
  ``~/.tars/host_identity.json``, env-overridable). Disable with
  ``TARS_PAIRING_VAULT=disabled`` for ephemeral test installs.

End-to-end test path (sealed event survives the durable buffer
round-trip): :mod:`tests.test_pairing_envelope_e2e`. Encryption math
in :mod:`tests.test_crypto_envelope`.

Future Phase L5.2 (post-handshake key rotation) will re-key paired
devices without reissuing the QR — the single line in :meth:`store.PairingStore.accept`
that promotes ``client_epk`` to the device key is the only
implementation detail that changes.
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
