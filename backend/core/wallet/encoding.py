"""Tiny encoding helpers used by wallet derivation.

Stdlib-only on purpose — wallet code must run anywhere TARS runs and
must never pull in random crypto packages from PyPI.

- :func:`b58encode` / :func:`b58decode` — Base58 (Bitcoin/Solana
  alphabet, no Ripple variant). Pure-Python, ≤30 lines.
- :func:`keccak256` — wraps the stdlib SHA3-256, but EVM requires the
  *Keccak-256 with original Keccak padding* (pre-FIPS). Until we add
  ``pycryptodome`` we expose a hash that's "EVM-shaped" but flagged
  ``placeholder=True`` so the wallet layer can advertise honestly.
"""

from __future__ import annotations

import hashlib
from typing import Final

_B58_ALPHABET: Final = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX: Final = {ch: i for i, ch in enumerate(_B58_ALPHABET)}


def b58encode(data: bytes) -> str:
    """Encode ``data`` as Base58 (Bitcoin/Solana variant)."""
    if not data:
        return ""
    # Count leading zero bytes — they encode as leading '1's.
    n_zero = 0
    for byte in data:
        if byte == 0:
            n_zero += 1
        else:
            break
    num = int.from_bytes(data, "big")
    out = bytearray()
    while num > 0:
        num, rem = divmod(num, 58)
        out.append(_B58_ALPHABET[rem])
    out.reverse()
    return ("1" * n_zero) + out.decode("ascii")


def b58decode(text: str) -> bytes:
    """Decode a Base58 string. Raises ``ValueError`` on invalid input."""
    if not text:
        return b""
    n_zero = 0
    for ch in text:
        if ch == "1":
            n_zero += 1
        else:
            break
    num = 0
    for ch in text:
        try:
            num = num * 58 + _B58_INDEX[ord(ch)]
        except KeyError as exc:
            raise ValueError(f"invalid base58 char: {ch!r}") from exc
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    return b"\x00" * n_zero + body


def keccak256_placeholder(data: bytes) -> bytes:
    """SHA3-256 standin used to derive deterministic EVM-shaped addresses.

    Real EVM signing/address derivation uses Keccak-256 (NOT FIPS
    SHA3-256). We mark the resulting Wallet with ``signing_supported
    = False`` so the cockpit + agent layer never claim we can sign
    EVM transactions on this code path.
    """
    return hashlib.sha3_256(data).digest()
