"""W260 — TARS-to-TARS code review handoff.

TARS A finishes a Composer plan (W253) and instead of approving it
locally, sends it to TARS B for a second pair of eyes. TARS B sees
the diff in their REVIEW inbox, can leave a voice/text comment, and
signs back an approval or rejection. When the approval receipt
returns to TARS A, the plan auto-applies through the regular
composer executor so the chain of custody (drafted -> reviewed ->
applied) ends up in the W67 receipt ledger as one coherent story.

Three sibling modules:

- :mod:`.protocol` -- :class:`ReviewRequest` and
  :class:`ReviewResponse` dataclasses + the signed-envelope
  canonicalisation helpers. Builds on the W82 T2T handshake (signed
  payload + sender pubkey + base64 ed25519 signature over the
  canonical JSON).

- :mod:`.outbox` -- pending outgoing reviews waiting for a response
  from a peer TARS. ``~/.tars/t2t_reviews.sqlite`` ``outbox`` +
  ``responses`` tables.

- :mod:`.inbox` -- incoming review requests we received and need to
  approve/reject. Same SQLite, ``inbox`` table.

Disable with ``TARS_T2T_REVIEW_DB=disabled``. Disabled mode keeps the
router endpoints alive but they return ``{"ok": False, "error":
"disabled"}`` rather than 500'ing.
"""

from __future__ import annotations

from .protocol import (
    ENVELOPE_VERSION,
    ReviewRequest,
    ReviewResponse,
    canonical_bytes,
    sign_envelope,
    verify_envelope,
)
from .inbox import InboxStore, get_inbox, reset_inbox
from .outbox import OutboxStore, get_outbox, reset_outbox

__all__ = [
    "ENVELOPE_VERSION",
    "ReviewRequest",
    "ReviewResponse",
    "canonical_bytes",
    "sign_envelope",
    "verify_envelope",
    "InboxStore",
    "OutboxStore",
    "get_inbox",
    "get_outbox",
    "reset_inbox",
    "reset_outbox",
]
