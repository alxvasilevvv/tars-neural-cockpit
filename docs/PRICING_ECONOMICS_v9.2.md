# Pricing Economics — TARS v9.2

> **Author:** TARS strategy desk, 2026-05-15.
> **Audience:** brother @ meeet.world (billing/usage_event wiring), operator
> (Alien), Claude lane (cockpit), Cursor lane (frontend).
> **Companion docs:** `COMPETITIVE_ANALYSIS_CURSOR.md` §7 (the strategic
> rationale), `ROADMAP_W234_to_v10.md` §4 (the endpoint contracts).
> **Status:** locked numbers — these are the inputs to `tiers.py` LIMITS and
> brother's billing column defaults. Treat as canonical until a v9.3
> revision lands.

This file gives brother every number he needs to wire `/api/billing/usage_event`
and `/api/billing/balance` correctly.

---

## 1. Tier matrix — the topline

| Tier      | USD price       | $MEEET price     | Monthly requests | Models           | $MEEET earning | Receipts        | Audit log | Workspaces |
|-----------|-----------------|------------------|------------------|------------------|----------------|-----------------|-----------|------------|
| FREE      | $0              | n/a              | 50 / mo          | Basic only       | Disabled       | Watermarked     | None      | 1 personal |
| PRO       | $20 / mo        | 200 $MEEET / mo  | 1 000 / mo       | All providers    | Enabled        | Clean           | None      | 1 personal |
| BUSINESS  | $40 / seat / mo | 400 $MEEET / seat / mo | 5 000 soft cap (unlimited fair use) | All providers, BYO key | Enabled (team pool) | Clean + branded | SOC2-style | Unlimited team |

Notes:
- The $MEEET price assumes a peg of $0.10/MEEET (operator-controllable
  in meeet.world admin; document the actual peg as of brother's deploy day).
- "Request" = one consequential agent action (voice command, chat message,
  pack action, vision call). Background tasks the daemon runs without user
  intent don't count.
- "Basic only" on FREE = local models + cheapest provider tier (gpt-4o-mini,
  haiku, or local llama). No Opus, no GPT-5, no Sonnet 4.6 on FREE.
- BUSINESS soft cap = 5 000 requests/seat/month; auto-warn at 4 000;
  fair-use review at 8 000 (no hard block — sales conversation).

---

## 2. Cost-per-request model (provider passthrough)

These are the inputs TARS uses to convert a request into a USD cost in
the ledger. Brother needs the same numbers to debit balances.

### 2.1 Provider unit costs (USD per million tokens)

| Model                              | Input $/Mtok | Output $/Mtok | Notes |
|------------------------------------|--------------|---------------|-------|
| anthropic-claude-sonnet-4.6        | 15.00        | 75.00         | Default for consequential actions |
| anthropic-claude-haiku-4.6         | 1.00         | 5.00          | Default for routine actions |
| anthropic-claude-opus-4.6          | 30.00        | 150.00        | Council dissent voice |
| openai-gpt-5                       | 12.00        | 60.00         | Cursor parity model |
| openai-gpt-5-mini                  | 1.50         | 6.00          | Cheap completion |
| openai-gpt-4o-mini                 | 0.15         | 0.60          | FREE-tier default |
| openrouter (any model)             | provider rate + 5% | provider rate + 5% | TARS markup covers OpenRouter's own 5.5% spread |
| local llama-3.2-3b (M-series)      | $0           | $0            | Voice cockpit fallback |
| tars-local-chat-v1                 | $0           | $0            | On-device clone responses |

### 2.2 Per-request multiplier

- Voice transcription (whisper): $0.006 per minute of audio (OpenAI rate)
  or $0 (local whisper.cpp).
- Vision call: priced as the underlying model's input cost (images count
  ~1500 tokens per 1024px tile).
- OCR via pytesseract: $0 (local).
- Embedding for code-RAG: $0.013/Mtok (text-embedding-3-small) or $0 (local).

### 2.3 TARS markup policy

- **Anthropic / OpenAI direct (BYO key):** 0% markup. User pays provider
  directly. TARS still ledger-records the cost for audit.
- **Anthropic / OpenAI via TARS-managed key (PRO/BUSINESS):** 15% markup
  over provider list. This funds infrastructure + meeet.world billing
  overhead.
- **OpenRouter:** 5% markup (lower because OpenRouter already takes its
  cut).
- **Local models:** $0 cost, but TARS still emits a receipt with
  `cost_usd=0` for ledger continuity.

### 2.4 Example: one Sonnet 4.6 prompt

Prompt: 2 000 input tokens, 800 output tokens.
- Provider cost: (2000 / 1e6 * 15) + (800 / 1e6 * 75) = $0.030 + $0.060 = **$0.090**.
- TARS-managed key with 15% markup: **$0.1035**.
- BYO key: **$0.090** (user pays Anthropic; TARS records $0.090; no
  balance deducted).

The cockpit cost estimator (W252) calls this formula client-side using
the price table from W250 endpoint.

---

## 3. Tier ceilings — what "1 000 requests / mo" buys

Assume the average user mix on PRO is 30% haiku, 50% sonnet, 20% opus,
all at ~1500 in / 600 out. Average per-request cost:

```
0.30 * ((1500/1e6 * 1.00) + (600/1e6 * 5.00))    = 0.30 * (0.0015 + 0.003) = $0.00135
0.50 * ((1500/1e6 * 15.00) + (600/1e6 * 75.00))  = 0.50 * (0.0225 + 0.045) = $0.0338
0.20 * ((1500/1e6 * 30.00) + (600/1e6 * 150.00)) = 0.20 * (0.045 + 0.090)  = $0.027
total avg per request = $0.0621
```

1 000 requests * $0.0621 = **$62.10 of LLM cost**.

But PRO costs $20. That's a $42 gross-margin negative.

**Resolution path** (operator decides):

1. **Conservative ceiling.** Cap PRO at 300 requests/mo (`$18.63` of LLM
   cost, ~7% margin). Bump cap to 1 000 only for users with BYO key.
2. **Aggressive ceiling.** Keep 1 000 requests/mo but force 60% haiku-default
   (router routes consequential-only to sonnet). Recompute: `0.6 * 0.00135
   + 0.3 * 0.0338 + 0.1 * 0.027 = $0.0138 avg`, 1 000 * $0.0138 = $13.80
   total cost, ~31% margin. Recommended.
3. **Premium ceiling.** Keep 1 000 requests; let user pick model. Lose
   money on power users; cross-subsidize from BUSINESS tier. NOT
   recommended at $20 price.

**Decision:** ship option 2. Cockpit defaults to haiku for routine, sonnet
for consequential, opus only when council dissent is invoked. Router
heuristic in `backend/core/agents/router.py` (already W116).

---

## 4. BUSINESS tier math

Same mix, BUSINESS $40/seat:
- Assume 5 000 requests/seat soft cap and option-2 mix.
- 5 000 * $0.0138 = **$69 LLM cost per seat**.
- Bill $40, lose $29? No — BUSINESS users skew toward BYO key + local models
  more (regulated industries, privacy-conscious). Realistic mix:
  - 40% BYO key (TARS records $0 cost) → $0/request
  - 30% local llama → $0/request
  - 30% TARS-managed haiku/sonnet at option-2 mix → $0.0138/request
- 5 000 * 0.30 * $0.0138 = **$20.70 LLM cost per seat**.
- $40 - $20.70 = $19.30 contribution per seat. ~48% margin.

If a BUSINESS seat exceeds 5 000 requests/month consistently (>2 months),
sales contacts for fair-use upgrade conversation.

---

## 5. Anti-abuse rules

### 5.1 Rate limits

| Tier      | Per-IP / hour | Per-token / hour | Per-token / day |
|-----------|---------------|------------------|-----------------|
| FREE      | 10            | 5                | 50              |
| PRO       | 200           | 100              | 1 000           |
| BUSINESS  | 1 000         | 500              | 5 000           |

Enforced at FastAPI middleware level (slowapi or similar). Brother also
enforces at `/api/billing/usage_event` ingress to catch TARS-side bugs
flooding events.

### 5.2 Hard caps on FREE tier

- **Daily USD cap:** $0.05 across all consequential actions (covers about
  50 cheap haiku prompts or 5 cheap sonnet prompts).
- **Daily compute minutes:** 30 minutes of background daemon CPU. Beyond
  that, daemon pauses with a "Upgrade to PRO" toast.
- **Storage cap:** 100 MB of RAG-indexed content. Beyond that, new ingests
  fail with a 402.
- **Connector cap:** max 2 active OAuth connectors on FREE. PRO/BUSINESS
  unlimited.

### 5.3 Token-rotation rules

- A meeet token grants access to the user's tier. Rotated weekly via the
  watchdog ping. Stale tokens (>14d unused) get expired and require
  re-magic-link.
- If a token is flagged abusive (>3x the per-hour limit in a single hour),
  watchdog suspends it; user must re-magic-link to reactivate.

### 5.4 IP-shared FREE detection

- If 5+ distinct FREE tokens share an IP within 24h, all 5 get rate-limited
  to 1 request/hour until distinct payment methods are added.
- Mitigates the "1 family = 1 PRO subscription" abuse (handled in PRO via
  workspace seats, not in FREE).

---

## 6. Refund / credit logic

### 6.1 Failed actions

- Any agent action that fails *due to TARS bug* (not user error) emits a
  receipt with `outcome=tars_error` and **does not** count against the
  monthly quota. Brother's `/api/billing/usage_event` ingress must respect
  this field — `tars_error` events log for ops but don't debit balance.
- Any agent action that fails due to **provider error** (Anthropic/OpenAI
  returning 5xx) also doesn't debit, but emits a receipt with
  `outcome=provider_error` for ops visibility.

### 6.2 Refunds

- FREE: no refunds possible (no charge).
- PRO: pro-rated refund on cancellation within first 14 days. After that,
  monthly bill is non-refundable but auto-renew off keeps the rest of the
  month active.
- BUSINESS: annual contracts are non-refundable. Monthly contracts pro-rated
  within first 30 days.
- $MEEET-paid subscriptions: refunded in $MEEET at the same token-USD
  ratio as paid (no $MEEET-side appreciation captured by the user, no
  TARS-side depreciation passed through).

### 6.3 Credit grants

- Beta testers (W198 install line): $25 USD credit auto-applied on first
  PRO subscription.
- Workshop attendees: $40 USD credit per workshop (covers 2 months of PRO).
- $MEEET-earning bounties: paid out monthly, capped at 1 000 $MEEET/user
  for FREE (forces a tier-up to keep earning). PRO/BUSINESS no cap.
- AI Clone training contribution: 10 $MEEET per ingested 100 messages
  (capped 500 $MEEET/month/user).

### 6.4 Disputes

- Any disputed receipt can be replayed via the public Merkle verifier
  (W204). User shows the Solana memo; brother's billing replays the proof.
- Dispute → ops queue (brother's dashboard) → 48h resolution SLA.

---

## 7. $MEEET economy specifics

### 7.1 Token peg

- Reference rate: $0.10 / $MEEET (operator-controlled).
- Pricing display: cockpit always shows USD-equivalent alongside $MEEET.
- Receipts record both the $MEEET amount and the USD-at-time-of-receipt
  for audit. Quarterly compliance bundle (W104) converts to USD-at-VWAP
  for the period.

### 7.2 Earning paths

| Action                                       | $MEEET earned |
|----------------------------------------------|---------------|
| Sign up + first action                       | 5             |
| Daily streak (per day, capped 30/streak)     | 1             |
| Publish a marketplace skill (one-time)       | 50            |
| Skill install (per install)                  | 1             |
| Skill rating from another user (per rating)  | 0.5           |
| Cowork session contribution (per session)    | 2             |
| AI Clone training data ingest (per 100 msgs) | 10 (cap 500/mo) |
| Invite a friend who tier-ups to PRO          | 30            |
| Bug bounty (per accepted bug, severity-scaled) | 50-500      |

FREE tier earns max 50 $MEEET / month (cap). PRO/BUSINESS uncapped.

### 7.3 Spending paths

- Pay for PRO subscription: 200 $MEEET/mo (= $20 at peg).
- Pay for BUSINESS subscription: 400 $MEEET/seat/mo.
- Buy a marketplace skill: per skill price (publisher-set).
- T2T deal escrow: variable, user-set.
- Top up balance: via Solana wallet swap (USDC -> $MEEET) on jup.ag or
  similar.

### 7.4 Burn vs circulation

- 30% of marketplace fees (the TARS take) get burned monthly (anti-inflation).
- 70% flows back to publishers (W96).
- Subscription $MEEET payments treasury-held, recycled into the earning
  pool monthly.

---

## 8. Compliance & audit

### 8.1 Per-action audit fields (emitted in every usage_event)

- `ts` (ISO8601 with timezone)
- `trace_id` (UUID, links to receipt + Solana memo)
- `user_id` (UUID, never PII)
- `tier` (free / pro / business)
- `action` (`voice.transcribe`, `chat.message`, `agent.run`, etc.)
- `provider` (`anthropic`, `openai`, `local`, `openrouter`)
- `model` (specific model string)
- `tokens_in`, `tokens_out` (integers, exact)
- `cost_usd` (decimal, 6dp)
- `cost_meeet` (decimal, 6dp, $MEEET-denominated)
- `markup_pct` (float, 0.0 / 0.05 / 0.15)
- `outcome` (`ok` / `tars_error` / `provider_error` / `denied_by_rule` / `denied_by_quota`)
- `receipt_id` (UUID, links to hash-chained ledger)
- `merkle_root_anticipated` (string, the daily root this receipt will be
  anchored into)

### 8.2 BUSINESS-only audit features

- Quarterly compliance export bundle (W104) packaging all usage events
  with their Merkle proofs.
- Per-seat usage report (admin dashboard).
- Configurable retention period (default 7 years, GDPR-shorter on request).
- Export formats: JSON, CSV, PDF (signed).

### 8.3 GDPR / CCPA

- User can request export of all their usage events: `GET /api/usage/export?user=me`.
- User can request deletion: brother's side wipes balance + spend history;
  TARS-side anonymizes receipts (replaces user_id with `deleted-<sha256>`)
  but keeps the hash-chain intact (otherwise the ledger is broken).
- Anonymized receipts still count toward Merkle proofs — chain integrity
  preserved.

---

## 9. Numbers brother needs verbatim

For `/api/billing/usage_event` ingress:

```yaml
tier_caps:
  free:
    monthly_requests: 50
    monthly_usd_cap: 1.50    # generous; mostly the request cap binds
    daily_usd_cap: 0.05
    daily_compute_minutes: 30
    storage_mb: 100
    max_connectors: 2
  pro:
    monthly_requests: 1000
    monthly_usd_cap: 20.00    # what they paid; treat as ceiling on TARS-managed key cost
    daily_usd_cap: 5.00
    daily_compute_minutes: 480   # 8h
    storage_mb: 10000           # 10GB
    max_connectors: 999
  business:
    monthly_requests: 5000_soft   # advisory; no hard block
    monthly_usd_cap: 40.00
    daily_usd_cap: 10.00
    daily_compute_minutes: 1440   # 24h, daemon allowed
    storage_mb: 100000            # 100GB
    max_connectors: 999

prices:
  pro_usd: 20.00
  pro_meeet: 200
  business_usd: 40.00
  business_meeet: 400
  meeet_peg_usd: 0.10

markup:
  byo_key: 0.00
  managed_key: 0.15
  openrouter: 0.05

refund_window_days:
  pro: 14
  business_monthly: 30
  business_annual: 0
```

---

## 10. Open questions for operator

1. **Sonnet 4.6 markup.** Should TARS-managed key keep the 15% markup, or
   pass through at 0% and recoup via subscription only? Decision affects
   PRO unit economics by ~3-5%.
2. **$MEEET peg policy.** Fixed $0.10 forever, or float with token
   market price? Fixed is operationally simpler; floating shifts FX risk
   off the platform.
3. **FREE tier daily USD cap.** $0.05 is tight (5 sonnet prompts max).
   Too tight discourages exploration; too loose loses money. Test $0.10 in
   v9.3?
4. **Workshop credit grant.** $40/attendee is generous. Lower to $25 once
   demand is proven?
5. **BUSINESS minimum seats.** 1 seat or 3 seats minimum? 3-seat minimum
   protects from "personal use disguised as business"; 1-seat opens the
   door to solo regulated-industry users.

Default for all five: ship as documented above. Revisit at W260 retro
once we have 2 weeks of v9.3 usage data.

---

## 11. Linkage

- Lives at `docs/PRICING_ECONOMICS_v9.2.md`.
- Drives constants in `backend/core/entitlements/tiers.py` LIMITS table.
- Drives the cockpit Settings → Billing UI in Wave A (W251).
- Drives brother's `/api/billing/*` endpoints in W245-W247.
- Drives landing page `/pricing` copy in W260b.
- Drives the cockpit Usage tab cap math in W242.

Any change to these numbers requires updating all 5 sites in lockstep.
Cap math drift between cockpit and brother is the highest-severity bug
class for v9.3. Recommend nightly reconcile script (W249) catches it.

---

## 12. Sign-off

These numbers are operator-locked until v9.3 retro. Brother can wire
`/api/billing/usage_event` against this spec with no further questions;
any contract change comes as a new dated revision of this file.

If brother needs to deviate (his side has different db column constraints,
auth flow, etc.), he opens a PR against this file with the proposed
delta. Until merged, this file is canonical.
