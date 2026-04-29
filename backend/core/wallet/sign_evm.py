"""Real EVM signing primitives (Phase N3).

Wraps `eth-account` (canonical Ethereum signer in the Python ecosystem)
behind the same interface our wallet module already uses for Solana.
This unblocks "send real ETH" because the resulting signed
transactions are valid raw hex you can ``eth_sendRawTransaction``
against any JSON-RPC endpoint.

Three primitives:

- :func:`derive_evm_account` — BIP-44 ``m/44'/60'/0'/0/{index}`` from a
  BIP-39 mnemonic. Real Keccak-256 over the uncompressed public key
  → 20-byte address (mixed-case checksum format per EIP-55).
- :func:`sign_evm_personal_message` — EIP-191 personal_sign envelope
  (``"\x19Ethereum Signed Message:\n" + len(msg) + msg``). Compatible
  with Metamask `eth_sign` / `personal_sign`.
- :func:`sign_evm_transaction` — EIP-1559 typed-2 transactions by
  default; falls back to legacy when the request lacks fee fields.

Imports of `eth_account` happen inside the functions so the rest of
the wallet module can be imported in environments where the dep is
unavailable (e.g. test slimming). The dispatcher in :mod:`derive`
honours the same lazy-import pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _ensure_0x(s: str) -> str:
    """``hexbytes.hex()`` may or may not prepend ``0x`` depending on the
    version. Normalise so callers can rely on the prefix."""
    return s if s.startswith("0x") else "0x" + s


@dataclass(frozen=True)
class EVMDerived:
    private_key: bytes  # 32 bytes
    public_key: bytes  # 64 bytes (uncompressed, no 0x04 prefix)
    address: str  # EIP-55 mixed-case
    derivation_path: str


def derive_evm_account(
    *,
    mnemonic: str,
    index: int = 0,
    account_path: str | None = None,
) -> EVMDerived:
    """Real BIP-44 derivation. Same path Metamask / Hardhat / Anvil use."""

    from eth_account import Account

    Account.enable_unaudited_hdwallet_features()
    path = account_path or f"m/44'/60'/0'/0/{index}"
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    sk_bytes = bytes(acct.key)
    # Canonical ethereum address derivation: keccak(uncompressed_pubkey)[-20:].
    from eth_keys import keys  # local import — small dep graph

    pk = keys.PrivateKey(sk_bytes)
    pub_bytes = pk.public_key.to_bytes()  # 64 bytes (no 0x04 prefix)
    return EVMDerived(
        private_key=sk_bytes,
        public_key=pub_bytes,
        address=acct.address,  # already EIP-55 mixed-case
        derivation_path=path,
    )


def sign_evm_personal_message(*, private_key: bytes, message: bytes) -> dict[str, Any]:
    """EIP-191 personal_sign — wraps the message and signs."""

    from eth_account import Account
    from eth_account.messages import encode_defunct

    encoded = encode_defunct(primitive=message)
    signed = Account.sign_message(encoded, private_key)
    return {
        "signature_hex": _ensure_0x(signed.signature.hex()),
        "r": hex(signed.r),
        "s": hex(signed.s),
        "v": signed.v,
        "message_hash": _ensure_0x(signed.message_hash.hex()),
    }


def recover_evm_personal_message(
    *, message: bytes, signature_hex: str
) -> str:
    """Verify a personal_sign signature; returns the recovered address."""

    from eth_account import Account
    from eth_account.messages import encode_defunct

    encoded = encode_defunct(primitive=message)
    return Account.recover_message(encoded, signature=signature_hex)


def sign_evm_transaction(
    *, private_key: bytes, tx: Mapping[str, Any]
) -> dict[str, Any]:
    """Sign a transaction dict.

    The tx dict is what `eth_account.Account.sign_transaction` accepts:

    - Type-2 (EIP-1559): ``{"to", "value", "gas", "maxFeePerGas",
      "maxPriorityFeePerGas", "nonce", "chainId", "data"?}``.
    - Legacy: ``{"to", "value", "gas", "gasPrice", "nonce",
      "chainId", "data"?}``.

    Returns ``{raw, hash, r, s, v}`` — ``raw`` is the broadcastable
    hex string, ``hash`` is the canonical tx hash. Validation errors
    bubble up as ``ValueError``.
    """

    from eth_account import Account

    # eth_account expects Python ints for value/gas/gasPrice/nonce/chainId.
    normalised: dict[str, Any] = {}
    for k, v in tx.items():
        if k in {
            "value",
            "gas",
            "gasPrice",
            "maxFeePerGas",
            "maxPriorityFeePerGas",
            "nonce",
            "chainId",
            "type",
        }:
            if isinstance(v, str):
                normalised[k] = int(v, 0)  # accepts "0x…" or decimal
            else:
                normalised[k] = int(v)
        else:
            normalised[k] = v
    signed = Account.sign_transaction(normalised, private_key)
    return {
        "raw": _ensure_0x(signed.raw_transaction.hex()),
        "hash": _ensure_0x(signed.hash.hex()),
        "r": hex(signed.r),
        "s": hex(signed.s),
        "v": signed.v,
    }
