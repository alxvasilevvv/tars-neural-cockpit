"""Wallet domain pack — exposes :class:`backend.core.wallet.WalletService`
through the standard ``DomainPack`` surface so agents can call
``wallet.list``, ``wallet.address``, ``wallet.balance``,
``wallet.propose_send`` like any other action."""

from .pack import WalletPack

# Auto-register on import (matches the discipline of the other packs).
from ...registry import register

register(WalletPack())
