# Waitlist — `POST /api/waitlist`

Status: **draft 1.0** · client implemented 2026-04-29 · server pending brother

Pre-launch email capture for `meeet.world/#waitlist`. We tell users we
will email **once**, when the binary drops. That promise is enforced
on the server: no newsletter, no drip, no marketing.

The frontend (`src/components/Waitlist.tsx`) POSTs to `/api/waitlist`.
If the endpoint is missing pre-launch, the entry is buffered in
`localStorage["tars-waitlist"]` (capped at 50 entries, oldest evicted)
so we don't lose anyone — once brother lands the route, the next
`<Waitlist/>` mount can drain via a tiny migration helper (TBD in
`src/lib/waitlist.ts`).

## Wire shape

```http
POST /api/waitlist
content-type: application/json

{
  "email": "operator@example.com",
  "role":  "founder",
  "ref":   "https://news.ycombinator.com/..."
}
```

Fields:

- `email` — already lowercased + trimmed by the client; **server still
  re-validates and re-normalises** (lowercase, NFKC, trim).
- `role` — one of `trader · founder · researcher · engineer · other`.
  Free-text wider rules permitted; server should accept any
  `^[a-z_]{2,32}$` and bin everything else as `other`.
- `ref` — `document.referrer` at submit. May be empty.

## Responses

```http
200 OK
{ "ok": true, "position": 1247 }

409 Conflict
{ "ok": false, "error": "duplicate", "position": 1182 }

422 Unprocessable
{ "ok": false, "error": "invalid_email" }

429 Too Many Requests
Retry-After: 30
{ "ok": false, "error": "rate_limit" }
```

`position` is the 1-indexed signup count for that email (or the
existing one for duplicates). The frontend renders `position #N` in
the success state; safe to omit if you don't want to expose the
counter — frontend handles `null`.

## Brother's responsibilities

1. **De-dupe by lowercased email.** First-write-wins; later attempts
   return `409` with the original `position`.
2. **Rate limit** by IP + email (`5/min/IP`, `1/min/email`).
3. **Validate** with `email-validator` or equivalent; reject MX-absent
   domains. If unsure, accept and re-validate async.
4. **Single email promise.** When the binary drops the first stable
   build, send exactly one templated email with the install URL and
   the `position` referenced. After that, **archive the row** — never
   re-send.
5. **Privacy compliance** — see `docs/PRIVACY_POLICY.md § 4`. Retention
   capped at 365 days; users can request deletion via the email link
   in the launch announcement (one-click unsubscribe = full deletion).
6. **Honour CCPA/GDPR DSAR** — same envelope as everything else on
   meeet.world.

## Headers we'd like in responses

```
Cache-Control: no-store, max-age=0
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

## Storage shape (suggestion, not enforced)

```sql
CREATE TABLE waitlist_tars (
  id              BIGSERIAL PRIMARY KEY,
  email           CITEXT UNIQUE NOT NULL,
  role            TEXT NOT NULL DEFAULT 'other',
  ref             TEXT,
  ip_hash         BYTEA,           -- SHA-256(ip + daily salt)
  user_agent      TEXT,            -- raw, debugging only
  country         TEXT,            -- CF-Country
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  notified_at     TIMESTAMPTZ
);
CREATE INDEX ON waitlist_tars (created_at);
```

`position` returned to the client = `id` for new rows, or the existing
`id` for duplicates.

## What we never store

- No raw IP — only a hash with a daily-rotating salt.
- No tracking pixel insertion in the launch email.
- No third-party ESP that profiles. Use the meeet.world transactional
  pipeline (Postmark / SES / our own SMTP).
