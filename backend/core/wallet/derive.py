"""Per-chain key + address derivation.

Each chain plugs in two functions:

- ``derive(seed, index)`` → ``(private_key_bytes, public_key_bytes,
  address_str, derivation_path_str)``.
- ``sign(private_key, message)`` → ``signature_bytes`` (raises
  ``NotImplementedError`` when signing is not supported).

The chain table is intentionally small and explicit. Real
production-grade EVM/BTC support belongs in a follow-up phase that
adds ``coincurve`` / ``eth-account`` as dependencies.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from nacl.signing import SigningKey

from .encoding import b58encode
from .models import WalletChain


@dataclass(frozen=True)
class DerivedAccount:
    chain: WalletChain
    private_key: bytes
    public_key: bytes
    address: str
    derivation_path: str


def _derive_chain_seed(seed: bytes, *, chain: WalletChain, index: int) -> bytes:
    """HMAC-SHA512 to mix the BIP-39 seed with the chain + index.

    Not BIP-32 — those slip-0010 derivations need ed25519-bip32 / secp256k1
    primitives we don't have. This is a deterministic, well-defined
    *TARS-specific* derivation that's stable across hosts.
    """
    label = f"tars-wallet/v1/{chain.value}/{index}".encode("ascii")
    return hmac.new(seed, label, hashlib.sha512).digest()[:32]


def derive_solana(
    seed: bytes,
    *,
    index: int = 0,
    derivation_scheme: str = "tars-v1",
) -> DerivedAccount:
    """Derive a Solana ed25519 keypair from the BIP-39 seed.

    Schemes:

    - ``tars-v1`` (default): legacy HMAC-SHA512(seed, label).
    - ``bip44-501-phantom``: SLIP-0010 ed25519 at
      ``m/44'/501'/{index}'/0'``. The resulting address matches what
      Phantom / Solflare / Backpack would derive from the same
      mnemonic, so the operator can re-import the recovery phrase
      into any of those wallets and see TARS-minted funds.
    """

    if derivation_scheme == "bip44-501-phantom":
        from .slip10 import derive_solana_phantom

        derived = derive_solana_phantom(seed, account=index, change=0)
        return DerivedAccount(
            chain=WalletChain.SOLANA,
            private_key=derived.private_key,
            public_key=derived.public_key,
            address=derived.address,
            derivation_path=derived.derivation_path,
        )

    sk_bytes = _derive_chain_seed(seed, chain=WalletChain.SOLANA, index=index)
    sk = SigningKey(sk_bytes)
    pk_bytes = bytes(sk.verify_key)
    address = b58encode(pk_bytes)
    return DerivedAccount(
        chain=WalletChain.SOLANA,
        private_key=sk_bytes,
        public_key=pk_bytes,
        address=address,
        derivation_path=f"m/tars/v1/solana/{index}",
    )


def derive_evm(
    seed: bytes,
    *,
    index: int = 0,
    mnemonic: str | None = None,
) -> DerivedAccount:
    """Real BIP-44 EVM derivation when ``mnemonic`` is supplied.

    Without the mnemonic we fall back to the legacy placeholder so
    pure-seed callers still get a deterministic id (used by older
    test fixtures). New callers should always pass ``mnemonic`` —
    the wallet service does this automatically.
    """

    if mnemonic is not None:
        from .sign_evm import derive_evm_account

        derived = derive_evm_account(mnemonic=mnemonic, index=index)
        return DerivedAccount(
            chain=WalletChain.EVM,
            private_key=derived.private_key,
            public_key=derived.public_key,
            address=derived.address,
            derivation_path=derived.derivation_path,
        )

    # Legacy placeholder (kept so older fixtures still derive a
    # deterministic id; new code paths always pass mnemonic).
    from .encoding import keccak256_placeholder

    sk_bytes = _derive_chain_seed(seed, chain=WalletChain.EVM, index=index)
    pk_proxy = keccak256_placeholder(sk_bytes)
    address_hash = keccak256_placeholder(pk_proxy)
    address = "0x" + address_hash[-20:].hex()
    return DerivedAccount(
        chain=WalletChain.EVM,
        private_key=sk_bytes,
        public_key=pk_proxy,
        address=address,
        derivation_path=f"m/tars/v1/evm/{index}",
    )


def derive_ton(seed: bytes, *, index: int = 0) -> DerivedAccount:
    """Real wallet **v3R2** address derivation (Phase N4).

    The 32-byte ed25519 seed comes from our HMAC-SHA512 chain-seed
    scheme — *not* the TON-mnemonic PBKDF2 path. The resulting v3R2
    address is canonical and can receive funds; signing is wired
    through :mod:`sign_ton`.
    """

    sk_bytes = _derive_chain_seed(seed, chain=WalletChain.TON, index=index)
    from .sign_ton import derive_ton_account

    derived = derive_ton_account(ed25519_seed=sk_bytes, workchain=0)
    return DerivedAccount(
        chain=WalletChain.TON,
        # Store the 32-byte ed25519 seed (NOT the 64-byte expanded
        # secret_key) — the wallet service treats this as the single
        # source of truth and re-expands it on every signing call.
        private_key=sk_bytes,
        public_key=derived.public_key,
        address=derived.address,
        derivation_path=f"m/tars/v1/ton/{index}",
    )


def derive(
    *,
    chain: WalletChain,
    seed: bytes,
    index: int = 0,
    mnemonic: str | None = None,
    derivation_scheme: str = "tars-v1",
) -> DerivedAccount:
    if chain == WalletChain.SOLANA:
        return derive_solana(seed, index=index, derivation_scheme=derivation_scheme)
    if chain == WalletChain.EVM:
        return derive_evm(seed, index=index, mnemonic=mnemonic)
    if chain == WalletChain.TON:
        return derive_ton(seed, index=index)
    raise ValueError(f"derive: unsupported chain {chain}")


def sign_message(*, chain: WalletChain, private_key: bytes, message: bytes) -> bytes:
    if chain == WalletChain.SOLANA:
        return SigningKey(private_key).sign(message).signature
    if chain == WalletChain.EVM:
        # EIP-191 personal_sign — returns 65-byte (r||s||v) signature.
        from .sign_evm import sign_evm_personal_message

        out = sign_evm_personal_message(private_key=private_key, message=message)
        return bytes.fromhex(out["signature_hex"].removeprefix("0x"))
    if chain == WalletChain.TON:
        # ed25519 over the message bytes; symmetric to Solana.
        return SigningKey(private_key).sign(message).signature
    raise NotImplementedError(
        f"signing not supported for chain={chain.value}"
    )
