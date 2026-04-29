"""Live JSON-RPC helpers for transaction-prep flows (Phase P2/P3/P4).

Building a chain-specific transaction in TARS requires knowing the
current ``recent_blockhash`` (Solana), ``nonce`` (EVM), or ``seqno``
(TON). Those are read-only RPC queries — we never broadcast from
here. Each helper has a dedicated HTTP route in
``web_extras/routers/wallet.py``.

Stdlib only (``urllib.request``) — same hard rule as
``balance.py``. Endpoints are configurable via the existing
``TARS_*_RPC_URL`` env vars, so operators can point them at a
private RPC if desired.
"""

from __future__ import annotations

from typing import Any

from .balance import (
    DEFAULT_TIMEOUT_S,
    BalanceError,
    _post_json_rpc,
    _resolve_rpc,
)
from .models import WalletChain


class RPCError(BalanceError):
    """Specific to chain_helpers; subclass of BalanceError so existing
    wallet error handling keeps working."""


# ---- Solana --------------------------------------------------------------


def get_solana_blockhash(
    *, rpc_url: str | None = None, timeout: float = DEFAULT_TIMEOUT_S
) -> dict[str, Any]:
    """Fetch the current ``recent_blockhash`` via ``getLatestBlockhash``.

    Returns ``{blockhash, last_valid_block_height, rpc_url}``.

    Raises :class:`RPCError` on transport / parsing failure.
    """

    url = _resolve_rpc(WalletChain.SOLANA, rpc_url)
    out = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": [{"commitment": "finalized"}],
        },
        timeout=timeout,
    )
    result = out.get("result")
    if not isinstance(result, dict):
        raise RPCError(f"getLatestBlockhash unexpected shape: {result}")
    value = result.get("value")
    if not isinstance(value, dict):
        raise RPCError(f"getLatestBlockhash missing value: {result}")
    blockhash = value.get("blockhash")
    last_valid = value.get("lastValidBlockHeight")
    if not isinstance(blockhash, str) or not blockhash:
        raise RPCError(f"getLatestBlockhash empty blockhash: {value}")
    return {
        "blockhash": blockhash,
        "last_valid_block_height": (
            int(last_valid) if isinstance(last_valid, (int, float)) else None
        ),
        "rpc_url": url,
    }


# ---- EVM -----------------------------------------------------------------


def get_evm_nonce(
    address: str,
    *,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    block_tag: str = "pending",
) -> dict[str, Any]:
    """Fetch ``eth_getTransactionCount`` for ``address``.

    ``block_tag=pending`` matches what wallets like MetaMask use
    when constructing the next outgoing transaction. Pass
    ``"latest"`` to count only mined txs.

    Returns ``{address, nonce, nonce_hex, block_tag, rpc_url}``.
    """

    url = _resolve_rpc(WalletChain.EVM, rpc_url)
    if not address.startswith("0x") or len(address) != 42:
        raise RPCError(f"evm address malformed: {address}")
    if block_tag not in ("pending", "latest", "earliest"):
        raise RPCError(f"evm block_tag invalid: {block_tag}")
    out = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getTransactionCount",
            "params": [address, block_tag],
        },
        timeout=timeout,
    )
    result = out.get("result")
    if not isinstance(result, str) or not result.startswith("0x"):
        raise RPCError(f"eth_getTransactionCount unexpected shape: {result}")
    try:
        nonce = int(result, 16)
    except ValueError as exc:
        raise RPCError(f"eth_getTransactionCount nonce not hex: {result}") from exc
    return {
        "address": address,
        "nonce": nonce,
        "nonce_hex": result,
        "block_tag": block_tag,
        "rpc_url": url,
    }


# ---- TON -----------------------------------------------------------------


def get_ton_seqno(
    address: str,
    *,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Fetch the seqno of a v3R2 wallet via TON Center / TON HTTP API.

    Returns ``{address, seqno, rpc_url}``. If the wallet hasn't been
    deployed on-chain yet, seqno is ``0`` and the call still succeeds.

    TON Center exposes a ``runGetMethod`` JSON-RPC entry. For the
    standard v3R2 wallet contract we call the ``seqno`` getter
    which returns a stack with a single int.
    """

    url = _resolve_rpc(WalletChain.TON, rpc_url)
    if len(address) < 4:
        raise RPCError(f"ton address malformed: {address}")
    out = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "runGetMethod",
            "params": {
                "address": address,
                "method": "seqno",
                "stack": [],
            },
        },
        timeout=timeout,
    )
    result = out.get("result")
    if not isinstance(result, dict):
        raise RPCError(f"ton runGetMethod unexpected shape: {result}")
    # TON Center returns the stack under "stack" with type-tagged tuples
    # like [["num", "0x0"]]. Fresh, undeployed wallets return exit_code != 0
    # and an empty stack — surface that as seqno=0.
    exit_code = result.get("exit_code", 0)
    stack = result.get("stack") or []
    if exit_code != 0 or not stack:
        return {"address": address, "seqno": 0, "rpc_url": url}
    try:
        head = stack[0]
        # Tonsdk style: ["num", "0x..."]
        if isinstance(head, list) and len(head) >= 2 and head[0] == "num":
            seqno = int(head[1], 16) if isinstance(head[1], str) and head[1].startswith("0x") else int(head[1])
        elif isinstance(head, dict) and "value" in head:
            v = head["value"]
            seqno = int(v, 16) if isinstance(v, str) and v.startswith("0x") else int(v)
        else:
            raise RPCError(f"ton seqno stack head unrecognised: {head}")
    except (TypeError, ValueError, IndexError) as exc:
        raise RPCError(f"ton seqno parse failed: {exc}") from exc
    return {"address": address, "seqno": seqno, "rpc_url": url}
