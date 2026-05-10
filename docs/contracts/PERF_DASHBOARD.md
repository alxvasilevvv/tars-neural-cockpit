# Performance dashboard contract (Wave 108)

Operator-facing health dashboard at `/admin/perf`. Aggregates
latency, connector health, webhook delivery counters, receipt-chain
integrity, background-job state and (best-effort) host resource
usage into a single read-only view.

The page is single-tenant for now -- every operator sees it. When
multi-tenant gating lands, the FE reads a role flag and hides the
nav link / Cmd+K entry; the `/api/perf/*` endpoints stay loopback-
only.

## Endpoints

| Method | Path                                   | Returns |
|--------|----------------------------------------|---------|
| GET    | `/api/perf/summary?window=24h`         | One-shot snapshot (everything below). |
| GET    | `/api/perf/latency?op=<op>&window=24h` | Stats + bucketed histogram for a single op. |
| GET    | `/api/perf/health/connectors`          | Connector status table. |
| GET    | `/api/perf/jobs`                       | Scheduler / reflection / autopilot. |

`window` accepts `Nh` / `Nm` / `Ns` / raw seconds. Default `24h`.

## What each metric means

### Latency cards

Four cards, each pulling from the in-process recorder
`backend.core.observability.latency`:

* **Council LLM** -- per-message duration of council deliberation
  calls (`record("council", ms)` at the LLM call site).
* **Backtest** -- algotrade backtest run wall time (per request).
* **Webhook delivery** -- end-to-end POST round-trip time.
* **Connector call** -- per-API-call duration for any connector
  (Slack/Gmail/Calendar/GitHub/Telegram).

Stats: P50 / P95 / P99 / Max (linear-interpolation percentiles over
the rolling window). Buffer is capped at 2048 samples per op so
memory stays bounded even under churn.

### Connector health

Lists all four registered connectors with the cached `configured /
connected` flags. The "Test all" button fires `health_check` on each
in parallel via `/api/connectors/{name}/health`. Real network calls
do not happen inside `/api/perf/summary` -- it returns the cached
status only, so the dashboard never blocks on a slow upstream.

### Webhook delivery stats

Counters for the requested window (default 24h):

* **Total** -- deliveries created (`created_at >= cutoff`).
* **Success** -- 2xx response.
* **Retrying** -- still in the retry budget.
* **Failed** -- exhausted retries; manual replay required.

The failed-deliveries table lists the last 25 failed rows with the
last error string. The "replay" button POSTs to
`/api/webhooks/deliveries/{id}/replay`. `avg_signature_ms` is the
mean HMAC compute time -- a sustained jump signals body-size issues.

### Receipt chain integrity

* **Today's count** -- number of receipts appended today (UTC).
* **Chain valid?** -- runs `verify_chain` over today's NDJSON. Any
  signature / ordering issue flips the badge to "chain broken".
* **Merkle root** -- daily root, computed lazily on first read.
* **Anchored to Solana** -- whether the day's root has a
  non-empty `solana_signature`.

### Background jobs

Scheduler state pulled from `SchedulerStore`:

* **Schedule count / enabled count** -- total + active schedules.
* **Next run in** -- countdown to the next due schedule (or "due"
  when overdue).
* **Tick interval** -- runner cadence (`TARS_SCHEDULER_TICK_S`,
  default 30s).

Reflection + autopilot panels surface their `*_ENABLED` /
`*_INTERVAL_S` env state. Disabled by default -- empty cards are
expected on a fresh install.

### Resource usage

Best-effort via `psutil`. When `psutil` is missing the panel shows
a static notice ("psutil not installed -- pip install psutil").
Reports CPU%, memory used / total / percent, and disk usage for
`~/.tars` (the per-user state directory).

## Operating notes

* All endpoints are read-only and side-effect-free.
* Missing modules degrade gracefully -- the FE never collapses on a
  disabled subsystem; instead each card explains the reason.
* The dashboard polls `/api/perf/summary` every 30s. The "Test all
  connectors" button bypasses the cache by hitting the live
  `/api/connectors/{name}/health` endpoints in parallel and then
  re-fetching the summary.
* No customer data leaves the host -- all aggregation is in-process.
