"""macOS iMessage bridge — send + read (Wave 160).

Send path: AppleScript via ``osascript``. Apple's Messages.app
needs to be running and the handle (phone/email) needs to exist
in the operator's iMessage history; both are Apple-side
constraints we surface as honest errors.

Read path: SQLite read of ``~/Library/Messages/chat.db``. The
schema is stable across macOS releases (Apple uses an internal
``message`` + ``handle`` join). We only SELECT — never INSERT or
UPDATE — so the operator's database is never modified.

Both paths require:
  - macOS (sys.platform == 'darwin')
  - Full Disk Access for the process that runs us (Settings →
    Privacy & Security → Full Disk Access → add Terminal / TARS)

Honest no-ops:
  - Non-macOS: every public function returns the
    ``not_supported_on_platform`` error.
  - chat.db unreadable: ``recent_messages`` returns
    ``permission_denied`` with the System Settings path the
    operator needs to grant.
  - osascript missing or returns non-zero: ``send_imessage``
    returns the captured stderr.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


log = logging.getLogger("tars.notifications.imessage")


CONTRACT_VERSION = "0.1.0"


# Apple's "Cocoa epoch" — seconds since 2001-01-01 UTC, not 1970.
# Newer macOS releases store nanoseconds in the same column, so we
# detect by magnitude and divide if needed.
_COCOA_EPOCH_OFFSET = 978307200  # seconds between unix epoch and Cocoa epoch
_DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"


class IMessageError(Exception):
    """Base error for the iMessage bridge."""


@dataclass
class Message:
    """One row from chat.db, normalised."""

    id: int
    handle: str   # phone or email of the other party (may be "" for system)
    text: str
    is_from_me: bool
    sent_at: float  # unix timestamp (UTC), 0.0 if unknown
    service: str  # "iMessage" | "SMS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── platform support ─────────────────────────────────────────────


def is_supported() -> bool:
    """True iff this host can talk to iMessage."""

    return sys.platform == "darwin"


def _resolve_db_path() -> Path:
    raw = os.getenv("TARS_IMESSAGE_DB_PATH")
    return Path(raw).expanduser() if raw else _DEFAULT_DB_PATH


# ─── timestamp conversion ─────────────────────────────────────────


def _cocoa_to_unix(ts: int | float) -> float:
    """Convert Cocoa-epoch ts (seconds or nanoseconds) → unix seconds."""

    if not ts:
        return 0.0
    # Heuristic: anything > 1e15 is in nanoseconds (Big Sur+).
    if ts > 1e15:
        ts = ts / 1_000_000_000.0
    return float(ts) + _COCOA_EPOCH_OFFSET


# ─── send via AppleScript ─────────────────────────────────────────


_OSASCRIPT_TEMPLATE = """
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{handle}" of targetService
    send "{text}" to targetBuddy
end tell
"""


def _escape_for_applescript(s: str) -> str:
    # AppleScript string literal: escape backslash + double quote.
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send_imessage(handle: str, text: str) -> dict[str, Any]:
    """Send an iMessage to ``handle`` (phone in +E.164 or email).

    Returns ``{ok, handle, text_len, error?, stderr?}``. Never
    raises — failures land in the error/stderr fields.
    """

    if not is_supported():
        return {
            "ok": False,
            "error": "not_supported_on_platform",
            "platform": sys.platform,
        }
    handle = (handle or "").strip()
    text = (text or "").strip()
    if not handle:
        return {"ok": False, "error": "handle_required"}
    if not text:
        return {"ok": False, "error": "text_required"}
    if len(text) > 8000:
        return {"ok": False, "error": "text_too_long"}

    # Sanity-check the handle: phone or email shape only.
    if not _looks_like_handle(handle):
        return {"ok": False, "error": "handle_invalid_shape", "handle": handle}

    if shutil.which("osascript") is None:
        return {"ok": False, "error": "osascript_not_found"}

    script = _OSASCRIPT_TEMPLATE.format(
        handle=_escape_for_applescript(handle),
        text=_escape_for_applescript(text),
    )

    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "osascript_timeout",
            "handle": handle,
        }

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "osascript_failed",
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "").strip(),
            "handle": handle,
        }

    return {
        "ok": True,
        "handle": handle,
        "text_len": len(text),
        "sent_at": time.time(),
    }


def _looks_like_handle(s: str) -> bool:
    """Accept '+E.164 phone' or 'name@host.tld' email."""

    s = s.strip()
    if "@" in s and len(s) >= 5:
        # very light email shape — Apple does the real validation
        local, _, dom = s.partition("@")
        return bool(local) and "." in dom
    # phone number: optional +, digits, optional spaces/dashes
    return bool(re.fullmatch(r"\+?[0-9][0-9\-\s]{6,}", s))


# ─── read via chat.db ─────────────────────────────────────────────


_RECENT_SQL = """
SELECT
    m.ROWID                                AS id,
    h.id                                   AS handle,
    m.text                                 AS text,
    m.is_from_me                           AS is_from_me,
    m.date                                 AS date,
    m.service                              AS service
FROM message m
LEFT JOIN handle h ON h.ROWID = m.handle_id
ORDER BY m.date DESC
LIMIT ?
"""


def recent_messages(*, limit: int = 50) -> dict[str, Any]:
    """Read the most recent N messages from chat.db.

    Returns ``{ok, messages: [Message.to_dict()], db_path}`` or
    ``{ok: False, error, hint?}`` on platform/permission failure.
    """

    if not is_supported():
        return {
            "ok": False,
            "error": "not_supported_on_platform",
            "platform": sys.platform,
        }

    limit = max(1, min(int(limit), 1000))
    db = _resolve_db_path()
    if not db.exists():
        return {
            "ok": False,
            "error": "db_not_found",
            "db_path": str(db),
            "hint": (
                "chat.db is missing. Confirm Messages.app has been opened "
                "at least once on this machine (or set TARS_IMESSAGE_DB_PATH)."
            ),
        }
    if not os.access(db, os.R_OK):
        return {
            "ok": False,
            "error": "permission_denied",
            "db_path": str(db),
            "hint": (
                "macOS sandboxes ~/Library/Messages/chat.db. Grant Full "
                "Disk Access in System Settings → Privacy & Security → "
                "Full Disk Access → add the process that runs TARS."
            ),
        }

    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(_RECENT_SQL, (limit,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "error": "sqlite_error",
            "detail": str(exc),
            "db_path": str(db),
        }

    messages: list[dict[str, Any]] = []
    for row in rows:
        msg = Message(
            id=int(row["id"]),
            handle=str(row["handle"] or ""),
            text=str(row["text"] or ""),
            is_from_me=bool(row["is_from_me"]),
            sent_at=_cocoa_to_unix(row["date"] or 0),
            service=str(row["service"] or ""),
        )
        messages.append(msg.to_dict())

    return {
        "ok": True,
        "db_path": str(db),
        "count": len(messages),
        "messages": messages,
    }
