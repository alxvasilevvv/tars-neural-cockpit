# Connectors contract (Wave 91)

Real OAuth-backed read connectors for Slack, Gmail and Google Calendar.
Replaces the empty-list stubs that the awareness pack previously
returned. The legacy stub is still the fallback when env vars are
missing, so dev / local installs keep working without OAuth
credentials.

GitHub (Wave 73) is a separate token-based connector with its own
router under `/api/connectors/github/*`. Notion + Linear are scheduled
for v9.3 and Jira + Asana for v9.4.

## Supported services

| Connector | Mode      | Scopes                                                    | Storage key |
|-----------|-----------|-----------------------------------------------------------|-------------|
| `slack`   | OAuth v2  | `channels:read,history,groups:read,im:read,search:read`   | `slack`     |
| `gmail`   | Google OAuth (offline) | `gmail.readonly`                             | `google`    |
| `calendar`| Google OAuth (offline) | `calendar.readonly` (shares token with Gmail)| `google`    |
| `github`  | personal access token (Wave 73) | repo / workflow scopes                | n/a         |

## Setup

### Slack

1. Visit <https://api.slack.com/apps> and create an app for your
   workspace. Add the OAuth scopes listed above (these are user-token
   scopes; bot tokens cannot run `search.messages`).
2. Add `SLACK_REDIRECT_URI` (e.g. `https://your-host/api/connectors/slack/callback`)
   to the OAuth redirect URLs list.
3. Set env vars:
   ```
   SLACK_CLIENT_ID=...
   SLACK_CLIENT_SECRET=...
   SLACK_REDIRECT_URI=https://your-host/api/connectors/slack/callback
   ```

### Google (Gmail + Calendar)

1. Visit <https://console.cloud.google.com/apis/credentials> and create
   an OAuth client of type **Web application**.
2. Add `GOOGLE_REDIRECT_URI` to authorized redirects.
3. Enable Gmail API and Google Calendar API for the project.
4. Set env vars:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://your-host/api/connectors/gmail/callback
   ```

A single Google token covers both Gmail and Calendar -- finish OAuth
once and both light up.

## Token storage

Tokens persist at `~/.tars/connectors/<name>.json` (override the dir
with `TARS_CONNECTORS_DIR`). Mode `0o600`. The Gmail and Calendar
connectors share the `google.json` blob -- one refresh token, two
scopes.

Security model:

* the cockpit is single-tenant by design, so plaintext JSON is the
  default
* if the host has a vault key available the connector layer will wrap
  the blob in a Fernet-style envelope (Wave 92+ -- not yet active)
* deleting `~/.tars/connectors/<name>.json` is equivalent to "log out"

## API endpoints

```
GET    /api/connectors                                  status of all 3
GET    /api/connectors/{name}/auth-url?state=...        kick off OAuth
POST   /api/connectors/{name}/callback {code, state}    finish OAuth
POST   /api/connectors/{name}/disconnect                revoke + delete
GET    /api/connectors/{name}/health                    ping API

GET    /api/connectors/slack/channels?types=...&limit=...
GET    /api/connectors/slack/channels/{id}/messages?limit=...
GET    /api/connectors/gmail/threads?query=...&max=...
GET    /api/connectors/gmail/threads/{id}
GET    /api/connectors/calendar/today?calendar_id=primary
GET    /api/connectors/calendar/upcoming?days=7&calendar_id=primary
```

When env vars are missing every endpoint returns `503` with body:

```json
{"error":"connector_not_configured","name":"slack",
 "hint":"set SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_REDIRECT_URI"}
```

When a token is missing or rejected: `401` with
`connector_auth_error`. Upstream 5xx / network errors map to `502` with
`connector_upstream_error`.

## Awareness fallback

`backend/core/domains/packs/business/awareness.py` keeps its stub
output for `gmail` / `gcalendar` sources. The fetcher tries the real
connector first; on `ConnectorNotConfigured` or any exception it falls
back to the legacy stub so existing dashboards keep rendering.

## Roadmap

| Version | Connector              |
|---------|------------------------|
| v9.1    | GitHub (shipped)       |
| v9.2    | Slack / Gmail / Calendar (Wave 91) |
| v9.2    | Telegram bridge (Wave 108) |
| v9.3    | Notion, Linear         |
| v9.4    | Jira, Asana            |

## Telegram bridge (Wave 108)

Bot-API-based delivery channel. Operator creates a bot via
[@BotFather](https://t.me/BotFather), copies the token, drops it into
`TELEGRAM_BOT_TOKEN` (env) or POSTs it to
`/api/connectors/telegram/callback {code: "<bot_token>"}`. There is
no OAuth -- `get_auth_url` returns the BotFather URL so the FE can
render the same "connect" button shape as Slack/Gmail/Calendar.

* `TELEGRAM_BOT_TOKEN`         -- bot token (required)
* `TELEGRAM_OPERATOR_CHAT_ID`  -- optional; takes precedence over
  the saved blob field. Use to wire CI / sandbox bots.

Endpoints:

* `GET    /api/connectors/telegram/bot-info`   -- getMe identity
* `GET    /api/connectors/telegram/chats`      -- recent updates
* `POST   /api/connectors/telegram/save-self`  -- `{chat_id}` -> store
* `POST   /api/connectors/telegram/send-self`  -- `{text, parse_mode?}`

Webhook integration: outgoing webhook URLs may use the
`telegram://self` or `telegram://chat/{chat_id}` schemes. The
dispatcher recognises both and routes the JSON envelope through
`backend.core.webhooks.dispatcher.deliver_telegram` instead of an
HTTP POST -- payloads render as Markdown code blocks (Telegram has
no rich envelope).

## Notes

* `SlackClient.post_message` is intentionally disabled until Wave 92+
  -- it returns `{"ok": False, "error": "post_disabled"}` so callers
  can wire UI today and graduate later without a code change.
* Slack mentions search uses `search.messages` which requires a user
  token, not a bot token. Set scopes accordingly.
* The ICS calendar source (`IcsCalendarSource(url)`) is exposed for
  users without a Google account -- iCloud share links work directly.
