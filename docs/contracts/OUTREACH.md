# Outreach contract (Wave 98)

Contract version: **1.0**.
Module: `backend/core/outreach`.
Router: `web_extras/routers/outreach.py` (`/api/outreach/*`).

## Surface

The outreach module persists three record types and exposes a small
HTTP surface for an operator to draft, approve, and send emails (LP
updates, founder DD, intros, follow-ups, welcome touches) in their
own voice via the AI Clone style profile.

### Records

| Type | Lifecycle |
|------|-----------|
| `OutreachTemplate` | created (built-in or custom) -> patched -> never deleted |
| `OutreachDraft` | `draft` -> `approved` -> `sent` (or `failed`) |
| `OutreachCampaign` | `planning` -> `sending` -> `done` (or `aborted`) |

### Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/api/outreach/templates` | seeds five built-ins on first call |
| POST   | `/api/outreach/templates` | create custom |
| PATCH  | `/api/outreach/templates/{id}` | edit prompt / variables |
| POST   | `/api/outreach/drafts` | generate one draft |
| GET    | `/api/outreach/drafts?status=draft\|approved\|sent\|failed` | list |
| GET    | `/api/outreach/drafts/{id}` | fetch one |
| PATCH  | `/api/outreach/drafts/{id}` | edit subject/body or status (draft -> approved) |
| DELETE | `/api/outreach/drafts/{id}` | discard |
| POST   | `/api/outreach/drafts/{id}/send` | HIL-gated Gmail send |
| GET    | `/api/outreach/drafts/{id}/preview` | render with safety report |
| POST   | `/api/outreach/campaigns` | create + bulk draft |
| GET    | `/api/outreach/campaigns` | list |
| GET    | `/api/outreach/campaigns/{id}` | detail + drafts |
| POST   | `/api/outreach/campaigns/{id}/generate` | re-run drafting for missing rows |
| POST   | `/api/outreach/campaigns/{id}/approve-all` | bulk approve (with `except_ids`) |
| POST   | `/api/outreach/campaigns/{id}/send` | paced bulk send (HIL-gated) |
| POST   | `/api/outreach/campaigns/{id}/abort` | mark `aborted` |

## Built-in templates

Five starter templates ship with the module and are auto-seeded on
first call to any endpoint:

1. **`lp_update`** -- quarterly limited-partner update.
   Variables: `quarter`, `aum_change`, `top_3_wins`, `headwinds`, `next_quarter`.
2. **`founder_dd`** -- founder reach-out after deck review.
   Variables: `founder_name`, `company`, `key_points`, `meeting_request`.
3. **`intro`** -- warm intro to a portfolio company.
   Variables: `intro_party`, `recipient_party`, `mutual_context`, `ask`.
4. **`follow_up`** -- 7+ day no-reply nudge.
   Variables: `original_thread_subject`, `original_ask`, `urgency`.
5. **`welcome_lp`** -- onboarding a new LP after the wire lands.
   Variables: `lp_name`, `commit_amount`, `first_call_date`.

Each template's `system_prompt` instructs the LLM to mimic the
operator's existing AI Clone style profile; the drafter
(`backend.core.outreach.drafter.generate_draft`) layers nearest-
example messages + the variable values on top at draft time.

## HIL gate

`POST /api/outreach/drafts/{id}/send` and
`POST /api/outreach/campaigns/{id}/send` call
`web_extras.policy_gate.require_confirm`. When the env var
`TARS_REQUIRE_OPERATOR_CONFIRM=1` is set, the request must carry an
`X-TARS-Confirm` token minted via the wallet confirm flow (Wave 76).

## Daily cap

The safety layer (`backend.core.outreach.safety.check_send_eligibility`)
counts `status='sent'` rows in the trailing 24h window and refuses
the next send when the count reaches `TARS_OUTREACH_DAILY_CAP`
(default: 50). The router's expensive-routes middleware also adds
an HTTP-edge cap of 50 / day per IP via the `outreach.send` bucket
in `web_extras/middleware/expensive_routes_rate_limit.py`.

The drafting endpoint has a separate `outreach.draft` bucket
(30 burst / 20 per minute) so the LLM cost is bounded too.

## Gmail dependency

Sending requires the **Wave 91 Gmail OAuth token**. Run the OAuth
flow via `/api/connectors/google/auth` (or the cockpit settings
panel) to provision `~/.tars/connectors/google.json` before any
`POST /drafts/{id}/send` call. Without a token the send endpoint
returns `502 {"reason": "gmail_no_token"}`.

`TARS_OUTREACH_FROM` overrides the synthesised `From:` header.
The Gmail API rewrites `From:` to the authenticated user's primary
address regardless, so the override is mainly cosmetic.

## AI Clone integration

`generate_draft` calls `backend.core.clone.style.profile()` to
fetch the operator's style snapshot and `_nearest_examples()` to
pull up to 3 most-similar past messages. Both calls are best-
effort -- if the clone module is disabled
(`CLONE_STORE=disabled`), the drafter falls back to a neutral
profile and the prompt's examples block reads
`"(no operator examples yet -- write in a measured, professional tone)"`.

## Receipts

Successful sends emit a `outreach.email_sent` receipt;
failures emit `outreach.email_failed`. Both go through the Wave 95
`backend.core.receipts.record` helper -- best-effort, never raises.
Payload includes `draft_id`, `template_id`, `recipient_email`,
`subject`, and (on success) `gmail_message_id` + `sent_at`.

## Storage

SQLite at `~/.tars/outreach.sqlite` (override with
`TARS_OUTREACH_DB_PATH`; disable with `TARS_OUTREACH_STORE=disabled`).
WAL + `asyncio.to_thread` discipline matches the cohort + scheduler
modules.

## Compatibility

- Schema is auto-created on first connect.
- Template upsert is keyed by `slug`; existing rows have body fields
  refreshed but `id` + `created_at` preserved -- so the FE never sees
  ID churn after a starter prompt is bumped.
- Draft status `sent` is terminal; `failed` is recoverable (operator
  edits + flips back to `draft`, which the safety layer accepts).
