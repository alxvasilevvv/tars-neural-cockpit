"""Optional Solana memo anchoring for daily Merkle roots (Wave 95).

Off by default. Enable by setting ``SOLANA_KEYPAIR_PATH`` in the env
to a JSON file produced by ``solana-keygen new`` (an array of 64
ints — the same format the official CLI emits). The anchor writes a
memo transaction with the body
``tars-receipt-root:<YYYY-MM-DD>:<root_hex>``; the txid is recorded
back into the ledger's ``merkle_roots`` row.

The Solana primitives live in :mod:`backend.core.wallet.sign_sol`
(transaction building / signing) and the live RPC helper in
:mod:`web_extras.routers.wallet` (blockhash fetch). To keep this
module dependency-light + testable without RPC, anchoring is a thin
async wrapper that:

1. Loads the keypair from ``SOLANA_KEYPAIR_PATH``.
2. Fetches a recent blockhash from the configured RPC
   (``SOLANA_RPC_URL`` — default ``https://api.mainnet-beta.solana.com``).
3. Builds + signs a memo transaction (system program + memo program).
4. Submits it via ``sendTransaction`` JSON-RPC.
5. Records the txid via ``store.upsert_merkle_root``.

Any failure short-circuits with a structured ``{"anchored": False,
"reason": "..."}`` response — never raises.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import httpx

MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def _is_configured() -> bool:
    return bool(os.getenv("SOLANA_KEYPAIR_PATH"))


def _rpc_url() -> str:
    return os.getenv("SOLANA_RPC_URL") or DEFAULT_RPC


def _load_keypair_bytes() -> bytes | None:
    """Read the operator keypair from ``SOLANA_KEYPAIR_PATH``.

    Returns 64-byte secret (Solders ``Keypair`` representation —
    32-byte seed + 32-byte pubkey). ``None`` on failure.
    """

    path = os.getenv("SOLANA_KEYPAIR_PATH")
    if not path:
        return None
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            arr = json.load(fh)
        if not isinstance(arr, list) or len(arr) != 64:
            return None
        return bytes(arr)
    except Exception:
        return None


async def _fetch_blockhash(client: httpx.AsyncClient) -> str | None:
    try:
        r = await client.post(
            _rpc_url(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash",
                "params": [{"commitment": "finalized"}],
            },
            timeout=10.0,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        return body.get("result", {}).get("value", {}).get("blockhash")
    except Exception:
        return None


def _build_memo_tx(
    *, signer_secret_64: bytes, memo: str, recent_blockhash: str
) -> str:
    """Build + sign a memo-only transaction. Returns base64-encoded
    raw bytes ready for ``sendTransaction``.
    """

    from solders.hash import Hash
    from solders.instruction import AccountMeta, Instruction
    from solders.keypair import Keypair
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.transaction import Transaction

    kp = Keypair.from_bytes(signer_secret_64)
    memo_program = Pubkey.from_string(MEMO_PROGRAM_ID)
    ix = Instruction(
        program_id=memo_program,
        accounts=[
            AccountMeta(pubkey=kp.pubkey(), is_signer=True, is_writable=False)
        ],
        data=memo.encode("utf-8"),
    )
    msg = Message.new_with_blockhash(
        [ix], kp.pubkey(), Hash.from_string(recent_blockhash)
    )
    tx = Transaction([kp], msg, Hash.from_string(recent_blockhash))
    raw = bytes(tx)
    return base64.b64encode(raw).decode("ascii")


async def _send_tx(client: httpx.AsyncClient, raw_b64: str) -> str | None:
    try:
        r = await client.post(
            _rpc_url(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    raw_b64,
                    {"encoding": "base64", "skipPreflight": False},
                ],
            },
            timeout=15.0,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        return body.get("result")  # signature
    except Exception:
        return None


async def anchor_to_solana(day_iso: str, root_hex: str) -> dict[str, Any]:
    """Submit ``tars-receipt-root:<day>:<root>`` as a Solana memo tx.

    Updates the corresponding ``merkle_roots`` row with
    ``anchored_at`` + ``solana_signature`` on success.

    Result shape:
        {"anchored": True,  "signature": "<base58>", "day_iso": ...,
         "root_hex": ...}
        {"anchored": False, "reason": "not_configured"|"keypair_load_failed"|
                                       "blockhash_failed"|"sign_failed"|
                                       "submit_failed"|"store_unavailable"}
    """

    if not _is_configured():
        return {"anchored": False, "reason": "not_configured"}
    secret = _load_keypair_bytes()
    if secret is None:
        return {"anchored": False, "reason": "keypair_load_failed"}

    from .store import get_store

    store = get_store()
    if store is None:
        return {"anchored": False, "reason": "store_unavailable"}

    memo = f"tars-receipt-root:{day_iso}:{root_hex}"

    async with httpx.AsyncClient() as client:
        blockhash = await _fetch_blockhash(client)
        if not blockhash:
            return {"anchored": False, "reason": "blockhash_failed"}
        try:
            raw_b64 = _build_memo_tx(
                signer_secret_64=secret,
                memo=memo,
                recent_blockhash=blockhash,
            )
        except Exception as exc:
            return {
                "anchored": False,
                "reason": f"sign_failed: {exc}",
            }
        sig = await _send_tx(client, raw_b64)
        if not sig:
            return {"anchored": False, "reason": "submit_failed"}

    cached = await store.get_merkle_root(day_iso)
    leaf_count = cached.leaf_count if cached else 0
    await store.upsert_merkle_root(
        day_iso=day_iso,
        root_hex=root_hex,
        leaf_count=leaf_count,
        anchored_at=time.time(),
        solana_signature=sig,
    )
    return {
        "anchored": True,
        "signature": sig,
        "day_iso": day_iso,
        "root_hex": root_hex,
    }
