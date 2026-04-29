"""SLIP-0010 ed25519 derivation (Phase O3 — Phantom compatibility).

Spec: https://github.com/satoshilabs/slips/blob/master/slip-0010.md

The default TARS Solana derivation (`tars-v1`) uses HMAC-SHA512 over
the BIP-39 seed mixed with a TARS-specific label. That keypair is
valid Solana but does NOT match what Phantom / Solflare / Backpack
would derive from the same mnemonic, because those wallets all use
**SLIP-0010 ed25519** with the standard BIP-44 path
``m/44'/501'/0'/0'``.

This module adds the Phantom-compat path side-by-side with `tars-v1`.
Operators can opt in by passing ``derivation_scheme=bip44-501-phantom``
to ``POST /api/wallet`` — the resulting wallet has the same address
their Phantom would show for the same mnemonic, so they can import
the recovery phrase into Phantom and see TARS-minted funds.

Existing wallets are unchanged — `tars-v1` remains the default.

Test vector (canonical 12-word zero BIP-39 mnemonic):

    mnemonic   = "abandon abandon abandon abandon abandon abandon
                  abandon abandon abandon abandon abandon about"
    path       = m/44'/501'/0'/0'
    expected   = HAgk14JpMQLgt6rVgv7cBQFJWFto5Dqxi472uT3DKpqk
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass

from nacl.signing import SigningKey

from .encoding import b58encode

# Hardened-only ed25519 derivation per SLIP-0010 §3.
HARDENED_OFFSET = 0x80000000


@dataclass(frozen=True)
class SLIP10DerivedAccount:
    private_key: bytes  # 32 bytes (ed25519 seed)
    public_key: bytes  # 32 bytes
    address: str  # Base58 of the public key
    derivation_path: str


def _master_node(seed: bytes) -> tuple[bytes, bytes]:
    """SLIP-0010 master: HMAC-SHA512('ed25519 seed', seed) → (sk, cc)."""
    I = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    return I[:32], I[32:]


def _ckd_priv(sk: bytes, cc: bytes, index: int) -> tuple[bytes, bytes]:
    """SLIP-0010 child key derivation. ed25519 supports hardened only."""
    if index < HARDENED_OFFSET:
        index += HARDENED_OFFSET
    data = b"\x00" + sk + struct.pack(">I", index)
    I = hmac.new(cc, data, hashlib.sha512).digest()
    return I[:32], I[32:]


def _derive_along(seed: bytes, levels: list[int]) -> bytes:
    sk, cc = _master_node(seed)
    for level in levels:
        sk, cc = _ckd_priv(sk, cc, level)
    return sk


def derive_solana_phantom(
    bip39_seed: bytes, *, account: int = 0, change: int = 0
) -> SLIP10DerivedAccount:
    """Derive at ``m/44'/501'/{account}'/{change}'`` (Phantom default).

    Phantom's UI calls these levels "account" and "change" (a slight
    misnomer in ed25519 because everything is hardened). The first
    wallet uses ``account=0, change=0``; additional accounts increment
    ``account`` while keeping ``change=0``.
    """

    levels = [44, 501, account, change]
    sk_bytes = _derive_along(bip39_seed, levels)
    sk = SigningKey(sk_bytes)
    pk_bytes = bytes(sk.verify_key)
    address = b58encode(pk_bytes)
    path_str = "/".join(f"{level}'" for level in levels)
    return SLIP10DerivedAccount(
        private_key=sk_bytes,
        public_key=pk_bytes,
        address=address,
        derivation_path=f"m/{path_str}",
    )
