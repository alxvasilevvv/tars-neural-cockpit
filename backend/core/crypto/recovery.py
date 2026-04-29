"""BIP-39 recovery seed (24 words, 256-bit entropy).

Phase **L5 G1**. The recovery seed is shown to the operator **exactly
once** at first install. From it we deterministically derive the
host's master keyring (X25519 identity + later sync keys), so a lost
desktop can be recovered onto a new machine without losing access
to the encrypted thread history on `meeet.world`.

Implementation rules:

- Pure stdlib (``hashlib`` + ``secrets``). No third-party BIP-39 libs.
- Standard 256-bit entropy → 24 words via the canonical BIP-39
  English wordlist (2048 entries).
- Mnemonic ↔ seed conversion uses PBKDF2-HMAC-SHA512 with passphrase
  ``"mnemonic" + passphrase`` (BIP-39 spec).
- The first 32 bytes of the resulting 64-byte seed are interpreted
  as the master X25519 secret. ``DeviceKey`` will be derived from
  that with libsodium.

What this module is **not**:

- A general-purpose Bitcoin wallet. We don't need the BIP-32 / BIP-44
  derivation tree.
- An alternative to encrypted Keychain storage. The seed is a
  *recovery* mechanism, not the daily-driver key store.

Wordlist source: ``data/bip39_english.txt`` (the canonical 2048-word
English list, identical to the one in the BIP-39 reference). It's
loaded lazily so unit tests that don't touch this module don't pay
the I/O cost.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from nacl.public import PrivateKey

from .envelope import DeviceKey


WORDLIST_PATH = Path(__file__).resolve().parent / "data" / "bip39_english.txt"

ENTROPY_BITS = 256                       # 24-word mnemonic
ENTROPY_BYTES = ENTROPY_BITS // 8        # 32
WORD_COUNT = 24
PBKDF2_ITERS = 2048                      # BIP-39 standard
PBKDF2_DKLEN = 64


# ---------------------------------------------------------------------
# Wordlist
# ---------------------------------------------------------------------


@lru_cache(maxsize=1)
def _wordlist() -> tuple[str, ...]:
    if not WORDLIST_PATH.exists():
        raise RuntimeError(
            f"BIP-39 wordlist not found at {WORDLIST_PATH}; the file ships "
            "with the repo and is required for recovery seed support."
        )
    raw = WORDLIST_PATH.read_text(encoding="utf-8").splitlines()
    words = tuple(w.strip() for w in raw if w.strip() and not w.startswith("#"))
    if len(words) != 2048:
        raise RuntimeError(
            f"BIP-39 wordlist must have 2048 entries; got {len(words)}"
        )
    return words


def _word_index(word: str) -> int:
    try:
        return _wordlist().index(word)
    except ValueError as exc:
        raise ValueError(f"unknown BIP-39 word: {word!r}") from exc


# ---------------------------------------------------------------------
# Entropy ↔ mnemonic (BIP-39 standard algorithm)
# ---------------------------------------------------------------------


def _bytes_to_bits(data: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in data)


def _bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("bits length must be a multiple of 8")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def _checksum(entropy: bytes) -> str:
    """Top ``len(entropy) * 8 / 32`` bits of SHA256(entropy)."""

    digest = hashlib.sha256(entropy).digest()
    cs_len = (len(entropy) * 8) // 32
    return _bytes_to_bits(digest)[:cs_len]


def entropy_to_mnemonic(entropy: bytes) -> str:
    if len(entropy) != ENTROPY_BYTES:
        raise ValueError(
            f"entropy must be {ENTROPY_BYTES} bytes for a {WORD_COUNT}-word seed"
        )
    bits = _bytes_to_bits(entropy) + _checksum(entropy)
    if len(bits) != WORD_COUNT * 11:
        raise AssertionError("internal: bit length doesn't match BIP-39 spec")
    words = _wordlist()
    out = []
    for i in range(WORD_COUNT):
        idx = int(bits[i * 11 : (i + 1) * 11], 2)
        out.append(words[idx])
    return " ".join(out)


def mnemonic_to_entropy(mnemonic: str) -> bytes:
    """Decode a BIP-39 mnemonic into raw entropy bytes.

    Accepts any standard BIP-39 word count (12, 15, 18, 21, 24) for
    *importing* third-party wallet phrases (e.g. Metamask 12-word,
    Anvil dev mnemonic). The host's own recovery seed is still
    24-word — see :func:`generate_mnemonic`.
    """

    parts = mnemonic.strip().lower().split()
    if len(parts) not in {12, 15, 18, 21, 24}:
        raise ValueError(
            f"mnemonic must have 12 / 15 / 18 / 21 / 24 words; got {len(parts)}"
        )
    bits = "".join(f"{_word_index(w):011b}" for w in parts)
    total_bits = len(parts) * 11
    cs_len = total_bits // 33
    entropy_bit_count = total_bits - cs_len
    entropy_bits = bits[:entropy_bit_count]
    cs_bits = bits[entropy_bit_count:]
    entropy = _bits_to_bytes(entropy_bits)
    expected_cs = _checksum(entropy)
    if not hmac.compare_digest(expected_cs, cs_bits):
        raise ValueError("invalid BIP-39 checksum")
    return entropy


def generate_mnemonic() -> str:
    """Generate a fresh 24-word recovery seed."""

    return entropy_to_mnemonic(secrets.token_bytes(ENTROPY_BYTES))


# ---------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """BIP-39 PBKDF2-HMAC-SHA512 → 64-byte seed."""

    norm_mnemonic = " ".join(mnemonic.strip().lower().split())
    salt = ("mnemonic" + (passphrase or "")).encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha512",
        norm_mnemonic.encode("utf-8"),
        salt,
        PBKDF2_ITERS,
        PBKDF2_DKLEN,
    )


def seed_to_master_key(seed: bytes, *, host_id: str) -> DeviceKey:
    """First 32 bytes of the BIP-39 seed → X25519 master keypair.

    libsodium's X25519 accepts any 32-byte secret (it clamps internally
    when computing the curve scalar) so we don't need a separate
    derivation step for v1.
    """

    if len(seed) < 32:
        raise ValueError("seed must be at least 32 bytes")
    sk = PrivateKey(seed[:32])
    return DeviceKey(
        device_id=host_id,
        public_key=bytes(sk.public_key),
        secret_key=bytes(sk),
    )


# ---------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class RecoverySeed:
    mnemonic: str
    fingerprint: str  # 12-hex-char SHA-256 of the seed; safe to log

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self.mnemonic.split())


def make_recovery_seed(passphrase: str = "") -> RecoverySeed:
    mnemonic = generate_mnemonic()
    seed = mnemonic_to_seed(mnemonic, passphrase=passphrase)
    fingerprint = hashlib.sha256(seed).hexdigest()[:12].upper()
    return RecoverySeed(mnemonic=mnemonic, fingerprint=fingerprint)


def fingerprint_of(mnemonic: str, passphrase: str = "") -> str:
    """Validate the mnemonic and return a stable 12-char fingerprint.

    Raises ``ValueError`` if the input isn't a well-formed BIP-39 phrase
    (wrong word count / unknown word / bad checksum). This is the
    function the HTTP ``verify`` endpoint relies on to reject garbage.
    """

    mnemonic_to_entropy(mnemonic)
    seed = mnemonic_to_seed(mnemonic, passphrase=passphrase)
    return hashlib.sha256(seed).hexdigest()[:12].upper()
