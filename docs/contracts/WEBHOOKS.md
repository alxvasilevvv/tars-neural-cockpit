# TARS Webhooks — Public Contract v1.0

Wave 90 introduces a **two-way webhook surface** for B2B integrations:

- **Outgoing** — TARS POSTs signed events to operator-registered URLs
  whenever a tracked source emits one (playbook lifecycle, HIL
  decisions, receipts, agent CRUD).
- **Incoming** — external systems (Slack, Stripe, GitHub Actions, n8n,
  Zapier, custom) POST into TARS to trigger a playbook.

The whole subsystem is **opt-in**:

| Switch                                  | Default | Effect                                  |
| --------------------------------------- | ------- | --------------------------------------- |
| `TARS_WEBHOOKS_STORE`                   | enabled | Set to `disabled` to short-circuit `emit()` and the router. |
| `TARS_WEBHOOKS_ENABLED`                 | unset   | Background dispatcher loop runs only when set to `1`. |
| `TARS_WEBHOOKS_DISPATCH_INTERVAL_S`     | 30      | Loop tick cadence (`0` disables).       |
| `TARS_WEBHOOKS_DISPATCH_BATCH`          | 50      | Max deliveries fired per tick.          |
| `TARS_WEBHOOKS_DB_PATH`                 | `~/.tars/webhooks.sqlite` | DB location override. |
| `TARS_WEBHOOKS_INBOUND_SECRET`          | unset   | Optional shared secret for inbound HMAC verification on `/api/webhooks/inbox/{token}`. |

Existing TARS deployments that don't touch the new endpoints behave
identically — no migration runs against any other store.

---

## 1. Event envelope

Every outgoing POST body is a single JSON object:

```json
{
  "id": "evt_8f3c8...",
  "type": "playbook.started",
  "occurred_at": 1715379600.123,
  "data": {
    "playbook_id": "pb_morning_brief",
    "steps": 4,
    "mode": "confirm"
  }
}
```

| Field         | Type    | Notes                                                    |
| ------------- | ------- | -------------------------------------------------------- |
| `id`          | string  | Idempotency key; stable across retries of the same event. |
| `type`        | string  | One of the [standard event types](#3-standard-event-types). Unknown types must be tolerated. |
| `occurred_at` | float   | Unix seconds (UTC) when the event was minted.            |
| `data`        | object  | Event-specific payload. May add fields without bumping contract. |

Consumers MUST treat unknown `type` values as no-ops and SHOULD use
`id` for deduplication.

---

## 2. Signature scheme

Each outgoing POST carries an HMAC-SHA256 signature in the
`X-TARS-Signature` header:

```
X-TARS-Signature: t=1715379600,v1=8d92c9e4...
X-TARS-Event:     playbook.started
X-TARS-Delivery-Id: del_a1b2c3d4...
Content-Type:     application/json
User-Agent:       TARS-Webhooks/1.0
```

### Computing the signature

```
signed_string = f"{timestamp}.{raw_body_bytes}"
v1_hex        = hmac_sha256(secret, signed_string).hexdigest()
header_value  = f"t={timestamp},v1={v1_hex}"
```

### Verifying

1. Parse `t` and `v1`.
2. Reject if `abs(now - t) > 300` seconds (the **replay window**;
   tunable per-consumer).
3. Re-compute `hmac_sha256(secret, f"{t}.{raw_body}")` and compare in
   constant time.

A reference implementation lives in
`backend/core/webhooks/signing.py` (`sign_payload` / `verify_payload`).

The header format is intentionally **Stripe-compatible** so
existing tooling that parses `t=,v1=` works unchanged.

---

## 3. Standard event types

| Type                       | Source module                                | Notes |
| -------------------------- | -------------------------------------------- | ----- |
| `playbook.started`         | `backend/core/playbooks/runner.py`           | Fired before the first step. |
| `playbook.finished`        | `backend/core/playbooks/runner.py`           | All steps non-failed. |
| `playbook.failed`          | `backend/core/playbooks/runner.py`           | At least one step failed (counted under `steps_failed`). |
| `hil.requested`            | `backend/core/policy/gate.py`                | Confirm gate staged a token. |
| `hil.approved`             | `web_extras/routers/policy.py`               | Operator confirmed. |
| `hil.denied`               | `web_extras/routers/policy.py`               | Operator cancelled. |
| `agent.created`            | `backend/core/agents/store.py`               | Agent persisted. |
| `agent.deleted`            | `backend/core/agents/store.py`               | Agent transitioned to `archived`. |
| `webhook.test`             | `web_extras/routers/webhooks.py` (`/test`)  | Synthetic event from the test endpoint. |
| `receipt.created`          | (planned, owned by the wallet pack)          | Reserved. |
| `receipt.anchored`         | (planned, owned by the anchor batcher)       | Reserved. |

Event filters use **glob patterns**. Examples:

- `playbook.*` — every playbook lifecycle event.
- `hil.requested` — exact match.
- `*` — receive everything.

Empty filter (`[]`) is treated as "subscribe to everything".

---

## 4. Idempotency

Use `id` (top-level event id, unique per dispatch) for dedupe. Note:

- The same logical event re-fired on retry keeps its `id`.
- Two distinct events of the same `type` get distinct `id`s.

External handlers should `INSERT ... ON CONFLICT DO NOTHING` keyed on
this id.

---

## 5. Retry policy

Outgoing deliveries follow exponential backoff:

| Attempt | Delay since previous |
| ------- | -------------------- |
| 1       | immediate            |
| 2       | 30 s                 |
| 3       | 2 min                |
| 4       | 10 min               |
| 5       | 1 hr                 |

After attempt 5 (4 retries) the delivery is marked `failed` and
remains in the store for manual replay via
`POST /api/webhooks/outgoing/{id}/deliveries/{delivery_id}/replay`.

If the upstream returns `Retry-After` (seconds or HTTP-date), the
loop waits at least that long even if the backoff schedule would have
fired earlier.

A successful 2xx response moves the delivery to `success` and stops
retries.

---

## 6. Inbound webhooks

### Creating

```http
POST /api/webhooks/incoming
{
  "name": "github-actions-build",
  "trigger_playbook_id": "pb_release_smoke",
  "allowed_event_schemas": []
}

→ 200
{
  "ok": true,
  "webhook": {
    "id": "ihk_...",
    "name": "github-actions-build",
    "token": "lONGr4ndomURLs4feSTRing",
    ...
  }
}
```

The **token is returned in the create response only**; multi-tenant
deployments should treat that response as the authoritative
copy-to-clipboard moment and hash on disk thereafter. The local
single-tenant cockpit additionally exposes the token on
`GET /api/webhooks/incoming` for operator convenience — set
`TARS_WEBHOOKS_HIDE_TOKENS=1` (or filter at your reverse proxy) when
deploying remotely.

### Calling

```http
POST /api/webhooks/inbox/{token}
Content-Type: application/json
X-Signature: t=1715379600,v1=...        # optional; verified when
                                          # TARS_WEBHOOKS_INBOUND_SECRET is set

{ "any": "json", "you": "want" }
```

Auth = **token in path**. When `TARS_WEBHOOKS_INBOUND_SECRET` is
configured AND the caller sends `X-Signature`, the body is
HMAC-verified using the same scheme as outgoing (replay window
included).

If `trigger_playbook_id` is set on the webhook, the playbook runs in
`confirm` mode with context:

```python
{
  "source": "webhook",
  "webhook_id": "ihk_...",
  "webhook_name": "github-actions-build",
  "input": <parsed JSON body>,
}
```

The response carries `triggered_playbook` + `playbook_result`; if
the playbook errors, the inbox returns HTTP 500 with `playbook_failed:
…` so the caller can retry from its side.

---

## 7. Endpoints (summary)

| Method | Path                                                          | Purpose                                  |
| ------ | ------------------------------------------------------------- | ---------------------------------------- |
| GET    | `/api/webhooks/outgoing`                                      | List outgoing webhooks                   |
| POST   | `/api/webhooks/outgoing`                                      | Create one (returns plaintext secret)    |
| PATCH  | `/api/webhooks/outgoing/{id}`                                 | Update url / name / active / event_filter |
| DELETE | `/api/webhooks/outgoing/{id}`                                 | Soft-delete (`active=False`)             |
| POST   | `/api/webhooks/outgoing/{id}/test`                            | Fire a synthetic test event              |
| GET    | `/api/webhooks/outgoing/{id}/deliveries`                      | Last N delivery rows                     |
| POST   | `/api/webhooks/outgoing/{id}/deliveries/{delivery_id}/replay` | Re-attempt one delivery                  |
| GET    | `/api/webhooks/incoming`                                      | List incoming webhooks                   |
| POST   | `/api/webhooks/incoming`                                      | Create (token returned in response)      |
| DELETE | `/api/webhooks/incoming/{id}`                                 | Revoke (soft-delete)                     |
| POST   | `/api/webhooks/inbox/{token}`                                 | **Public** inbox entry point             |

---

## 8. Versioning

`CONTRACT_VERSION` = **1.0** (see
`backend/core/webhooks/models.py`). The `User-Agent` header is
`TARS-Webhooks/<contract_version>`. Breaking changes will bump the
major version and ship behind a feature flag for at least one minor
release.
