# TARS — Post-GA Roadmap (v10.1 → v11.0)

> **Author:** Claude lane, 2026-05-15 (rc.1 ready, GA imminent).
> **Audience:** operator (Alien), brother @ meeet.world, Cursor lane, future
> investors reading the strategy paper-trail.
> **Scope:** the six minor releases that follow `v10.0.0` GA, terminating at
> `v11.0.0` (Agentic OS). Concrete themes, five features per release, the
> single success metric we will defend, and the one gating dependency that
> can slip the date.
> **Status:** living document. Updated at each release retro.
> **Companion docs:** `LAUNCH_PLAYBOOK_v10_GA.md` (the GA day script),
> `V10.1_THROUGH_V11_GANTT.md` (the visual timeline),
> `MASTER_ROADMAP_v9.1_to_v10.0.md` (the predecessor — locks at GA).

---

## 0. The shape of the next six months

After GA, TARS has to stop *proving* itself and start *compounding*. The arc
below is deliberate:

1. **v10.1 — Stabilize.** Hotfix the bugs the first 1 000 installs surface.
2. **v10.2 — Spread.** Five languages, a mobile companion, self-monitoring
   telemetry so we can see what users actually do.
3. **v10.3 — Personalize.** AI Clone v2 + voice clone makes the product
   *feel* like yours, not like a generic LLM front-end.
4. **v10.4 — Enterprise-ready.** Workspaces v2 + Okta/Azure SSO. The on-prem
   leads from launch month get answers to their procurement questions.
5. **v10.5 — Marketplace economy.** Third-party publishers earn $MEEET.
   This is where the platform thesis either lives or dies.
6. **v11.0 — Agentic OS.** TARS becomes the always-on substrate. Voice-driven
   life planner closes the loop between intent and execution over 24-hour
   cycles. This is the slide-1 vision shipped as v11.

Each release is **5–6 weeks of work** (one v10.x every ~4 weeks until v10.5,
then 8 weeks to v11.0). No release ships without all five features green,
the success metric instrumented, and the gating dependency unblocked.

---

## 1. v10.1 — Stabilize (T+2 weeks, target 2026-05-29)

**Theme.** Hotfix release. Everything that the first cohort of GA installs
reveals — the bugs we couldn't catch in rc.1 soak because we don't have 1 000
machines and 50 OS variants. Brother's billing endpoints get one more polish
pass after seeing real `UsageEvent` volume. Apple notarization stability is
the silent killer; we tighten the pipeline.

### Five features

1. **rc.1 soak bug burn-down.** The top 20 bugs filed against `v10.0.0` in
   the first two weeks. Each gets a triage owner, a fix PR, and a regression
   test in `tests/` so it cannot return.
2. **Brother billing endpoint refinements.** `/api/billing/usage_event` and
   `/api/billing/balance` get back-pressure handling (429 with retry-after),
   batched ingest (drop the per-event roundtrip below 25 ms), and a
   reconciliation cron that catches drift before it crosses $0.50/day.
3. **Apple notarization stability.** The `SIGN-AND-NOTARIZE.command` flake
   rate today is ~3% (intermittent stapler failures). Target: <0.5%. Add
   retries with exponential backoff, a notarization-status poller, and a
   `--dry-run` mode for CI.
4. **Tauri updater hardening.** The `latest.json` feed gets a staged-rollout
   query parameter (10% → 25% → 100% over 48h) so a bad patch can be paused
   mid-rollout without yanking the release.
5. **`tars-doctor` v2.** Three new checks: notarization-stapler integrity,
   updater-feed reachability, meeet.world ingest lag. The dashboard widget
   in `/status` shows a 7-day uptime sparkline.

### Success metric

**Crash-free sessions >= 99.5%** across the first 1 000 GA installs, measured
over a rolling 7-day window. Pre-launch baseline (rc.1 soak): 99.1%.

### Gating dependency

Brother must ship the back-pressure response shape on `/api/billing/usage_event`
**by T+10 days** or v10.1 slips by however long that takes. This is the only
external blocker; everything else is local.

---

## 2. v10.2 — Spread (T+1 month, target 2026-06-15)

**Theme.** Polish + reach. Five-language UI (we already have the i18n
scaffolding from W215/W216 reverted — bring it back, properly this time).
Mobile companion app as iOS PWA first, native iOS later. Self-monitoring
telemetry dashboard so we can see what users actually do — not a dark-pattern
analytics scraper, an opt-in dashboard the user owns.

### Five features

1. **Five-language UI (EN/RU/ZH/ES/JA).** Full re-introduction of i18n
   on all 60+ routes. EN remains default; locale switcher in `/settings`.
   Translation pipeline: Claude-translate-then-human-review for RU/ZH/ES/JA.
   String budget locked at 1 800 keys (was 2 400 in W215 — we cut chrome).
2. **iOS PWA companion.** The cockpit at `tars.meeet.world/m` works as a
   home-screen install. Push notifications via meeet.world relayer. Read-only
   feed of the desktop daemon's activity + reply-to-message + approve-HIL.
   No new agents on mobile — it's a remote control for the desktop.
3. **Self-monitoring telemetry dashboard.** `/dashboard/telemetry` shows
   *your* TARS usage: actions/week, packs used, top voice intents, model
   spend, receipt count, latency p50/p95. All local — never leaves your
   machine unless you opt into the meeet.world rollup.
4. **Polished onboarding wizard.** Six-step flow (role -> packs -> voice
   sample -> first action -> cowork invite -> done) replaces the current
   four-step. First-action completion rate target: 85% (currently 62% in
   beta).
5. **Universal capture inbox.** Drop anything (file, URL, email forward,
   text snippet) into a single `/inbox` and TARS triages it to the right
   pack with a one-tap confirm. The first feature that *actively
   simplifies* the user's workflow rather than mirroring what they already
   do.

### Success metric

**WAU/MAU >= 0.55** in the first month of v10.2. We learn whether language
expansion + mobile drive return visits or just one-time installs.

### Gating dependency

Translation reviews for RU/ZH/ES/JA must land by T+25 days. We have native
speakers lined up (Alien — RU; brother's contact — ZH; community for ES/JA).
If any one of these slips past the deadline, we ship with three languages
and add the rest in v10.2.1.

---

## 3. v10.3 — Personalize (T+2 months, target 2026-07-15)

**Theme.** AI Clone v2 + voice clone + voice-first onboarding. The product
stops being a generic LLM cockpit and becomes *yours*. This is the moat that
copying Cursor's surface cannot replicate — every TARS install diverges from
every other after a week of use.

### Five features

1. **AI Clone v2.** Extended per-user style learning. Today (v0.2): sentence
   length, exclamation rate, vocab. v2: paragraph structure, opener phrases,
   sign-off habits, code-comment style, decision-making vocabulary
   (hedges vs. assertions). Trained from the user's last 30 days of
   chat + email drafts, never leaves the machine.
2. **XTTS-v2 voice clone.** 30-second voice sample produces a fine-tuned
   TTS that sounds like the user. The daemon now narrates outbound emails
   in your voice (opt-in; off by default for sane reasons). The "TARS reads
   your morning briefing back to you in your own voice" demo lands here.
3. **Voice-first onboarding.** The six-step wizard from v10.2 gets a
   voice-only path. The user speaks their name, role, and goals; TARS
   transcribes, confirms, and configures packs. Skip-to-keyboard always
   available.
4. **Memory reflection v2.** Weekly summary becomes daily-and-themed. Every
   evening at 8 PM local time the daemon emits a `reflection.daily` event:
   what you worked on, what you didn't finish, what tomorrow's calendar
   suggests for prep. User approves or edits before it commits to long-term
   memory.
5. **Persona drift detection.** If AI Clone v2 starts drifting away from
   the user (e.g., the user changed jobs and now writes differently), the
   `tars-doctor` raises a `clone.drift` warning and offers a retrain.

### Success metric

**AI Clone acceptance rate >= 70%.** When TARS drafts a reply or email in
your style, you accept (with or without edits) 70%+ of the time. Pre-v10.3
baseline: ~45%.

### Gating dependency

XTTS-v2 fine-tuning on consumer-grade Macs (M2/M3) must complete in <5
minutes from a 30-second sample. If the model proves too heavy, we fall back
to a hosted fine-tune in the meeet.world inference cluster and ship voice
clone behind a PRO/BUSINESS flag.

---

## 4. v10.4 — Enterprise-ready (T+3 months, target 2026-08-15)

**Theme.** Workspaces v2 at scale. RBAC polish. Enterprise SSO (Okta + Azure
AD + Google Workspace). This is where the on-prem leads we collected during
launch month (target: 10 qualified) close into paying contracts.

### Five features

1. **Workspaces v2 — multi-tenant at scale.** The schema-only MVP from W110
   becomes a fully load-tested multi-tenant database. Tested at 100 orgs
   x 50 seats x 5k receipts/day without contention. Per-tenant encrypted
   data segregation enforced at the ORM layer (not just app code).
2. **RBAC polish.** Five roles (Owner / Admin / Operator / Member / Guest)
   with a UI for custom-role creation in BUSINESS tier. Every receipt
   stamps the role of the actor, not just the user id.
3. **Enterprise SSO — Okta + Azure AD + Google Workspace.** Three identity
   providers, all via SAML 2.0 + OIDC. SCIM 2.0 user provisioning so an IT
   admin can offboard a user once and TARS access goes with it.
4. **Audit log v2.** Searchable, exportable, retention-policy-aware. The
   audit explorer from W255 becomes a first-class admin tool with saved
   queries, scheduled reports, and a webhook for SIEM integration (Splunk,
   Datadog, Elastic).
5. **Procurement-friendly artifacts.** SOC2 Type II report (the audit we
   started in W257, completed by an external auditor). Standard MSA
   template. Security questionnaire pre-fill (CAIQ Lite + SIG Lite).
   Pen-test report from a reputable firm. The full "send these to legal"
   bundle.

### Success metric

**10 paid on-prem deployments live** at the end of v10.4 month. Each
generating >= $1k/month in seat licenses + meeet.world relay fees.

### Gating dependency

SOC2 Type II auditor sign-off is the single longest-lead-time item — start
the engagement *the day v10.0 ships GA*. If we don't have a signed report
by T+90 days, v10.4 ships without it and we promise "Q4 SOC2 report" in
sales conversations.

---

## 5. v10.5 — Marketplace economy (T+4 months, target 2026-09-15)

**Theme.** Marketplace v1. Third-party agent publishers earn money. The W261
marketplace v0 (in-process registry + browse) becomes a real economy with
revenue split UI, featured-agents curation, and discovery search. This is
where the platform thesis either compounds or stalls.

### Five features

1. **Publisher accounts + KYC.** Anyone can register as a publisher at
   `tars.meeet.world/publish`. Light KYC (email + Solana wallet + tax form
   for US payers > $600/yr). Each publisher signs their skills with their
   ed25519 key (re-using W27).
2. **Revenue split UI.** Publishers see their earnings in real time —
   $MEEET volume, USD-equivalent, payout schedule (weekly to wallet,
   monthly to bank). 70/30 split: 70% publisher, 30% platform. (W96 had
   this as an API; v10.5 surfaces it.)
3. **Featured agents curation.** Editorial team (Alien + 2 contributors)
   curates a weekly "Featured Agent" slot on the marketplace homepage.
   Featured agents see ~10x install lift from past releases of this
   pattern in adjacent marketplaces.
4. **Discovery search.** Full-text + semantic search across all
   marketplace skills. Filters by pack, by tier requirement, by language,
   by 5-star rating, by recent activity. Search-to-install funnel
   instrumented end-to-end.
5. **Anti-fraud + safety review.** Every submitted skill goes through an
   automated audit (sandbox execution, network egress check, malicious
   import detection) + manual review for the first 30 days. Skills that
   fail audit get a public "rejected — reason" badge.

### Success metric

**50 published skills with >= 100 monthly active installs each** by the end
of v10.5. This is the threshold below which a marketplace is dead and above
which it self-reinforces.

### Gating dependency

Brother's $MEEET payout pipeline must support batched weekly payouts to
arbitrary Solana addresses (not just relayer-internal accounts). If brother
can't ship this by T+110 days, we delay revenue payouts to monthly and
absorb the publisher complaint.

---

## 6. v11.0 — Agentic OS (T+6 months, target 2026-11-15)

**Theme.** TARS becomes the substrate for autonomous task execution across
all seven domain packs. The background daemon evolves from a polling
heartbeat into an always-on companion. The killer feature: a voice-driven
life planner that schedules and executes across calendar, email, and finance
in 24-hour cycles.

### Five features

1. **Always-on daemon — v2.** The launchd plist from W181 becomes a true
   companion. The daemon listens for triggers (calendar events, email
   arrival, file changes, voice wake-word) and proactively *suggests*
   actions. User confirms via mobile push (v10.2) or voice.
2. **Voice-driven life planner.** Speak: "I'm flying to NYC on Friday for
   a 2-day trip. Get me ready." TARS schedules calendar, books a hotel
   draft, drafts the OOO email, blocks focus time on Thursday, and queues
   a packing checklist. Every step is a receipt-anchored, user-approved
   action.
3. **24-hour execution cycles.** The planner thinks in days, not turns. A
   high-level intent ("ship the v11.1 hotfix by Friday") decomposes into a
   24-hour-rolling plan that re-plans every morning based on what got done
   the previous day. The first product to make "ambient AI" feel earned.
4. **Cross-pack action graphs.** A single intent can span wealth + product
   + family packs (e.g., "I want to retire in 10 years" touches budgeting,
   career roadmap, and family logistics). v11 introduces a cross-pack
   action graph that respects per-pack permissions while letting the
   planner reason globally.
5. **Skill-marketplace plug-ins to the planner.** v10.5 marketplace skills
   can register as *planner contributors* — i.e., a "Tax Optimization
   2026" skill registers itself with the wealth pack's planner and gets
   called automatically during financial planning. The marketplace stops
   being a list and becomes a substrate.

### Success metric

**DAU/MAU >= 0.40 + average 12+ daemon-suggested actions/week accepted per
user.** This is the threshold above which "always-on AI" is real and below
which it is a UX gimmick.

### Gating dependency

v10.3 voice clone + v10.5 marketplace economy must both ship on time. v11
literally cannot work without per-user style (so suggestions feel like the
user wrote them) and marketplace contributors (so the planner has tools
beyond what we shipped). If either slips, v11 slips by the same amount.

---

## 7. Recurring themes — across all six releases

Some work is too important to be a single feature in a single release:

- **Performance.** Every release must beat the previous release's p95
  latency on the 5 SLOs from `PERF_REPORT_v10.0.md`. No regressions allowed.
- **Security.** Each release ships at least one security improvement from
  the SOC2 backlog. Aim for cumulative SOC2 Type II readiness by v10.4.
- **i18n.** New strings get added to all 5 languages before merge. No
  EN-only ship after v10.2.
- **Accessibility.** Every new page passes the WCAG 2.1 AA checklist in
  `engineering:testing-strategy`. No exceptions.
- **Receipts.** Every consequential agent action emits a receipt. This is
  non-negotiable for the audit story.
- **Brother sync.** Each release has at least one endpoint contract that
  brother either provides or consumes. The handoff doc is updated before
  the release ships.

---

## 8. What is *not* on this roadmap (and why)

- **Native Windows/Linux GUI parity.** Tauri already runs on both — we
  don't owe a Windows-native UX before v11. Linux is a server target
  (on-prem); a GUI ships when there's demand.
- **Mobile-native (Swift/Kotlin) apps.** iOS PWA in v10.2 is enough until
  we see DAU on mobile justify the native investment. Plan: revisit
  after v11.0.
- **A custom local LLM.** We pass through Anthropic/OpenAI/Gemini/Ollama
  via the W175 router. Building our own foundation model is a $50M+
  bet that contradicts the local-first thesis. Not on the roadmap.
- **Crypto trading agents shipped by us.** The algotrade workshop pack
  is *enablement* (we teach), not *execution* (we don't trade for you).
  This is a regulatory line we don't cross.
- **A general chat surface.** TARS is task-oriented. The chat panel
  exists to *converse with the agents*, not to be ChatGPT. Adding a
  general-purpose chat would dilute the cockpit thesis.

---

## 9. Release cadence + retrospective discipline

- **Cadence.** v10.1–v10.5 ship every ~4 weeks. v11.0 ships at T+6 months
  with an 8-week dedicated cycle. Patch releases (v10.x.y) ship as needed
  within hours of a critical bug.
- **Retrospective.** Every release ships with a written retro in
  `docs/RETRO_v10.x.md`: what shipped, what slipped, what we learned,
  what changes in the next release. 1 hour max to write; 30 minutes max
  to read.
- **Definition of done.** Five features green + success metric instrumented
  + gating dependency unblocked + retrospective written + handoff doc
  updated + brother synced. No release ships with any of those open.

---

## 10. The single most important question

Past v11.0, the question becomes: **does the always-on daemon + marketplace
substrate compound into a fundamentally different product, or is it a
better cockpit?** The answer determines whether TARS raises a Series B in
2027 as an Agentic OS or as a productivity tool. We don't have the answer
yet. v11 is the experiment that tells us.

— end —
