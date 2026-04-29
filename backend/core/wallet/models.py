"""Wallet dataclasses for Phase M2."""

from __future__ import annotations

import enum
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional


class WalletChain(str, enum.Enum):
    SOLANA = "solana"
    EVM = "evm"
    TON = "ton"

    @classmethod
    def from_str(cls, raw: str) -> "WalletChain":
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"unsupported chain: {raw}; expected one of "
                f"{[c.value for c in cls]}"
            ) from exc


def new_wallet_id() -> str:
    return "wlt_" + secrets.token_hex(8)


# Derivation schemes — how the BIP-39 seed maps to a chain keypair.
# - tars-v1: legacy. HMAC-SHA512(seed, "tars-wallet/v1/{chain}/{index}")[:32].
#   Default for backward compatibility.
# - bip44-501-phantom: Phantom-compatible. SLIP-0010 ed25519,
#   m/44'/501'/{account}'/0'. Solana-only.
# - bip44-60-evm: deferred — EVM already uses BIP-44 m/44'/60'/0'/0/{i}
#   inside `sign_evm.py`.
DERIVATION_SCHEMES = ("tars-v1", "bip44-501-phantom")


def _now() -> float:
    return time.time()


@dataclass(frozen=True)
class Wallet:
    """Public-only view of a wallet (safe to serialise)."""

    id: str
    label: str
    chain: WalletChain
    address: str
    public_key_hex: str
    derivation_path: str
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    metadata_json: str = "{}"
    seed_fingerprint: Optional[str] = None  # 12-hex of sha256(seed); safe to log
    derivation_scheme: str = "tars-v1"

    @property
    def signing_supported(self) -> bool:
        # All three chains now sign locally:
        #   - Solana: ed25519 via PyNaCl.
        #   - EVM:    secp256k1 + Keccak-256 via eth-account
        #             (BIP-44 + EIP-191 + EIP-1559).
        #   - TON:    ed25519 + wallet v3R2 message build via tonsdk.
        return self.chain in {
            WalletChain.SOLANA,
            WalletChain.EVM,
            WalletChain.TON,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "chain": self.chain.value,
            "address": self.address,
            "public_key_hex": self.public_key_hex,
            "derivation_path": self.derivation_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "seed_fingerprint": self.seed_fingerprint,
            "signing_supported": self.signing_supported,
            "derivation_scheme": self.derivation_scheme,
        }


@dataclass(frozen=True)
class WalletPrivate:
    """Sensitive material kept inside :class:`WalletService` only.

    Never returned by the HTTP layer. Stored encrypted at rest via the
    file vault using XChaCha20-Poly1305 (same primitive used for the
    host identity).
    """

    wallet_id: str
    chain: WalletChain
    private_key: bytes
    seed: bytes
