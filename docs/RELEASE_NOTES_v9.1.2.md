# TARS v9.1.2 — release notes

**Released:** 2026-05-13 (Waves 160-164, all on `main`)
**Channel:** stable · additive over v9.1.1
**Platforms:** macOS + Linux (notifications trio works
cross-platform except iMessage which is macOS-only)
**Codename:** Phase L10.1 — operator alerts

## What's in this release

v9.1.2 closes the **last** W148 reality-audit honesty drift
(iMessage bridge, task #66) and completes the operator alerting
loop: when something drifts in TARS, the operator's phone /
inbox actually rings within ~30 seconds.

v9.1.1 shipped the daemon + doctor + drift-webhook. v9.1.2 ties
that webhook to three real notification channels.

## TL;DR — one paragraph

The notifications module ships three sibling bridges (iMessage,
Telegram, SMTP/Email) under a unified contract. The daemon's
doctor watcher (W157) optionally fans out every
`doctor.status_changed` entry through any subset of channels the
operator configures via `TARS_DAEMON_FANOUT_CHANNELS`. Operator
config is six env vars. End-state: drift in MCP / scheduler /
clone / cowork / receipts / vault triggers a Telegram + iMessage
+ Email alert in ~30 seconds.

## Wave-by-wave changelog

### W160 — iMessage bridge

- `backend/core/notifications/imessage.py` — macOS-only.
- `send_imessage(handle, text)` via AppleScript / `osascript`
  (15s timeout, handles E.164 phone OR email).
- `recent_messages(limit)` reads `~/Library/Messages/chat.db`
  (read-only SQLite, requires Full Disk Access).
- Cocoa-epoch timestamp conversion (seconds + nanoseconds).
- 22 test cases.
- Contract: `docs/contracts/IMESSAGE.md` (now superseded by
  `NOTIFICATIONS.md`).
- **Closes W148 task #66 honesty drift.**

### W161 — Telegram bridge sibling

- `backend/core/notifications/telegram.py` — cross-platform.
- `send_telegram(chat_id, text, *, token, parse_mode, ...)` via
  Bot API over plain urllib.
- `fanout_doctor_change(change)` helper reads
  `TARS_DOCTOR_ALERT_CHAT_ID`.
- 14 test cases.

### W162 — Daemon auto fan-out

- `fanout_all(change, channels)` dispatcher in
  `notifications/__init__.py`.
- `backend/core/daemon/doctor_watch._emit_changes` wires
  `TARS_DAEMON_FANOUT_CHANNELS` → `fanout_all` per change.
- Best-effort: fan-out failures never demote webhook emit success.
- 11 test cases on the fan-out + integration.

### W163 — Email/SMTP bridge

- `backend/core/notifications/email.py` — cross-platform.
- `send_email(to, subject, body, *, host, port, user, password,
  from_addr, tls)` via stdlib smtplib.
- Three TLS modes: `starttls` (default, 587), `ssl` (465), `plain` (25).
- Anonymous SMTP supported (login skipped when user/password unset).
- 17 test cases.

### W164 — Unified NOTIFICATIONS.md contract

- New `docs/contracts/NOTIFICATIONS.md` consolidates all three
  bridges, the dispatcher, the daemon wiring, the error catalog
  (25 wire codes), and the roadmap.
- `IMESSAGE.md` gets a "superseded by" banner pointing at the
  unified doc; retained as deep-dive for Cocoa-epoch / AppleScript
  / chat.db specifics.

## New env vars

| Variable | Default | Effect | Wave |
| --- | --- | --- | --- |
| `TARS_DAEMON_FANOUT_CHANNELS` | unset | comma-separated channel list (`telegram,imessage,email`); enables auto-fanout | W162 |
| `TARS_DOCTOR_ALERT_CHAT_ID` | — | Telegram chat for fanout | W161 |
| `TARS_DOCTOR_ALERT_IMESSAGE_HANDLE` | — | iMessage handle for fanout | W162 |
| `TARS_DOCTOR_ALERT_EMAIL` | — | Email recipient for fanout | W163 |
| `TARS_SMTP_HOST` | required (for email) | SMTP relay host | W163 |
| `TARS_SMTP_PORT` | 587 / 465 / 25 (per TLS mode) | Port | W163 |
| `TARS_SMTP_USER` | — | Auth user (optional) | W163 |
| `TARS_SMTP_PASSWORD` | — | Auth password | W163 |
| `TARS_SMTP_FROM` | required (for email) | From header | W163 |
| `TARS_SMTP_TLS` | `starttls` | `starttls` / `ssl` / `plain` | W163 |
| `TARS_IMESSAGE_DB_PATH` | `~/Library/Messages/chat.db` | Override (test seam) | W160 |

## New public surface

```python
from backend.core.notifications import (
    # bridges
    send_imessage, recent_messages, is_supported,
    send_telegram, telegram_is_configured,
    send_email, email_is_configured,
    # per-bridge fanout helpers
    imessage_fanout_doctor_change,
    telegram_fanout_doctor_change,
    email_fanout_doctor_change,
    # back-compat alias (telegram default from W161)
    fanout_doctor_change,
    # multi-channel dispatcher (W162)
    fanout_all,
    # types
    Message, IMessageError, CONTRACT_VERSION,
)
```

## Operator quick-start

```bash
# 1. Pick channels
export TARS_DAEMON_FANOUT_CHANNELS=telegram,imessage,email

# 2. Telegram
export TELEGRAM_BOT_TOKEN=123456:abc...
export TARS_DOCTOR_ALERT_CHAT_ID=987654321

# 3. iMessage (macOS only)
export TARS_DOCTOR_ALERT_IMESSAGE_HANDLE=+15551234567

# 4. Email
export TARS_DOCTOR_ALERT_EMAIL=ops@example.com
export TARS_SMTP_HOST=smtp.gmail.com
export TARS_SMTP_FROM=alien@example.com
export TARS_SMTP_USER=alien@example.com
export TARS_SMTP_PASSWORD=app-specific-password

# 5. Enable the daemon watcher
export TARS_DAEMON_DOCTOR_ENABLED=1
scripts/tars-daemon restart
```

Drift in any subsystem fires all configured channels within ~30 seconds.

## Honest framing

- **iMessage is macOS-only.** Linux operators get Telegram + Email.
- **Plain text only.** No HTML email (v9.1.3), no attachments (v9.2),
  no group chats (v9.2).
- **No throttling.** Every drift fires immediately. Operators who
  want quieter signal increase `TARS_DAEMON_DOCTOR_EVERY_N`.
- **No per-severity routing.** All configured channels see all
  drifts. Per-severity routing is v9.2.

## Testing

64 new tests across the 5 waves (138 cumulative across this
release cycle including the v9.1.1 daemon/doctor/clone modules):

- `tests/test_imessage.py` — 22 cases (W160)
- `tests/test_telegram_notify.py` — 14 cases (W161)
- `tests/test_email_notify.py` — 17 cases (W163)
- `tests/test_fanout_all.py` — 11 cases (W162)

All run on pure stdlib; no real SMTP / Telegram API / AppleScript
traffic in tests.

## Migration path

Zero breaking changes. v9.1.2 is purely additive over v9.1.1:

- New env vars all default to off / safe values.
- The notifications module is opt-in via env config.
- Without `TARS_DAEMON_FANOUT_CHANNELS`, the daemon behaves
  exactly as in v9.1.1 (just fires the webhook).
- v9.1.1 webhook contract unchanged — brother-side handlers
  don't need touching for v9.1.2.

## Brother handoff (meeet.world side)

**No new webhook events.** v9.1.2's `doctor.status_changed`
payload is identical to v9.1.1. The change is entirely
client-side — the operator now has three local notification
channels they can wire instead of relying on meeet.world's
dashboard alone.

If you want to mirror the fanout server-side (for operators on
mobile-only deployments without a TARS host running locally),
the meeet.world edge function can re-implement `fanout_all`
behaviour by reading the same `doctor.status_changed` event and
calling Telegram Bot API + your SMTP relay directly.

## Reality-audit drift status

**All three W148 reality-audit drifts now closed:**

| Drift | Closed by |
| --- | --- |
| MCP server bridge (#17, #85) | ✅ Wave 150 |
| Background TARS daemon (#65) | ✅ Waves 152 + 153 |
| iMessage bridge (#66) | ✅ Wave 160 |

The W148 audit catalogue is empty for the first time since the
audit ran.

## Roadmap

- **W165 (this release):** tag + release notes
- **W166-W170:** `tars-doctor --fix` auto-remediation mode
- **W171-W175:** Windows daemon parity (Task Scheduler)
- **W176-W180:** AI Clone v0.3 — signed envelopes (ed25519)
- **v9.2 — Phase L11:** cockpit Background panel, HTML email,
  per-severity routing, group-chat notifications

## Tagging

This release sits at `a28d3ae` on `main`. To tag locally:

```bash
git tag -a v9.1.2 -m "TARS v9.1.2 — operator alerts"
git push origin v9.1.2
```

Or use the W159 helper:

```bash
scripts/auto-push-tag.command v9.1.2
```
