# v10.0.0 brother handoff — TARS ↔ meeet.world coord brief

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-m
**Authoring date:** 2026-05-18
**From:** TARS lane (Cursor + Claude orchestration)
**To:** meeet.world brother (backend on Lovable + Supabase Edge Functions)
**Target release:** `v10.0.0` GA (drop `-rc.1` suffix; current tag-cut block per `docs/PRODUCT_MASTER_PLAN.md` Phase 11)
**Supersedes:** Auth scope only of `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` and `docs/HANDOFF_AUTH_FOR_BROTHER_W284.md` — billing and clone-sync contracts there remain authoritative; this brief adds the **delta** for v10 GA dock-down.
**Phase ID:** `ph11-brother-handoff` (companion to `ph11-qa-sweep`, PR #197)

---

## 1. Why this brief exists

`docs/V10_GA_CHECKLIST.md` lists 8 hard GA blockers (per
`docs/handoff/PH11_QA_SWEEP_BRIEF.md` §3 reconciliation). **3 of
those 8 are brother-side** — A1, A2, A5 from category A. The other
5 are operator-side Apple signing (B1-B5).

The brother side already shipped:

- ✅ v9.1.0 launch readiness (Wave 78 → 119) via `docs/BROTHER_HANDOFF_v9.1.0.md`
- ✅ v9.2.0-beta2 auth surface (W219, W220, W233) via `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` — magic-link + OAuth, 4 endpoints
- ✅ Billing edge function `tars-billing` on Supabase project `zujrmifaabkletgnpoyw` (per `docs/contracts/TARS_MEEET_BILLING.md` §1, deployed 2026-05-05)

What v10.0.0 GA needs from brother is a **convergence check** on the
items below — not net-new shipping, but a **status reconciliation**
so we can either flip the 3 hard-blocker checklist items to `[x]`
or unblock them with a known scope.

This is **not** a "ship these 4 new endpoints" brief like v9.2.0-beta2.
It's a "confirm what's live, fix what's drifted, document what's
deferred" brief.

---

## 2. The 3 hard brother-side blockers

### A1 — `POST /api/billing/usage_event`

**v10 GA expectation (per `V10_GA_CHECKLIST.md`):** "live, HMAC-signed `UsageEvent` ingest."

**Current state in TARS canon (per `docs/contracts/TARS_MEEET_BILLING.md` §1):**

The contract surface is **`POST {MEEET_BILLING_BASE_URL}/operator/usage`** on the Supabase edge function `tars-billing` (project `zujrmifaabkletgnpoyw`). TARS calls this when `TARS_BILLING_SOURCE=remote` and `usage.tokens` events have `route ∈ {cloud, fallback, mixed}` with positive `cost_usd`. Idempotency is enforced via the `tars_billing_usage_dedupe` table.

**Required confirmation from brother:**

1. Confirm the endpoint **path** matches the checklist's spelling. Two paths in flight:
   - `POST /api/billing/usage_event` (V10_GA_CHECKLIST §A1 wording)
   - `POST /operator/usage` (canonical TARS contract per §1 of `TARS_MEEET_BILLING.md`)
   
   These are likely the same endpoint with different aliases — confirm whether `/api/billing/usage_event` is a reverse-proxy alias of `/operator/usage`, or a separate route. **If they're the same, update `V10_GA_CHECKLIST.md` §A1 to use the canonical path** (handled via a TARS-side PR after brother confirms).

2. Confirm HMAC signing — TARS currently sends `Authorization: Bearer <MEEET_BILLING_API_KEY>` (per `TARS_MEEET_BILLING.md`). The checklist says "HMAC-signed `UsageEvent` ingest." Either:
   - HMAC was an intended future-state and Bearer is the v10 GA shape → update checklist wording, OR
   - HMAC is required for GA → brother ships an HMAC sig path AND TARS rolls a small client patch (~1 h work).
   
   **TARS expects Bearer to be sufficient for GA** — please confirm.

3. Confirm idempotency table reset cadence — `tars_billing_usage_dedupe` should retain dedupe records for at least 24 h (TARS retry windows are 24 h max). Brother to confirm GC policy doesn't evict mid-window.

**Smoke probe (brother-runnable):**

```bash
bash scripts/probe-meeet-billing.command
# expects: POST /operator/usage returns 200 with body {"ok":true, "stored":true}
# expects: a second POST with the same trace_id returns 200 with {"ok":true, "stored":false, "deduped":true}
```

**Test on TARS side:** `tests/test_meeet_billing_remote_usage.py` already covers the happy path against `meeet_mock`. Brother to run their version against live `tars-billing` and confirm parity.

---

### A2 — `GET /api/billing/balance`

**v10 GA expectation:** "returns live balance for any logged-in user."

**Current state in TARS canon:** The canonical endpoint is **`GET {MEEET_BILLING_BASE_URL}/operator`** (per `TARS_MEEET_BILLING.md` §1), which returns:

```json
{
  "ok": true,
  "contract_version": "1.0.0",
  "tier": "free" | "pro" | "business",
  "byo_enabled": false,
  "live": { "spent_usd_24h": ..., "cap_usd_daily": ..., "remaining_usd": ..., "allowed_cloud": ... },
  "checkout": { "pro": "...", "business": "..." },
  "account_url": "..."
}
```

`live.remaining_usd` IS the balance for v10's purposes — TARS uses it for the cockpit balance pill (`apps/cockpit/...` integration in W219).

**Required confirmation from brother:**

1. Confirm `GET /operator` is live at the Supabase function URL with HTTP 200 and the JSON shape above.
2. Confirm `Authorization: Bearer <MEEET_BILLING_API_KEY>` succeeds.
3. Confirm `live.remaining_usd` reflects the **same value** as the user-facing balance on `https://meeet.world/account` (the latter is the source of truth; the former mirrors it).

**Naming reconciliation (same as A1):** the checklist says `/api/billing/balance` but the contract canonical is `GET /operator`. Brother to confirm if `/api/billing/balance` is a separate routes or an alias.

**Smoke probe (TARS-runnable):**

```bash
bash scripts/CHECK-MEEET-LIVE.command
# pings GET /operator and asserts {ok:true, contract_version, tier, live, checkout}
```

---

### A5 — Auth endpoints (4 routes)

**v10 GA expectation:** "magic-link start/redeem + OAuth start + `/api/me` (4 routes)."

**Current state:** All 4 endpoints were specified in `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` §A (W233, 2026-05-15). Brother shipped at the time. **GA needs a re-verification pass — nothing new.**

**The 4 routes (verbatim from v9.2.0-beta2 handoff):**

| Route | Method | TARS-side caller |
| ----- | ------ | ---------------- |
| `/api/magic-link/start` | POST | `web_extras/routers/auth_meeet.py::magic_link_start` |
| `/api/magic-link/redeem` | POST (called by `https://meeet.world/auth/magic` page) | redirects to `tars://auth` deep-link |
| `/api/oauth/{provider}/start` | GET | `web_extras/routers/auth_meeet.py::oauth_start` |
| `/api/me` | GET | called by `/api/auth/meeet/exchange` to enrich the session |

**Required confirmation from brother:**

1. Run brother's version of `scripts/smoke_auth_meeet_e2e.sh` (if it exists; if not, brother ships it as a 30-line script — same probes as TARS-side `tests/test_auth_meeet_*.py`).
2. Confirm all 4 routes return their documented shapes against live `api.meeet.world`.
3. Confirm `tars://auth` redirect from `https://meeet.world/auth/magic?code=...` still works post-W219 frontend changes.

---

## 3. Soft / deferred coord items (not GA-blocking)

### A3 — `POST /api/billing/topup`

**v10 GA expectation:** "works for both $MEEET (Solana) and card."

**Reality check:** Top-up flows through `https://meeet.world/billing/tars?plan=...`
(per `TARS_MEEET_BILLING.md` §1 `checkout` field). TARS doesn't call a
top-up endpoint directly — it opens the checkout URL. So A3 isn't a
TARS-facing endpoint at all; it's a brother-side UX flow on the
billing page itself.

**Required confirmation:** brother confirms the SOL + card flows on
`/billing/tars` are live. **TARS doesn't gate GA on A3** because the
cockpit just opens the URL — the user completes purchase in the
browser.

→ Move A3 from "hard blocker" to "brother-side smoke item" in
`V10_GA_CHECKLIST.md`. TARS-side PR to update wording once brother
confirms.

### A4 — Daily reconciliation handshake

**v10 GA expectation:** "`scripts/reconcile-meeet-billing.py` < $0.50 drift."

**Reality check:** `scripts/reconcile-meeet-billing.py` doesn't exist
on `main` yet. The closest TARS-side artifact is `scripts/audit_billing.py`
+ `scripts/audit_meeet_e2e.py`. Brother may have an equivalent.

**Required confirmation:** brother either
- confirms the reconciliation script lives on the meeet-side repo with
  the same < $0.50 threshold, and TARS just needs a pointer in the
  checklist, OR
- ships the reconciliation script (small — ~150 LoC, hits `GET /operator/usage` for the day, compares to `meeet_events.jsonl`).

**TARS-side action if brother defers:** Cursor agent will ship
`scripts/reconcile-meeet-billing.py` as a separate small PR
(~3 h work) using the existing `audit_billing.py` as scaffolding.

### `ph3-pair-ttl` — pair_id TTL on `meeet.world` relay

**From master plan Phase 3 (v10.2 slot, NOT v10 GA):** "pair_id TTL
on meeet.world relay (brother coord)."

**Current state:** L5 pairing surface on TARS side is fully shipped
(REAL_CRYPTO_SHIPPED per W310-a). The `meeet.world` relay is the
encrypted forwarder for `kind ∈ {pair.*, recovery.*}` events — it
doesn't decrypt, just routes by `pair_id`.

**Brother-side TODO for v10.2 (NOT v10 GA — heads-up only):**

The relay should evict `pair_id` rows after a TTL (suggested: 7 days
since last activity). Currently the relay holds them indefinitely
per L5_PAIRING_DRAFT.md §6 (TODO).

**Suggested protocol:**
- Table `meeet_relay_pair_ttl(pair_id PRIMARY KEY, last_seen TIMESTAMP, expires_at TIMESTAMP)`
- GC cron evicts rows where `expires_at < NOW()`
- TARS bumps `last_seen` on every relayed event
- TTL slides forward 7 days on each bump

**Coord ask:** brother confirms ownership of `ph3-pair-ttl` and adds
it to their v10.2 backlog. No v10 GA dependency.

### D-category (on-prem deployment)

**Not GA-blocking** per `docs/PRODUCT_MASTER_PLAN.md §2.1`. On-prem
slips to v10.0.x. Brother coord: when a real on-prem customer materialises
(D3 trigger), brother + TARS coordinate the SAML / OIDC IdP integration
(D4). Until then, no action.

---

## 4. What's already done on TARS side that brother doesn't need to redo

| Item | Status | Evidence |
| ---- | ------ | -------- |
| L5 host crypto (X25519, XChaCha20-Poly1305, BIP-39 recovery seed) | shipped real (W310-a) | `backend/core/crypto/envelope.py`, `tests/test_crypto_envelope.py` |
| L5 pairing endpoints (10 routes) | shipped (rc.1) | `web_extras/routers/pairing.py` |
| L5 audit + identity rotation | shipped (rc.1) | `tests/test_pairing_audit.py`, `tests/test_pairing_rotate_identity.py` |
| meeet contract 1.1.0 (envelope additive) | shipped | `tests/test_meeet_contract_v11.py` |
| meeet bridge (trace context, event emitter, replay CLI) | shipped | `backend/core/meeet/` (10 modules) |
| Cockpit shell + W309 step 1 voice mode | shipped (PR #187 pending merge) | `apps/cockpit/`, `tests/cockpit/` |
| Voice fallback hardening L4.2 | shipped (PR #191 pending merge) | `backend/core/voice/persona.py`, `tests/test_voice_*.py` |
| Install funnel v10 cross-target | shipped (PR #190 pending merge) | `experiments/neural-showcase-v3/functions/api/product/` |

**TL;DR:** brother doesn't need to re-implement any of L5, L4.2,
or W309. The desktop shell is GA-ready post-#187 merge.

---

## 5. Coord test handoff

### TARS-side scripts brother can re-run

| Script | What it does | Brother runs to verify |
| ------ | ------------ | ---------------------- |
| `scripts/CHECK-MEEET-LIVE.command` | Pings live `tars-billing` and asserts the contract shape | A2 verification |
| `scripts/probe-meeet-billing.command` | Posts an idempotent usage event and verifies dedupe | A1 verification |
| `scripts/smoke_billing_tars_backend.sh` | End-to-end: TARS local backend → `tars-billing` edge → balance reflects | A1 + A2 combined |
| `scripts/MEEET-MOCK.command` | Spins up `meeet_mock` for local-only dev (no live calls) | Reproduce TARS test env without touching prod |
| `scripts/acceptance_tars_meeet.sh` | Cross-stack acceptance (auth + billing + ingest) | Pre-GA full sanity |

All of these live on `main` today. Brother runs them against `api.meeet.world` /
the Supabase function URL and reports any non-2xx or shape drift in a
GitHub issue (template per `docs/DISASTER_RECOVERY.md` §2.2).

### Brother-side artifacts TARS expects to see by GA

1. **Brother's mirror of the smoke probes** — anything from §5 above that brother runs in their CI on each meeet.world deploy.
2. **Reconciliation script** (A4) — either pointed at by URL or shipped TARS-side per §3.
3. **GA sign-off comment** in the v10 GA tag PR (TBD — opens when §3 reconciliation + soak both pass).

---

## 6. meeet contract version bump path

**Current:** `MEEET_CONTRACT_VERSION=1.0.0` (default in `backend/core/meeet/config.py`)
**Additive shipped:** `1.1.0` (envelope `ciphertext` + `envelope` fields for L5 — optional, additive)
**v10 GA target:** `1.0.0` stays default; `1.1.0` is opt-in for L5-paired traffic.

**Future bumps (no brother action for v10 GA, heads-up only):**

| Version | Trigger | TARS PR |
| ------- | ------- | ------- |
| 1.2.0 | Phase 2 voice streaming (`ph2-stt` lands) — additive `stream_segment` event kind | TBD |
| 1.3.0 | Phase 3 cross-platform keyring (`ph3-keyring`) — additive `vault.platform` field on identity events | TBD |
| 2.0.0 | Major rewire on Phase 7 planner (`ph7-planner` v11) — breaking event kinds | v11 |

Brother to confirm meeet.world ingest tolerates additive minor bumps
(should — current contract is forward-compatible per W203 design).
**No v10 GA action required.**

---

## 7. Pre-GA brother sync — concrete asks

Brother does these **once**, in any order, before v10 GA tag cut:

- [ ] **Sync 1.** Confirm A1 endpoint path + auth scheme (§2.A1 items 1-3)
- [ ] **Sync 2.** Confirm A2 endpoint path + balance value parity (§2.A2 items 1-3)
- [ ] **Sync 3.** Re-run A5 auth e2e smoke and post status in `#tars-coord` (§2.A5 item 1-3)
- [ ] **Sync 4.** Confirm A3 (top-up via checkout URL) lives at `/billing/tars` — checklist wording update follows (§3.A3)
- [ ] **Sync 5.** Confirm A4 reconciliation: either brother ships the script or TARS does (§3.A4)
- [ ] **Sync 6.** Acknowledge `ph3-pair-ttl` ownership for v10.2 (§3.ph3-pair-ttl)
- [ ] **Sync 7.** Run `scripts/acceptance_tars_meeet.sh` against live and post result

Each sync is < 1 h of brother time. **No new endpoints shipped for v10 GA** — this is convergence work.

---

## 8. Post-GA coordination cadence

After v10.0.0 tags:

- **Daily reconciliation** runs from cron on TARS host, posts to `#tars-coord` if drift > $0.50 (per A4)
- **Weekly sync** on Friday: brother + TARS lane review previous week's `meeet_events.jsonl` vs meeet.world ingest counts
- **Sev escalation** per `docs/DISASTER_RECOVERY.md` §1 ladder — Sev 1 = both down = 15 min response window
- **v10.0.x patch slot** (per `PRODUCT_MASTER_PLAN.md`) absorbs anything that drifts post-GA (typically VS Code marketplace, on-prem, additional Linux distros)

### 8.A First-week brother-side runbook (T+0 → D+7)

(Added W310-aq cross-stack: TARS-side runbook lives at
`docs/W310_WAVE_SUMMARY.md §"Operator post-GA first-week runbook"`;
this subsection is its brother-side mirror so both sides have matched
mental models and can escalate to each other on a shared signal
taxonomy.)

#### Cadence checkpoints

| Time | Brother-side check | Threshold for escalation |
|---|---|---|
| **T+0** (tag cut moment) | Confirm `tars.installer.tagged` event arrives in meeet.world ingest with version `10.0.0` | If no event in 5 min → escalate (TARS-side meeet bridge not firing) |
| **T+0 to T+72 h** | Watch ingest dashboard for: (a) auth endpoint p95 (A5), (b) usage_event 5xx rate (A1), (c) balance endpoint p95 (A2) | Any of: p95 >2x baseline for >15 min / 5xx rate >5% / event throughput drop >50% vs baseline → escalate |
| **T+24 h** | Run brother-side reconciliation against TARS daily reconcile output; confirm drift <$0.50 per Sync 5 contract | Drift ≥$0.50 → escalate (root-cause within 4 h or flip to v10.0.1) |
| **T+72 h** | Same as T+24 h; confirm 3 consecutive daily reconciles within tolerance | Two consecutive drifts ≥$0.50 → escalate (rollback consideration) |
| **D+1 → D+7 (weekday)** | Daily 5-min ingest dashboard glance; weekly Friday review per existing cadence | Any sustained anomaly → file `#tars-coord` ticket within 1 h |

#### Brother-side signal taxonomy → TARS escalation

| Brother-observed signal | Source | Class | Escalation path |
|---|---|---|---|
| **`tars.installer.tagged` missing T+5 min** | meeet.world ingest dashboard | CRITICAL | Page TARS operator immediately — meeet bridge broken on v10.0.0 binary, possible Apple sign chain regression |
| **A1 `/usage_event` 5xx >5% for >15 min** | brother backend logs + ingest dashboard | CRITICAL | Page TARS operator — likely TARS-side billing client bug; brother pauses ingest if 5xx blocks queue |
| **A2 `/balance` p95 >2x baseline for >15 min** | brother backend perf monitoring | CRITICAL | Page TARS operator — usually TARS-side polling regression; brother rate-limits if approaching capacity |
| **A5 auth endpoint p95 spike** | brother backend perf monitoring | CRITICAL | Page TARS operator — likely TARS-side token refresh regression |
| **Daily reconcile drift ≥$0.50** | TARS-side cron post to `#tars-coord` | CRITICAL | Both sides debug within 4 h; rollback decision at T+24 h if not root-caused |
| **Event ingest throughput drop >50%** | meeet.world ingest dashboard | CRITICAL | Page TARS operator — likely TARS-side meeet bridge crash, OR widespread updater issue blocking event submission |
| **Single 5xx on any endpoint (no pattern)** | brother backend logs | NOISE | Triage to next sync; no action |
| **Slow user growth / low adoption** | brother sales analytics | LOW | Not a v10.0.0 GA escalation; routes to PH10 design polish backlog or v10.1 voice features instead |
| **Feature request "I wish TARS could X"** | brother user-facing support inbox | LOW | Forward to TARS via existing IDEAS.md queue; not GA escalation |

**Iron rule (brother-side parallel of TARS-side W310-aq rule):** any
CRITICAL signal triggers a `#tars-coord` page within 1 h of detection;
brother does NOT improvise mitigation on the TARS-side service (auth,
billing, ingest) without coordination, because TARS-side rollback paths
may already be in flight.

#### Bidirectional escalation tree (who-decides-what)

```text
CRITICAL signal detected (either side)
│
├── Where is the root cause?
│   ├── TARS-side (binary / meeet bridge / installer)
│   │   → TARS operator owns decision tree per W310-aq:
│   │     - hotfix v10.0.1 (TARS rebuilds, brother stays)
│   │     - forward-fix v10.0.1 (TARS rebuilds, brother stays)
│   │     - full rollback to v9.1.0 (TARS rebuilds + brother
│   │       coordinates feature flag banner via meeet.world endpoint
│   │       `/api/feature_flags/tars/rollback_banner`)
│   │
│   ├── Brother-side (auth / billing / ingest service)
│   │   → Brother operator owns decision tree:
│   │     - hot-patch brother service in place (TARS continues
│   │       running v10.0.0; users see brief brother-side downtime)
│   │     - feature-flag the affected endpoint to graceful-degrade
│   │       mode (TARS-side: balance shows stale, billing queues
│   │       events, auth uses cached tokens)
│   │     - if degradation insufficient AND brother fix >4 h →
│   │       page TARS operator to consider new-user funnel pause
│   │       via meeet.world feature flag (NO TARS rollback)
│   │
│   └── Both / unclear (need triage)
│       → 15-min joint debug session per DISASTER_RECOVERY.md §1
│         Sev 1 ladder; if root cause unclear after 30 min,
│         default to NEW-USER FUNNEL PAUSE (lowest-impact
│         containment) and continue triage to root cause
│
└── What's the user-facing comms split?
    ├── TARS-side rollback → TARS-side cockpit banner (via meeet.world
    │   feature flag — brother owns the flag flip but TARS owns the
    │   banner content; coordination via `#tars-coord` within 15 min)
    ├── Brother-side service degradation → brother-side status page
    │   update (brother owns; TARS posts URL to `#tars-coord`)
    └── Joint outage → joint status post on meeet.world status page +
        cross-link from TARS cockpit + brother dashboard
```

#### Brother-side feature flag endpoints brother owns (for TARS-side escalations)

These are NOT new for v10.0.0 — they exist on `meeet.world` already.
Listed here so TARS operator knows what to ask brother to flip when
the W310-aq rollback decision tree calls for it:

| Flag | What TARS sees when ON | Owner | Used in rollback class |
|---|---|---|---|
| `tars/rollback_banner` | Cockpit shows "TARS is rolling back to v9.1.0 due to <reason>" banner; users get v9.1.0 on next updater check | Brother | Full rollback to v9.1.0 |
| `tars/new_user_pause` | Onboarding page shows "Sign-ups temporarily paused; existing users unaffected" | Brother | Brother-side coord issue (no TARS rollback) |
| `tars/hotfix_v10_0_1_banner` | Cockpit shows "TARS v10.0.1 hotfix available; please restart" banner; updater serves v10.0.1 | Brother | Hotfix v10.0.1 (Apple sign or forward-fix) |
| `tars/degraded_mode_<endpoint>` | Specific affected endpoint shows degraded UI (e.g. `degraded_mode_billing` → "Billing is in read-only mode; usage tracking continues") | Brother | Brother-side service degradation |

Brother flips these via `gh api -X POST /repos/.../meeet-platform/
dispatches -f event_type=tars_<flag_name> -f client_payload='...'`
exactly as documented in the TARS-side W310-aq rollback playbook
Step 1. The dispatch is idempotent; brother can flip ON and OFF
multiple times during incident response.

#### Brother-side post-mortem cadence

If any rollback or hotfix happens in the first week, **both sides** open
parallel post-mortem docs within 24 h:

- **TARS-side**: `docs/handoff/POSTMORTEM_v10.0.0_rollback_YYYYMMDD.md`
  (template in W310-aq §"Rollback to v9.1.0 — exact bash playbook" Step 6)
- **Brother-side**: equivalent in brother repo with the same fields PLUS
  brother-specific: brother-service-version-at-incident-time, brother-
  side response timeline, brother-side mitigation applied, post-mortem
  joint review scheduled within 7 days

The joint review must establish: (1) was the right escalation path
taken? (2) did the W310-aq signal taxonomy classify the signal
correctly? (3) does the runbook need amendment? Amendment, if any,
goes to PR #192 (W310_WAVE_SUMMARY.md) as a docs-only follow-up
within 14 days of incident close.

---

## 9. Acceptance criteria for Phase 11 brother handoff done

- [ ] All 7 syncs in §7 completed and confirmed in `#tars-coord`
- [ ] V10_GA_CHECKLIST.md A1-A5 items flipped to `[x]` (TARS-side PR after brother confirms)
- [ ] A3 + A4 wording updated to reflect reality (top-up = checkout URL; reconciliation = either brother script or TARS-shipped)
- [ ] `ph3-pair-ttl` added to brother's v10.2 backlog with explicit owner
- [ ] meeet contract version bump path acknowledged (no v10 GA work, just FYI)
- [ ] Brother runs `scripts/acceptance_tars_meeet.sh` against live; posts pass/fail

---

## 10. Open questions for operator / brother

| # | Question | Default |
| - | -------- | ------- |
| Q1 | Should we cut a brother-specific GitHub issue per sync, or batch in one tracker? | Single tracker issue with 7 checkboxes; less ceremony |
| Q2 | If A1 needs HMAC and TARS sends Bearer, do we ship the HMAC client patch on v10 GA or defer to v10.0.1? | v10 GA — small patch, ~1 h, worth the alignment |
| Q3 | Reconciliation script (§3.A4) — brother or TARS? | TARS ships it during the §5.A scripts PR from `ph11-qa-sweep` brief — same release-eng PR, ~3 h add |
| Q4 | Do we need an updated `INTEGRATION_FOR_BROTHER.md` doc for v10, or does this brief subsume it? | This brief subsumes for v10 GA scope; full integration doc gets a v10.1 refresh |

---

## 11. Estimated effort

- Brother: ~5-7 h total across the 7 syncs (mostly verification, not coding)
- TARS-side wording-update PR: ~1 h after brother confirms
- TARS-side HMAC client patch (Q2, if needed): ~1 h
- TARS-side reconciliation script (Q3): ~3 h, folds into `ph11-qa-sweep` §5.A PR
- Brother-side: confirm 4 feature flag endpoints in §8.A are live + dashboard panels for the 6 critical-class signals exist + paging integration for `#tars-coord` works (W310-aq cross-stack): ~2-3 h

**Total cross-stack effort: ~12-15 h.**

This is the **smallest net-new-code** ph11 deliverable because nearly
everything is already shipped — the work is convergence + sign-off +
shared runbook validation, not net-new code. The §8.A runbook is the
only "new thinking" required; the feature flag endpoints, dashboard
panels, and paging integration are already operational on the brother
side from earlier TARS releases.

---

## 12. Pointers / references

### Existing TARS-side canon

- Contract canon: `docs/contracts/TARS_MEEET_BILLING.md` (billing endpoints) — **authoritative for naming**
- Auth handoff: `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` (4 auth endpoints — A5 source)
- v9.1 brother handoff: `docs/BROTHER_HANDOFF_v9.1.0.md` (template + earlier surface)
- meeet bridge code: `backend/core/meeet/` (client, config, events, store, replay, tracing, trace_summary)
- meeet billing mirror code: `backend/core/meeet_billing/mirror_usage.py`
- L5 pairing contract: `docs/contracts/L5_PAIRING_DRAFT.md`
- v10 GA checklist: `docs/V10_GA_CHECKLIST.md` (29-item, A-G categories)
- v10 launch playbook: `docs/LAUNCH_PLAYBOOK_v10_GA.md` (T-7 → T+30 sequencing)
- Disaster recovery: `docs/DISASTER_RECOVERY.md` (post-GA Sev ladder)

### Companion W310 briefs

- `docs/handoff/PH11_QA_SWEEP_BRIEF.md` (PR #197) — soak + tag protocol (companion to this)
- `docs/handoff/PH3_KEYRING_BRIEF.md` (PR #195) — cross-platform vault (independent)
- `docs/handoff/PH3_PAIRING_UX_BRIEF.md` (PR #196) — cockpit pairing UI (independent)
- `docs/handoff/PH2_STT_STREAMING_BRIEF.md` (PR #193) — v10.1 voice loop (independent)
- `docs/handoff/PH2_VOICE_GALLERY_BRIEF.md` (PR #194) — v10.1 voice gallery (independent)
- `docs/W310_WAVE_SUMMARY.md` (PR #192) — single-page wave overview; **§"Operator post-GA first-week runbook + rollback decision tree" (W310-aq) is the TARS-side mirror of §8.A above** — both sides MUST keep matched mental models; any amendment to either side goes via PR #192 within 14 days of incident close

### Coord channels

- GitHub: `https://github.com/alxvasilevvv/tars-neural-cockpit/issues` (TARS canonical)
- meeet ingest: Supabase project `zujrmifaabkletgnpoyw`
- Coord chat: `#tars-coord` (assumed; brother to confirm channel name)

---

**End of brief.**

This brief is the v10 GA brother coord document. Together with
`PH11_QA_SWEEP_BRIEF.md` (PR #197) it closes the full Phase 11
release dock-down — TARS-side methodology (soak + tag) + brother-side
coord (sync + sign-off). No further planning surface needed for the
v10.0.0 GA tag cut.

§8.A (added W310-aq cross-stack) closes the post-GA first-week
operational gap: brother now has a matched mental model with TARS for
incident response in T+0 → D+7, with bidirectional escalation tree,
4 named feature flag endpoints brother owns, 9-row signal taxonomy
shared with TARS-side W310-aq, and joint post-mortem cadence. The
W310 wave's full operator-orchestration surface — pre-tag verification
(6 verdict wrappers + Gate A + Gate B + Tag-Guard + Post-Install +
Postflight), tag-day execution (W310-ao GA cookbook execution
sequence), drift-detection (W310-ap rehearsal matrix), and first-week
operations (W310-aq runbook + this §8.A) — is now spec'd on BOTH
sides of the bridge.
