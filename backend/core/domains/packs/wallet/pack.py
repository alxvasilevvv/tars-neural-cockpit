"""Wallet pack manifest + action wiring."""

from __future__ import annotations

from ...base import DomainManifest, DomainPack
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class WalletPack(DomainPack):
    manifest = DomainManifest(
        slug="wallet",
        name="Wallet",
        short="Crypto wallet under operator + agent control.",
        description=(
            "User-owned wallets across Solana, EVM and TON. Agents can "
            "read balances, build transactions, sign messages on chains "
            "where local signing is supported. Destructive actions flow "
            "through the policy gate."
        ),
        color="#fbbf24",
        capabilities=(
            "wallet_list",
            "wallet_address",
            "wallet_balance",
            "wallet_sign_message",
            "wallet_propose_send",
        ),
        audience="founders, traders, treasury operators",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return (
            "TARS_WALLETS_PASSPHRASE",
            # Per-chain RPC URLs the balance reader can use.
            "TARS_EVM_RPC_URL",
            "TARS_SOLANA_RPC_URL",
            "TARS_TON_RPC_URL",
        )

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT
