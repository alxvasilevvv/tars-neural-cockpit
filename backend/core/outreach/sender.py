"""Gmail-based outreach send (Wave 98).

:func:`send_draft` takes an approved draft, runs it through the
safety layer one last time, then hits the Gmail API
``users.messages.send`` using the existing Wave 91 Gmail OAuth token.

Requirements:

- ``draft.status == 'approved'`` (HIL gate already passed at the
  HTTP edge).
- The Wave 91 Google connector must have a stored token (run the
  OAuth flow first); otherwise the function returns a structured
  ``ok=False`` dict so the router can map it to a 503.

Side effects on success:

- ``draft.status`` -> ``sent``.
- ``draft.sent_at`` set.
- ``draft.gmail_message_id`` set.
- A receipt of type ``outreach.email_sent`` is recorded via
  :func:`backend.core.receipts.record` (Wave 95). Best-effort -- a
  receipt-store outage never fails the send.

Side effects on error:

- ``draft.status`` -> ``failed``.
- ``draft.error`` set with the first 240 chars of the exception
  message.
- A receipt of type ``outreach.email_failed`` is recorded.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Any

from .models import OutreachDraft
from .safety import check_send_eligibility
from .store import OutreachStore, get_store


log = logging.getLogger("tars.outreach.sender")

_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_TIMEOUT_S = 20.0


def _build_mime(draft: OutreachDraft, *, sender_email: str) -> str:
    msg = EmailMessage()
    msg["To"] = (
        f"{draft.recipient.get('name', '').strip()} <{draft.recipient['email']}>"
        if draft.recipient.get("name")
        else draft.recipient["email"]
    )
    msg["From"] = sender_email
    msg["Subject"] = draft.subject
    msg.set_content(draft.body)
    raw = msg.as_bytes()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _resolve_sender_email(token_blob: dict[str, Any]) -> str:
    """Resolve the From: header.

    Override via ``TARS_OUTREACH_FROM``. Otherwise fall back to a
    generic ``me@`` -- the Gmail API rewrites this to the
    authenticated user's primary address regardless, but a header is
    still required by the MIME layer.
    """

    override = (os.getenv("TARS_OUTREACH_FROM") or "").strip()
    if override:
        return override
    # Gmail API treats "me" as the authenticated user, but RFC 5322
    # requires an addr-spec in From:, so synthesise a placeholder.
    return token_blob.get("operator_email") or "me@tars.local"


async def _record_receipt(
    *,
    type_: str,
    draft: OutreachDraft,
    extra: dict[str, Any] | None = None,
) -> None:
    """Best-effort receipt emission. Never raises."""

    try:
        from backend.core.receipts import record

        payload = {
            "draft_id": draft.id,
            "template_id": draft.template_id,
            "recipient_email": draft.recipient.get("email"),
            "subject": draft.subject,
            "campaign_id": draft.campaign_id,
        }
        if extra:
            payload.update(extra)
        await record(
            type=type_,
            actor="outreach",
            resource=draft.id,
            payload=payload,
        )
    except Exception as exc:
        log.debug("outreach receipt emit failed (%s): %s", type_, exc)


async def send_draft(
    draft_id: str,
    *,
    store: OutreachStore | None = None,
) -> dict[str, Any]:
    """Send one approved draft via Gmail.

    Returns ``{"ok": True, "draft": {...}}`` on success, or
    ``{"ok": False, "reason": "...", "detail": "..."}`` on failure.
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}

    draft = await s.get_draft(draft_id)
    if not draft:
        return {"ok": False, "reason": "draft_not_found", "detail": draft_id}
    if draft.status != "approved":
        return {
            "ok": False,
            "reason": "not_approved",
            "detail": f"draft.status={draft.status!r}; must be 'approved'",
        }

    safety = await check_send_eligibility(draft, store=s)
    if not safety.ok:
        return {
            "ok": False,
            "reason": safety.reason,
            "detail": safety.detail,
        }

    # Lazy import so the outreach module doesn't require the connectors
    # package at import time (helps with isolated unit tests).
    try:
        from backend.core.connectors import (
            ConnectorAuthError,
            ConnectorNotConfigured,
            ConnectorTransportError,
        )
        from backend.core.connectors.gmail import GmailClient
    except Exception as exc:
        return {
            "ok": False,
            "reason": "connector_unavailable",
            "detail": str(exc),
        }

    try:
        client = GmailClient.from_stored_token()
    except ConnectorNotConfigured as exc:
        return {"ok": False, "reason": "gmail_not_configured", "detail": str(exc)}
    except ConnectorAuthError as exc:
        return {"ok": False, "reason": "gmail_no_token", "detail": str(exc)}

    try:
        token = client._ensure_fresh()  # type: ignore[attr-defined]
    except ConnectorAuthError as exc:
        return {"ok": False, "reason": "gmail_auth_error", "detail": str(exc)}

    sender_email = _resolve_sender_email(getattr(client, "_blob", {}))
    raw_b64 = _build_mime(draft, sender_email=sender_email)

    body = json.dumps({"raw": raw_b64}).encode("utf-8")
    req = urllib.request.Request(
        _GMAIL_SEND_URL,
        data=body,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        # Update draft to failed + record a receipt + bubble the error.
        err_text = str(exc)[:240]
        await s.update_draft(
            draft.id,
            status="failed",
            error=err_text,
        )
        await _record_receipt(
            type_="outreach.email_failed",
            draft=draft,
            extra={"error": err_text},
        )
        return {"ok": False, "reason": "gmail_send_failed", "detail": err_text}

    gmail_id = payload.get("id") or ""
    sent_ts = time.time()
    updated = await s.update_draft(
        draft.id,
        status="sent",
        sent_at=sent_ts,
        gmail_message_id=gmail_id,
    )
    final = updated or draft
    await _record_receipt(
        type_="outreach.email_sent",
        draft=final,
        extra={"gmail_message_id": gmail_id, "sent_at": sent_ts},
    )
    return {"ok": True, "draft": final.to_dict()}


__all__ = ["send_draft"]
