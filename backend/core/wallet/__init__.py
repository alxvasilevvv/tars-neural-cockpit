"""Phase M2 — agent-controllable crypto wallets.

Each TARS user can mint many wallets; agents (Phase M1) can be bound
to a wallet and call wallet domain actions to read balances or
**propose** transactions. Sending is destructive and always flows
through the policy gate.

Privacy posture:

- The mnemonic is generated locally (BIP-39 24-word seed) and is shown
  to the operator **exactly once** at creation time; it is never
  persisted in plaintext.
- Per-wallet private material is encrypted at rest with
  XChaCha20-Poly1305 (same primitive as the host identity vault) under
  a key derived from the host's master secret.
- HTTP responses NEVER contain the mnemonic, the seed, or any private
  key bytes after creation.

Chains supported in v1:

- ``solana`` — full keypair + address derivation via ed25519 (pynacl);
  signing is locally implemented.
- ``evm`` — address derivation only (placeholder hash-based id; proper
  secp256k1 signing lands when we add ``coincurve`` / ``eth-account``).
- ``ton`` — placeholder same shape as EVM.
"""

from .balance import (
    Balance,
    BalanceError,
    fetch_balance,
    fetch_evm_balance,
    fetch_solana_balance,
    fetch_ton_balance,
)
from .models import (
    Wallet,
    WalletChain,
    WalletPrivate,
    new_wallet_id,
)
from .service import (
    WalletError,
    WalletService,
    get_wallet_service,
    reset_wallet_service_for_tests,
)

__all__ = [
    "Balance",
    "BalanceError",
    "Wallet",
    "WalletChain",
    "WalletError",
    "WalletPrivate",
    "WalletService",
    "fetch_balance",
    "fetch_evm_balance",
    "fetch_solana_balance",
    "fetch_ton_balance",
    "get_wallet_service",
    "new_wallet_id",
    "reset_wallet_service_for_tests",
]
