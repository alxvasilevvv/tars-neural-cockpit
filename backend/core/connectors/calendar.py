"""Google Calendar + .ics calendar connector (Wave 91).

Two read paths:

1. **Google Calendar** -- shares the OAuth refresh token with
   :mod:`backend.core.connectors.gmail` (storage key ``google``,
   scope ``calendar.readonly``).
2. **ICS feed** -- minimal RFC 5545 parser for users without a Google
   account (e.g. iCloud share links, school calendars). No auth.

Both expose the same shape so the awareness pack / cockpit doesn't
care which is configured:

::

    {
        "ok": True,
        "kind": "live",
        "source": "google" | "ics",
        "as_of": <epoch>,
        "events": [{summary, start, end, location, ...}, ...],
    }
"""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from . import (
    ConnectorAuthError,
    ConnectorNotConfigured,
    ConnectorTransportError,
)
from . import _storage
from . import gmail as _google_oauth


_API_BASE = "https://www.googleapis.com/calendar/v3"
_TIMEOUT_S = 12.0
_USER_AGENT = "TARS-cockpit/9.2.0 (+https://tars.meeet.world)"
_NAME = "google"  # share token with gmail


# -- env / config --------------------------------------------------------


def is_configured() -> bool:
    """Calendar piggybacks on the Google OAuth env."""

    return _google_oauth.is_configured()


def has_token() -> bool:
    return _storage.has_token(_NAME)


def get_auth_url(state: str | None = None) -> str:
    """Reuse Gmail's auth URL (same scopes by default)."""

    return _google_oauth.get_auth_url(state=state)


def exchange_code(code: str) -> dict[str, Any]:
    return _google_oauth.exchange_code(code)


def disconnect() -> bool:
    return _google_oauth.disconnect()


# -- ICS source ----------------------------------------------------------


_ICS_LINE = re.compile(r"^([A-Z0-9-]+)(?:;[^:]+)?:(.*)$")


def _parse_ics_dt(value: str) -> str | None:
    """Best-effort RFC 5545 datetime to ISO 8601 string."""

    v = value.strip()
    if not v:
        return None
    # All-day: YYYYMMDD
    if re.fullmatch(r"\d{8}", v):
        try:
            dt = datetime.strptime(v, "%Y%m%d").replace(tzinfo=timezone.utc)
            return dt.date().isoformat()
        except ValueError:
            return None
    # YYYYMMDDTHHMMSSZ
    if re.fullmatch(r"\d{8}T\d{6}Z", v):
        try:
            dt = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            return None
    # YYYYMMDDTHHMMSS (floating)
    if re.fullmatch(r"\d{8}T\d{6}", v):
        try:
            dt = datetime.strptime(v, "%Y%m%dT%H%M%S")
            return dt.isoformat()
        except ValueError:
            return None
    return v  # leave as-is for caller to interpret


class IcsCalendarSource:
    """Minimal .ics fetcher + parser (read-only).

    Not a full RFC 5545 implementation -- pulls VEVENT blocks and a few
    common fields. Recurrence rules (RRULE) are surfaced raw, not
    expanded.
    """

    def __init__(self, ics_url: str) -> None:
        if not ics_url:
            raise ValueError("ics_url is required")
        self._url = ics_url

    def fetch_text(self) -> str:
        req = urllib.request.Request(
            self._url,
            method="GET",
            headers={"user-agent": _USER_AGENT, "accept": "text/calendar"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise ConnectorTransportError(
                f"ICS HTTP {exc.code}: {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectorTransportError(f"ICS transport error: {exc}") from exc
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ConnectorTransportError(f"ICS decode error: {exc}") from exc

    @staticmethod
    def parse_events(ics_text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        # Unfold long lines (RFC 5545: continuation lines start with space/tab)
        lines: list[str] = []
        for raw_line in ics_text.splitlines():
            if raw_line.startswith((" ", "\t")) and lines:
                lines[-1] += raw_line[1:]
            else:
                lines.append(raw_line)

        cur: dict[str, Any] | None = None
        for line in lines:
            if line == "BEGIN:VEVENT":
                cur = {}
                continue
            if line == "END:VEVENT":
                if cur is not None:
                    events.append(cur)
                cur = None
                continue
            if cur is None:
                continue
            m = _ICS_LINE.match(line)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            kl = key.lower()
            if kl == "summary":
                cur["summary"] = val
            elif kl == "description":
                cur["description"] = val
            elif kl == "location":
                cur["location"] = val
            elif kl == "uid":
                cur["uid"] = val
            elif kl == "dtstart":
                cur["start"] = _parse_ics_dt(val)
            elif kl == "dtend":
                cur["end"] = _parse_ics_dt(val)
            elif kl == "rrule":
                cur["rrule"] = val
            elif kl == "status":
                cur["status"] = val
        return events

    def list_events(self, time_min: datetime | None = None, time_max: datetime | None = None) -> list[dict[str, Any]]:
        text = self.fetch_text()
        events = self.parse_events(text)
        if time_min or time_max:
            return [e for e in events if _within_window(e, time_min, time_max)]
        return events


def _within_window(
    event: Mapping[str, Any],
    time_min: datetime | None,
    time_max: datetime | None,
) -> bool:
    start = event.get("start")
    if not isinstance(start, str):
        return True  # don't drop events we can't parse
    try:
        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    if time_min and dt < time_min:
        return False
    if time_max and dt > time_max:
        return False
    return True


# -- Google Calendar Client ---------------------------------------------


class CalendarClient:
    """Google Calendar read client.

    Construct via :meth:`from_stored_token` -- shares the Gmail token.
    """

    def __init__(self, gmail_client: "_google_oauth.GmailClient") -> None:
        self._gmail = gmail_client

    @classmethod
    def from_stored_token(cls) -> "CalendarClient":
        gc = _google_oauth.GmailClient.from_stored_token()
        return cls(gc)

    def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = "primary",
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        token = self._gmail._ensure_fresh()  # noqa: SLF001 -- shared token lifecycle
        params = urllib.parse.urlencode(
            {
                "timeMin": _to_rfc3339(time_min),
                "timeMax": _to_rfc3339(time_max),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(int(max_results), 250)),
            }
        )
        url = (
            f"{_API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events?{params}"
        )
        payload = _google_oauth._http_get(url, token=token)  # noqa: SLF001
        items = payload.get("items") or []
        if not isinstance(items, list):
            return []
        return [_normalize_event(e) for e in items if isinstance(e, dict)]

    def today_summary(self, calendar_id: str = "primary") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = self.list_events(start, end, calendar_id=calendar_id)
        return {
            "ok": True,
            "kind": "live",
            "source": "google",
            "as_of": int(time.time()),
            "calendar_id": calendar_id,
            "count": len(events),
            "events": events,
        }


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    start = raw.get("start") or {}
    end = raw.get("end") or {}
    return {
        "id": raw.get("id"),
        "summary": raw.get("summary"),
        "description": raw.get("description"),
        "location": raw.get("location"),
        "html_link": raw.get("htmlLink"),
        "status": raw.get("status"),
        "start": (
            start.get("dateTime") or start.get("date") if isinstance(start, dict) else None
        ),
        "end": (
            end.get("dateTime") or end.get("date") if isinstance(end, dict) else None
        ),
        "attendees": [
            {
                "email": a.get("email"),
                "response_status": a.get("responseStatus"),
                "organizer": a.get("organizer"),
            }
            for a in (raw.get("attendees") or [])
            if isinstance(a, dict)
        ],
        "creator": (raw.get("creator") or {}).get("email"),
        "organizer": (raw.get("organizer") or {}).get("email"),
    }


def upcoming_summary(
    days: int = 7, calendar_id: str = "primary"
) -> dict[str, Any]:
    """Convenience: today + N days. Raises if not configured."""

    if not is_configured():
        raise ConnectorNotConfigured("Google Calendar env vars missing")
    client = CalendarClient.from_stored_token()
    now = datetime.now(timezone.utc)
    return {
        "ok": True,
        "kind": "live",
        "source": "google",
        "as_of": int(time.time()),
        "calendar_id": calendar_id,
        "days": int(days),
        "events": client.list_events(
            now, now + timedelta(days=int(days)), calendar_id=calendar_id
        ),
    }


__all__ = [
    "CalendarClient",
    "IcsCalendarSource",
    "is_configured",
    "has_token",
    "get_auth_url",
    "exchange_code",
    "disconnect",
    "upcoming_summary",
]
