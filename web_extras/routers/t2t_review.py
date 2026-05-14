"""W260 -- HTTP surface for the T2T code-review handoff.

Endpoints
---------

Sender (TARS A) side:

- ``POST /api/t2t/review/send``               -- package + sign + ship
- ``GET  /api/t2t/review/outbox``             -- list outgoing reviews
- ``GET  /api/t2t/review/outbox/{review_id}/status``  -- poll one

Recipient (TARS B) side:

- ``POST /api/t2t/review/receive``            -- accept inbound envelope
- ``GET  /api/t2t/review/inbox``              -- list pending reviews
- ``POST /api/t2t/review/{review_id}/approve``-- sign + return approval
- ``POST /api/t2t/review/{review_id}/reject`` -- sign + return rejection

Callback (sender side, receives signed verdicts from peer):

- ``POST /api/t2t/review/response``           -- accept response envelope

The two sides live in the same process for now because the cockpit
ships one TARS instance per user. The ``/send`` endpoint posts to
the peer's ``/receive`` URL over plain HTTPS; loopback POSTs are
allowed in tests + in the single-machine "peer = me" mode so the
contract can be exercised end-to-end without a second TARS running.

Every state transition (send / receive / approve / reject /
auto-applied) emits a receipt through the W67 ledger so the receipt
chain ends up telling a coherent story.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException

from backend.core.composer import (
    apply_plan as _apply_plan,
    get_store as _get_composer_store,
)
from backend.core.t2t_review.protocol import (
    REQUEST_TYPE,
    RESPONSE_TYPE,
    ReviewRequest,
    ReviewResponse,
    new_review_id,
    sign_envelope,
    tars_id_from_pubkey,
    verify_envelope,
)
from backend.core.t2t_review.inbox import get_inbox
from backend.core.t2t_review.outbox import get_outbox


log = logging.getLogger("tars.t2t_review")

router = APIRouter(prefix="/api/t2t/review", tags=["t2t-review"])


# ---------------------------------------------------------------------------
# Identity helpers (delegate to W67 host key so the whole stack uses one keypair)
# ---------------------------------------------------------------------------


def _host_identity() -> tuple[bytes, str, str]:
    """Return (priv_seed_32, public_key_b64, tars_id) for this TARS.

    Lazy-loads through the receipt store so we don't duplicate the
    "load or create ed25519 host key" logic. Raises if the store is
    disabled -- the router catches and returns a 503.
    """

    from backend.core.receipts.store import get_store as _rstore

    rs = _rstore()
    if rs is None:
        raise RuntimeError("receipt store disabled; cannot sign T2T envelopes")
    # store has a sync init path we can call without an event loop.
    rs._init_sync()  # noqa: SLF001 -- intentional, see W260 doc
    priv = rs._priv  # noqa: SLF001
    pub_b64 = rs.public_key_b64
    if priv is None or pub_b64 is None:
        raise RuntimeError("receipt host key not initialised")
    return priv, pub_b64, tars_id_from_pubkey(pub_b64)


def _peer_url(recipient_tars_id: str, explicit_url: str | None) -> str:
    """Resolve a peer URL.

    Precedence:
      1. ``peer_url`` in the request body.
      2. ``TARS_T2T_PEER_<TARS_ID>`` env var (uppercase id).
      3. ``TARS_T2T_DEFAULT_PEER`` env var (loopback / single-host).

    The default-peer fallback exists so the contract is testable on
    a single laptop without spinning up two TARS instances. In
    production the cockpit "Send for review" modal supplies the URL
    from the W82 peers list.
    """

    if explicit_url:
        return str(explicit_url).rstrip("/")
    key = f"TARS_T2T_PEER_{recipient_tars_id.upper()}"
    if os.environ.get(key):
        return str(os.environ[key]).rstrip("/")
    if os.environ.get("TARS_T2T_DEFAULT_PEER"):
        return str(os.environ["TARS_T2T_DEFAULT_PEER"]).rstrip("/")
    return ""


async def _emit_receipt(
    type_: str,
    actor: str,
    resource: str | None,
    payload: dict[str, Any],
) -> None:
    """Best-effort receipt emission. Never raises."""

    try:
        from backend.core.receipts import record

        await record(type_, actor, resource, payload)
    except Exception as exc:  # noqa: BLE001
        log.debug("t2t_review.receipt_failed type=%s err=%s", type_, exc)


# ---------------------------------------------------------------------------
# Sender side
# ---------------------------------------------------------------------------


@router.post("/send")
async def send_review(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Package a composer plan + signed envelope and POST it to peer.

    Body: ``{plan_id, recipient_tars_id, comment?, peer_url?}``.
    """

    body = payload or {}
    plan_id = str(body.get("plan_id") or "").strip()
    recipient_tars_id = str(body.get("recipient_tars_id") or "").strip()
    comment = body.get("comment")
    peer_url_override = body.get("peer_url")

    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id required")
    if not recipient_tars_id:
        raise HTTPException(
            status_code=400, detail="recipient_tars_id required"
        )

    cstore = _get_composer_store()
    if cstore is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    plan = await asyncio.to_thread(cstore.load_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")

    outbox = get_outbox()
    if outbox is None:
        raise HTTPException(status_code=503, detail="t2t review store disabled")

    try:
        priv, _pub_b64, sender_tars_id = _host_identity()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    review_id = new_review_id()
    request = ReviewRequest(
        review_id=review_id,
        sender_tars_id=sender_tars_id,
        recipient_tars_id=recipient_tars_id,
        plan=plan.to_dict(),
        comment=(str(comment) if comment is not None else None),
    )
    envelope = sign_envelope(
        envelope_type=REQUEST_TYPE,
        body=request.to_dict(),
        sender_tars_id=sender_tars_id,
        sender_priv_seed=priv,
    )

    peer_url = _peer_url(recipient_tars_id, peer_url_override)
    await asyncio.to_thread(
        outbox.insert_outgoing,
        review_id=review_id,
        plan_id=plan_id,
        recipient_tars_id=recipient_tars_id,
        peer_url=peer_url or None,
        comment=request.comment,
        request_envelope=envelope,
    )

    # Best-effort POST. A 404/timeout / connection-refused leaves the
    # row in ``pending`` (or transitions it to ``failed`` if we had a
    # URL but couldn't deliver) so the operator can retry from the
    # REVIEW tab; we don't raise to the caller -- the receipt +
    # outbox row is the source of truth.
    delivery_ok = False
    delivery_error: str | None = None
    if peer_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{peer_url}/api/t2t/review/receive",
                    json={"envelope": envelope},
                )
                delivery_ok = resp.status_code < 400
                if not delivery_ok:
                    delivery_error = f"http_{resp.status_code}"
        except httpx.HTTPError as exc:
            delivery_error = type(exc).__name__
            log.warning(
                "t2t_review.delivery_failed review_id=%s err=%s",
                review_id, exc,
            )

    if peer_url and not delivery_ok:
        await asyncio.to_thread(outbox.set_state, review_id, "failed")

    await _emit_receipt(
        "t2t.review.sent",
        actor=sender_tars_id,
        resource=review_id,
        payload={
            "plan_id": plan_id,
            "recipient_tars_id": recipient_tars_id,
            "peer_url": peer_url,
            "delivered": delivery_ok,
            "error": delivery_error,
        },
    )

    return {
        "ok": True,
        "review_id": review_id,
        "envelope": envelope,
        "state": "failed" if (peer_url and not delivery_ok) else "pending",
        "delivered": delivery_ok,
        "peer_url": peer_url,
        "error": delivery_error,
    }


@router.get("/outbox")
async def list_outbox(limit: int = 50) -> dict[str, Any]:
    outbox = get_outbox()
    if outbox is None:
        return {"ok": False, "error": "disabled", "items": []}
    rows = await asyncio.to_thread(outbox.list_outbox, limit=limit)
    return {"ok": True, "items": rows}


@router.get("/outbox/{review_id}/status")
async def get_outbox_status(review_id: str) -> dict[str, Any]:
    outbox = get_outbox()
    if outbox is None:
        raise HTTPException(status_code=503, detail="t2t review store disabled")
    row = await asyncio.to_thread(outbox.get_outbox, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="review not found")
    return {"ok": True, "review": row}


# ---------------------------------------------------------------------------
# Recipient side
# ---------------------------------------------------------------------------


@router.post("/receive")
async def receive_review(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Accept a signed inbound review envelope from a peer."""

    body = payload or {}
    envelope = body.get("envelope")
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=400, detail="envelope required")
    if envelope.get("type") != REQUEST_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"unexpected envelope type {envelope.get('type')!r}",
        )
    if not verify_envelope(envelope):
        raise HTTPException(status_code=400, detail="envelope signature invalid")

    try:
        request = ReviewRequest.from_dict(dict(envelope.get("body") or {}))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"malformed body: {exc}")
    if not request.review_id or not request.plan:
        raise HTTPException(status_code=400, detail="body missing required fields")

    inbox = get_inbox()
    if inbox is None:
        raise HTTPException(status_code=503, detail="t2t review store disabled")

    plan_id = str(request.plan.get("plan_id") or "")
    await asyncio.to_thread(
        inbox.insert_incoming,
        review_id=request.review_id,
        sender_tars_id=request.sender_tars_id,
        plan_id=plan_id,
        request_envelope=envelope,
    )

    await _emit_receipt(
        "t2t.review.received",
        actor=request.sender_tars_id,
        resource=request.review_id,
        payload={
            "plan_id": plan_id,
            "ops": len(request.plan.get("ops") or []),
            "comment": request.comment,
        },
    )

    return {
        "ok": True,
        "review_id": request.review_id,
        "state": "pending",
    }


@router.get("/inbox")
async def list_inbox(state: str | None = None, limit: int = 50) -> dict[str, Any]:
    inbox = get_inbox()
    if inbox is None:
        return {"ok": False, "error": "disabled", "items": []}
    if state is not None and state not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="invalid state filter")
    rows = await asyncio.to_thread(inbox.list_inbox, state=state, limit=limit)
    return {"ok": True, "items": rows}


async def _decide(
    review_id: str,
    *,
    decision: str,
    reviewer_comment: str | None,
    reject_reason: str | None,
) -> dict[str, Any]:
    """Shared approve / reject path.

    Builds a signed :class:`ReviewResponse` envelope, persists it on
    the inbox row, and (best-effort) POSTs it back to the original
    sender so their outbox can auto-apply on approval.
    """

    inbox = get_inbox()
    if inbox is None:
        raise HTTPException(status_code=503, detail="t2t review store disabled")

    row = await asyncio.to_thread(inbox.get_inbox, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="review not found")
    if row["state"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"review already {row['state']!r}",
        )

    try:
        priv, _pub_b64, reviewer_tars_id = _host_identity()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    response = ReviewResponse(
        review_id=review_id,
        decision=decision,
        reviewer_tars_id=reviewer_tars_id,
        comment=reviewer_comment,
        reason=reject_reason,
    )
    response_envelope = sign_envelope(
        envelope_type=RESPONSE_TYPE,
        body=response.to_dict(),
        sender_tars_id=reviewer_tars_id,
        sender_priv_seed=priv,
    )

    await asyncio.to_thread(
        inbox.mark_decided,
        review_id=review_id,
        decision=decision,
        response_envelope=response_envelope,
        comment=reviewer_comment,
    )

    receipt_type = (
        "t2t.review.approved" if decision == "approve" else "t2t.review.rejected"
    )
    await _emit_receipt(
        receipt_type,
        actor=reviewer_tars_id,
        resource=review_id,
        payload={
            "plan_id": row["plan_id"],
            "sender_tars_id": row["sender_tars_id"],
            "comment": reviewer_comment,
            "reason": reject_reason,
        },
    )

    # Try to ship the response back to the sender. The original
    # request envelope may embed a ``reply_to`` URL in its body;
    # otherwise we fall back to env-var resolution for the sender id.
    sender_id = row["sender_tars_id"]
    request_env = row.get("request_envelope") or {}
    reply_to = ""
    try:
        reply_to = str(((request_env.get("body") or {}).get("reply_to") or ""))
    except Exception:  # noqa: BLE001
        reply_to = ""
    reply_url = _peer_url(sender_id, reply_to or None)
    delivered_back = False
    if reply_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{reply_url}/api/t2t/review/response",
                    json={"envelope": response_envelope},
                )
                delivered_back = resp.status_code < 400
        except httpx.HTTPError as exc:
            log.warning(
                "t2t_review.reply_failed review_id=%s err=%s",
                review_id, exc,
            )

    return {
        "ok": True,
        "review_id": review_id,
        "decision": decision,
        "envelope": response_envelope,
        "delivered_back": delivered_back,
    }


@router.post("/{review_id}/approve")
async def approve_review(
    review_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    comment = body.get("comment")
    return await _decide(
        review_id,
        decision="approve",
        reviewer_comment=(str(comment) if comment is not None else None),
        reject_reason=None,
    )


@router.post("/{review_id}/reject")
async def reject_review(
    review_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason required")
    comment = body.get("comment")
    return await _decide(
        review_id,
        decision="reject",
        reviewer_comment=(str(comment) if comment is not None else None),
        reject_reason=reason,
    )


# ---------------------------------------------------------------------------
# Response callback (sender side, called by the reviewer's TARS)
# ---------------------------------------------------------------------------


@router.post("/response")
async def receive_response(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Sender-side callback for the reviewer's signed verdict.

    Verifies the envelope, persists it in ``responses``, transitions
    the outbox row, and on approval auto-applies the original plan
    through the standard composer executor. Receipt chain ties every
    step together.
    """

    body = payload or {}
    envelope = body.get("envelope")
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=400, detail="envelope required")
    if envelope.get("type") != RESPONSE_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"unexpected envelope type {envelope.get('type')!r}",
        )
    if not verify_envelope(envelope):
        raise HTTPException(status_code=400, detail="envelope signature invalid")

    try:
        response = ReviewResponse.from_dict(dict(envelope.get("body") or {}))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"malformed body: {exc}")

    outbox = get_outbox()
    if outbox is None:
        raise HTTPException(status_code=503, detail="t2t review store disabled")
    row = await asyncio.to_thread(outbox.get_outbox, response.review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown review_id")

    await asyncio.to_thread(
        outbox.record_response,
        review_id=response.review_id,
        decision=response.decision,
        response_envelope=envelope,
    )

    await _emit_receipt(
        f"t2t.review.response.{response.decision}",
        actor=response.reviewer_tars_id,
        resource=response.review_id,
        payload={
            "plan_id": row["plan_id"],
            "decision": response.decision,
            "comment": response.comment,
            "reason": response.reason,
        },
    )

    apply_result: dict[str, Any] | None = None
    if response.decision == "approve":
        apply_result = await _auto_apply(row["plan_id"], response.review_id)
        if apply_result is not None and apply_result.get("ok"):
            await asyncio.to_thread(
                outbox.set_state, response.review_id, "applied"
            )

    return {
        "ok": True,
        "review_id": response.review_id,
        "decision": response.decision,
        "apply_result": apply_result,
    }


async def _auto_apply(plan_id: str, review_id: str) -> dict[str, Any] | None:
    """Apply the locally-stored composer plan after a peer approval."""

    cstore = _get_composer_store()
    if cstore is None:
        return None
    plan = await asyncio.to_thread(cstore.load_plan, plan_id)
    if plan is None:
        return {"ok": False, "error": "plan_not_found"}
    if plan.state == "applied":
        return {"ok": True, "applied_ops": [], "already_applied": True}
    plan.state = "approved"
    await asyncio.to_thread(cstore.save_plan, plan)
    result = await asyncio.to_thread(_apply_plan, plan)

    await _emit_receipt(
        "t2t.review.auto_applied",
        actor="composer",
        resource=plan_id,
        payload={
            "review_id": review_id,
            "ok": bool(result.ok),
            "applied_ops": list(result.applied_ops),
            "error": result.error,
            "receipts": list(result.receipts),
        },
    )
    return result.to_dict()
