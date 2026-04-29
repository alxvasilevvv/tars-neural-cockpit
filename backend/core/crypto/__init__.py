"""TARS local-first cryptography.

Phase **L5**. Tiny, explicit, single-purpose. The two primitives we
ship at this stage are:

- **X25519** identity keys. Each TARS host has a long-term identity
  pair plus a per-pairing ephemeral pair; each paired device is
  identified by its X25519 public key.

- **XChaCha20-Poly1305** AEAD. Used for the sync envelope: each
  ``meeet`` event ciphertext is sealed with a per-event symmetric
  key; that key is wrapped (sealed) per-recipient with their
  X25519 long-term key via libsodium's *crypto_box_seal* style.

We deliberately do **not** roll our own primitives — every call goes
through ``pynacl``'s libsodium bindings.

The envelope wire shape is documented in
``docs/contracts/L5_PAIRING_DRAFT.md`` § 4.
"""

from .envelope import (
    DeviceKey,
    SyncEnvelope,
    SealedEvent,
    decode_envelope,
    decrypt_event,
    encrypt_event,
    generate_device_key,
)

__all__ = [
    "DeviceKey",
    "SealedEvent",
    "SyncEnvelope",
    "decode_envelope",
    "decrypt_event",
    "encrypt_event",
    "generate_device_key",
]
