"""Minimal 5-field cron parser + ``next_after`` calculator.

Pure stdlib (no croniter / APScheduler dep). The five fields are:

    minute hour day-of-month month day-of-week
       0-59  0-23     1-31    1-12  0-6 (Sun=0)

Each field accepts:

- ``*``                 — any value
- ``N``                 — literal integer
- ``A-B``               — inclusive range
- ``A,B,C``             — explicit list (commas can mix with ranges)
- ``*/N`` or ``A-B/N``  — step values
- Day-of-week names     — ``MON``, ``TUE``, ``WED``, ``THU``, ``FRI``,
                          ``SAT``, ``SUN`` (case-insensitive)
- Month names           — ``JAN`` … ``DEC`` (case-insensitive)
- ``SUN`` is also accepted as ``7`` (so ``0`` and ``7`` both mean Sun)

Shortcuts:

- ``@hourly``    → ``0 * * * *``
- ``@daily``     → ``0 0 * * *``
- ``@midnight``  → ``0 0 * * *`` (alias)
- ``@weekly``    → ``0 0 * * 0``
- ``@monthly``   → ``0 0 1 * *``
- ``@yearly``    → ``0 0 1 1 *``
- ``@annually``  → ``0 0 1 1 *`` (alias)

Day-of-month + day-of-week interaction follows the classic Vixie cron
rule: if both fields are restricted (i.e. neither is ``*``) the entry
fires when *either* matches. Most operators don't hit this corner so
the unit tests cover it explicitly.

Timezone handling uses :class:`zoneinfo.ZoneInfo` so any TZ database
name works (``"UTC"`` default; ``"America/Los_Angeles"`` etc.). The
returned ``datetime`` from :func:`next_after` is always **UTC** — the
caller stores it as a unix timestamp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

try:  # py>=3.9 stdlib
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9 fallback to UTC only
    ZoneInfo = None  # type: ignore[assignment]


SHORTCUTS: dict[str, str] = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}


_DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}
_MON_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


# Field bounds — (min, max).
_BOUNDS = {
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 6),
}


# ---------- Errors ---------------------------------------------------------


class CronParseError(ValueError):
    """Raised when a cron expression is malformed."""


# ---------- Parsed expression ---------------------------------------------


@dataclass(frozen=True)
class CronExpression:
    """A parsed 5-field cron expression.

    Each field is the explicit set of integer values that satisfy it.
    For ``*`` we just store the full inclusive range as a frozenset so
    ``in`` checks stay O(1).
    """

    raw: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    dows: frozenset[int]
    dom_restricted: bool
    dow_restricted: bool

    def matches(self, dt: datetime) -> bool:
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False
        # Vixie-cron OR rule when both DOM and DOW are restricted.
        # python's weekday(): Mon=0..Sun=6. Cron: Sun=0..Sat=6.
        cron_dow = (dt.weekday() + 1) % 7
        dom_match = dt.day in self.days
        dow_match = cron_dow in self.dows
        if self.dom_restricted and self.dow_restricted:
            if not (dom_match or dow_match):
                return False
        else:
            if not (dom_match and dow_match):
                return False
        return True


# ---------- Field parsing -------------------------------------------------


_TOKEN_RE = re.compile(r"^[\d\*\-\,\/A-Za-z]+$")


def _resolve_name(token: str, field: str) -> str:
    """Resolve month / dow name aliases into integer strings."""

    upper = token.upper()
    if field == "dow":
        if upper in _DOW_NAMES:
            return str(_DOW_NAMES[upper])
        # Allow "7" as Sunday alias.
        if upper == "7":
            return "0"
    if field == "month" and upper in _MON_NAMES:
        return str(_MON_NAMES[upper])
    return token


def _parse_field(raw: str, field: str) -> frozenset[int]:
    lo, hi = _BOUNDS[field]
    raw = raw.strip()
    if not raw:
        raise CronParseError(f"empty {field} field")
    if not _TOKEN_RE.match(raw):
        raise CronParseError(f"invalid characters in {field} field: {raw!r}")
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise CronParseError(f"empty list element in {field}: {raw!r}")
        out.update(_parse_part(part, field, lo, hi))
    if not out:
        raise CronParseError(f"no values resolved for {field}: {raw!r}")
    return frozenset(out)


def _parse_part(part: str, field: str, lo: int, hi: int) -> set[int]:
    step = 1
    if "/" in part:
        base, step_str = part.split("/", 1)
        if not step_str:
            raise CronParseError(f"missing step value in {field}: {part!r}")
        try:
            step = int(step_str)
        except ValueError as exc:
            raise CronParseError(
                f"non-int step in {field}: {part!r}"
            ) from exc
        if step <= 0:
            raise CronParseError(f"step must be positive in {field}: {part!r}")
    else:
        base = part
    if base == "*":
        a, b = lo, hi
    elif "-" in base:
        a_raw, b_raw = base.split("-", 1)
        a = _atom(_resolve_name(a_raw, field), field, lo, hi)
        b = _atom(_resolve_name(b_raw, field), field, lo, hi)
        if a > b:
            raise CronParseError(
                f"range backwards in {field}: {part!r}"
            )
    else:
        a = b = _atom(_resolve_name(base, field), field, lo, hi)
    return {v for v in range(a, b + 1, step)}


def _atom(token: str, field: str, lo: int, hi: int) -> int:
    try:
        v = int(token)
    except ValueError as exc:
        raise CronParseError(
            f"non-int atom in {field}: {token!r}"
        ) from exc
    if v < lo or v > hi:
        raise CronParseError(
            f"value out of range for {field}: {v} (allowed {lo}-{hi})"
        )
    return v


# ---------- Public API -----------------------------------------------------


def _expand_shortcut(expression: str) -> str:
    e = expression.strip()
    if not e:
        raise CronParseError("empty cron expression")
    if e.startswith("@"):
        try:
            return SHORTCUTS[e.lower()]
        except KeyError as exc:
            raise CronParseError(
                f"unknown shortcut: {expression!r} "
                f"(supported: {sorted(SHORTCUTS)})"
            ) from exc
    return e


def parse(expression: str) -> CronExpression:
    """Parse a 5-field cron expression (or supported shortcut).

    Raises :class:`CronParseError` on any malformed field.
    """

    raw = expression.strip()
    expanded = _expand_shortcut(raw)
    parts = expanded.split()
    if len(parts) != 5:
        raise CronParseError(
            f"expected 5 fields, got {len(parts)}: {expanded!r}"
        )
    minute_raw, hour_raw, dom_raw, month_raw, dow_raw = parts
    minutes = _parse_field(minute_raw, "minute")
    hours = _parse_field(hour_raw, "hour")
    days = _parse_field(dom_raw, "dom")
    months = _parse_field(month_raw, "month")
    dows = _parse_field(dow_raw, "dow")
    return CronExpression(
        raw=raw,
        minutes=minutes,
        hours=hours,
        days=days,
        months=months,
        dows=dows,
        dom_restricted=(dom_raw.strip() != "*"),
        dow_restricted=(dow_raw.strip() != "*"),
    )


def validate(expression: str) -> bool:
    """Return True iff ``expression`` parses without error."""

    try:
        parse(expression)
        return True
    except CronParseError:
        return False


def _resolve_tz(tz_name: str):
    if tz_name in ("", "UTC"):
        return timezone.utc
    if ZoneInfo is None:
        # Fallback for stripped Python builds without zoneinfo data.
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except Exception as exc:  # KeyError / ZoneInfoNotFoundError
        raise CronParseError(f"unknown timezone: {tz_name!r}") from exc


def next_after(
    expression: str,
    after_dt: datetime,
    tz: str = "UTC",
) -> datetime:
    """Return the next firing time strictly after ``after_dt``.

    ``after_dt`` may be naive or tz-aware. The returned datetime is
    always in **UTC** (tz-aware) so callers can store it as a unix
    timestamp without further conversion.

    The walk is bounded at four years ahead — that's enough room for
    every legal 5-field expression to fire at least once. We raise if
    we exceed that (which can't happen for any well-formed expression
    but guards against future bugs in :func:`parse`).
    """

    cron = parse(expression)
    zone = _resolve_tz(tz)
    if after_dt.tzinfo is None:
        after_dt = after_dt.replace(tzinfo=timezone.utc)
    # Walk in the schedule's local timezone so DST rolls cleanly.
    local = after_dt.astimezone(zone).replace(second=0, microsecond=0)
    # Step to the next minute boundary so "after" is strict.
    local = local + timedelta(minutes=1)
    end_at = local + timedelta(days=366 * 4)
    while local <= end_at:
        # Fast-forward optimisations to keep the worst case cheap on
        # narrow expressions like "0 0 1 1 *" (yearly).
        if local.month not in cron.months:
            local = _advance_month(local, cron.months)
            continue
        if local.day not in cron.days and not cron.dow_restricted:
            local = _advance_day(local)
            continue
        if local.hour not in cron.hours:
            local = _advance_hour(local, cron.hours)
            continue
        if cron.matches(local):
            return local.astimezone(timezone.utc)
        local = local + timedelta(minutes=1)
    raise CronParseError(
        f"could not find next firing within 4y for {expression!r}"
    )


def _advance_month(dt: datetime, allowed: Iterable[int]) -> datetime:
    cur_month = dt.month
    cur_year = dt.year
    sorted_months = sorted(allowed)
    next_month = next((m for m in sorted_months if m > cur_month), None)
    if next_month is None:
        next_month = sorted_months[0]
        cur_year += 1
    return dt.replace(
        year=cur_year,
        month=next_month,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _advance_day(dt: datetime) -> datetime:
    nxt = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt


def _advance_hour(dt: datetime, allowed: Iterable[int]) -> datetime:
    sorted_hours = sorted(allowed)
    next_h = next((h for h in sorted_hours if h > dt.hour), None)
    if next_h is None:
        return _advance_day(dt)
    return dt.replace(hour=next_h, minute=0, second=0, microsecond=0)
