# Launch metrics dashboard — TARS v9.3.0-beta1

> A spec for the post-launch tracker. Reuses the W235 metering substrate; nothing new on the data plane.
> Owner: Alien. Surface: `/admin/launch` (gated by `MEEET_ADMIN_TOKEN`).
> Refresh cadence: 60s push via the W248 event bus.

---

## 1. KPIs (six tiles, in priority order)

### Tile 1 — Downloads per day

- **Source:** Cloudflare Pages access logs for `/download/*.dmg` and `/download/*.tar.gz`. Aggregated daily.
- **Existing instrumentation:** the `dl-proxy` Worker (W144) already emits a `download.served` event with `{platform, version, signed, ts}`. Read-side query lives in `web_extras/routers/admin_metrics.py` (add `GET /api/admin/metrics/downloads`).
- **Display:** stacked area chart, Mac vs Linux-source vs Windows-source. 30-day window.
- **Target for week 1:** 500 mac downloads.

### Tile 2 — DAU / MAU

- **Source:** `~/.tars/usage.sqlite` on each install posts a daily ping `client.heartbeat` to `/api/telemetry/heartbeat` (opt-in, defaults off). Anonymous; hashed install ID.
- **New instrumentation:** wire `client.heartbeat` into the existing W235 ingest pipe — same schema as `usage.tokens`, different `event_type`. One day of work.
- **Display:** DAU as a single number (today), MAU as a single number (rolling 30), DAU/MAU ratio as a sparkline.
- **Privacy:** if the user is in `local` privacy plane (W244), the heartbeat is suppressed. Plane-aware metering is the whole point.

### Tile 3 — TTFR (time to first receipt)

- **Definition:** seconds between first launch (W231 boot record) and the first successful action receipt (any `receipt.emitted` event).
- **Source:** boot timestamps in `~/.tars/onboarding.sqlite` ↔ first receipt in `~/.tars/receipts.sqlite`. Reported back as a single `onboarding.ttfr` event when the user opts in to telemetry.
- **Existing instrumentation:** the receipt ledger (W67, hardened in W95) already emits `receipt.emitted`. Just need the join.
- **Display:** histogram (p50 / p90 / p99) over the last 30 days.
- **Target:** p50 < 90 seconds. p90 < 5 minutes.

### Tile 4 — Consumption events per day

- **Source:** the W235 consumption console. Already in production.
- **Existing instrumentation:** `usage.tokens` and `usage.action` events stream into the meeet.world ingest pipe. Daily aggregate query exists.
- **Display:** line chart, by event type. Stacked breakdown by provider (Anthropic / OpenAI / OpenRouter / Ollama).
- **Target for week 1:** >10k events/day across the active install base.

### Tile 5 — Magic-link signups vs Skip-to-local-only ratio

- **Source:** the auth screen (W219) emits `auth.magic_link_sent` or `auth.skip_local_only` on choice.
- **Existing instrumentation:** these events already flow into the W235 pipe under `event_type=onboarding`.
- **Display:** stacked bar by day, "magic-link" vs "skip". The ratio is the read.
- **Why it matters:** if Skip dominates >70%, the meeet.world value-prop is not landing for early adopters; tune the magic-link CTA copy. If magic-link dominates >70%, brother's billing endpoints are the gating risk and we double the urgency on his side.
- **Target ratio for week 1:** 30/70 magic-link / skip is healthy for beta.

### Tile 6 — NPS via in-app prompt at day 3

- **Source:** on day 3 of usage (≥3 distinct daily heartbeats), the cockpit surfaces a one-question modal: "How likely are you to recommend TARS? (0–10)" + optional one-line comment.
- **New instrumentation:** add `NPSPrompt.tsx` component in `experiments/neural-showcase-v3/src/components/`. POST to `/api/admin/nps`. Persist in `~/.tars/usage.sqlite` so we never ask twice.
- **Display:** rolling-30 NPS score (promoters minus detractors as a %), comments feed below.
- **Target for week 1:** raw response rate >15%. Score >+30 (early-adopter floor).

---

## 2. Instrumentation summary

What already exists (no new code):

- `download.served` (W144, dl-proxy Worker)
- `usage.tokens` and `usage.action` (W235 metering middleware)
- `receipt.emitted` (W67 receipt ledger, W95 anchor)
- `auth.magic_link_sent`, `auth.skip_local_only` (W219 auth gate)
- `boot.completed` (W231 boot-time DB init)

What needs to be wired (1-2 days of work, all additive):

- `client.heartbeat` — anonymous daily ping. New endpoint `POST /api/telemetry/heartbeat`. Plane-aware (suppressed under `local`).
- `onboarding.ttfr` — join query between boot and first receipt, emitted as a single event when first receipt lands.
- `nps.response` — new `/api/admin/nps` POST endpoint + cockpit `NPSPrompt.tsx` component.
- `/api/admin/metrics/*` — read-side endpoints for the six tiles. Gated by `MEEET_ADMIN_TOKEN`.

---

## 3. Dashboard surface

- **Route:** `/admin/launch` in `experiments/neural-showcase-v3/src/pages/AdminLaunch.tsx`.
- **Auth:** existing `MEEET_ADMIN_TOKEN` guard (already in place for the consumption console admin views).
- **Layout:** six tiles in a 3x2 grid on desktop, vertical stack on mobile. Each tile fetches from its `/api/admin/metrics/*` endpoint with 60s SWR.
- **Live updates:** subscribe to the W248 event bus on topic `admin.metrics.tick`; the backend publishes a tick every 60s with summarized counters.

---

## 4. Open questions

- **Heartbeat opt-in default.** Default OFF (consistent with the local-first stance), or default ON for beta-channel users with a clearly visible toggle? I lean toward default-OFF + a one-time prompt on day 3 ("Help us see how TARS is being used — anonymous, plane-aware. Yes/No").
- **NPS sample bias.** Day-3 prompt only fires for users who reach day 3. Will skew positive. Acceptable for beta-channel signal; reconsider for GA.
- **Receipt anchor cadence vs TTFR.** TTFR currently measures first *emitted* receipt, not first *anchored* receipt. If anchoring cadence is hourly, the anchored TTFR is misleading. Keep TTFR = first-emitted; report anchored separately if asked.

---

## 5. Cadence

- **Daily 09:00 PT** — Alien reviews the six tiles for 5 minutes. Anything red triggers a Telegram alert via the W117 synthetic-monitor channel.
- **Weekly Friday** — exported to `marketing/v9.3.0-beta1/weekly_report_{w}.md` automatically by a small cron job.
- **End of beta cycle (~6 weeks)** — full retrospective, fold learnings into the v9.4 plan.
