# TARS notifications — unified contract (Waves 160-163)

**Module:** `backend/core/notifications/` · **Contract:** `0.2.0`

The notifications module is the operator's alerting surface. It
turns the W157 `doctor.status_changed` webhook (and any other
caller) into a real ping on the operator's phone or inbox.

Three bridges + one dispatcher:

| Bridge | Module | Platforms | Channel slug |
| --- | --- | --- | --- |
| iMessage | `imessage.py` *(Wave 160)* | macOS only | `imessage` |
| Telegram | `telegram.py` *(Wave 161)* | macOS / Linux / Windows | `telegram` |
| SMTP/Email | `email.py` *(Wave 163)* | macOS / Linux / Windows | `email` |
| Dispatcher | `__init__.py` *(Wave 162)* — `fanout_all()` | All | — |

The W157 daemon doctor watcher fans out automatically when
`TARS_DAEMON_FANOUT_CHANNELS` is set.

## Shape contract

Every bridge exposes:

```python
def send_<channel>(target, content, ...) -> dict[str, Any]
def fanout_doctor_change(change, *, target=None) -> dict[str, Any]
def is_configured() -> bool   # iMessage uses is_supported()
```

Return-dict shape:

```python
{
    "ok": bool,
    "error"?: str,       # only when ok=False
    "detail"?: str,      # human-readable detail
    "hint"?: str,        # how to fix (env var to set, etc.)
    # + channel-specific fields on success
}
```

**Nothing ever raises.** Every transport / auth / validation error
lands in the `error` field. This matters because the doctor
watcher fans out inside the daemon tick loop — a raise would
break the tick.

## iMessage bridge (macOS)

```python
from backend.core.notifications import send_imessage, recent_messages

send_imessage("+15551234567", "Daily briefing ready.")
recent_messages(limit=50)
```

| Function | Returns |
| --- | --- |
| `send_imessage(handle, text)` | `{ok, handle, text_len, sent_at}` |
| `recent_messages(limit=50)` | `{ok, db_path, count, messages: [Message.to_dict()]}` |
| `is_supported()` | `True` only on macOS |

Validation order: platform → handle → text → handle shape →
osascript available → AppleScript exec. Each failure surfaces a
distinct `error` slug (see catalog below).

**Permissions:** read path requires Full Disk Access for
`~/Library/Messages/chat.db`. Send path requires Messages.app to
be running and the handle to exist in iMessage history.

**Env override (test seam):** `TARS_IMESSAGE_DB_PATH` for chat.db path.

## Telegram bridge (cross-platform)

```python
from backend.core.notifications import send_telegram

send_telegram(chat_id, "Hello", parse_mode="Markdown")
```

| Function | Returns |
| --- | --- |
| `send_telegram(chat_id, text, *, token, parse_mode, disable_web_page_preview, timeout_s)` | `{ok, chat_id, message_id, text_len}` |
| `telegram_is_configured()` | `True` iff bot token resolves |

`text` is capped at 4096 chars (Telegram's hard limit). HTTP is
plain `urllib` — no third-party deps.

**Env:**

| Variable | Default | Effect |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | required | Bot token |
| `TARS_DOCTOR_ALERT_CHAT_ID` | — | Default chat for `fanout_doctor_change` |

## SMTP/Email bridge (cross-platform)

```python
from backend.core.notifications import send_email

send_email("ops@example.com", "Alert", "Body")
```

| Function | Returns |
| --- | --- |
| `send_email(to, subject, body, *, host, port, user, password, from_addr, tls, timeout_s)` | `{ok, to, subject, message_id, body_len}` |
| `email_is_configured()` | `True` iff HOST + FROM are set |

`to` accepts a string, list, or comma-separated string. Plain
text only (HTML is v9.1.3).

**Env:**

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_SMTP_HOST` | required | SMTP relay host |
| `TARS_SMTP_PORT` | 587 (starttls) / 465 (ssl) / 25 (plain) | Port |
| `TARS_SMTP_USER` | — | Auth user (optional — skipped if unset) |
| `TARS_SMTP_PASSWORD` | — | Auth password |
| `TARS_SMTP_FROM` | required | From header |
| `TARS_SMTP_TLS` | `starttls` | `starttls` / `ssl` / `plain` |
| `TARS_DOCTOR_ALERT_EMAIL` | — | Default recipient for `fanout_doctor_change` |

## Dispatcher (`fanout_all`)

```python
from backend.core.notifications import fanout_all

fanout_all(change, channels=["telegram", "imessage", "email"])
# → [
#   {"channel": "telegram", "ok": True, "message_id": 42, ...},
#   {"channel": "imessage", "ok": True, ...},
#   {"channel": "email", "ok": True, ...},
# ]
```

When `channels=None`, reads `TARS_DAEMON_FANOUT_CHANNELS`
(comma-separated). Unknown channel slugs return
`{channel: <slug>, ok: false, error: "unknown_channel"}`.

## Daemon auto fan-out (W162 wiring)

When `TARS_DAEMON_FANOUT_CHANNELS` is set, the W157 daemon
watcher dispatches every `doctor.status_changed` entry through
`fanout_all` immediately after firing the webhook. Best-effort —
a failed bridge dispatch never demotes the webhook emit success.

Full operator config:

```bash
export TARS_DAEMON_DOCTOR_ENABLED=1
export TARS_DAEMON_FANOUT_CHANNELS=telegram,imessage,email

# Telegram
export TELEGRAM_BOT_TOKEN=...
export TARS_DOCTOR_ALERT_CHAT_ID=123456

# iMessage (macOS only)
export TARS_DOCTOR_ALERT_IMESSAGE_HANDLE=+15551234567

# Email
export TARS_DOCTOR_ALERT_EMAIL=ops@example.com
export TARS_SMTP_HOST=smtp.gmail.com
export TARS_SMTP_FROM=alien@example.com
export TARS_SMTP_USER=alien@example.com
export TARS_SMTP_PASSWORD=app-specific-password
```

Drift → 3 channels within ~30 seconds.

## Error catalog

| Wire | Bridge | Cause |
| --- | --- | --- |
| `not_supported_on_platform` | imessage | non-macOS host |
| `handle_required` | imessage | empty handle on send |
| `text_required` | imessage / telegram | empty text |
| `text_too_long` | imessage (8000) / telegram (4096) | length cap exceeded |
| `handle_invalid_shape` | imessage | handle isn't phone-like or email-like |
| `osascript_not_found` | imessage | osascript not on PATH |
| `osascript_failed` | imessage | AppleScript returned non-zero |
| `osascript_timeout` | imessage | send > 15s |
| `db_not_found` | imessage | chat.db missing |
| `permission_denied` | imessage | chat.db unreadable (no FDA) |
| `sqlite_error` | imessage | sqlite raised |
| `token_missing` | telegram | `TELEGRAM_BOT_TOKEN` unset |
| `chat_id_required` | telegram | empty chat_id |
| `http_error` | telegram | non-2xx response (with status + detail) |
| `transport_error` | telegram / email | URLError / DNS / timeout |
| `telegram_api_error` | telegram | body `ok:false` (with description + code) |
| `bad_response` | telegram | non-dict JSON body |
| `to_required` | email | empty recipients |
| `subject_required` | email | empty subject |
| `body_required` | email | empty body |
| `host_missing` | email | `TARS_SMTP_HOST` unset |
| `from_missing` | email | `TARS_SMTP_FROM` unset |
| `auth_failed` | email | SMTP login rejected |
| `smtp_error` | email | smtplib raised non-auth error |
| `unknown_channel` | fanout_all | channel slug not in registry |

## Honest framing

- **iMessage is poll-only.** No incoming-message webhook in v0.1;
  v9.2 may add watch-mode that diffs `recent_messages`.
- **No HTML email yet.** v0.1 is text/plain. HTML lands in v9.1.3.
- **No attachments anywhere.** Body-only across all three.
- **No DKIM signing.** That's the SMTP relay's job.
- **No throttling.** Every drift fires every configured channel
  immediately. Operators who want quieter signal set
  `TARS_DAEMON_DOCTOR_EVERY_N` > 1 (run doctor less often).
- **No per-channel routing.** All channels see all drifts. Per-
  severity routing (e.g. "only fail goes to Telegram") is v9.2.

## Roadmap

- **v0.1 (Wave 160):** iMessage send + read primitives
- **v0.2 (Waves 161, 162, 163 — *this release*):** Telegram + SMTP siblings + auto-fanout in daemon watcher
- **v0.3 (v9.1.3 target):** HTML email body, attachment support
- **v0.4 (v9.2 target):** iMessage watch-mode webhook (incoming)
- **v0.5 (v9.2 target):** Per-severity routing (operator picks "warn → telegram only", "fail → all")
- **v1.0 (v9.3 target):** Cockpit notification routing UI — drag-drop event → channel mappings

## Testing

64 cases across the three bridges + dispatcher, all stdlib:

- `tests/test_imessage.py` — 22 cases
- `tests/test_telegram_notify.py` — 14 cases
- `tests/test_email_notify.py` — 17 cases
- `tests/test_fanout_all.py` — 11 cases (covers `fanout_all` + daemon-watch wiring)

Real SMTP / Telegram API / AppleScript traffic is fully mocked
via `unittest.mock` — no network or shell calls leave the test
process.
