"""Operator query DSL — extract scoped filters from a free-text query.

Recognised tokens (case-insensitive keys, case-preserved values):

    role:operator      → message role
    pack:business      → thread.pack_slug
    thread:thr_abc     → thread id
    trace:trc_123      → trace id
    kind:domain.action.completed   → meeet event kind
    since:7d           → window lower bound (relative or YYYY-MM-DD)
    until:2026-04-01   → window upper bound

Quoted values are supported (``pack:"my pack"``); a leading ``-``
inverts the filter (``-role:tool``) — exclusion semantics live one
layer up (the FTS path only consumes positive bounds today, but the
parser preserves the polarity so future callers can opt in).

The parser is liberal: an unrecognised key is left in the cleaned
text so FTS still has a fallback. Whitespace is collapsed.

Time-window helpers (``since`` / ``until``) accept:

- relative: ``7d``, ``24h``, ``45m``, ``2w`` (suffix d/h/m/w);
- ISO date:  ``YYYY-MM-DD`` (interpreted as UTC midnight);
- ISO timestamp: ``YYYY-MM-DDTHH:MM[:SS][Z]``.

Returns POSIX seconds (float). Invalid values silently drop.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_KEYS = ("role", "pack", "thread", "trace", "kind", "since", "until", "mime")

# token: optional leading '-', a recognised key, ':', then either a
# quoted "..." or a non-whitespace run.
_TOKEN_RE = re.compile(
    r"""
    (?P<neg>-)?
    (?P<key>role|pack|thread|trace|kind|since|until|mime)
    :
    (?:
        "(?P<qval>[^"]*)"
        |
        (?P<val>\S+)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


_REL_RE = re.compile(r"^(?P<n>\d+)(?P<unit>[smhdwSMHDW])$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ParsedQuery:
    """Result of :func:`parse_query_filters`.

    ``text`` is the cleaned-up free-text portion (filters stripped).
    ``filters`` carries the parsed key/value pairs. Negated filters
    surface as ``filters_neg`` so downstream callers can decide whether
    to honour the polarity.
    """

    text: str
    filters: dict[str, Any] = field(default_factory=dict)
    filters_neg: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "filters": dict(self.filters),
            "filters_neg": dict(self.filters_neg),
        }


def parse_query_filters(query: str) -> ParsedQuery:
    """Extract recognised filter tokens from ``query``.

    Repeated tokens for the same key — e.g. ``pack:a pack:b`` —
    collapse into a list. Unrecognised tokens stay in the cleaned
    text. Empty / blank input returns an empty :class:`ParsedQuery`.
    """

    if not query or not query.strip():
        return ParsedQuery(text="")

    positive: dict[str, Any] = {}
    negative: dict[str, Any] = {}
    cleaned_parts: list[str] = []
    last_end = 0

    for match in _TOKEN_RE.finditer(query):
        prefix = query[last_end : match.start()]
        if prefix.strip():
            cleaned_parts.append(prefix)
        key = match.group("key").lower()
        value = (match.group("qval") if match.group("qval") is not None
                 else match.group("val"))
        if value is None:
            last_end = match.end()
            continue
        target = negative if match.group("neg") else positive
        coerced = _coerce(key, value)
        if coerced is None:
            last_end = match.end()
            continue
        existing = target.get(key)
        if existing is None:
            target[key] = coerced
        elif isinstance(existing, list):
            existing.append(coerced)
        else:
            target[key] = [existing, coerced]
        last_end = match.end()

    tail = query[last_end:]
    if tail.strip():
        cleaned_parts.append(tail)

    cleaned = " ".join(p.strip() for p in cleaned_parts if p.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return ParsedQuery(
        text=cleaned, filters=positive, filters_neg=negative
    )


def _coerce(key: str, raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    if key in {"since", "until"}:
        return _parse_time_bound(raw)
    return raw


def _parse_time_bound(raw: str) -> float | None:
    """Interpret ``raw`` as a POSIX timestamp (UTC).

    Returns ``None`` for unrecognised input rather than raising; the
    caller can decide whether to drop the filter or fall through.
    """

    rel = _REL_RE.match(raw)
    if rel:
        n = int(rel.group("n"))
        unit = rel.group("unit").lower()
        seconds = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 86400 * 7,
        }.get(unit, 0)
        if seconds <= 0 or n <= 0:
            return None
        return time.time() - n * seconds
    if _ISO_DATE_RE.match(raw):
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None
        return dt.timestamp()
    iso = raw.rstrip("Z")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def merge_filters(
    *,
    parsed: ParsedQuery,
    explicit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine parsed filters with caller-supplied overrides.

    Explicit (caller) wins over parsed (from query) — operators who
    POST a saved-search ``filters`` body get the final say. Lists are
    not merged; the explicit value replaces the parsed one entirely
    for that key.
    """

    out: dict[str, Any] = dict(parsed.filters)
    if explicit:
        for k, v in explicit.items():
            if v is None:
                continue
            out[k] = v
    return out
