"""Wallet pack action handlers."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Mapping

from backend.core.wallet import (
    BalanceError,
    WalletError,
    fetch_balance,
    get_wallet_service,
)

from ...base import ActionSpec


async def _list_wallets(args: Mapping[str, Any]) -> Mapping[str, Any]:
    chain = args.get("chain")
    svc = get_wallet_service()
    items = await svc.list_wallets(chain=chain)
    return {
        "ok": True,
        "count": len(items),
        "wallets": [w.to_dict() for w in items],
    }


async def _wallet_address(args: Mapping[str, Any]) -> Mapping[str, Any]:
    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    if not wallet_id:
        return {"ok": False, "error": "wallet_id is required"}
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        return {"ok": False, "error": "wallet_not_found"}
    return {
        "ok": True,
        "address": wallet.address,
        "chain": wallet.chain.value,
        "label": wallet.label,
    }


async def _wallet_balance(args: Mapping[str, Any]) -> Mapping[str, Any]:
    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    rpc_url = args.get("rpc_url")
    if not wallet_id:
        return {"ok": False, "error": "wallet_id is required"}
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        return {"ok": False, "error": "wallet_not_found"}
    try:
        bal = await asyncio.to_thread(
            fetch_balance,
            chain=wallet.chain,
            address=wallet.address,
            rpc_url=rpc_url if isinstance(rpc_url, str) and rpc_url else None,
        )
    except BalanceError as exc:
        return {
            "ok": False,
            "wallet_id": wallet_id,
            "chain": wallet.chain.value,
            "error": str(exc),
        }
    return {"ok": True, "balance": bal.to_dict()}


async def _wallet_sign_solana_transfer(args: Mapping[str, Any]) -> Mapping[str, Any]:
    from backend.core.wallet.sign_sol import parse_lamports

    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    to = str(args.get("to") or "").strip()
    blockhash = str(args.get("recent_blockhash") or "").strip()
    amount = args.get("amount")
    if not wallet_id or not to or not blockhash or amount is None:
        return {
            "ok": False,
            "error": "wallet_id, to, recent_blockhash, and amount required",
        }
    try:
        lamports = parse_lamports(amount)
    except (ValueError, ArithmeticError) as exc:
        return {"ok": False, "error": f"invalid_amount: {exc}"}
    try:
        signed = await svc.sign_solana_transfer(
            wallet_id=wallet_id,
            to=to,
            lamports=lamports,
            recent_blockhash=blockhash,
            memo=args.get("memo"),
        )
    except WalletError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "signed": signed}


async def _wallet_sign_ton_transfer(args: Mapping[str, Any]) -> Mapping[str, Any]:
    from backend.core.wallet.sign_ton import parse_amount

    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    to = str(args.get("to") or "").strip()
    amount = args.get("amount")
    if not wallet_id or not to or amount is None:
        return {"ok": False, "error": "wallet_id, to, and amount required"}
    try:
        amount_nanoton = parse_amount(amount)
    except (ValueError, ArithmeticError) as exc:
        return {"ok": False, "error": f"invalid_amount: {exc}"}
    try:
        signed = await svc.sign_ton_transfer(
            wallet_id=wallet_id,
            to=to,
            amount_nanoton=amount_nanoton,
            seqno=int(args.get("seqno") or 0),
            payload=args.get("payload"),
            send_mode=int(args.get("send_mode") or 3),
        )
    except WalletError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "signed": signed}


async def _wallet_sign_evm_tx(args: Mapping[str, Any]) -> Mapping[str, Any]:
    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    tx = args.get("tx")
    if not wallet_id or not isinstance(tx, dict):
        return {"ok": False, "error": "wallet_id and tx (object) required"}
    try:
        signed = await svc.sign_evm_transaction(wallet_id=wallet_id, tx=tx)
    except WalletError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "signed": signed}


async def _wallet_propose_send(args: Mapping[str, Any]) -> Mapping[str, Any]:
    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    to = str(args.get("to") or "").strip()
    amount = str(args.get("amount") or "").strip()
    memo = args.get("memo")
    if not (wallet_id and to and amount):
        return {"ok": False, "error": "wallet_id, to, amount are required"}
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        return {"ok": False, "error": "wallet_not_found"}
    envelope = svc.build_unsigned_send(wallet=wallet, to=to, amount=amount, memo=memo)
    return {"ok": True, "envelope": envelope}


async def _wallet_sign_message(args: Mapping[str, Any]) -> Mapping[str, Any]:
    svc = get_wallet_service()
    wallet_id = str(args.get("wallet_id") or "").strip()
    message = args.get("message")
    if not wallet_id or message is None:
        return {"ok": False, "error": "wallet_id and message are required"}
    if isinstance(message, str):
        msg_bytes = message.encode("utf-8")
    else:
        return {"ok": False, "error": "message must be a string"}
    try:
        signature = await svc.sign_message(wallet_id=wallet_id, message=msg_bytes)
    except WalletError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
        "wallet_id": wallet_id,
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="list",
        name="List wallets",
        description="Return the roster of operator-owned wallets (no secrets).",
        handler=_list_wallets,
        schema={
            "type": "object",
            "properties": {
                "chain": {
                    "type": "string",
                    "enum": ["solana", "evm", "ton"],
                    "description": "Filter by chain. Optional.",
                }
            },
        },
        destructive=False,
    ),
    ActionSpec(
        id="address",
        name="Wallet address",
        description="Return the public address for a single wallet id.",
        handler=_wallet_address,
        schema={
            "type": "object",
            "required": ["wallet_id"],
            "properties": {
                "wallet_id": {"type": "string"},
            },
        },
        destructive=False,
    ),
    ActionSpec(
        id="balance",
        name="Wallet balance",
        description=(
            "Read the on-chain balance via JSON-RPC. Returns "
            "{raw, decimals, symbol, display}. Read-only."
        ),
        handler=_wallet_balance,
        schema={
            "type": "object",
            "required": ["wallet_id"],
            "properties": {
                "wallet_id": {"type": "string"},
                "rpc_url": {
                    "type": "string",
                    "description": "Override RPC endpoint. Optional.",
                },
            },
        },
        destructive=False,
    ),
    ActionSpec(
        id="propose_send",
        name="Propose a send",
        description=(
            "Build an unsigned transaction envelope. Does NOT broadcast or sign — "
            "the cockpit / operator must confirm via the policy gate first."
        ),
        handler=_wallet_propose_send,
        schema={
            "type": "object",
            "required": ["wallet_id", "to", "amount"],
            "properties": {
                "wallet_id": {"type": "string"},
                "to": {"type": "string"},
                "amount": {
                    "type": "string",
                    "description": "Decimal string in chain-native units.",
                },
                "memo": {"type": "string"},
            },
        },
        destructive=True,
    ),
    ActionSpec(
        id="sign_message",
        name="Sign a message",
        description=(
            "Sign a UTF-8 string with the wallet's private key. "
            "Solana ed25519 + EVM EIP-191 personal_sign. TON returns "
            "signing_unsupported."
        ),
        handler=_wallet_sign_message,
        schema={
            "type": "object",
            "required": ["wallet_id", "message"],
            "properties": {
                "wallet_id": {"type": "string"},
                "message": {"type": "string"},
            },
        },
        destructive=True,
    ),
    ActionSpec(
        id="sign_solana_transfer",
        name="Sign Solana transfer",
        description=(
            "Build + sign a system_program::transfer transaction. "
            "Returns base64 / base58 / hex raw transaction encodings "
            "and the explorer signature. Does NOT broadcast — caller "
            "supplies recent_blockhash."
        ),
        handler=_wallet_sign_solana_transfer,
        schema={
            "type": "object",
            "required": ["wallet_id", "to", "amount", "recent_blockhash"],
            "properties": {
                "wallet_id": {"type": "string"},
                "to": {"type": "string"},
                "amount": {
                    "type": "string",
                    "description": "lamports (digits) or SOL (e.g. '0.5')",
                },
                "recent_blockhash": {"type": "string"},
                "memo": {"type": "string"},
            },
        },
        destructive=True,
    ),
    ActionSpec(
        id="sign_ton_transfer",
        name="Sign TON transfer",
        description=(
            "Build + sign a wallet v3R2 external transfer message. "
            "Returns the broadcastable BoC (base64). Does NOT broadcast — "
            "that's the policy gate's problem."
        ),
        handler=_wallet_sign_ton_transfer,
        schema={
            "type": "object",
            "required": ["wallet_id", "to", "amount"],
            "properties": {
                "wallet_id": {"type": "string"},
                "to": {"type": "string"},
                "amount": {
                    "type": "string",
                    "description": "Either nanoton (digits) or TON (e.g. '0.5')",
                },
                "seqno": {"type": "integer", "minimum": 0},
                "payload": {"type": "string"},
                "send_mode": {"type": "integer"},
            },
        },
        destructive=True,
    ),
    ActionSpec(
        id="sign_evm_tx",
        name="Sign EVM transaction",
        description=(
            "Sign an EIP-1559 (or legacy) transaction. Returns the raw "
            "broadcastable hex. Does NOT broadcast — that's the policy "
            "gate's problem."
        ),
        handler=_wallet_sign_evm_tx,
        schema={
            "type": "object",
            "required": ["wallet_id", "tx"],
            "properties": {
                "wallet_id": {"type": "string"},
                "tx": {
                    "type": "object",
                    "description": (
                        "{to, value, gas, nonce, chainId, "
                        "maxFeePerGas|gasPrice, ...}"
                    ),
                },
            },
        },
        destructive=True,
    ),
)
