# iMessage bridge — v0.1 contract (Wave 160)

> **📚 Superseded by `NOTIFICATIONS.md`** as of Wave 164. This
> doc remains as the deep-dive for the iMessage-specific bits
> (Cocoa-epoch conversion, AppleScript escaping, chat.db
> schema). For the full notifications surface (iMessage +
> Telegram + Email + dispatcher + env table), see
> [docs/contracts/NOTIFICATIONS.md](./NOTIFICATIONS.md).

**Module:** `backend/core/notifications/imessage.py` · **Contract:** `0.1.0` · **Platform:** macOS only

Closes the last W148 reality-audit honesty drift — task #66
"Notification bridges (iMessage / Telegram / Email)" was marked
complete back in Wave 8.4.0 but no code existed. Wave 160 ships
the real iMessage half. Telegram + Email are v9.1.2.

## What this is

Two primitives operators can compose against:

| Function | Purpose | Platform | Permissions |
| --- | --- | --- | --- |
| `send_imessage(handle, text)` | Send a single message via Messages.app | macOS | none extra |
| `recent_messages(limit=50)` | Read last N messages from chat.db | macOS | Full Disk Access |

Both are sync (return a result dict); both never raise — every
failure case lands in the `error` field.

## What this is NOT

- **Not a real-time inbox.** `recent_messages` is poll-only; the
  cockpit / playbook can call it on a schedule.
- **Not auto-reply.** No automation hooks into the doctor's
  `doctor.status_changed` webhook by default. Per the safety
  rules in the system prompt: messaging on-behalf-of needs
  per-message operator approval.
- **Not Linux / Windows.** iMessage is Apple-only; the module
  returns `not_supported_on_platform` elsewhere.
- **Not a replacement for ipush/APNs.** This bridges from TARS
  to a person via the operator's own Messages.app — it doesn't
  bypass Apple's normal sending rules (TOS still apply).

## Send path

```python
from backend.core.notifications import send_imessage

result = send_imessage("+15551234567", "Daily briefing ready.")
# → {"ok": True, "handle": "+15551234567", "text_len": 21, "sent_at": …}
```

Validation order:
1. Platform must be macOS → `not_supported_on_platform`
2. Handle + text required → `handle_required` / `text_required`
3. Text ≤ 8000 chars → `text_too_long`
4. Handle must look like phone or email → `handle_invalid_shape`
5. `osascript` must exist on PATH → `osascript_not_found`
6. AppleScript timeout = 15s → `osascript_timeout`
7. Non-zero return code → `osascript_failed` (with stderr)

The AppleScript itself is the canonical iMessage send recipe:

```applescript
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "<handle>" of targetService
    send "<text>" to targetBuddy
end tell
```

The `<handle>` and `<text>` are escaped (`\\` → `\\\\`, `"` →
`\\"`) before substitution so user-supplied strings can't break
out of the AppleScript literal.

## Read path

```python
from backend.core.notifications import recent_messages

result = recent_messages(limit=50)
# → {
#     "ok": True,
#     "db_path": "/Users/alien/Library/Messages/chat.db",
#     "count": 50,
#     "messages": [
#         {
#             "id": 12345, "handle": "+15551234567", "text": "Hello",
#             "is_from_me": false, "sent_at": 1747200000.0,
#             "service": "iMessage"
#         },
#         …
#     ]
#   }
```

Permissions: macOS sandboxes `~/Library/Messages/chat.db`. On
first call without Full Disk Access, the module returns:

```json
{
  "ok": false,
  "error": "permission_denied",
  "db_path": "/Users/…/Library/Messages/chat.db",
  "hint": "macOS sandboxes ~/Library/Messages/chat.db. Grant Full Disk Access in System Settings → Privacy & Security → Full Disk Access → add the process that runs TARS."
}
```

The operator follows the hint, restarts TARS, and the second
call returns the rows.

## Cocoa-epoch timestamps

Apple stores `message.date` in Cocoa epoch (seconds or
nanoseconds since 2001-01-01 UTC). The module auto-detects:

| Magnitude | Format | Conversion |
| --- | --- | --- |
| `0` | unknown | returns `0.0` |
| `< 1e15` | seconds | `+ 978307200` (Cocoa epoch offset) |
| `≥ 1e15` | nanoseconds (Big Sur+) | `/ 1e9 + 978307200` |

## Env vars

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_IMESSAGE_DB_PATH` | `~/Library/Messages/chat.db` | Override the chat.db location (test seam). |

## Error catalog

| Wire error | When |
| --- | --- |
| `not_supported_on_platform` | non-macOS host |
| `handle_required` | empty handle on send |
| `text_required` | empty text on send |
| `text_too_long` | text > 8000 chars |
| `handle_invalid_shape` | handle isn't phone-like or email-like |
| `osascript_not_found` | `osascript` not on PATH |
| `osascript_failed` | AppleScript returned non-zero (stderr included) |
| `osascript_timeout` | send took > 15s |
| `db_not_found` | chat.db missing (Messages.app never opened) |
| `permission_denied` | chat.db exists but unreadable (no FDA) |
| `sqlite_error` | sqlite raised during SELECT |

## Honest framing

- **No incoming-message webhook.** v0.1 is poll-only. v9.2 may
  add a watch-mode that diffs `recent_messages` against a cache
  and fires `imessage.received` when new rows appear.
- **No group chat support.** Apple's `buddy` AppleScript path
  targets a single recipient. Groups land in v9.2.
- **No attachments.** Send path is text-only; read path returns
  only the `text` column. Attachments are stored separately in
  `~/Library/Messages/Attachments/` and v9.2 will join them.

## Roadmap

- **v0.1 (this release):** macOS send + read primitives
- **v0.2 (v9.1.2 target):** Telegram bridge module sibling
- **v0.3 (v9.1.2 target):** Email (SMTP) bridge module sibling
- **v0.4 (v9.2 target):** `imessage.received` webhook (watch mode)
- **v0.5 (v9.2 target):** Group chats + attachments
- **v1.0 (v9.3 target):** Cockpit notification routing — operator
  picks which doctor / receipt / clone events fan out to which
  bridge.
