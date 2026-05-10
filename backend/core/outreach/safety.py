"""Outreach send-eligibility guardrails (Wave 98).

Three checks run before any draft can transition to ``sent``:

1. Recipient email looks valid (RFC 5322-lite + length cap).
2. Body has no leftover placeholder markers like ``{{name}}`` or
   ``{variable}`` -- a real email with raw braces is a tell-tale sign
   that the LLM (or the operator's manual edit) missed a substitution.
3. Daily send-cap not exceeded (default 50 / day; override via
   ``TARS_OUTREACH_DAILY_CAP``). Counted off the store's
   ``status='sent'`` rows in the trailing 24h window.

The HIL gate (operator confirm via ``policy_gate.require_confirm``) is
enforced at the router edge, not here -- this module's contract is
about message-level safety, not transport-level authorisation.

Public API:

- :class:`SafetyResult` -- structured outcome (ok + reason).
- :func:`check_send_eligibility(draft)` -- runs all three checks.
- :func:`check_unsubscribe(body)` -- returns the body with the footer
  appended if it isn't already present.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from .models import OutreachDraft
from .store import OutreachStore, get_store


# Liberal-ish email regex. We're not trying to validate every legal RFC
# 5322 address; we're trying to catch fat-finger mistakes before Gmail
# rejects them with a 400.
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)

# Common placeholder shapes. Hits {{var}}, {var}, %var%, <<var>>.
_PLACEHOLDER_RE = re.compile(
    r"(?:\{\{[^}\n]{1,80}\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%[A-Za-z_][A-Za-z0-9_]*%|<<[^>\n]{1,80}>>)"
)


_DEFAULT_DAILY_CAP = 50

_UNSUBSCRIBE_MARKER = "Reply STOP"
_UNSUBSCRIBE_FOOTER = (
    "\n\n---\n"
    "You're receiving this because we previously corresponded. "
    "Reply STOP to opt out of future operator-initiated outreach."
)


@dataclass(frozen=True)
class SafetyResult:
    ok: bool
    reason: str | None = None
    detail: str | None = None


def _daily_cap() -> int:
    raw = (os.getenv("TARS_OUTREACH_DAILY_CAP") or "").strip()
    if not raw:
        return _DEFAULT_DAILY_CAP
    try:
        v = int(raw)
        return max(1, v)
    except ValueError:
        return _DEFAULT_DAILY_CAP


def _is_valid_email(addr: str) -> bool:
    if not addr or not isinstance(addr, str):
        return False
    addr = addr.strip()
    if len(addr) > 254 or len(addr) < 3:
        return False
    return bool(_EMAIL_RE.match(addr))


def _has_placeholders(text: str) -> str | None:
    """Return the offending substring, or ``None`` if clean."""

    if not text:
        return None
    m = _PLACEHOLDER_RE.search(text)
    return m.group(0) if m else None


async def check_send_eligibility(
    draft: OutreachDraft,
    *,
    store: OutreachStore | None = None,
) -> SafetyResult:
    """Run all pre-send checks. Return :class:`SafetyResult`.

    Does NOT enforce the HIL gate -- that lives at the HTTP edge so
    tests of the safety layer don't need a fake FastAPI request.
    """

    if not isinstance(draft.recipient, dict):
        return SafetyResult(False, "recipient_invalid", "recipient must be a dict")
    email = (draft.recipient.get("email") or "").strip()
    if not _is_valid_email(email):
        return SafetyResult(
            False, "recipient_invalid", f"recipient email looks malformed: {email!r}"
        )

    if draft.status not in {"approved", "draft"}:
        return SafetyResult(
            False,
            "bad_status",
            f"draft.status={draft.status!r}; expected 'approved' for send",
        )

    bad_subject = _has_placeholders(draft.subject or "")
    if bad_subject:
        return SafetyResult(
            False,
            "placeholder_in_subject",
            f"subject still contains {bad_subject!r}",
        )
    bad_body = _has_placeholders(draft.body or "")
    if bad_body:
        return SafetyResult(
            False,
            "placeholder_in_body",
            f"body still contains {bad_body!r}",
        )

    if not (draft.subject or "").strip():
        return SafetyResult(False, "empty_subject", "subject is empty")
    if not (draft.body or "").strip():
        return SafetyResult(False, "empty_body", "body is empty")

    s = store or get_store()
    if s.enabled:
        cap = _daily_cap()
        since = time.time() - 24 * 60 * 60
        sent_today = await s.count_sent_since(since)
        if sent_today >= cap:
            return SafetyResult(
                False,
                "daily_cap_exceeded",
                f"daily send cap of {cap} reached ({sent_today} sent in last 24h)",
            )

    return SafetyResult(True)


def check_unsubscribe(body: str) -> str:
    """Append the unsubscribe footer if not already present."""

    if not body:
        return body
    if _UNSUBSCRIBE_MARKER in body:
        return body
    return body + _UNSUBSCRIBE_FOOTER


__all__ = [
    "SafetyResult",
    "check_send_eligibility",
    "check_unsubscribe",
]
