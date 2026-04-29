"""Real Solana transaction signing primitives (Phase N5).

Closes the last partial in `docs/LAUNCH_READINESS.md`'s wallet matrix.
Solana wallets already had ed25519 *message* signing via PyNaCl; this
module adds *transaction* signing — building a `system_program::transfer`
instruction, dropping it into a `Transaction` keyed on a recent
blockhash, and emitting the broadcastable raw bytes (base64 +
base58 + hex) so the operator can `sendTransaction` against any RPC.

We deliberately do **not** fetch the blockhash here — the caller
(usually the cockpit or an agent task) supplies one because:

- It keeps `sign_sol.py` synchronous and trivially testable.
- It matches the EVM / TON pattern (caller owns nonce / seqno).
- It lets the policy gate inspect the prepared tx *before* we hit
  the RPC, which is the trust-model TARS uses everywhere.

Two primitives mirror the EVM/TON modules:

- :func:`derive_solana_keypair` — 32-byte seed → solders ``Keypair``
  with the public address (Base58). Same address our existing
  `derive.derive_solana` produces (both are pure ed25519).
- :func:`sign_solana_transfer` — system_program::transfer +
  signature. Returns ``{raw_b64, raw_b58, raw_hex, tx_signature,
  signer, recipient, lamports, blockhash}``.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from .encoding import b58encode


@dataclass(frozen=True)
class SolanaDerived:
    secret_key: bytes  # 64 bytes (solders Keypair representation)
    public_key: bytes  # 32 bytes
    address: str  # Base58, 32–44 chars


def derive_solana_keypair(*, ed25519_seed: bytes) -> SolanaDerived:
    """Construct a solders Keypair from the 32-byte seed."""

    if len(ed25519_seed) != 32:
        raise ValueError(
            f"ed25519 seed must be 32 bytes, got {len(ed25519_seed)}"
        )
    from solders.keypair import Keypair

    kp = Keypair.from_seed(ed25519_seed)
    full = bytes(kp)  # 64 bytes (seed || pubkey)
    pub = bytes(kp.pubkey())
    return SolanaDerived(
        secret_key=full,
        public_key=pub,
        address=str(kp.pubkey()),
    )


def sign_solana_transfer(
    *,
    ed25519_seed: bytes,
    to: str,
    lamports: int,
    recent_blockhash: str,
    memo: str | None = None,
) -> dict[str, Any]:
    """Build + sign a ``system_program::transfer`` transaction.

    Returns a dict with the broadcastable encodings:

    - ``raw_b64`` — base64 (what most RPC clients expect for
      ``sendTransaction`` with ``encoding=base64``).
    - ``raw_b58`` — base58 (the historical Solana default).
    - ``raw_hex`` — convenience for inspection.
    - ``tx_signature`` — base58 of the first signature, what
      explorers (Solscan / Solana Explorer) key on.
    - ``signer``, ``recipient``, ``lamports``, ``blockhash`` — echoes
      back the inputs for audit.

    The caller is responsible for supplying ``recent_blockhash`` —
    typically by calling ``getLatestBlockhash`` on a Solana RPC and
    passing the ``blockhash`` field through. ``memo`` is currently
    advisory (used in the policy-gate display); attaching it as a
    real spl-memo instruction is a follow-up.
    """

    if len(ed25519_seed) != 32:
        raise ValueError("ed25519 seed must be 32 bytes")
    if lamports < 0:
        raise ValueError("lamports must be non-negative")

    from solders.hash import Hash
    from solders.keypair import Keypair
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solders.transaction import Transaction

    try:
        recipient = Pubkey.from_string(to)
    except Exception as exc:  # solders raises broad ValueError-ish
        raise ValueError(f"invalid_recipient: {exc}") from exc
    try:
        bh = Hash.from_string(recent_blockhash)
    except Exception as exc:
        raise ValueError(f"invalid_blockhash: {exc}") from exc

    kp = Keypair.from_seed(ed25519_seed)
    ix = transfer(
        TransferParams(
            from_pubkey=kp.pubkey(),
            to_pubkey=recipient,
            lamports=int(lamports),
        )
    )
    msg = Message.new_with_blockhash([ix], kp.pubkey(), bh)
    tx = Transaction([kp], msg, bh)
    raw = bytes(tx)
    sig = tx.signatures[0]
    return {
        "raw_b64": base64.b64encode(raw).decode("ascii"),
        "raw_b58": b58encode(raw),
        "raw_hex": "0x" + raw.hex(),
        "tx_signature": str(sig),
        "signer": str(kp.pubkey()),
        "recipient": to,
        "lamports": int(lamports),
        "blockhash": recent_blockhash,
        "memo": memo,
    }


def parse_lamports(value: str | int | float) -> int:
    """Accept ``"1.5"`` (SOL), ``"1500000000"`` (lamports), int, float.

    Bare integers / digit-strings → already lamports.
    Strings with a decimal point / floats → SOL → ×10**9.
    """

    if isinstance(value, int):
        return value
    if isinstance(value, float):
        from decimal import Decimal

        return int((Decimal(str(value)) * Decimal(10**9)).to_integral_value())
    s = str(value).strip()
    if not s:
        raise ValueError("empty amount")
    if "." in s:
        from decimal import Decimal

        return int((Decimal(s) * Decimal(10**9)).to_integral_value())
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    return int(s)
