"""Read on-chain balances via configurable JSON-RPC endpoints.

Stdlib only (``urllib.request``) — same hard rule as the rest of the
wallet module. Each chain has a default RPC endpoint that the operator
overrides via env:

- ``TARS_SOLANA_RPC_URL`` (default: ``https://api.mainnet-beta.solana.com``)
- ``TARS_EVM_RPC_URL``    (default: ``https://eth.llamarpc.com``)
- ``TARS_TON_RPC_URL``    (default: ``https://toncenter.com/api/v2/jsonRPC``)

This module is **read-only**: it never sends private material over the
wire and never broadcasts a transaction. Sending is the policy gate's
problem.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from .models import WalletChain


SOLANA_DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
EVM_DEFAULT_RPC = "https://eth.llamarpc.com"
TON_DEFAULT_RPC = "https://toncenter.com/api/v2/jsonRPC"

DEFAULT_TIMEOUT_S = 8.0


class BalanceError(RuntimeError):
    """Raised when an RPC call fails or returns an unparsable shape."""


@dataclass(frozen=True)
class Balance:
    chain: WalletChain
    address: str
    raw: int  # smallest indivisible unit (lamports / wei / nanoton)
    decimals: int  # 9 for SOL, 18 for ETH, 9 for TON
    symbol: str
    rpc_url: str

    @property
    def display(self) -> str:
        """Human-readable string with full precision (no rounding)."""
        if self.raw == 0:
            return "0"
        if self.decimals == 0:
            return str(self.raw)
        s = str(self.raw).zfill(self.decimals + 1)
        whole, frac = s[:-self.decimals], s[-self.decimals:]
        frac = frac.rstrip("0")
        return f"{whole}.{frac}" if frac else whole

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": self.chain.value,
            "address": self.address,
            "raw": str(self.raw),  # stringify — JS can't fit > 2^53 reliably
            "decimals": self.decimals,
            "symbol": self.symbol,
            "display": self.display,
            "rpc_url": self.rpc_url,
        }


def _resolve_rpc(chain: WalletChain, override: str | None) -> str:
    if override:
        return override.strip()
    if chain == WalletChain.SOLANA:
        return os.getenv("TARS_SOLANA_RPC_URL", SOLANA_DEFAULT_RPC)
    if chain == WalletChain.EVM:
        return os.getenv("TARS_EVM_RPC_URL", EVM_DEFAULT_RPC)
    if chain == WalletChain.TON:
        return os.getenv("TARS_TON_RPC_URL", TON_DEFAULT_RPC)
    raise BalanceError(f"unsupported chain: {chain}")


def _post_json_rpc(
    url: str,
    body: Mapping[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise BalanceError(f"rpc HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise BalanceError(f"rpc unreachable: {exc.reason}") from exc
    except (OSError, TimeoutError) as exc:
        # Covers DNS failures, broken sockets, OS-level resets, ssl errors.
        raise BalanceError(f"rpc transport failure: {exc}") from exc
    try:
        out = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BalanceError(f"rpc response not JSON: {exc}") from exc
    if not isinstance(out, dict):
        raise BalanceError(f"rpc response unexpected shape: {type(out).__name__}")
    if "error" in out and out["error"]:
        err = out["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise BalanceError(f"rpc error: {msg}")
    return out


# ---- per-chain readers --------------------------------------------------


def fetch_solana_balance(
    address: str,
    *,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Balance:
    url = _resolve_rpc(WalletChain.SOLANA, rpc_url)
    out = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address],
        },
        timeout=timeout,
    )
    result = out.get("result")
    if not isinstance(result, dict) or "value" not in result:
        raise BalanceError(f"solana getBalance shape unexpected: {result}")
    try:
        lamports = int(result["value"])
    except (TypeError, ValueError) as exc:
        raise BalanceError(f"solana value not int: {result['value']}") from exc
    return Balance(
        chain=WalletChain.SOLANA,
        address=address,
        raw=lamports,
        decimals=9,
        symbol="SOL",
        rpc_url=url,
    )


def fetch_evm_balance(
    address: str,
    *,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Balance:
    url = _resolve_rpc(WalletChain.EVM, rpc_url)
    out = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getBalance",
            "params": [address, "latest"],
        },
        timeout=timeout,
    )
    raw = out.get("result")
    if not isinstance(raw, str) or not raw.startswith("0x"):
        raise BalanceError(f"evm eth_getBalance shape unexpected: {raw}")
    try:
        wei = int(raw, 16)
    except ValueError as exc:
        raise BalanceError(f"evm result not hex: {raw}") from exc
    return Balance(
        chain=WalletChain.EVM,
        address=address,
        raw=wei,
        decimals=18,
        symbol="ETH",
        rpc_url=url,
    )


def fetch_ton_balance(
    address: str,
    *,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Balance:
    url = _resolve_rpc(WalletChain.TON, rpc_url)
    # toncenter exposes JSON-RPC ``getAddressBalance``.
    out = _post_json_rpc(
        url,
        {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "getAddressBalance",
            "params": {"address": address},
        },
        timeout=timeout,
    )
    res = out.get("result")
    if isinstance(res, dict) and "balance" in res:
        raw_val = res["balance"]
    else:
        raw_val = res
    try:
        nano = int(str(raw_val))
    except (TypeError, ValueError) as exc:
        raise BalanceError(f"ton balance not int: {raw_val}") from exc
    return Balance(
        chain=WalletChain.TON,
        address=address,
        raw=nano,
        decimals=9,
        symbol="TON",
        rpc_url=url,
    )


def fetch_balance(
    *,
    chain: WalletChain,
    address: str,
    rpc_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Balance:
    if chain == WalletChain.SOLANA:
        return fetch_solana_balance(address, rpc_url=rpc_url, timeout=timeout)
    if chain == WalletChain.EVM:
        return fetch_evm_balance(address, rpc_url=rpc_url, timeout=timeout)
    if chain == WalletChain.TON:
        return fetch_ton_balance(address, rpc_url=rpc_url, timeout=timeout)
    raise BalanceError(f"unsupported chain: {chain}")
