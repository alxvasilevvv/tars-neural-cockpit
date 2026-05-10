"""Incoming webhook handling.

External systems (Slack, Stripe, GitHub Actions, n8n, custom) POST
JSON bodies to ``/api/webhooks/inbox/{token}``. This module is the
business logic the router calls into; it stays framework-agnostic so
tests can exercise it without spinning up FastAPI.

Flow:

1. Look up the :class:`IncomingWebhook` by token. Reject if missing
   or inactive.
2. Optionally verify the request body via HMAC if the caller passed
   a ``signature_header`` (and the webhook has a configured secret —
   inbound HMAC is opt-in per webhook because not every external
   system signs requests the same way).
3. If the webhook has a ``trigger_playbook_id``, dispatch that
   playbook with the parsed body as input. The playbook runner is
   imported lazily so cold-import stays light.
4. Return a structured ``{ok, ...}`` dict the router can serialise.

Failures are returned as ``{ok: False, reason: str, status: int}``
rather than raising — the router decides whether to translate to an
HTTP error code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .models import IncomingWebhook
from .signing import verify_payload
from .store import WebhookStore

log = logging.getLogger("tars.webhooks.inbox")


async def handle_inbox(
    *,
    token: str,
    body_bytes: bytes,
    signature_header: str | None,
    store: WebhookStore,
    inbound_secret: bytes | None = None,
    max_age_s: int = 300,
) -> dict[str, Any]:
    """Process one inbound POST.

    ``inbound_secret`` is the operator-side secret for verifying the
    request. Today we do not persist a per-incoming inbound secret —
    callers can pass one explicitly (or set
    ``TARS_WEBHOOKS_INBOUND_SECRET``) when they want HMAC enforcement.
    When the secret is not provided, signature verification is
    skipped even if a header is sent.
    """

    if not token:
        return {"ok": False, "reason": "token_required", "status": 400}
    incoming = await store.get_incoming_by_token(token)
    if incoming is None or not incoming.active:
        return {"ok": False, "reason": "unknown_token", "status": 404}

    # Optional HMAC verification.
    if inbound_secret and signature_header:
        if not verify_payload(
            inbound_secret,
            body_bytes,
            signature_header,
            max_age_s=max_age_s,
        ):
            return {"ok": False, "reason": "bad_signature", "status": 401}

    try:
        parsed: Any = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "reason": f"bad_json: {exc}", "status": 400}

    triggered_playbook: str | None = None
    playbook_result: Any = None
    if incoming.trigger_playbook_id:
        triggered_playbook = incoming.trigger_playbook_id
        try:
            playbook_result = await _run_playbook(
                playbook_id=incoming.trigger_playbook_id,
                payload=parsed if isinstance(parsed, dict) else {"value": parsed},
                webhook=incoming,
            )
        except Exception as exc:  # never crash the inbox
            log.warning(
                "inbox playbook dispatch failed: webhook=%s playbook=%s err=%s: %s",
                incoming.id,
                incoming.trigger_playbook_id,
                type(exc).__name__,
                exc,
            )
            return {
                "ok": False,
                "reason": f"playbook_failed: {exc}",
                "status": 500,
                "webhook_id": incoming.id,
                "triggered_playbook": triggered_playbook,
            }

    return {
        "ok": True,
        "status": 200,
        "webhook_id": incoming.id,
        "webhook_name": incoming.name,
        "triggered_playbook": triggered_playbook,
        "playbook_result": playbook_result,
    }


async def _run_playbook(
    *,
    playbook_id: str,
    payload: dict[str, Any],
    webhook: IncomingWebhook,
) -> Any:
    """Best-effort playbook dispatch.

    Imports are local so the inbox module doesn't drag the entire
    playbook stack into cold-start. Returns whatever the runner
    returns (dict / dataclass / None).
    """

    try:
        from backend.core.playbooks import get_playbook, run_playbook
    except Exception as exc:  # playbooks module not available
        return {
            "ok": False,
            "reason": f"playbooks_module_unavailable: {exc}",
        }

    pb = get_playbook(playbook_id) if callable(get_playbook) else None
    if pb is None:
        return {"ok": False, "reason": "playbook_not_found", "playbook_id": playbook_id}

    context = {
        "source": "webhook",
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
        "input": payload,
    }
    # Resolve PolicyMode lazily so the import stays cheap when the
    # inbox isn't dispatching to a playbook.
    try:
        from backend.core.policy.gate import PolicyMode

        mode = PolicyMode.CONFIRM
    except Exception:
        mode = "confirm"  # type: ignore[assignment]
    try:
        result = await run_playbook(pb, context=context, mode=mode)
    except TypeError:
        # Older runner signature — fall back without explicit kwargs.
        result = await run_playbook(pb, context)  # type: ignore[arg-type]
    return result
