"""Speech intents — slash-command + voice intent extraction.

Phase L4.1 follow-up: parse the dictated transcript for TARS slash-
commands ("/run traders.morning_check") *before* the LLM sees it
so confident actions execute deterministically and only the
ambiguous residue gets routed to the chat voice.

Public surface:

- :func:`parse_intent` — parse a transcript, return an
  :class:`Intent` (kind, target, args, residual).
- :class:`Intent` — frozen dataclass.
- :data:`KNOWN_KINDS` — the intent vocabulary.

The router (:mod:`web_extras.routers.speech`) wraps
:func:`parse_intent` behind ``POST /api/speech/intents``.
"""

from __future__ import annotations

from .intents import (
    KNOWN_KINDS,
    Intent,
    parse_intent,
)


__all__ = [
    "KNOWN_KINDS",
    "Intent",
    "parse_intent",
]
