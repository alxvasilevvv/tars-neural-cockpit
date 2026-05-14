"""W204 — Public verifiable-proof endpoints.

The TARS receipt ledger is hash-chained, signed (Ed25519), and anchored
batch-wise to Solana memos. Anyone with the Merkle root + a single
receipt + the inclusion proof should be able to verify that receipt
came from TARS — without trusting any TARS-controlled server.

This module exposes two **public** (unauthenticated) read-only
endpoints to make that practical:

  GET  /api/public/proof/anchor/{merkle_root}
       → if we have an anchor row for this root, return
         {day, leaf_count, anchored_at, solana_signature, explorer_url}
       → otherwise 404 with {known_roots_count}

  POST /api/public/proof/verify
       Body: {leaf_hex, path:[{sibling, side}], root_hex}
       → {ok: True/False, valid: True/False}
       Pure-function Merkle replay — no DB access needed.

The point: journalists, regulators, or any TARS user should be able to
verify a printed receipt against the public Solana memo without an
account, a key, or any trust in our infra. This costs us nothing
(read-only over already-public data) and meaningfully strengthens the
"receipts" trust story.

Privacy: we never return personally-identifying parts of receipts
through these endpoints. The verify endpoint takes the proof IN — it
doesn't go fetch a receipt by ID. Roots and Solana tx signatures are
already public on-chain.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.receipts.merkle import verify_proof
from backend.core.receipts.store import get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/proof", tags=["public", "proof"])


# ─── /anchor/{root} ────────────────────────────────────────────────────────
@router.get("/anchor/{merkle_root}")
async def anchor_lookup(merkle_root: str) -> dict[str, Any]:
    """Public: given a Merkle root hex, return anchor metadata if known."""
    root = (merkle_root or "").strip().lower()
    if not root or len(root) != 64 or any(c not in "0123456789abcdef" for c in root):
        raise HTTPException(status_code=400, detail={"error": "bad_root_format"})

    try:
        s = get_store()
        row = await s.get_merkle_root_by_root(root) if hasattr(s, "get_merkle_root_by_root") else None
    except Exception as exc:
        logger.exception("public_proof.anchor_lookup.store_error")
        raise HTTPException(status_code=503, detail={"error": "store_unavailable", "message": str(exc)})

    if not row:
        return {
            "ok": False,
            "error": "root_not_found",
            "hint": "This Merkle root has not been anchored by this TARS instance.",
        }

    # Build a Solana explorer URL for the anchor tx, if we have one.
    sig = row.get("solana_signature") or row.get("anchor_signature")
    cluster = os.getenv("SOLANA_CLUSTER", "mainnet-beta")
    explorer_url = None
    if sig:
        if cluster == "mainnet-beta":
            explorer_url = f"https://explorer.solana.com/tx/{sig}"
        else:
            explorer_url = f"https://explorer.solana.com/tx/{sig}?cluster={cluster}"

    return {
        "ok": True,
        "merkle_root": root,
        "day": row.get("day"),
        "leaf_count": row.get("leaf_count"),
        "anchored_at": row.get("anchored_at"),
        "solana_signature": sig,
        "explorer_url": explorer_url,
        "cluster": cluster,
    }


# ─── /verify ───────────────────────────────────────────────────────────────
class ProofStep(BaseModel):
    sibling: str = Field(..., description="Hex of sibling hash at this level.")
    side: str = Field(..., description="'left' or 'right' — which side the sibling is on.")


class VerifyRequest(BaseModel):
    leaf_hex: str = Field(..., min_length=64, max_length=64)
    path: List[ProofStep]
    root_hex: str = Field(..., min_length=64, max_length=64)


@router.post("/verify")
async def verify(req: VerifyRequest) -> dict[str, Any]:
    """Public: pure Merkle-proof replay. Returns {ok, valid}.

    No DB access — caller supplies leaf, path, and expected root.
    """
    try:
        valid = verify_proof(
            req.leaf_hex.lower(),
            [{"sibling": s.sibling.lower(), "side": s.side} for s in req.path],
            req.root_hex.lower(),
        )
    except Exception as exc:
        return {"ok": False, "error": "verify_failed", "message": str(exc), "valid": False}
    return {"ok": True, "valid": bool(valid)}


# ─── /health ───────────────────────────────────────────────────────────────
@router.get("/health")
async def health() -> dict[str, Any]:
    """Tiny liveness probe so monitors / journalists can confirm the public
    verifier is up before they paste a proof in."""
    return {
        "ok": True,
        "service": "tars.public_proof",
        "endpoints": [
            "GET  /api/public/proof/anchor/{merkle_root}",
            "POST /api/public/proof/verify",
        ],
    }
