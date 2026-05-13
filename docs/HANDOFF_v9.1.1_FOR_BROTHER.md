# Handoff for brother (meeet.world side) — v9.1.1

**Period covered:** Waves 151-157 (2026-05-13)
**Companion doc:** `RELEASE_NOTES_v9.1.1.md`
**Posture:** additive over v9.1.0 — no breaking changes

This is the single doc brother needs to wire the v9.1.1 release
into the meeet.world side. It covers ONLY what changed since the
v9.1.0 handoff: two new webhook events to accept + two new HTTP
endpoints to optionally proxy.

## What changed (operator-visible)

| Surface | What | Brother side action |
| --- | --- | --- |
| Webhook: `clone.profile.synced` | Style profile heartbeat from TARS clones | Store summary, expose `/tars/clone/snapshot` for restore |
| Webhook: `doctor.status_changed` | Health drift across 8 subsystems | Surface in status dashboard, optionally fan-out to operator's Telegram/Slack |
| `POST /api/clone/export` | TARS-side endpoint operator can call directly | None — pure local |
| `POST /api/clone/import` | Same — local rehydrate | None — pure local |
| `GET /api/doctor*` | TARS-side HTTP doctor surface | None — pure local |

## Webhook 1 — `clone.profile.synced`

**Fired by:** TARS background daemon (or web app) every Nth
recorded message (default 50, env-tunable). Best-effort,
fire-and-forget — TARS never blocks on the response.

**Payload:**
```json
{
  "event_type": "clone.profile.synced",
  "data": {
    "schema_version": 1,
    "contract_version": "0.2.0",
    "exported_at": 1747252800.0,
    "sample_count": 124,
    "profile": {
      "version": "0.1",
      "sample_count": 124,
      "avg_sentence_length": 14.3,
      "casual_vs_formal": "casual",
      "top_vocab": ["deal", "sync", "ship", "…"]
    },
    "trait_count": 124
  }
}
```

**Note:** `profile` is the small summary; the **full envelope**
with `traits[]` is NOT in the webhook. Operator's TARS exposes
the full envelope via `POST /api/clone/export` — if you need it
for cloud-backed restore, call that endpoint from your edge
function on receipt of the webhook (Pro tier + explicit consent
flag).

**Suggested storage shape (your side):**
```sql
CREATE TABLE clone_snapshots (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    machine_id TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    schema_version INT NOT NULL,
    contract_version TEXT NOT NULL,
    sample_count INT,
    profile_summary JSONB,
    full_envelope JSONB  -- nullable; populate only with explicit consent
);
```

**Restore endpoint to expose:**
```
GET /tars/clone/snapshot?tenant_id=…&machine_id=…
→ 200 { envelope: <envelope> } | 404 { error: "no_snapshot" }
```

The TARS-side `tars-ops Restore from cloud` action will call this
endpoint and then POST the result to its local
`/api/clone/import`.

## Webhook 2 — `doctor.status_changed`

**Fired by:** TARS background daemon every Nth tick when any
subsystem health check transitions status (e.g. `ok → warn`).
Opt-in via `TARS_DAEMON_DOCTOR_ENABLED=1` on the operator's side.

**Payload:**
```json
{
  "event_type": "doctor.status_changed",
  "data": {
    "changes": [
      {"slug": "daemon", "from": "ok", "to": "warn", "summary": "heartbeat older than 90s"},
      {"slug": "mcp", "from": "ok", "to": "fail", "summary": "registry failed: <err>"}
    ],
    "summary": {"ok": 4, "warn": 2, "fail": 1, "skip": 1},
    "results": [
      {"slug": "daemon", "label": "Background daemon", "status": "warn", "summary": "…", "elapsed_ms": 5.0, …}
    ],
    "fired_at": 1747252830.0
  }
}
```

**Suggested integration on your side:**

1. **Status dashboard panel** — show the per-tenant rolling
   health timeline. Each event becomes a row; the `summary`
   counters drive a sparkline.
2. **Fan-out to operator's Telegram/Slack** — if the operator
   has a Telegram bot wired (we already accept their bot token
   under `/connectors/telegram`), post a one-line alert on every
   `fail` transition. Throttle to once per (tenant, slug) per
   hour to avoid spam.
3. **Auto-create incident** — on the first `fail` of a
   subsystem, create an incident row in the existing incident
   table (Wave 117 monitor already populates this for prod
   route outages; this extends it to local-subsystem health).

## Endpoints brother may proxy

These all live on the operator's local TARS host. Brother
generally doesn't need to proxy them — but if you want to mirror
them under `tars.meeet.world/<tenant>/...` for the cockpit
embed, the shapes are:

| Operator-side | Proposed proxy | Auth |
| --- | --- | --- |
| `GET /api/doctor` | `GET /tars/<tenant>/doctor` | tenant token |
| `GET /api/doctor/{slug}` | `GET /tars/<tenant>/doctor/{slug}` | tenant token |
| `POST /api/clone/export` | `POST /tars/<tenant>/clone/export` | tenant token + Pro tier |
| `POST /api/clone/import` | `POST /tars/<tenant>/clone/import` | tenant token + Pro tier + signed envelope |

If you proxy, the local-TARS-side response shapes are identical
to what your edge function returns — no transformation needed.

## Apple cert situation

**Unchanged from v9.1.0 handoff.** Still waiting on operator's
Developer ID Application cert export. The v9.1.1 release is
backend-only so the unsigned-dmg posture from v9.1.0 carries
over: notarised `.dmg` ships when the cert lands.

## Testing

Smoke-test the new webhook events on your side with curl:

```bash
# Synthetic clone.profile.synced
curl -X POST $YOUR_WEBHOOK_URL \
  -H 'content-type: application/json' \
  -H "x-tars-signature: $(compute_hmac)" \
  -d '{"event_type":"clone.profile.synced","data":{"schema_version":1,"contract_version":"0.2.0","exported_at":1747252800.0,"sample_count":42,"profile":{"version":"0.1"},"trait_count":42}}'

# Synthetic doctor.status_changed
curl -X POST $YOUR_WEBHOOK_URL \
  -H 'content-type: application/json' \
  -H "x-tars-signature: $(compute_hmac)" \
  -d '{"event_type":"doctor.status_changed","data":{"changes":[{"slug":"daemon","from":"ok","to":"warn","summary":"test"}],"summary":{"ok":7,"warn":1,"fail":0,"skip":0},"results":[],"fired_at":1747252830.0}}'
```

HMAC signing follows the same scheme as v9.1.0 webhooks (W90):
`HMAC-SHA256(BRIDGE_SHARED_SECRET, body)`.

## Reality-audit drift status

Two historical "marked-done but missing" gaps closed in v9.1.1:

| Drift | Status | Closed by |
| --- | --- | --- |
| MCP server bridge (tasks #17 + #85) | ✅ Closed in Wave 150 | `backend/core/mcp/` |
| Background TARS daemon (task #65) | ✅ Closed in Waves 152 + 153 | `backend/core/daemon/` |

Still pending from W148 audit (not in v9.1.1):

| Drift | Target |
| --- | --- |
| iMessage bridge (task #66) | v9.1.2 — Wave 163-167 |
| Windows daemon | v9.2 — Wave 158-162 |
| AI Clone v1 (real fine-tune) | v9.2 |

## Contact

If anything in the webhook shapes or restore endpoint needs
changes, push back via GitHub issue against this repo and tag
`@brother-side`. TARS-side endpoints are the source of truth —
brother adapts to them, not the other way around.
