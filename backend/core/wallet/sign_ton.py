"""Real TON signing primitives (Phase N4).

Closes the second crypto blocker from `docs/LAUNCH_READINESS.md`. We
now derive a canonical wallet **v3R2** contract address (the same
shape Tonkeeper / MyTonWallet / OpenMask issue), and we can sign
transfer messages locally so the operator can broadcast the resulting
BoC via TON Center / a public liteserver / their own bag-of-cells
endpoint.

Three primitives mirror the EVM module:

- :func:`derive_ton_account` — given a 32-byte ed25519 seed, produce
  the v3R2 wallet contract address and the matching pub/priv keys.
- :func:`sign_ton_message` — pure ed25519 signature over an arbitrary
  byte string (used by the cockpit "prove ownership" flow).
- :func:`sign_ton_transfer` — build a v3R2 external message that
  contains the operator's transfer (to / amount / seqno / optional
  text comment) and sign it. Returns ``{boc, body_hash}`` —
  ``boc`` is base64-encoded and broadcastable.

Why not BIP-39 → TON mnemonic? TON's mnemonic format is a *different*
standard (PBKDF2 over the 24-word phrase, not BIP-39's checksum +
BIP-32). Re-using BIP-39 phrases for TON is a deliberate trade: the
resulting v3R2 address is just as valid (it's keyed on the public
key, not on how the mnemonic was derived), but it won't match the
canonical TON-mnemonic → address path. Operators who want to import
an existing Tonkeeper wallet would hand it the TON mnemonic
directly — that's a separate path we can wire later.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Mapping

from nacl.bindings import crypto_sign_seed_keypair
from nacl.signing import SigningKey


@dataclass(frozen=True)
class TONDerived:
    private_key: bytes  # 64 bytes (ed25519 expanded; nacl secret_key)
    public_key: bytes  # 32 bytes
    address: str  # user-friendly bounceable, e.g. "EQ…"
    raw_address: str  # raw "0:<hex>"
    workchain: int
    seed_seed: bytes  # 32-byte ed25519 seed (kept for re-derivation)


def derive_ton_account(*, ed25519_seed: bytes, workchain: int = 0) -> TONDerived:
    """Construct a v3R2 wallet address from a 32-byte ed25519 seed."""

    if len(ed25519_seed) != 32:
        raise ValueError(
            f"ed25519 seed must be 32 bytes, got {len(ed25519_seed)}"
        )
    public_key, secret_key = crypto_sign_seed_keypair(ed25519_seed)
    # Local import — keeps the rest of the wallet module importable in
    # environments where tonsdk is not yet installed.
    from tonsdk.contract.wallet import WalletV3ContractR2

    contract = WalletV3ContractR2(
        public_key=public_key, private_key=secret_key, wc=workchain
    )
    addr = contract.address
    return TONDerived(
        private_key=secret_key,
        public_key=public_key,
        address=addr.to_string(True, True, True),  # bounceable + url-safe + b64
        raw_address=addr.to_string(False),
        workchain=workchain,
        seed_seed=ed25519_seed,
    )


def sign_ton_message(*, ed25519_seed: bytes, message: bytes) -> dict[str, Any]:
    """Pure ed25519 signature; symmetric to the Solana primitive."""

    if len(ed25519_seed) != 32:
        raise ValueError("ed25519 seed must be 32 bytes")
    sk = SigningKey(ed25519_seed)
    sig = sk.sign(message).signature
    return {
        "signature_hex": "0x" + sig.hex(),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
        "public_key_hex": "0x" + sk.verify_key.encode().hex(),
    }


def sign_ton_transfer(
    *,
    ed25519_seed: bytes,
    to: str,
    amount_nanoton: int,
    seqno: int,
    workchain: int = 0,
    payload: str | None = None,
    send_mode: int = 3,
) -> dict[str, Any]:
    """Build + sign a wallet v3R2 external transfer message.

    Returns ``{boc, body_hash, address, to, amount_nanoton, seqno}``.
    ``boc`` is base64 of the signed external-in message — broadcast
    via TON Center ``sendBoc`` (or any liteserver client).

    ``payload`` is an optional UTF-8 text comment (the same field
    Tonkeeper exposes as the "Comment" line). Pass ``None`` to send
    a bare transfer.
    """

    if len(ed25519_seed) != 32:
        raise ValueError("ed25519 seed must be 32 bytes")
    if amount_nanoton < 0:
        raise ValueError("amount_nanoton must be non-negative")
    if seqno < 0:
        raise ValueError("seqno must be non-negative")

    derived = derive_ton_account(ed25519_seed=ed25519_seed, workchain=workchain)

    from tonsdk.contract.wallet import WalletV3ContractR2

    contract = WalletV3ContractR2(
        public_key=derived.public_key,
        private_key=derived.private_key,
        wc=workchain,
    )
    try:
        query = contract.create_transfer_message(
            to_addr=to,
            amount=int(amount_nanoton),
            seqno=int(seqno),
            payload=payload,
            send_mode=send_mode,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"ton_transfer_invalid: {exc}") from exc

    message = query["message"]  # signed external-in message Cell
    body = query["body"]  # signed body Cell (for hashing)
    boc_b64 = base64.b64encode(message.to_boc(False)).decode("ascii")
    body_hash = body.bytes_hash().hex()
    return {
        "boc": boc_b64,
        "body_hash": "0x" + body_hash,
        "address": derived.address,
        "to": to,
        "amount_nanoton": int(amount_nanoton),
        "seqno": int(seqno),
        "workchain": workchain,
    }


def to_nano(amount_ton: str | float) -> int:
    """Convert a TON amount (e.g. ``"0.5"``) into nanoton (10**9 units)."""

    from decimal import Decimal

    return int((Decimal(str(amount_ton)) * Decimal(10**9)).to_integral_value())


def parse_amount(value: str | int | float) -> int:
    """Accept ``"1.5"``, ``"1500000000"``, or an int → nanoton.

    The convention: bare integers (or strings of digits) are already
    nanoton; anything with a decimal point is treated as TON and
    multiplied by 10**9.
    """

    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return to_nano(value)
    s = str(value).strip()
    if not s:
        raise ValueError("empty amount")
    if "." in s:
        return to_nano(s)
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    return int(s)
