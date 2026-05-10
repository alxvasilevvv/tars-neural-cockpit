"""HTTP surface for the user-owned crypto wallets (Phase M2).

Endpoints:

- ``POST   /api/wallet``                       create (returns mnemonic ONCE)
- ``POST   /api/wallet/import``                import from existing mnemonic
- ``GET    /api/wallet``                       list
- ``GET    /api/wallet/{wallet_id}``           single
- ``DELETE /api/wallet/{wallet_id}``           policy-gated destructive
- ``POST   /api/wallet/{wallet_id}/sign``      sign an arbitrary message
- ``POST   /api/wallet/{wallet_id}/build_send`` build an unsigned tx envelope

The mnemonic is only ever surfaced from ``POST /api/wallet``, only on
the response of that single call (not on subsequent reads), and is
never persisted. Private keys live encrypted on disk under
``~/.tars/wallet_secrets.json``.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.meeet import get_client, trace_scope
from backend.core.wallet import (
    BalanceError,
    WalletChain,
    WalletError,
    fetch_balance,
    get_wallet_service,
)
from backend.core.wallet.audit import enrich_signed_event, prune_signed_events
from backend.core.wallet.chain_helpers import (
    RPCError,
    get_evm_nonce,
    get_solana_blockhash,
    get_ton_seqno,
)
from web_extras import policy_gate


router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class ConfirmRequest(BaseModel):
    """Mint a one-shot confirm token bound to a wallet + action +
    parameter-hash tuple. The token is required by destructive
    routes when ``TARS_REQUIRE_OPERATOR_CONFIRM=1``."""

    action: str = Field(..., min_length=1, max_length=120)
    params: Optional[dict] = None
    ttl_s: int = Field(default=300, ge=1, le=3600)


@router.post("/{wallet_id}/confirm")
async def mint_confirm_token(
    wallet_id: str,
    body: ConfirmRequest = Body(...),
) -> dict[str, Any]:
    """Mint a confirm token for a destructive action on this wallet."""
    out = policy_gate.mint_token(
        wallet_id=wallet_id,
        action=body.action,
        params_hash_hex=policy_gate.params_hash(body.params),
        ttl_s=body.ttl_s,
    )
    return {
        "ok": True,
        "wallet_id": wallet_id,
        "action": body.action,
        "params_hash": policy_gate.params_hash(body.params),
        "required": policy_gate.is_required(),
        **out,
    }


@router.get("/policy/status")
async def policy_status() -> dict[str, Any]:
    """Tell cockpit / mobile whether the gate is currently enforced."""
    return {"ok": True, "required": policy_gate.is_required()}


class CreateWalletRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    chain: str = Field(..., description="solana | evm | ton")
    index: int = Field(default=0, ge=0, le=255)
    metadata: Optional[dict[str, Any]] = None
    derivation_scheme: str = Field(
        default="tars-v1",
        description="tars-v1 (legacy) | bip44-501-phantom (Phantom-compat, Solana only)",
    )


class ImportWalletRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    chain: str = Field(..., description="solana | evm | ton")
    mnemonic: str = Field(..., min_length=8, max_length=400)
    passphrase: str = Field(default="")
    index: int = Field(default=0, ge=0, le=255)
    metadata: Optional[dict[str, Any]] = None
    derivation_scheme: str = Field(default="tars-v1")


class SignRequest(BaseModel):
    message_b64: Optional[str] = None
    message: Optional[str] = None


class BuildSendRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=200)
    amount: str = Field(..., min_length=1, max_length=80)
    memo: Optional[str] = None


class SignSolanaTransferRequest(BaseModel):
    """system_program::transfer. ``amount`` accepts lamports
    (digit-string or int) or SOL (decimal like ``"0.5"``)."""

    to: str = Field(..., min_length=32, max_length=44)
    amount: str = Field(..., min_length=1, max_length=80)
    recent_blockhash: str = Field(..., min_length=32, max_length=44)
    memo: Optional[str] = Field(default=None, max_length=512)


class SignTONTransferRequest(BaseModel):
    """v3R2 external transfer. ``amount`` accepts either nanoton
    (digits only) or TON (with a decimal point, e.g. ``"0.5"``)."""

    to: str = Field(..., min_length=4, max_length=80)
    amount: str = Field(..., min_length=1, max_length=80)
    seqno: int = Field(default=0, ge=0)
    payload: Optional[str] = Field(default=None, max_length=1024)
    send_mode: int = Field(default=3)


class SignEVMTxRequest(BaseModel):
    """EIP-1559 typed-2 by default; provide ``gasPrice`` for legacy."""

    to: str = Field(..., min_length=42, max_length=42)
    value: str = Field(..., description="Decimal or 0x-hex wei.")
    gas: str = Field(default="21000")
    nonce: str = Field(...)
    chainId: int = Field(...)
    data: Optional[str] = None
    maxFeePerGas: Optional[str] = None
    maxPriorityFeePerGas: Optional[str] = None
    gasPrice: Optional[str] = None
    type: Optional[int] = None


@router.post("")
async def create_wallet(
    body: CreateWalletRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    svc = get_wallet_service()
    try:
        wallet, mnemonic = await svc.create_wallet(
            label=body.label,
            chain=body.chain,
            index=body.index,
            metadata=body.metadata,
            derivation_scheme=body.derivation_scheme,
        )
    except (WalletError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.created",
            {
                "wallet_id": wallet.id,
                "chain": wallet.chain.value,
                "address": wallet.address,
                "seed_fingerprint": wallet.seed_fingerprint,
                "derivation_scheme": wallet.derivation_scheme,
            },
        )
        return {
            "ok": True,
            "trace_id": tid,
            "wallet": wallet.to_dict(),
            "mnemonic": mnemonic,
            "mnemonic_warning": (
                "This phrase is shown EXACTLY ONCE. Write it down on paper "
                "and store it offline. It is the only way to recover this wallet."
            ),
        }


@router.post("/import")
async def import_wallet(
    body: ImportWalletRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    svc = get_wallet_service()
    try:
        wallet, _ = await svc.create_wallet(
            label=body.label,
            chain=body.chain,
            mnemonic=body.mnemonic,
            index=body.index,
            passphrase=body.passphrase,
            metadata=body.metadata,
            derivation_scheme=body.derivation_scheme,
        )
    except (WalletError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.imported",
            {
                "wallet_id": wallet.id,
                "chain": wallet.chain.value,
                "address": wallet.address,
                "seed_fingerprint": wallet.seed_fingerprint,
            },
        )
        return {"ok": True, "trace_id": tid, "wallet": wallet.to_dict()}


@router.get("")
async def list_wallets(chain: str | None = None) -> dict[str, Any]:
    svc = get_wallet_service()
    try:
        items = await svc.list_wallets(chain=chain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "count": len(items),
        "wallets": [w.to_dict() for w in items],
    }


@router.get("/{wallet_id}")
async def get_wallet(wallet_id: str) -> dict[str, Any]:
    svc = get_wallet_service()
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="wallet_not_found")
    return {"ok": True, "wallet": wallet.to_dict()}


@router.delete("/{wallet_id}")
async def delete_wallet(
    wallet_id: str,
    request: Request,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    await policy_gate.require_confirm(
        request, wallet_id=wallet_id, action="wallet.delete", params=None
    )
    svc = get_wallet_service()
    removed = await svc.delete_wallet(wallet_id)
    if not removed:
        raise HTTPException(status_code=404, detail="wallet_not_found")
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit("wallet.removed", {"wallet_id": wallet_id})
        return {"ok": True, "trace_id": tid, "wallet_id": wallet_id}


@router.post("/{wallet_id}/sign")
async def sign(
    wallet_id: str,
    request: Request,
    body: SignRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    # Wave 79 security audit — `/sign` was the only wallet signing
    # endpoint that bypassed the policy gate. Arbitrary message
    # signing is destructive (an attacker on the loopback could
    # forge auth tokens, sign permits, etc.), so it now requires a
    # confirm token whenever ``TARS_REQUIRE_OPERATOR_CONFIRM=1``,
    # the same as the chain-specific transfer endpoints.
    await policy_gate.require_confirm(
        request,
        wallet_id=wallet_id,
        action="wallet.sign_message",
        params=body.model_dump(exclude_none=True),
    )
    svc = get_wallet_service()
    if body.message_b64:
        try:
            message = base64.b64decode(body.message_b64.encode("ascii"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid base64: {exc}") from exc
    elif body.message is not None:
        message = body.message.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="message or message_b64 required")
    try:
        signature = await svc.sign_message(wallet_id=wallet_id, message=message)
    except WalletError as exc:
        detail = str(exc)
        status_code = 404 if "not_found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.signed",
            {"wallet_id": wallet_id, "message_bytes": len(message)},
        )
        return {
            "ok": True,
            "trace_id": tid,
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        }


@router.post("/{wallet_id}/sign_solana_transfer")
async def sign_solana_transfer(
    wallet_id: str,
    request: Request,
    body: SignSolanaTransferRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    from backend.core.wallet.sign_sol import parse_lamports

    await policy_gate.require_confirm(
        request,
        wallet_id=wallet_id,
        action="wallet.sign_solana_transfer",
        params=body.model_dump(exclude_none=True),
    )
    svc = get_wallet_service()
    try:
        lamports = parse_lamports(body.amount)
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid_amount: {exc}") from exc
    try:
        signed = await svc.sign_solana_transfer(
            wallet_id=wallet_id,
            to=body.to,
            lamports=lamports,
            recent_blockhash=body.recent_blockhash,
            memo=body.memo,
        )
    except WalletError as exc:
        detail = str(exc)
        status_code = 404 if "not_found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.solana_transfer_signed",
            enrich_signed_event(
                base={
                    "wallet_id": wallet_id,
                    "to": body.to,
                    "lamports": lamports,
                    "tx_signature": signed["tx_signature"],
                },
                signed=signed,
            ),
        )
        # Wave 95 — unified receipt ledger.
        try:
            from backend.core.receipts import record as _rcpt_record

            await _rcpt_record(
                type=f"wallet.{signed.get('kind') or 'tx'}_signed",
                actor=f"wallet:{wallet_id}",
                resource=str(signed.get("tx_signature") or signed.get("hash") or signed.get("body_hash") or wallet_id),
                payload={"trace_id": tid, "wallet_id": wallet_id},
            )
        except Exception:
            pass
        return {"ok": True, "trace_id": tid, "signed": signed}


@router.post("/{wallet_id}/sign_ton_transfer")
async def sign_ton_transfer(
    wallet_id: str,
    request: Request,
    body: SignTONTransferRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    from backend.core.wallet.sign_ton import parse_amount

    await policy_gate.require_confirm(
        request,
        wallet_id=wallet_id,
        action="wallet.sign_ton_transfer",
        params=body.model_dump(exclude_none=True),
    )
    svc = get_wallet_service()
    try:
        amount_nanoton = parse_amount(body.amount)
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid_amount: {exc}") from exc
    try:
        signed = await svc.sign_ton_transfer(
            wallet_id=wallet_id,
            to=body.to,
            amount_nanoton=amount_nanoton,
            seqno=body.seqno,
            payload=body.payload,
            send_mode=body.send_mode,
        )
    except WalletError as exc:
        detail = str(exc)
        status_code = 404 if "not_found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.ton_transfer_signed",
            enrich_signed_event(
                base={
                    "wallet_id": wallet_id,
                    "to": body.to,
                    "amount_nanoton": amount_nanoton,
                    "seqno": body.seqno,
                    "body_hash": signed["body_hash"],
                },
                signed=signed,
            ),
        )
        # Wave 95 — unified receipt ledger.
        try:
            from backend.core.receipts import record as _rcpt_record

            await _rcpt_record(
                type=f"wallet.{signed.get('kind') or 'tx'}_signed",
                actor=f"wallet:{wallet_id}",
                resource=str(signed.get("tx_signature") or signed.get("hash") or signed.get("body_hash") or wallet_id),
                payload={"trace_id": tid, "wallet_id": wallet_id},
            )
        except Exception:
            pass
        return {"ok": True, "trace_id": tid, "signed": signed}


@router.post("/{wallet_id}/sign_evm_tx")
async def sign_evm_tx(
    wallet_id: str,
    request: Request,
    body: SignEVMTxRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    await policy_gate.require_confirm(
        request,
        wallet_id=wallet_id,
        action="wallet.sign_evm_tx",
        params=body.model_dump(exclude_none=True),
    )
    svc = get_wallet_service()
    tx: dict[str, Any] = body.model_dump(exclude_none=True)
    try:
        signed = await svc.sign_evm_transaction(wallet_id=wallet_id, tx=tx)
    except WalletError as exc:
        detail = str(exc)
        status_code = 404 if "not_found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.evm_tx_signed",
            enrich_signed_event(
                base={
                    "wallet_id": wallet_id,
                    "to": body.to,
                    "chain_id": body.chainId,
                    "tx_hash": signed["hash"],
                },
                signed=signed,
                raw_keys=("raw", "hash"),  # EVM uses "raw"/"hash" not raw_b64/raw_hex
            ),
        )
        # Wave 95 — unified receipt ledger.
        try:
            from backend.core.receipts import record as _rcpt_record

            await _rcpt_record(
                type=f"wallet.{signed.get('kind') or 'tx'}_signed",
                actor=f"wallet:{wallet_id}",
                resource=str(signed.get("tx_signature") or signed.get("hash") or signed.get("body_hash") or wallet_id),
                payload={"trace_id": tid, "wallet_id": wallet_id},
            )
        except Exception:
            pass
        return {"ok": True, "trace_id": tid, "signed": signed}


@router.get("/solana/blockhash")
async def solana_blockhash() -> dict[str, Any]:
    """Live ``getLatestBlockhash`` from the configured Solana RPC.

    Used by the cockpit "build send" flow to autofill
    ``recent_blockhash`` before signing. Operators may override the
    endpoint with ``TARS_SOLANA_RPC_URL``.
    """
    import asyncio

    try:
        out = await asyncio.to_thread(get_solana_blockhash)
    except BalanceError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"wallet_balance_rpc_failure: {exc}",
        ) from exc
    return {"ok": True, **out}


@router.get("/evm/{address}/nonce")
async def evm_nonce(
    address: str,
    block_tag: str = "pending",
) -> dict[str, Any]:
    """Live ``eth_getTransactionCount`` for ``address``."""
    import asyncio

    try:
        out = await asyncio.to_thread(get_evm_nonce, address, block_tag=block_tag)
    except BalanceError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"wallet_balance_rpc_failure: {exc}",
        ) from exc
    return {"ok": True, **out}


@router.get("/ton/{address}/seqno")
async def ton_seqno(address: str) -> dict[str, Any]:
    """Live TON v3R2 seqno via TON Center / TON HTTP API."""
    import asyncio

    try:
        out = await asyncio.to_thread(get_ton_seqno, address)
    except BalanceError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"wallet_balance_rpc_failure: {exc}",
        ) from exc
    return {"ok": True, **out}


@router.post("/audit/prune")
async def audit_prune() -> dict[str, Any]:
    """Drop ``wallet.*_signed`` events older than the audit retention
    window (``TARS_AUDIT_RETENTION_DAYS``, default 30). Returns the
    count pruned. Safe to call any time; no-op when audit was never on.
    """
    pruned = await prune_signed_events()
    return {"ok": True, "pruned": int(pruned)}


@router.get("/{wallet_id}/balance")
async def balance(
    wallet_id: str,
    rpc_url: str | None = None,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    svc = get_wallet_service()
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="wallet_not_found")
    import asyncio

    try:
        bal = await asyncio.to_thread(
            fetch_balance,
            chain=wallet.chain,
            address=wallet.address,
            rpc_url=rpc_url,
        )
    except BalanceError as exc:
        # Don't leak the upstream URL; the cockpit just needs to know it failed.
        return {
            "ok": False,
            "wallet_id": wallet_id,
            "chain": wallet.chain.value,
            "error": str(exc),
        }
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.balance.read",
            {
                "wallet_id": wallet_id,
                "chain": wallet.chain.value,
                "raw": str(bal.raw),
                "decimals": bal.decimals,
            },
        )
        return {"ok": True, "trace_id": tid, "balance": bal.to_dict()}


@router.post("/{wallet_id}/build_send")
async def build_send(
    wallet_id: str,
    body: BuildSendRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    svc = get_wallet_service()
    wallet = await svc.get_wallet(wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="wallet_not_found")
    envelope = svc.build_unsigned_send(
        wallet=wallet,
        to=body.to,
        amount=body.amount,
        memo=body.memo,
    )
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as tid:
        await client.emit(
            "wallet.send_built",
            {
                "wallet_id": wallet_id,
                "chain": wallet.chain.value,
                "to": body.to,
                "amount": body.amount,
                "signing_supported": envelope["signing_supported"],
            },
        )
        return {"ok": True, "trace_id": tid, "envelope": envelope}
