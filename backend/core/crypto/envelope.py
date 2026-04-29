"""Sync envelope primitives — XChaCha20-Poly1305 + X25519.

Wire shape (matches ``docs/contracts/L5_PAIRING_DRAFT.md`` § 4):

```jsonc
{
  "ciphertext": "base64(XChaCha20-Poly1305 sealed JSON payload)",
  "envelope": {
    "scheme": "xchacha20-poly1305-x25519-v1",
    "nonce":   "base64(24 bytes)",
    "epk":     "base64(ephemeral X25519 public key, 32 bytes)",
    "recipient_keys": [
      { "device_id": "a1b2…", "wrapped_key": "base64(crypto_box_seal output, 32 + 16 + 32 bytes)" }
    ]
  }
}
```

Sealing flow per event:

1. Pick a random **content key** (32 bytes).
2. Pick a random **nonce** (24 bytes).
3. ``ciphertext = XChaCha20-Poly1305(key=content_key, nonce, plaintext=json.payload, ad=trace_id|kind)``.
4. For each recipient device, ``wrapped_key = crypto_box_seal(content_key, recipient_pk)``.
   ``crypto_box_seal`` already embeds an ephemeral X25519 keypair, so the
   ``epk`` field carries the *first* recipient's wrap pubkey for
   compatibility with future single-recipient optimisations; per-recipient
   ``wrapped_key`` blobs are self-contained.

Opening flow on a paired device:

1. Find the recipient row matching this device's ``device_id``.
2. ``content_key = crypto_box_seal_open(wrapped_key, my_pk, my_sk)``.
3. ``plaintext  = XChaCha20-Poly1305_open(content_key, nonce, ciphertext, ad)``.

The associated-data string ``trace_id|kind`` binds the ciphertext to its
event metadata; tampering with either invalidates the AEAD tag.

This module is intentionally **stateless**. Key persistence (macOS
Keychain, Android Keystore, iOS Secure Enclave) lives in
``backend/core/vault/`` (host) and the platform layers on mobile.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_KEYBYTES,
    crypto_aead_xchacha20poly1305_ietf_NPUBBYTES,
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
    crypto_box_PUBLICKEYBYTES,
    crypto_box_SECRETKEYBYTES,
)
from nacl.public import PrivateKey, PublicKey, SealedBox


SCHEME = "xchacha20-poly1305-x25519-v1"

KEYBYTES = crypto_aead_xchacha20poly1305_ietf_KEYBYTES   # 32
NONCEBYTES = crypto_aead_xchacha20poly1305_ietf_NPUBBYTES  # 24
PUBLICKEYBYTES = crypto_box_PUBLICKEYBYTES               # 32
SECRETKEYBYTES = crypto_box_SECRETKEYBYTES               # 32


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _ad(trace_id: str | None, kind: str) -> bytes:
    return f"{trace_id or ''}|{kind}".encode("utf-8")


# ---------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceKey:
    """X25519 keypair tied to a logical device.

    ``device_id`` matches the value the pairing endpoint hands out.
    On the host we typically only know the public half of paired
    devices; ``secret_key`` is populated only on the device that
    *owns* the key.
    """

    device_id: str
    public_key: bytes
    secret_key: bytes | None = None

    def to_public(self) -> "DeviceKey":
        return DeviceKey(device_id=self.device_id, public_key=self.public_key)

    @property
    def public_b64(self) -> str:
        return _b64e(self.public_key)


@dataclass(frozen=True)
class SyncEnvelope:
    scheme: str
    nonce: str
    epk: str
    recipient_keys: tuple[Mapping[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "nonce": self.nonce,
            "epk": self.epk,
            "recipient_keys": [dict(r) for r in self.recipient_keys],
        }


@dataclass(frozen=True)
class SealedEvent:
    """The bag of strings ready to drop into ``MeeetClient.emit``."""

    ciphertext: str
    envelope: SyncEnvelope

    def to_kwargs(self) -> dict[str, Any]:
        return {
            "ciphertext": self.ciphertext,
            "envelope": self.envelope.to_dict(),
        }


# ---------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------


def generate_device_key(device_id: str) -> DeviceKey:
    sk = PrivateKey.generate()
    return DeviceKey(
        device_id=device_id,
        public_key=bytes(sk.public_key),
        secret_key=bytes(sk),
    )


# ---------------------------------------------------------------------
# Encrypt / decrypt
# ---------------------------------------------------------------------


def encrypt_event(
    *,
    payload: Mapping[str, Any],
    recipients: Iterable[DeviceKey],
    trace_id: str | None,
    kind: str,
) -> SealedEvent:
    """Seal ``payload`` for every device in ``recipients``.

    Returns a :class:`SealedEvent` carrying the ciphertext and the
    envelope ready to be dropped into ``MeeetClient.emit(ciphertext=...,
    envelope=...)``. Raises ``ValueError`` if the recipient list is
    empty — sealing with no readers is a programming bug.
    """

    recipients = list(recipients)
    if not recipients:
        raise ValueError("encrypt_event requires at least one recipient")

    content_key = os.urandom(KEYBYTES)
    nonce = os.urandom(NONCEBYTES)
    plaintext = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
    ad = _ad(trace_id, kind)

    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(plaintext, ad, nonce, content_key)

    wrapped: list[Mapping[str, str]] = []
    epk: bytes | None = None
    for rec in recipients:
        if len(rec.public_key) != PUBLICKEYBYTES:
            raise ValueError(
                f"recipient {rec.device_id} has invalid pubkey length {len(rec.public_key)}"
            )
        sealed = SealedBox(PublicKey(rec.public_key)).encrypt(content_key)
        wrapped.append({"device_id": rec.device_id, "wrapped_key": _b64e(sealed)})
        if epk is None:
            # SealedBox prepends 32-byte ephemeral pubkey to the ciphertext;
            # surface it for fast-path single-recipient unwrap on devices
            # that recognise the form. Multi-recipient unwrap reads the
            # per-row wrapped_key blob anyway.
            epk = sealed[:PUBLICKEYBYTES]

    envelope = SyncEnvelope(
        scheme=SCHEME,
        nonce=_b64e(nonce),
        epk=_b64e(epk or b""),
        recipient_keys=tuple(wrapped),
    )
    return SealedEvent(ciphertext=_b64e(ciphertext), envelope=envelope)


def decode_envelope(raw: Mapping[str, Any] | None) -> SyncEnvelope | None:
    if not raw:
        return None
    try:
        return SyncEnvelope(
            scheme=str(raw["scheme"]),
            nonce=str(raw["nonce"]),
            epk=str(raw.get("epk") or ""),
            recipient_keys=tuple(
                {"device_id": str(r["device_id"]), "wrapped_key": str(r["wrapped_key"])}
                for r in raw.get("recipient_keys") or ()
                if isinstance(r, Mapping) and "device_id" in r and "wrapped_key" in r
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def decrypt_event(
    *,
    ciphertext: str,
    envelope: Mapping[str, Any] | SyncEnvelope,
    recipient: DeviceKey,
    trace_id: str | None,
    kind: str,
) -> dict[str, Any]:
    """Open a sealed event with the given recipient's secret key.

    Raises ``ValueError`` if the envelope can't be parsed, the
    recipient isn't listed, or the AEAD tag doesn't verify.
    """

    if recipient.secret_key is None:
        raise ValueError("recipient must include secret_key to decrypt")

    env = envelope if isinstance(envelope, SyncEnvelope) else decode_envelope(envelope)
    if env is None:
        raise ValueError("invalid envelope")
    if env.scheme != SCHEME:
        raise ValueError(f"unsupported scheme: {env.scheme}")

    wrapped: bytes | None = None
    for row in env.recipient_keys:
        if row.get("device_id") == recipient.device_id:
            wrapped = _b64d(row["wrapped_key"])
            break
    if wrapped is None:
        raise ValueError(f"recipient {recipient.device_id} not in envelope")

    sk = PrivateKey(recipient.secret_key)
    box = SealedBox(sk)
    content_key = box.decrypt(wrapped)
    if len(content_key) != KEYBYTES:
        raise ValueError("decrypted content key has wrong length")

    nonce = _b64d(env.nonce)
    if len(nonce) != NONCEBYTES:
        raise ValueError("envelope nonce has wrong length")
    ct = _b64d(ciphertext)
    ad = _ad(trace_id, kind)
    plaintext = crypto_aead_xchacha20poly1305_ietf_decrypt(ct, ad, nonce, content_key)
    return json.loads(plaintext.decode("utf-8"))
