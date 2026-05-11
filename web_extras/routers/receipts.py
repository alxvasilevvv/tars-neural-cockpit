"""HTTP surface for the unified receipt ledger (Wave 95).

Endpoints:

- ``GET    /api/receipts``                            query w/ filters
- ``GET    /api/receipts/{id}``                       single + verification
- ``POST   /api/receipts/verify``                     verify a receipt body
- ``GET    /api/receipts/chain/verify?day=YYYY-MM-DD`` full-day chain check
- ``GET    /api/receipts/merkle/{day}``               root + leaf count + anchor
- ``GET    /api/receipts/merkle/{day}/proof/{id}``    Merkle proof for receipt
- ``POST   /api/receipts/anchor/{day}``               manual Solana anchor
- ``GET    /api/receipts/export``                     ndjson | csv export

All endpoints return 503 ``{"detail": "receipts_disabled"}`` when
the store is disabled via ``TARS_RECEIPT_STORE=disabled``.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.core.receipts import (
    Receipt,
    compute_root,
    get_store,
    proof as merkle_proof,
    verify as verify_receipt,
    verify_chain,
)
from backend.core.receipts.anchor import anchor_to_solana


router = APIRouter(prefix="/api/receipts", tags=["receipts"])

# Wave 123: alias surface for the FE Compliance page; this surfaces
# as GET /api/audit/list. Both routers are registered in web_extras/app.py
# so the receipts module owns the audit alias too.
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


def _store_or_503():
    s = get_store()
    if s is None:
        raise HTTPException(status_code=503, detail="receipts_disabled")
    return s


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday_iso() -> str:
    from datetime import timedelta

    return (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).strftime("%Y-%m-%d")


# ----- query --------------------------------------------------------------


@router.get("")
async def list_receipts(
    type: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    since: float | None = Query(default=None),
    until: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    s = _store_or_503()
    rows = await s.query(
        type=type, actor=actor, since=since, until=until, limit=limit
    )
    return {
        "ok": True,
        "count": len(rows),
        "receipts": [r.to_dict() for r in rows],
    }


@router.get("/{receipt_id}")
async def get_receipt(receipt_id: str) -> dict[str, Any]:
    s = _store_or_503()
    r = await s.get_by_id(receipt_id)
    if r is None:
        raise HTTPException(status_code=404, detail="receipt_not_found")
    return {
        "ok": True,
        "receipt": r.to_dict(),
        "verified": verify_receipt(r),
    }


# ----- verify -------------------------------------------------------------


@router.post("/verify")
async def verify_endpoint(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Body: ``{"receipt": {...}}`` OR ``{"receipt_id": "..."}``."""

    s = _store_or_503()
    rid = body.get("receipt_id")
    receipt_payload = body.get("receipt")
    receipt: Receipt | None = None
    if rid:
        receipt = await s.get_by_id(str(rid))
        if receipt is None:
            return {
                "verified": False,
                "reason": "receipt_not_found",
            }
    elif receipt_payload:
        try:
            receipt = Receipt.from_dict(dict(receipt_payload))
        except Exception as exc:
            return {
                "verified": False,
                "reason": f"malformed_receipt: {exc}",
            }
    else:
        raise HTTPException(
            status_code=400, detail="receipt_or_receipt_id_required"
        )
    ok = verify_receipt(receipt)
    out: dict[str, Any] = {"verified": ok, "signer": receipt.public_key}
    if not ok:
        out["reason"] = "signature_or_hash_mismatch"
    return out


# ----- chain check --------------------------------------------------------


@router.get("/chain/verify")
async def chain_verify(
    day: str = Query(..., description="YYYY-MM-DD or 'today'"),
) -> dict[str, Any]:
    s = _store_or_503()
    day_iso = _today_iso() if day == "today" else day
    receipts = await s.replay_chain_for_day(day_iso)
    result = verify_chain(receipts)
    result["day"] = day_iso
    return result


# ----- merkle -------------------------------------------------------------


@router.get("/merkle/{day}")
async def merkle_for_day(day: str) -> dict[str, Any]:
    s = _store_or_503()
    day_iso = _today_iso() if day == "today" else day
    cached = await s.get_merkle_root(day_iso)
    if cached is not None:
        return {"ok": True, **cached.to_dict()}
    # Compute on demand.
    receipts = await s.replay_chain_for_day(day_iso)
    hashes = [r.hash for r in receipts]
    root_hex = compute_root(hashes)
    row = await s.upsert_merkle_root(
        day_iso=day_iso, root_hex=root_hex, leaf_count=len(hashes)
    )
    return {"ok": True, **row.to_dict()}


@router.get("/merkle/{day}/proof/{receipt_id}")
async def merkle_proof_endpoint(
    day: str, receipt_id: str
) -> dict[str, Any]:
    s = _store_or_503()
    day_iso = _today_iso() if day == "today" else day
    receipts = await s.replay_chain_for_day(day_iso)
    if not receipts:
        raise HTTPException(status_code=404, detail="day_has_no_receipts")
    idx: int | None = None
    for i, r in enumerate(receipts):
        if r.id == receipt_id:
            idx = i
            break
    if idx is None:
        raise HTTPException(status_code=404, detail="receipt_not_in_day")
    return {
        "ok": True,
        "day": day_iso,
        "receipt_id": receipt_id,
        **merkle_proof([r.hash for r in receipts], idx),
    }


# ----- anchor (operator only — gated by env config in anchor module) ----


@router.post("/anchor/{day}")
async def anchor(day: str) -> dict[str, Any]:
    s = _store_or_503()
    day_iso = _today_iso() if day == "today" else (
        _yesterday_iso() if day == "yesterday" else day
    )
    receipts = await s.replay_chain_for_day(day_iso)
    hashes = [r.hash for r in receipts]
    root_hex = compute_root(hashes)
    if not root_hex:
        return {"anchored": False, "reason": "no_receipts_for_day"}
    # Make sure the row exists before anchor pushes its update.
    await s.upsert_merkle_root(
        day_iso=day_iso, root_hex=root_hex, leaf_count=len(hashes)
    )
    return await anchor_to_solana(day_iso, root_hex)


# ----- export -------------------------------------------------------------


@router.get("/export")
async def export(
    since: float | None = Query(default=None),
    until: float | None = Query(default=None),
    format: str = Query(default="ndjson", pattern="^(ndjson|csv)$"),
    limit: int = Query(default=10000, ge=1, le=100000),
) -> StreamingResponse:
    s = _store_or_503()
    rows = await s.query(since=since, until=until, limit=limit)

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "ts",
                "type",
                "actor",
                "resource",
                "prev_hash",
                "hash",
                "signature",
                "public_key",
                "payload",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.ts,
                    r.type,
                    r.actor,
                    r.resource or "",
                    r.prev_hash,
                    r.hash,
                    r.signature,
                    r.public_key,
                    json.dumps(r.payload, sort_keys=True),
                ]
            )
        data = buf.getvalue().encode("utf-8")
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={
                "content-disposition": (
                    f'attachment; filename="tars-receipts-'
                    f'{_today_iso()}.csv"'
                )
            },
        )

    # ndjson
    def _gen():
        for r in rows:
            yield (json.dumps(r.to_dict(), sort_keys=True) + "\n").encode(
                "utf-8"
            )

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson",
        headers={
            "content-disposition": (
                f'attachment; filename="tars-receipts-'
                f'{_today_iso()}.ndjson"'
            )
        },
    )


# ---------------------------------------------------------------------
# Wave 123: /api/audit/list endpoint (FE Compliance page consumer)
# ---------------------------------------------------------------------


@audit_router.get("/list")
async def audit_list(
    since: float | None = Query(default=None),
    until: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    actor: str | None = Query(default=None),
    type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Audit feed: same store as /api/receipts but flattened for the FE
    Compliance page. Each row is annotated with `sig_verified` —
    derived once per response by re-running ed25519 verify on the
    receipt payload (cheap; verify is constant-time per row).

    Returns 503 when the receipt store is disabled.
    """

    s = _store_or_503()
    rows = await s.query(
        type=type, actor=actor, since=since, until=until, limit=limit,
    )

    items: list[dict[str, Any]] = []
    for r in rows:
        try:
            sig_ok = bool(verify_receipt(r))
        except Exception:
            sig_ok = False
        items.append(
            {
                "id": r.id,
                "ts": r.ts,
                "type": r.type,
                "actor": r.actor,
                "resource": r.resource,
                "impact": (r.payload or {}).get("impact"),
                "sig_verified": sig_ok,
            }
        )

    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }
