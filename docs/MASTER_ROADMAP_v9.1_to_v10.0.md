# TARS — Master roadmap v9.1 → v10.0

> **Author:** product strategist pass, 2026-05-14 (post-launch +1 day).
> **Audience:** operator (Alien), Claude lane, Cursor lane, brother @ meeet.world.
> **Scope:** the next 6 months. Concrete numbers, dated deliverables, no padding.
> **Companions:** `ROADMAP.md` (calendar-honest deltas), `IDEAS.md` (backlog),
> `AGENT_HANDOFF.md` (operational state). This file overrides only on prioritization
> conflicts — never on scope contracts.

---

## 1. North Star — what TARS is in 6 months

TARS is **the local-first operator console for AI agents on a Mac**. One install
gets you (a) a Cmd+Shift+Space cockpit that drives real apps, (b) a multi-LLM
council that cross-checks every consequential proposal, (c) a receipt ledger that
makes every agent action auditable, (d) Cowork sessions so a human teammate or
another TARS can join the loop, and (e) a marketplace where third parties ship
signed skills and get paid in $MEEET. By v10.0 the same product runs on Windows
and Linux, supports orgs/teams with RBAC, and the Cowork session is the default
way two TARS instances negotiate work between humans.

The wedge against everyone else: **local execution + multi-model dissent + a
visible audit trail**. Not a chat UI. Not an agent framework. A console.

---

## 2. Versions plan

### v9.1.1 — stabilize the launch (target: 2026-05-28, 2 weeks)

**Theme:** the dust settles. Every promise on the v9.1.0 HN post becomes
clickable.

**Features (must-ship):**

1. **Cowork wired end-to-end.** Brother lands the 10 `/api/cowork/*` routes per
   `docs/handoff/COWORK_WIRING_FOR_CURSOR.md`. Frontend mock fallback
   auto-deactivates. **Success:** two browsers in different sessions see each
   other's presence within 2s; handoff token round-trips.
2. **Apple Developer cert + notarization.** Operator exports the cert per
   `docs/APPLE_SIGNING_NEXT_TIME.md`; CI secrets populated; first notarized
   `.dmg` published. **Success:** Gatekeeper opens TARS.app with no warning.
3. **Magic-link auth live.** Brother's meeet.world bridge mints tokens against
   the onboarding wizard's email submission. **Success:** end-to-end signup in
   <60s from `tars://login`.
4. **Intel `.dmg` fix.** Pin the macos-13 runner OR fall back deterministically
   to arm64-via-Rosetta with a banner ("running under Rosetta — native Intel
   coming v9.2"). **Success:** 0% silent fallbacks; users always know which
   binary ran.
5. **iMessage bridge (read).** AppleScript + Messages.app DB read path. Full
   Disk Access prompt UX. **Success:** TARS can summarize "last 24h of texts
   with X" without leaving the box.
6. **Wake-word web (Picovoice wasm in PWA).** Already 80% complete. **Success:**
   `Hey TARS` in the browser triggers the cockpit listen state with <300ms latency.
7. **Cowork outgoing webhook on `handoff.accepted`.** Per-tenant integration
   hook so observers (Slack, Telegram) can see transfers.

**Metrics:** 200 active installs (`/api/product/version` ping in last 7d),
≥40% week-2 retention, ≥1 Cowork session per active user that triggers it,
<2% crash rate on sidecar startup.

**Dependencies:** brother (Cowork wiring, magic-link mint), operator (Apple cert
+ Cloudflare custom-domain swap on `tars-meeet-git`).

**Risks:**
- Brother's velocity is the bottleneck on Cowork + magic-link. Mitigation: ship
  v9.1.1 on Apple cert + Intel + iMessage alone if Cowork slips.
- Apple notarization rejection — mitigation: `install.sh` xattr already mitigates.

---

### v9.2 — the first big wave (target: 2026-06-25, 6 weeks)

**Theme:** the platform stops being Mac-only. The marketplace starts to make
money. The clone becomes real.

**Features:**

1. **Windows installer (signed `.msi`).** Authenticode cert purchase
   ($300/yr DigiCert or $99 Sectigo). pyoxidizer cross-target build. **Why:**
   ~60% of HN readers couldn't try v9.1.0. **Success:** 100 Windows installs in
   first 2 weeks of v9.2.
2. **Linux installer (`.AppImage` + `.deb`).** No signing dance. Cheap win.
   **Success:** present on the download grid; ≥30 installs in 2 weeks.
3. **AI Clone v1 (real fine-tune).** Per-user LoRA on top of a small open
   model (Llama-3.2-3B or similar) — train on the operator's sent
   email/Slack/Telegram corpus. Runs locally on M-series; falls back to remote
   inference for Intel/Windows. **Why:** Wave 73 v0.1 is a placeholder; the
   outreach flow is gated on this. **Success:** blind A/B — operator can't
   distinguish AI Clone draft from their own writing 50% of the time on a
   20-message sample.
4. **Marketplace 70/30 payouts.** Solana on-chain payouts (we already have a
   ledger and the wallet); per-publisher revenue dashboard. **Why:** turns the
   marketplace from a directory into a market. **Success:** ≥5 paid skill
   installs by end of v9.2, ≥1 third-party publisher.
5. **Skill SDK third-party publishing.** ed25519-signed bundle spec (already
   shipped) + a `tars skill publish` CLI. Onboard 5 friendly publishers with
   hand-held DX. **Success:** 10 third-party skills in marketplace.
6. **MCP server bridge (productized).** Already a reference in Wave 85. Promote
   to a first-class "MCP server" mode so TARS skills appear in Claude Desktop
   / Cursor / Continue.dev. **Why:** distribution to existing power users.
   **Success:** TARS appears in the MCP-server registry; ≥3 inbound users land
   from Claude Desktop trying to add TARS as a tool.
7. **`sqlite-vec` wired.** Replace Python cosine in memory KV. ~5× speedup at
   10k+ rows. **Success:** memory recall p95 < 50ms at 10k chunks.

**Metrics:** 1,000 weekly active installs, 100 Windows, 30 Linux, 5+ paid
marketplace transactions, ≥3 third-party skill publishers, median session
length up 25% vs v9.1.1.

**Dependencies:** infra (Windows CI runner + Authenticode cert), GPU pool for
fine-tune (rented; ~$200/mo on Modal/Runpod), brother for payout rails.

**Risks:**
- Authenticode cert rejection / SmartScreen reputation cold-start — mitigation:
  ship Windows behind a banner ("first 100 users — click 'More info → Run
  anyway'").
- AI Clone privacy panic — mitigation: training data never leaves the device,
  documented in `THREAT_MODEL.md` with screenshots.

---

### v9.3 — multi-tenant + workspace fencing (target: 2026-08-13, 2 months from now)

**Theme:** TARS becomes safely deployable inside an org. Workshop suite from
v9.1.0 finally gets the substrate it deserves.

**Features:**

1. **Multi-tenant Workspaces (full).** Build on the Wave 110 schema-only MVP.
   Every entity (threads, attachments, schedules, receipts, cowork sessions)
   gets `workspace_id` enforcement at the query layer. JWT auth replaces the
   single-user model. **Why:** workshop customers (funds, agencies) need this
   the day after the workshop ends.
2. **Org / Teams / RBAC.** 4 roles (owner / admin / member / guest), permissions
   matrix per workspace. Already scaffolded in Wave 50. **Why:** B2B sales
   gates open.
3. **T2T live + Solana escrow.** TARS-to-TARS handshake out of mock mode.
   Counterparty discovery via meeet.world reputation graph. Solana escrow
   program deployed. **Why:** the marketplace narrative compounds when
   agents pay other agents.
4. **Webhook `receipt.*` emission everywhere.** Outreach, scheduler, files,
   reports all emit. **Why:** closes the v9.1.0 honesty gap.
5. **Cowork over the wire.** Cowork sessions can cross workspaces (with
   explicit invite); Redis-backed presence (replacing in-process), 100+
   concurrent sessions per server.
6. **Reputation Graph public UI.** Wave 80 aggregator + leaderboard. **Why:**
   reputation becomes the discovery primitive for marketplace.
7. **GitHub connector — write side.** PR creation, issue write, comment.
   **Why:** the most-requested connector graduation from read-only.

**Metrics:** 50 paid B2B workspaces, 5,000 WAU, 20+ third-party skill
publishers, marketplace GMV $5k/mo, ≥10 cross-workspace Cowork sessions/week.

**Dependencies:** brother (escrow program + reputation API), infra (Redis,
upgraded Solana RPC), legal (per-jurisdiction payout review for marketplace).

**Risks:**
- Migration pain for v9.2 single-user installs — mitigation: opt-in workspace
  upgrade flow, single-user "default workspace" stays the fast path.
- Solana program audit — mitigation: limit escrow to $500 max per transaction
  for the first 30 days.

---

### v10.0 — the leap (target: 2026-11-13, 6 months from now)

**Theme:** TARS is a *platform*. Other people build on it. Voice latency is
edge-grade. The cockpit is everywhere you compute.

**Features:**

1. **Edge voice adapter.** Cloudflare Workers / Vercel Edge sub-100ms STT+TTS
   relay for users who don't have a GPU. **Why:** voice mode latency is the
   #1 complaint from non-M-series users.
2. **Native mobile companions (iOS first, Android in v10.1).** Swift/SwiftUI
   app that pairs with the desktop via the L5 pairing flow. Push notifications
   for HIL approvals, presence for Cowork, voice intents. **Why:** the
   conversation is already cross-device; the UX should be too.
3. **Browser extension (Chrome + Firefox).** Right-click any text or page →
   "send to TARS". Inline cockpit popover. **Why:** distribution to web-native
   users who never installed a `.dmg`. (Was in v9.2 plan; moved to v10.0 to
   ship alongside the polished mobile surface.)
4. **Skill marketplace v2 — discovery + bundles.** Curated collections,
   editorial picks, weekly newsletter, per-vertical hubs. **Why:** v9.2 ships
   the rails; v10.0 ships the storefront experience that converts.
5. **Headless daemon mode (`tarsd`).** Run TARS as a launchd / systemd / Windows
   Service. Cockpit becomes a client. **Why:** unlocks server-side deployment
   (a TARS in your homelab, on your VPS, in a Kubernetes pod). Direct
   competition with AutoGPT/OpenInterpreter on the agent-runtime axis.
6. **On-device fine-tune wizard (M-series only).** Repeat AI Clone v1's trick
   for any pack — train a personal "research analyst" / "outreach writer" /
   "code reviewer" voice. **Why:** the clone-everything moat — nobody else
   does per-user models locally.
7. **Council v2 — proposal markets.** Models bid (in $MEEET) for the right to
   propose; winning proposal pays losers if it's accepted. **Why:** ties the
   council to the economy. Speculative but defining.

**Metrics:** 25,000 WAU, $50k/mo marketplace GMV, 100+ third-party publishers,
median voice round-trip <800ms on non-M-series, 5,000 active iOS pairings,
100+ headless deployments.

**Dependencies:** Apple Developer account in good standing for iOS, edge
provider partnership, Solana program audit pass.

**Risks:**
- iOS App Store review for an "AI agent that controls your Mac" — mitigation:
  pairing-only feature framing, no agent runtime on iOS itself.
- Browser extension supply-chain attack surface — mitigation: extension is
  pairing-only, no code execution.

---

## 3. Hot list — top 10 features for the next 30 days

Ranked by `(impact × users-affected) / cost`. S = ≤3 days, M = ~1–2 weeks,
L = 3+ weeks.

| # | Feature | Why now | Effort | Owner |
|---|---------|---------|--------|-------|
| 1 | **Cowork live (10 routes wired)** | Marketing surface promises it; mock fallback is a credibility leak. | M | brother |
| 2 | **Apple Developer cert + notarization** | Every Mac install today shows Gatekeeper warning. Conversion killer. | S | operator |
| 3 | **Magic-link auth live** | Onboarding wizard claims it; today it's UI-only. | S | brother |
| 4 | **Intel `.dmg` deterministic fix** | Silent Rosetta fallback erodes trust on Intel Macs. | S | Cursor |
| 5 | **iMessage bridge** | High-frequency surface; Mac users live in Messages. 1 day of work, huge UX win. | S | Cursor |
| 6 | **Wake-word web (Picovoice wasm)** | Already 80% done. Differentiator vs Claude Desktop. | S | Cursor |
| 7 | **Synthetic monitor → public status page tile** | Wave 117 monitor exists; surface uptime publicly. Trust signal. | S | Claude |
| 8 | **GitHub Issues template + 3 starter labels** | The HN crowd will file issues. Triage substrate. | S | Claude |
| 9 | **Telemetry opt-in dialog + privacy doc** | We need usage data to make v9.2 decisions; today we collect nothing public. | S | Claude + operator |
| 10 | **One-line `tars upgrade` CLI** | Auto-updater works in-app; CLI users (the technical audience) want a flag. | S | Cursor |

**Order of operations:** #2 (operator, 15 min) → #4 (Cursor, 1 day) → #5/#6
(Cursor parallel, 2 days each) → #1 (brother, gated by his calendar) → rest in
any order during the v9.1.1 window.

---

## 4. Killer experiments — 3-5 wild ideas worth testing in v9.2

These are *not* committed scope. Each one is a 3-day spike with a kill-switch
metric. Run them on a `v9.2-experiments` branch.

1. **Browser extension (MV3, Chrome + Firefox).** "Send selection to TARS" +
   inline cockpit popover. **Hypothesis:** 30% of new installs in the next 60
   days come from a web context, not a dmg page. **Kill if:** <100 weekly
   active extension users after 30 days.

2. **Voice-first mode (`tars://voice`).** Boot directly into a fullscreen
   wake-word + ambient listen state, no chat UI. Inspired by the Friend.com
   wearable, but on your laptop. **Hypothesis:** unlocks a "voice journaling
   + ambient assistant" use case that the cockpit UI hides. **Kill if:** <5%
   of new users toggle it on in week 1.

3. **On-device fine-tune for any pack.** Already in v10.0 — try a one-pack
   prototype in v9.2 on the `wealth` pack. **Hypothesis:** a "your money,
   your model" headline pulls a different audience (finance Twitter, FIRE
   community) we currently miss. **Kill if:** fine-tune quality on a 200-row
   eval set is <70% of base-model quality.

4. **MCP-server marketplace inside Claude Desktop.** Package TARS skills as
   MCP servers, submit to whatever registry Anthropic ships. **Hypothesis:**
   the existing Claude Desktop user base is 10× our addressable HN audience;
   we ride their distribution. **Kill if:** Anthropic explicitly disallows
   third-party agent-runtime MCP servers.

5. **"Bring your own LLM" wizard for non-technical users.** Today connecting
   Claude/GPT/Gemini means putting an API key in a text field. Replace with
   a per-provider OAuth-style wizard that handles billing, model picker,
   spend cap. **Hypothesis:** doubles non-technical conversion. **Kill if:**
   <20% of new users use the wizard vs raw API key.

---

## 5. Pivots to avoid — what NOT to chase

History from the wave log:

- **Don't rebuild the 8 v7.1 agents.** The `browser / code / shell / vision /
  advisor / builder / cursor / local_model` model was replaced by the 6 domain
  packs in Wave 56 and the planner+smart-router in Wave 73. Going back to
  per-agent fan-fiction adds surface without adding outcomes.

- **Don't reintroduce the "7 killer agents" (research / analyst / meeting /
  doc / scraper / translator / image).** Wave 47 shipped them; Wave 71
  simplify pass cut them. The planner does this work; specialized agents add
  config burden.

- **Don't put the 3D neural-brain back in the main UI.** Removed Wave 71. It
  lives in `experiments/neural-showcase-v3/` for marketing screenshots, not
  the cockpit critical path. Cool ≠ daily-driver useful.

- **Don't translate the UI before there's a paying user asking.** Wave 70-72
  force-EN'd everything. The infrastructure (`useT()`) is preserved. Pay-as-
  you-go translation: a customer asks → we translate that locale only.

- **Don't ship named-customer branding in shared code.** Wave 87 stripped
  Cresco / CARF / 3V / Crypto Fund. All shared workshop content stays
  generic; per-customer branding lives in private forks/deployments.

- **Don't make the Quests UI a cockpit panel.** Quests live in the meeet.world
  economy backend; TARS surfaces them via the receipt ledger only. This was a
  Wave 71 cut and should stay cut.

- **Don't chase Open WebUI / LobeChat on chat-UI polish.** They will always
  win on chat aesthetics because that's their entire product. We win on
  *what happens after the message is sent* (real actions, real receipts,
  real council dissent).

- **Don't chase Cursor / Continue.dev on inline code completion.** That's
  a different shape of product (IDE-resident). TARS is the operator console;
  code is one of many things it operates *on*. MCP-bridge into Cursor instead.

- **Don't ship a TARS web SaaS to compete with Claude.ai.** Local-first is
  the brand. A hosted version is fine as a *trial surface* for the desktop
  installer — never as the product.

---

## 6. Marketing rhythm

One push per version, spaced to let metrics breathe.

### v9.1.0 (already done, 2026-05-13)
- HN Show HN — `docs/launch/HN.v9.1.0.md`.
- Twitter thread + LinkedIn (Wave 118 collateral).
- *Skip Product Hunt for v9.1.0* — Mac-only, Gatekeeper warning, Cowork in
  mock mode. PH is unforgiving on rough edges. Save it for v9.2.

### v9.1.1 (2026-05-28)
- **Quiet ship.** Changelog post, Twitter "we fixed X, Y, Z" thread. No HN.
- Email blast to the waitlist (~"the signed Mac dmg is here").
- Reddit `r/MacApps` post — Mac users care most about the cert news.

### v9.2 (2026-06-25)
- **Product Hunt launch.** Windows + Linux + signed Mac + AI Clone v1 is a
  clean PH story. Schedule for a Tuesday.
- **HN Show HN #2** — "TARS v9.2 — multi-platform + on-device fine-tune"
  posted 24h after PH so the audiences don't overlap.
- Twitter thread anchored on the AI Clone diff demo (your prose vs the clone).
- Sponsored placement in the AlphaSignal / TLDR.AI newsletters ($800-1200).

### v9.3 (2026-08-13)
- **B2B push.** LinkedIn long-form post for fund/agency audience. Workshop
  case study (anonymized) on the blog. Pitch to one tier-1 fintech newsletter.
- Skip HN/PH — too B2B for those audiences.
- AMA on `r/algotrading` and `r/fintech` if customer permission allows.

### v10.0 (2026-11-13)
- **HN Show HN #3** ("TARS 1.0 — local-first AI operator for Mac, Windows,
  Linux, iOS"). The 1.0 framing earns a fresh read.
- Product Hunt Maker of the Day pitch.
- Twitter mini-launch arc: countdown thread → release video → install demo.
- Podcast tour: 3 pods (Lex / Lenny / Latent Space tier — whoever bites).

**Cadence rule:** never two big public pushes within 14 days. Audience overlap
burns goodwill.

---

## 7. Honesty floor — what we will NOT claim until shipped

Pin this list inside the marketing review for every release. If a claim isn't
on the **shipped** side of the line, copy gets cut. No exceptions.

| Will NOT claim until... | Honest description today (v9.1.0) |
|---|---|
| "Cowork: multiplayer agent sessions" | "Cowork backend module ships; the live frontend lands in v9.1.1." |
| "Notarized macOS install" | "Ad-hoc codesigned; Gatekeeper warning until v9.1.1." |
| "Cross-platform" | "macOS only until v9.2." |
| "AI Clone" (without qualifier) | "AI Clone v0.1 = style hints. Real fine-tune in v9.2." |
| "Marketplace with payouts" | "Marketplace v0 = browse + install + local ratings. Payouts in v9.2." |
| "Third-party skills" | "In-process registry only. Third-party publish flow in v9.2." |
| "Multi-tenant / orgs / teams" | "Single-user. Multi-tenant Workspaces MVP in v9.2, full in v9.3." |
| "TARS-to-TARS payments" | "Mock-escrow handshake only. Live + Solana escrow in v9.3." |
| "Browser extension" | Not in any release until v10.0 spike confirms it. |
| "iOS / Android companions" | Not until v10.0 (iOS first). |
| "Headless server mode" | Not until v10.0. |
| "Voice latency <300ms anywhere" | Today: <300ms on M-series only. Edge adapter in v10.0. |
| "100+ skills in marketplace" | 12 seed listings today. Number is real-time on the page; don't round up. |

**Reviewers:** every press / blog / landing-page draft must be linted against
this table. If a claim is in the left column, the copy must match the right
column verbatim (or be cut). The `tars.meeet.world` landing already does this
correctly — keep it that way.

---

## Appendix A — What's measured and where

| Metric | Source | Cadence |
|---|---|---|
| WAU (weekly active installs) | `/api/product/version` ping (opt-in telemetry) | weekly |
| Crash rate | sidecar crash watcher events → meeet event store | weekly |
| TTFR (time-to-first-receipt) | onboarding wizard → first receipt timestamp | per cohort |
| Retention (week-2, week-4) | install id → ping cadence | monthly |
| Marketplace GMV | receipt ledger `marketplace.purchase.*` events | monthly |
| Cowork session count + duration | cowork store → events | weekly |
| Council disagreement rate | proposal events → `decision.dissent` payload | per release |
| Connector OAuth completion | oauth bridge logs | weekly |
| Voice round-trip p50/p95 | `/admin/perf` dashboard | daily |

All metrics live in the `/admin/perf` page (Wave 108) once we wire the
telemetry pings. Hot-list item #9 makes this real.

---

## Appendix B — Single-source-of-truth links

- **Calendar-honest deltas:** `docs/ROADMAP.md`
- **Capability ledger:** `docs/WHAT_WORKS.md`
- **Operational state:** `docs/AGENT_HANDOFF.md`
- **Backlog:** `docs/IDEAS.md`
- **Design-phase reference:** `docs/PHASE_L_ROADMAP.md`
- **Security boundaries:** `docs/THREAT_MODEL.md`
- **Workshop suite contract:** `docs/B2B_WORKSHOP.md`
- **Cowork contract:** `docs/contracts/COWORK.md`
- **Workspaces contract:** `docs/contracts/WORKSPACES.md`
- **Skill SDK contract:** `docs/contracts/SKILL_SDK.md`
- **Marketplace contract:** `docs/contracts/MARKETPLACE.md`
- **Pre-launch security audit:** `docs/security/AUDIT_2026-05-09.md`

---

## Appendix C — Owner glossary

- **Claude** — Anthropic assistant session, this lane. Owns architecture,
  contracts, docs sync, frontend integration, audits, roadmap.
- **Cursor** — neighbor Cursor agent. Owns functional backend implementation
  in shared lanes (algotrade pack, frontend wiring on shared pages).
- **Brother** — meeet.world backend owner. Owns OAuth bridge, magic-link mint,
  Cowork core wiring, Solana escrow, payout rails.
- **Operator** — Alien (alienram@icloud.com). Owns secrets, certs, Cloudflare
  config, GitHub repo, tag pushes, decisions of last resort.

---

**Last opinion before signing off:** the single biggest leverage point in the
next 30 days is **#1 + #2 from the hot list** (Cowork wiring + Apple cert).
Everything else is downstream. If you read nothing else in this doc, do those
two and ship v9.1.1 by 2026-05-28. The rest of the roadmap survives a slip;
those two don't.
