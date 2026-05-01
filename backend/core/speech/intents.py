"""Slash-command + voice intent parser.

Operators dictate TARS in two registers:

1. **Typed slash-commands** — explicit, precise, e.g.
   ``/run traders.morning_check`` or
   ``/jump research lab``.
2. **Voice prefixes** — verbose, e.g.
   ``"TARS, run traders morning check"`` or
   ``"Hey TARS, jump to research lab"``.

This parser handles both. It is *deterministic* (no LLM) so the
operator can rely on it firing every time, and it never executes
anything — it just returns a structured :class:`Intent` describing
what should run. The router/frontend decides whether to dispatch
or ask for confirmation.

Intent vocabulary
-----------------

================  ===========================================
``run_action``    ``<pack>.<action_id>`` invocation
``run_playbook``  ``<playbook_id>`` invocation
``jump``          fuzzy-jump to a thread / pack / saved search
``search``        run a cross-thread search
``snooze``        snooze a saved search
``help``          surface available slash-commands
``none``          no intent detected → fall through to LLM
================  ===========================================

If a slash command is recognised but the body is malformed, the
intent kind is set to the matched kind and ``error`` carries the
diagnostic. The router can surface that as a 400 to the operator
without paying for a chat round-trip.

The parser also strips wake words ("TARS,", "Hey TARS,",
"Computer,") so the residual transcript (``cleaned``) can be
forwarded to the chat voice when the intent is ``none``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping


KNOWN_KINDS: tuple[str, ...] = (
    "run_action",
    "run_playbook",
    "jump",
    "search",
    "snooze",
    "help",
    "none",
)


@dataclass(frozen=True)
class Intent:
    """One parsed intent.

    ``cleaned`` is the residual transcript with the matched intent
    prefix stripped. When ``kind == "none"`` it equals the
    wake-word-stripped transcript, ready for the LLM.
    """

    kind: str
    raw: str
    cleaned: str = ""
    target: str | None = None  # "<pack>.<action_id>" or "<playbook_id>"
    query: str | None = None
    args: Mapping[str, Any] = field(default_factory=dict)
    duration_s: int | None = None  # for snooze
    confidence: float = 1.0
    consumed: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "raw": self.raw,
            "cleaned": self.cleaned,
            "target": self.target,
            "query": self.query,
            "args": dict(self.args),
            "duration_s": self.duration_s,
            "confidence": self.confidence,
            "consumed": self.consumed,
            "error": self.error,
        }


# ---------------------------------------------------------------------
# Wake-word handling
# ---------------------------------------------------------------------


_WAKE_PHRASES: tuple[str, ...] = (
    "hey tars",
    "ok tars",
    "okay tars",
    "tars please",
    "tars",
    "hey computer",
    "computer",
    "jarvis",
)


def _strip_wake(text: str) -> str:
    """Remove a leading wake phrase (case-insensitive, optional comma)."""

    stripped = text.strip()
    lowered = stripped.lower()
    for phrase in _WAKE_PHRASES:
        if lowered.startswith(phrase):
            tail = stripped[len(phrase) :].lstrip(" ,.:;-—")
            return tail
    return stripped


# ---------------------------------------------------------------------
# Parsers per intent kind
# ---------------------------------------------------------------------


# Slash command body must start with a / followed by an alpha word.
_SLASH_RE = re.compile(r"^/(?P<verb>[a-zA-Z]+)\s*(?P<body>.*)$", re.DOTALL)

# Action target: pack.action with optional dotted segments inside the
# action_id. Pack slugs are conventionally a single token.
_ACTION_TARGET_RE = re.compile(
    r"^(?P<pack>[a-z][a-z0-9_]*)\.(?P<action>[a-z][a-z0-9_.]*)$"
)

# Voice form: "run pack action" or "run pack dot action" or
# "run pack.action [args]". We require the literal verb "run" up front.
_VOICE_RUN_RE = re.compile(
    r"^run\s+(?P<rest>.+)$", re.IGNORECASE | re.DOTALL
)
_VOICE_JUMP_RE = re.compile(
    r"^jump(?:\s+to)?\s+(?P<rest>.+)$", re.IGNORECASE | re.DOTALL
)
_VOICE_SEARCH_RE = re.compile(
    r"^search(?:\s+for)?\s+(?P<rest>.+)$", re.IGNORECASE | re.DOTALL
)
_VOICE_HELP_RE = re.compile(
    r"^(help|what can you do|commands)\s*\??$", re.IGNORECASE
)
_VOICE_SNOOZE_RE = re.compile(
    r"^snooze\s+(?P<rest>.+)$", re.IGNORECASE | re.DOTALL
)


def _parse_action_target(token: str) -> str | None:
    """Normalise a candidate target like ``"pack.action"``."""

    token = token.strip().rstrip(".")
    if _ACTION_TARGET_RE.match(token):
        return token
    return None


_WORD_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _voice_to_action(rest: str) -> tuple[str | None, str]:
    """Convert a voice fragment ("traders morning check" or
    "traders dot morning check") into a normalised
    ``"traders.morning_check"`` target.

    Returns ``(target_or_None, residual)``. ``residual`` is the
    leftover text after the target (used for arg parsing).
    """

    text = rest.strip()
    # Replace " dot " with "." so "traders dot morning check"
    # becomes "traders.morning check".
    text = re.sub(r"\s+dot\s+", ".", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, ""

    parts = text.split(" ")
    head = parts[0]

    # Already canonical pack.action_or_segment? Allow trailing
    # word-shaped tokens to extend the action_id with underscores
    # (so "traders.morning check" → "traders.morning_check").
    if _ACTION_TARGET_RE.match(head):
        action_tokens: list[str] = []
        consumed = 1
        for tok in parts[1:]:
            if _WORD_TOKEN_RE.fullmatch(tok):
                action_tokens.append(tok.lower())
                consumed += 1
            else:
                break
        if action_tokens:
            target = head + "_" + "_".join(action_tokens)
        else:
            target = head
        residual = " ".join(parts[consumed:]).strip()
        return target, residual

    # Voice form without dots: "<pack> <action_word_1> <action_word_2>".
    # We collapse the action words with underscore. Without a
    # registry lookup this is a best-effort guess, so the caller
    # decides whether to confirm.
    if len(parts) < 2:
        return None, ""
    pack = parts[0].lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", pack):
        return None, ""
    action_tokens = []
    consumed = 1
    for tok in parts[1:]:
        if _WORD_TOKEN_RE.fullmatch(tok):
            action_tokens.append(tok.lower())
            consumed += 1
        else:
            break
    if not action_tokens:
        return None, ""
    target = f"{pack}.{'_'.join(action_tokens)}"
    residual = " ".join(parts[consumed:]).strip()
    return target, residual


def _maybe_parse_json_args(s: str) -> tuple[Mapping[str, Any], str | None]:
    """If ``s`` looks like a JSON object, parse it; else return
    ``({}, None)``. ``None`` for the second slot means "no error";
    a string means "parsed as JSON-ish but failed".
    """

    s = s.strip()
    if not s:
        return {}, None
    if not (s.startswith("{") and s.endswith("}")):
        return {}, None
    try:
        data = json.loads(s)
    except (ValueError, TypeError):
        return {}, "invalid_json_args"
    if not isinstance(data, dict):
        return {}, "args_must_be_object"
    return data, None


# ---------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------


def parse_intent(
    transcript: str,
    *,
    known_playbook_ids: set[str] | None = None,
) -> Intent:
    """Parse ``transcript`` into a structured :class:`Intent`.

    ``known_playbook_ids`` lets the caller disambiguate
    ``run <id>`` between an action (``pack.action``) and a
    playbook id when ``<id>`` happens to match both shapes. If
    not provided, the parser falls back to "looks like
    pack.action → run_action; otherwise → run_playbook".
    """

    raw = transcript or ""
    if not raw.strip():
        return Intent(kind="none", raw=raw, cleaned="", consumed=False)

    text = _strip_wake(raw)
    if not text:
        # Wake word only, no payload — operator just got TARS's
        # attention; nothing to dispatch.
        return Intent(
            kind="none",
            raw=raw,
            cleaned="",
            consumed=True,
            confidence=0.6,
        )

    # --------- slash-command path ---------
    slash_match = _SLASH_RE.match(text)
    if slash_match:
        verb = slash_match.group("verb").lower()
        body = slash_match.group("body").strip()
        return _dispatch_verb(
            verb=verb,
            body=body,
            raw=raw,
            confidence=1.0,
            known_playbook_ids=known_playbook_ids,
        )

    # --------- voice path ---------
    if _VOICE_HELP_RE.match(text):
        return Intent(
            kind="help",
            raw=raw,
            cleaned="",
            confidence=0.85,
        )

    voice_run = _VOICE_RUN_RE.match(text)
    if voice_run:
        return _dispatch_verb(
            verb="run",
            body=voice_run.group("rest").strip(),
            raw=raw,
            confidence=0.7,
            known_playbook_ids=known_playbook_ids,
        )

    voice_jump = _VOICE_JUMP_RE.match(text)
    if voice_jump:
        return _dispatch_verb(
            verb="jump",
            body=voice_jump.group("rest").strip(),
            raw=raw,
            confidence=0.75,
            known_playbook_ids=known_playbook_ids,
        )

    voice_search = _VOICE_SEARCH_RE.match(text)
    if voice_search:
        return _dispatch_verb(
            verb="search",
            body=voice_search.group("rest").strip(),
            raw=raw,
            confidence=0.75,
            known_playbook_ids=known_playbook_ids,
        )

    voice_snooze = _VOICE_SNOOZE_RE.match(text)
    if voice_snooze:
        return _dispatch_verb(
            verb="snooze",
            body=voice_snooze.group("rest").strip(),
            raw=raw,
            confidence=0.7,
            known_playbook_ids=known_playbook_ids,
        )

    # No intent detected — this transcript belongs to the LLM.
    return Intent(
        kind="none",
        raw=raw,
        cleaned=text,
        consumed=False,
    )


def _dispatch_verb(
    *,
    verb: str,
    body: str,
    raw: str,
    confidence: float,
    known_playbook_ids: set[str] | None,
) -> Intent:
    if verb == "run":
        return _parse_run(body, raw=raw, confidence=confidence,
                          known_playbook_ids=known_playbook_ids)
    if verb == "jump":
        return _parse_jump(body, raw=raw, confidence=confidence)
    if verb == "search":
        return _parse_search(body, raw=raw, confidence=confidence)
    if verb == "snooze":
        return _parse_snooze(body, raw=raw, confidence=confidence)
    if verb == "help":
        return Intent(kind="help", raw=raw, cleaned="", confidence=1.0)
    # Unknown slash verb — surface as none with the verb in error so
    # the cockpit can show "unknown command /<verb>".
    return Intent(
        kind="none",
        raw=raw,
        cleaned=raw.strip(),
        consumed=False,
        confidence=0.0,
        error=f"unknown_verb:{verb}",
    )


def _parse_run(
    body: str,
    *,
    raw: str,
    confidence: float,
    known_playbook_ids: set[str] | None,
) -> Intent:
    """``run <pack>.<action> [json-args]`` or ``run <playbook_id>``."""

    body = body.strip()
    if not body:
        return Intent(
            kind="run_action",
            raw=raw,
            cleaned="",
            confidence=0.0,
            error="run_target_required",
        )

    head, _, tail = body.partition(" ")
    canonical = _parse_action_target(head)

    # Try voice-form ("traders morning check") if the head doesn't
    # already look canonical.
    voice_canonical: str | None = None
    voice_residual = ""
    if canonical is None:
        voice_canonical, voice_residual = _voice_to_action(body)

    target = canonical or voice_canonical
    args_residual = tail if canonical else voice_residual

    # Decide between action vs playbook.
    if target is not None and known_playbook_ids and target in known_playbook_ids:
        return Intent(
            kind="run_playbook",
            raw=raw,
            cleaned="",
            target=target,
            confidence=confidence,
        )
    if target is not None:
        args, args_err = _maybe_parse_json_args(args_residual)
        return Intent(
            kind="run_action",
            raw=raw,
            cleaned="",
            target=target,
            args=args,
            confidence=confidence
            if canonical is not None
            else max(0.5, confidence - 0.15),
            error=args_err,
        )

    # No `pack.action` shape — interpret as a playbook id (single
    # token) when it matches the registry, otherwise return an
    # error so the cockpit can ask for clarification.
    candidate = head.strip()
    if known_playbook_ids and candidate in known_playbook_ids:
        return Intent(
            kind="run_playbook",
            raw=raw,
            cleaned="",
            target=candidate,
            confidence=confidence,
        )
    if known_playbook_ids is None and candidate:
        # Optimistically dispatch as a playbook; the runner will
        # reject if it doesn't exist, and the operator gets a
        # readable error. Still mark consumed so we don't double-
        # send the transcript to the LLM.
        return Intent(
            kind="run_playbook",
            raw=raw,
            cleaned="",
            target=candidate,
            confidence=max(0.4, confidence - 0.3),
        )
    return Intent(
        kind="run_action",
        raw=raw,
        cleaned="",
        target=None,
        confidence=0.0,
        error="run_target_unrecognised",
    )


def _parse_jump(body: str, *, raw: str, confidence: float) -> Intent:
    body = body.strip()
    if not body:
        return Intent(
            kind="jump",
            raw=raw,
            cleaned="",
            confidence=0.0,
            error="jump_query_required",
        )
    return Intent(
        kind="jump",
        raw=raw,
        cleaned="",
        query=body,
        confidence=confidence,
    )


def _parse_search(body: str, *, raw: str, confidence: float) -> Intent:
    body = body.strip()
    if not body:
        return Intent(
            kind="search",
            raw=raw,
            cleaned="",
            confidence=0.0,
            error="search_query_required",
        )
    return Intent(
        kind="search",
        raw=raw,
        cleaned="",
        query=body,
        confidence=confidence,
    )


_DURATION_RE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>s|sec|secs|second|seconds|"
    r"m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|"
    r"w|week|weeks)\b",
    re.IGNORECASE,
)


def _duration_to_seconds(s: str) -> int | None:
    m = _DURATION_RE.search(s)
    if not m:
        return None
    n = float(m.group("n"))
    unit = m.group("unit").lower()
    if unit.startswith("s"):
        return int(n)
    if unit.startswith("m") and not unit.startswith("min"):
        # bare "m" is ambiguous; treat as minutes by convention
        return int(n * 60)
    if unit.startswith("min"):
        return int(n * 60)
    if unit.startswith("h"):
        return int(n * 3600)
    if unit.startswith("d"):
        return int(n * 86400)
    if unit.startswith("w"):
        return int(n * 7 * 86400)
    return None


def _parse_snooze(body: str, *, raw: str, confidence: float) -> Intent:
    """``snooze <saved_search_id> [for] <duration>``."""

    body = body.strip()
    if not body:
        return Intent(
            kind="snooze",
            raw=raw,
            cleaned="",
            confidence=0.0,
            error="snooze_target_required",
        )
    # Extract the duration first so we can isolate the id.
    duration_s = _duration_to_seconds(body)
    head = body.split(" ", 1)[0].strip()
    if not head:
        return Intent(
            kind="snooze",
            raw=raw,
            cleaned="",
            confidence=0.0,
            error="snooze_target_required",
        )
    return Intent(
        kind="snooze",
        raw=raw,
        cleaned="",
        target=head,
        duration_s=duration_s,
        confidence=confidence,
        error=None if duration_s else "snooze_duration_missing",
    )
