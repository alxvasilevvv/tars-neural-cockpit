/**
 * i18n — single-locale (English) string table for the marketing surface.
 *
 * Wave 70 forced the runtime locale to EN; Wave 72 deleted the dead RU
 * dictionary so a future refactor can't accidentally re-enable a stale
 * translation. The runtime indirection (``useT()``, ``t()``, locale
 * context) is intentionally kept so a future locale can be re-added in
 * one place — the ``STRINGS_BY_LOCALE`` map.
 *
 * Adding strings:
 *   1. Add the key + English value to ``STRINGS_EN`` below.
 *   2. Reference it via ``useT()(key)`` (in components) or ``t(key)``
 *      (in non-component contexts).
 *
 * Interpolation:
 *   useT()("waitlist.position", { n: 1247 })  // → "You're #1247 on the list."
 *
 * **Note:** missing translations fall back to the raw key (which now
 * always equals the English value, since EN is the only locale). The
 * ``pnpm vitest src/lib/i18n.test.ts`` parity guard catches typos.
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STRINGS_EN = {
  // Hero — three-beat sovereignty headline.
  "hero.eyebrow":         "TARS · operator-grade · local-first AI",
  "hero.title.line1":     "Your AI.",
  "hero.title.line2":     "Your machine.",
  "hero.title.line3":     "Your terms.",
  "hero.subline":         "A council of agents at the controls — files, voice, calendar, code, vision, on-chain. Local-first by default; cloud only when you say so.",
  "hero.demo.label":      "live demo · cycles every 4s",
  "hero.cta.cockpit":     "Open cockpit",
  "hero.cta.domains":     "Explore domains",

  // Sticky CTA bar
  "stickyCTA.notify":     "Notify me",
  "stickyCTA.cockpit":    "Open cockpit",
  "stickyCTA.ready":      "ready",

  // Waitlist
  "waitlist.eyebrow":     "pre-launch · waitlist",
  "waitlist.title.lead":  "Be first in line —",
  "waitlist.title.tail":  "ship day",
  "waitlist.body":        "One email, the day the binary drops. No newsletter, no follow-ups, no tracking pixels — see Privacy § 4.",
  "waitlist.email":       "Email address",
  "waitlist.role":        "Role",
  "waitlist.submit":      "Notify me",
  "waitlist.saving":      "Saving",
  "waitlist.success":     "You're on the list.",
  "waitlist.position":    "position #{n}",
  "waitlist.fallback":    "we'll email when binary drops",

  // Cookie consent
  "cookie.title":         "Functional cookies only.",
  "cookie.body":          "Session, theme, language, Cloudflare bot-management. No analytics, no ads, no tracking pixels — full list in",
  "cookie.privacy_link":  "Privacy Policy § 9",
  "cookie.accept":        "Got it",
  "cookie.dismiss":       "Dismiss cookie notice",

  // Footer
  "footer.cta":           "OPEN COCKPIT",
  "footer.col.product":   "Product",
  "footer.col.resources": "Resources",
  "footer.col.company":   "Company",
  "footer.col.connect":   "Connect",
  "footer.systems":       "all systems · 99.97%",
  "footer.trace":         "trace_id ready · contract 1.0.0",
  "footer.legal":         "© 2026 meeet.world · MIT licensed",

  // Toasts
  "toast.recovery.verified": "Recovery phrase verified",

  // Pricing
  "pricing.tag":                   "PRICING",
  "pricing.title":                 "Pay for cloud, not for thinking.",
  "pricing.description":           "Local install is free under MIT. Pro and Business unlock cloud features — T2T, AI Clone, council voting. Pay in dollars or in $MEEET.",
  "pricing.recommended":           "RECOMMENDED",
  "pricing.tier.free.name":        "Free",
  "pricing.tier.free.tagline":     "Local-first, forever.",
  "pricing.tier.free.priceSub":    "MIT, self-hosted",
  "pricing.tier.free.cta":         "Download for Mac",
  "pricing.tier.pro.name":         "Pro",
  "pricing.tier.pro.tagline":      "Your second brain, online.",
  "pricing.tier.pro.priceSub":     "per month",
  "pricing.tier.pro.meeetPrice":   "or 200 $MEEET / mo",
  "pricing.tier.pro.cta":          "Notify me at launch",
  "pricing.tier.business.name":    "Business",
  "pricing.tier.business.tagline": "Teams, audit, control.",
  "pricing.tier.business.priceSub":"per seat / month",
  "pricing.tier.business.cta":     "Talk to sales",
  // Bug #3 from docs/SYSTEM_AUDIT_2026-05-02.md — payments not yet
  // wired (no on-chain SOL / $MEEET checkout yet). Pricing page shows the
  // tiers as a public commitment, but the paid CTAs surface
  // "Coming soon" instead of pretending checkout works. Backend
  // /api/entitlements/upgrade returns 503 feature_disabled in
  // production unless TARS_PAYMENT_MODE=mock|onchain|tokens is set.
  "pricing.comingSoon.badge":      "COMING SOON",
  "pricing.comingSoon.tooltip":    "Paid tiers unlock once SOL / $MEEET on-chain checkout is live. Free tier is fully usable today; subscribe to be notified at launch.",
  "pricing.lifetime.comingSoon":   "Lifetime checkout opens at launch",
  "pricing.lifetime.tag":          "LIFETIME",
  "pricing.lifetime.badge":        "FOUNDERS",
  "pricing.lifetime.priceSub":     "one payment · forever",
  "pricing.lifetime.body":         "Pay once, get every Pro feature for as long as TARS exists — plus the founders edition badge, your handle reserved on T2T, and 1,000 $MEEET dropped to your wallet on launch.",
  "pricing.lifetime.cta":          "Claim lifetime",
  "pricing.footnote":              "Pay in USD via card · or in $MEEET / SOL · cancel anytime · 14-day refund window",

  // FAQ
  "faq.tag":                       "FAQ",
  "faq.title":                     "What people actually ask.",
  "faq.description":               "Real questions from the early access cohort. If something's missing, ping us — we'll add it here, not in a knowledge base no one reads.",
  "faq.summary":                   "14 of 38 questions on this page. Full doc covers privacy, $MEEET, security, audit, roles, roadmap.",
  "faq.link.full":                 "full faq",
  "faq.link.discord":              "join discord",

  // Compare
  "compare.tag":                   "VS",
  "compare.title":                 "How TARS stacks up.",
  "compare.description":           "Cursor owns the IDE. Claude Desktop owns the chat. TARS is the only one that runs your machine, votes between models, and pays you in $MEEET.",
  "compare.col.header":            "feature",
  "compare.col.tars.note":         "this app",
  "compare.col.cursor.note":       "IDE",
  "compare.col.claude.note":       "chat client",
  "compare.footer.disclaimer":     "Comparison reflects publicly documented features as of April 2026. Cursor and Claude Desktop are trademarks of their respective owners.",
  "compare.footer.source":         "Source: docs · pricing pages · changelogs",

  // TrustStrip
  "trust.local.label":             "Local-first",
  "trust.local.detail":            "Your data stays on your Mac",
  "trust.signed.label":            "Signed receipts",
  "trust.signed.detail":           "Every action SHA-256 + Solana memo",
  "trust.opensource.label":        "Open-source",
  "trust.opensource.detail":       "MIT · github.com/meeet-world/tars",
  "trust.sandboxed.label":         "Sandboxed",
  "trust.sandboxed.detail":        "macOS sandbox-exec for code",
  "trust.auditable.label":         "Auditable",
  "trust.auditable.detail":        "trace_id propagation end-to-end",
  "trust.edge.label":              "Edge LLM",
  "trust.edge.detail":             "Ollama / LM Studio first-class",

  // MeetTars
  "meetTars.eyebrow":              "Meet TARS",
  "meetTars.title.lead":           "Two voices.",
  "meetTars.title.tail":           "One verdict",
  "meetTars.body":                 "TARS is the persona for your local cockpit. Two-voice council decides the action, policy gate guards the destructive ones, every execution drops a signed receipt anchored to Solana memo.",
  "meetTars.draftedIn":            "drafted in {ms}",
  "meetTars.live.label":           "TARS · LIVE on this machine",
  "meetTars.live.demo":            "TARS · demo mode",
  "meetTars.live.cta":             "Daemon detected on localhost — try a real prompt",
  "meetTars.live.openCockpit":     "open cockpit",

  // DomainsCards
  "domains.traders.name":          "Traders",
  "domains.traders.teaser":        "Markets and signals at the speed of a thought.",
  "domains.business.name":         "Business",
  "domains.business.teaser":       "A second brain for your operating cadence.",
  "domains.entrepreneur.name":     "Entrepreneur",
  "domains.entrepreneur.teaser":   "Pipeline, leads and outreach — all in one rhythm.",
  "domains.science.name":          "Science",
  "domains.science.teaser":        "From paper pile to citation-aware council.",

  // Onboarding stepper
  "onboarding.step.signin":        "sign in",
  "onboarding.step.role":          "pick role",
  "onboarding.step.brief":         "first brief",

  // Onboarding step 0
  "onboarding.s0.title.lead":      "Sign in, or",
  "onboarding.s0.title.tail":      "stay local",
  "onboarding.s0.body":            "Sign-in unlocks T2T, AI Clone, council voting and $MEEET earn. You can skip and stay 100% local — TARS still runs everything on-device.",
  "onboarding.s0.wallet.title":    "Solana wallet",
  "onboarding.s0.wallet.detail":   "Phantom · Backpack · Solflare",
  "onboarding.s0.email.title":     "Email magic-link",
  "onboarding.s0.email.detail":    "We send a one-time link — no password ever.",
  "onboarding.s0.skip":            "Skip — stay 100% local",

  // Onboarding step 1
  "onboarding.s1.title.lead":      "Pick your",
  "onboarding.s1.title.tail":      "role",
  "onboarding.s1.body":            "Same neural core, six crafts plus your own. Switch later from the cockpit at any time — your data stays put.",
  "onboarding.role.founder.name":     "Founder / CEO",
  "onboarding.role.founder.desc":     "Daily brief from KPI + deals + calendar. Council on every send.",
  "onboarding.role.trader.name":      "Trader",
  "onboarding.role.trader.desc":      "Markets, signals, risk. Live across exchanges.",
  "onboarding.role.researcher.name":  "Researcher",
  "onboarding.role.researcher.desc":  "arXiv-aware. Citation-graph across your projects.",
  "onboarding.role.marketer.name":    "Marketer",
  "onboarding.role.marketer.desc":    "Outreach drafts in your voice. Engagement signals across channels.",
  "onboarding.role.engineer.name":    "Engineer",
  "onboarding.role.engineer.desc":    "Repos indexed. PR review queue. Code RAG over your stack.",
  "onboarding.role.operator.name":    "Operator",
  "onboarding.role.operator.desc":    "Generalist — full cockpit, all packs. Default if you skip.",
  "onboarding.s1.custom.name":        "Custom — describe your work",
  "onboarding.s1.custom.badge":       "· AI Clone trains on you",
  "onboarding.s1.custom.desc":        "Name your role, give it a 1-3 sentence description, and TARS synthesises a system prompt overlay. Your AI Clone learns from the first 50 interactions.",
  "onboarding.s1.custom.continue":    "Continue with custom role",

  // Onboarding custom role modal
  "onboarding.modal.eyebrow":          "07 / custom role",
  "onboarding.modal.title":            "Describe your work — TARS does the rest.",
  "onboarding.modal.body":             "We synthesise a system prompt overlay for the council and seed the AI Clone training set. Stored locally; you can edit later.",
  "onboarding.modal.name.label":       "Role name",
  "onboarding.modal.name.placeholder": "Sales Director",
  "onboarding.modal.desc.label":       "What you actually do",
  "onboarding.modal.desc.help":        "min 24 chars · sample tasks help",
  "onboarding.modal.cancel":           "Cancel",
  "onboarding.modal.save":             "Save role",

  // Onboarding step 2
  "onboarding.s2.role":            "Role:",
  "onboarding.s2.status":          "WIRING SOURCES",
  "onboarding.s2.title.lead":      "Drafting your first",
  "onboarding.s2.title.tail":      "briefing",
  "onboarding.s2.body":            "TARS is reading the sources you connected. Council is calibrating tone. ~60 seconds. You can close this tab — the daemon keeps going.",
  "onboarding.s2.cta":             "Open cockpit",

  // Press kit
  "press.eyebrow":                       "press kit",
  "press.title.lead":                    "For journalists, partners,",
  "press.title.tail":                    "and people writing about TARS.",
  "press.body":                          "Use anything from this page in articles, decks, or product listings. License: CC-BY for boilerplate, all-rights-reserved for the trademarks (don't modify the marks).",
  "press.section.boilerplate.tag":       "boilerplate",
  "press.section.boilerplate.title":     "Copy-paste descriptions",
  "press.section.brand.tag":             "brand",
  "press.section.brand.title":           "Color palette",
  "press.section.brand.body":            "Triad — indigo / violet / brand cyan — on OLED black. Two accent colours max in any single composition. Indigo dominates, violet and cyan accent.",
  "press.section.assets.tag":            "assets",
  "press.section.assets.title":          "Logo + social card",
  "press.section.facts.tag":             "facts",
  "press.section.facts.title":           "Quick facts",
  "press.section.contact.tag":           "contact",
  "press.section.contact.title":         "Press contacts",

  // Build-with badge generator
  "buildWith.eyebrow":             "build with TARS",
  "buildWith.title.lead":          "Stick the badge.",
  "buildWith.title.tail":          "Get the credit",
  "buildWith.body":                "Shipped something on top of TARS? Drop the badge into your README, blog post, or project site. Self-contained SVG — no external requests, no tracking. Free for any project, MIT or proprietary.",
  "buildWith.size.label":          "Size",
  "buildWith.size.full":           "Full · 120px",
  "buildWith.size.compact":        "Compact · 80px",
  "buildWith.theme.label":         "Theme",
  "buildWith.theme.dark":          "Dark · OLED",
  "buildWith.theme.light":         "Light · paper",
  "buildWith.link.label":          "Override link (optional — defaults to meeet.world)",
  "buildWith.preview":             "Preview",
  "buildWith.usage.title":         "Usage",
  "buildWith.examples.title":      "Where it goes",
  "buildWith.footer":              "Tag your repo with",
  "buildWith.footer.tail":         "and we'll feature it in the marketplace.",

  // CockpitGate — guards /cockpit* routes when daemon unreachable.
  "cockpitGate.eyebrow":           "cockpit · meeet.world · runtime check",
  "cockpitGate.status.lozenge":    "DAEMON OFFLINE",
  "cockpitGate.title.lead":        "The cockpit lives on",
  "cockpitGate.title.tail":        "your machine",
  "cockpitGate.body":               "TARS is local-first by design — every action runs against the daemon at 127.0.0.1:8765. Your browser can show the marketing surface, but the live operator console needs the desktop app installed. Install once, then this page becomes your real cockpit.",
  "cockpitGate.probing":            "checking for local daemon…",
  "cockpitGate.cta.eyebrow":        "primary action · auto-detected for your OS",
  "cockpitGate.cta.mac":            "Install TARS for macOS",
  "cockpitGate.cta.linux":          "Install TARS for Linux",
  "cockpitGate.cta.windows":        "Install TARS for Windows",
  "cockpitGate.cta.detail":         "free · MIT · 60-second setup · no telemetry",
  "cockpitGate.cta.button":         "Get the app",
  "cockpitGate.feature.local":      "Local-first",
  "cockpitGate.feature.signed":     "Signed receipts",
  "cockpitGate.feature.meeet":      "meeet.world bridge",
  "cockpitGate.alt.preview.eyebrow":"preview mode",
  "cockpitGate.alt.preview.title":  "Browse a read-only demo",
  "cockpitGate.alt.preview.body":   "Wireframe of the operator console with mocked traces. No daemon, no destructive actions, just the layout.",
  "cockpitGate.alt.docs.eyebrow":   "docs",
  "cockpitGate.alt.docs.title":     "Read the docs first",
  "cockpitGate.alt.docs.body":      "Architecture, domain packs, meeet bridge, the trace contract. Browse before installing.",
  "cockpitGate.alt.pitch.eyebrow":  "pitch",
  "cockpitGate.alt.pitch.title":    "See the 60-second pitch",
  "cockpitGate.alt.pitch.body":     "Why local-first beats SaaS chat. Why the meeet.world bridge matters. Why $MEEET pays you back.",
  "cockpitGate.footer.probe":       "probed",

  // Install page (rebuilt 2026-05-04 — big primary download CTA + Gatekeeper fix).
  "install.eyebrow":               "install · meeet.world · 1-click",
  "install.title.lead":            "Install TARS in",
  "install.title.tail":            "one click",
  "install.body":                  "Local install, free under MIT, released by meeet.world. No telemetry, no cloud account required. macOS, Linux, Windows — pick yours and we serve the matching binary.",
  "install.primary.label":         "primary download · auto-detected",
  "install.primary.mac":           "Download for macOS",
  "install.primary.linux":         "Download for Linux",
  "install.primary.windows":       "Download for Windows",
  "install.primary.cta":           "Download",
  "install.copy":                  "Copy",
  "install.copied":                "Copied",
  "install.private_github.banner":
    "Installer links currently point at GitHub Releases. While the repo is private, downloads may fail unless you are logged into GitHub — use Homebrew or the install.sh one-liner below as a fallback.",
  "install.gatekeeper.title":     "First time on macOS? Run this once after install.",
  "install.gatekeeper.body":      "Apple Gatekeeper flags binaries from non-paying developers as 'damaged'. The command below removes the quarantine flag — same one Apple uses for every signed app. We will notarize after public launch (Apple Developer Program, $99/yr).",
  "install.gatekeeper.alt":       "Prefer one curl line that does everything (download · install · de-quarantine · launch)?",
  "install.gatekeeper.alt.cta":   "copy the install.sh one-liner",
  "install.trust.local":          "Local-first",
  "install.trust.mit":            "MIT licensed",
  "install.trust.sandbox":        "Sandboxed",
  "install.trust.setup":          "60s setup",
  "install.advanced.show":        "Advanced · curl · brew · all assets",
  "install.advanced.hide":        "Hide advanced options",
  "install.advanced.curl.label":  "one-liner · downloads, signs, removes quarantine, launches",
  "install.advanced.brew.label":  "homebrew · pin to a tap and `brew upgrade` along with everything else",
  "install.advanced.assets.label":"all release assets · pick a specific format",
  "install.advanced.assets.download": "Download",
  "install.steps.eyebrow":        "WHAT HAPPENS AFTER",
  "install.steps.title":          "Four steps from download to your first briefing.",
  "install.steps.step":           "step",
  "install.steps.s1.title":       "Open the file you just downloaded",
  "install.steps.s1.body":        "macOS: drag TARS into Applications. Linux: AppImage runs as-is (chmod +x once). Windows: double-click the MSI. The first launch shows the Gatekeeper warning above — run the one-line fix.",
  "install.steps.s2.title":       "Sign in with magic-link (optional)",
  "install.steps.s2.body":        "Open meeet.world/auth in your browser, scan a QR with your wallet (or use email magic-link). The token gets handed back to the local agent over a one-shot localhost callback. Skip if you want to stay 100% local.",
  "install.steps.s3.title":       "Pick your domain pack",
  "install.steps.s3.body":        "Traders, business, entrepreneur, science. You can switch later. The pack tunes the daily briefing template, the council prompts, and the suggested skills.",
  "install.steps.s4.title":       "First Daily Briefing in 60 seconds",
  "install.steps.s4.body":        "TARS reads your calendar, mail and starred repos (only the sources you connect), drafts a one-page briefing, and asks two questions to calibrate tone. Every action emits a meeet trace receipt under your trace_id.",

  // Common chrome
  "common.back":                   "back to home",

  // Cockpit chat — operator-facing strings on the highest-visibility surfaces.
  "chat.composer.placeholder":     "message TARS — ⌘↵ to send · drop files to ground answers",
  "chat.threads.empty":            "no threads yet — start a conversation to populate the list",

  // Bug #5 — locale switcher (small public-facing UI element)
  "locale.label":                  "Language",
  "locale.en":                     "English",
  "locale.ru":                     "Russian",

  // Trace viewer (/cockpit/traces) — IDEAS #15 + audit follow-up.
  "traces.title":                  "Local trace viewer",
  "traces.eyebrow":                "operator // traces",
  "traces.subtitle":               "Every action TARS performs flows through the local meeet bridge. Each row is one trace_id rolled up — kind / route / cost / duration / contradictions.",
  "traces.refresh":                "Refresh",
  "traces.rebuild":                "Rebuild rollup",
  "traces.rebuilding":             "Rebuilding…",
  "traces.refreshing":             "Refreshing…",
  "traces.empty.title":            "No traces yet.",
  "traces.empty.body":             "Run a playbook, fire an action, or hit any cloud-touching endpoint — the trace will land here.",
  "traces.error.title":            "Trace viewer offline",
  "traces.error.hint":             "Check that the TARS daemon is up at",
  "traces.filter.route":           "route",
  "traces.filter.route.all":       "all",
  "traces.filter.route.edge":      "edge",
  "traces.filter.route.cloud":     "cloud",
  "traces.filter.route.fallback":  "fallback",
  "traces.filter.route.mixed":     "mixed",
  "traces.filter.search":          "filter by trace_id / kind / session",
  "traces.col.trace":              "trace_id",
  "traces.col.kinds":              "kinds",
  "traces.col.route":              "route",
  "traces.col.cost":               "cost",
  "traces.col.tokens":             "tokens",
  "traces.col.duration":           "duration",
  "traces.col.errors":             "errors",
  "traces.col.started":            "started",
  "traces.detail.eyebrow":         "trace detail",
  "traces.detail.events":          "events ({n})",
  "traces.detail.copy":            "Copy trace_id",
  "traces.detail.copied":          "Copied",
  "traces.detail.session":         "session_id",
  "traces.detail.contradictions":  "contradictions",
  "traces.detail.empty":           "Pick a trace from the rail to drill into the events.",
  "traces.unit.ms":                "ms",
  "traces.unit.s":                 "s",
  "traces.unit.usd":               "USD",

  // Cockpit nav additions (links to operator pages)
  "cockpit.nav.traces":            "traces",
  "cockpit.nav.policy":            "policy",
  "cockpit.nav.council":           "council",

  // Council debug page (/cockpit/council) — IDEAS #18.
  "council.title":                 "Council debug",
  "council.eyebrow":               "operator // council",
  "council.subtitle":              "Two voices, one verdict. Stage a deliberation against the local + cloud voices, watch the diff, and replay decisions from the meeet trail.",
  "council.run":                   "Deliberate",
  "council.running":               "Deliberating…",
  "council.refresh":               "Refresh history",
  "council.form.prompt":           "Prompt",
  "council.form.prompt.placeholder":"interpret morning market — risk-on or off?",
  "council.form.context":          "Context (JSON)",
  "council.form.context.placeholder":"{\"topic\":\"market\",\"avg_change_24h\":-0.8}",
  "council.form.mode":             "Mode",
  "council.form.mode.single":      "single",
  "council.form.mode.dual_vote":   "dual_vote",
  "council.form.mode.n_vote":      "n_vote",
  "council.form.invalidJson":      "Context is not valid JSON — using {}.",
  "council.history.title":         "Recent deliberations",
  "council.history.empty":         "No deliberations logged yet — stage one to populate the timeline.",
  "council.history.loading":       "loading sampler.decision events…",
  "council.error.title":           "Council unreachable",
  "council.error.hint":            "Check that the TARS daemon is up at",
  "council.detail.empty.title":    "No deliberation rendered yet.",
  "council.detail.empty.body":     "Stage a deliberation on the left, or click a row in the history to replay it.",
  "council.detail.eyebrow":        "deliberation detail",
  "council.detail.chosen":         "chosen stance",
  "council.detail.agreement":      "agreement",
  "council.detail.contradictions": "contradictions",
  "council.detail.contradictions.none":"no contradictions surfaced",
  "council.detail.rationale":      "rationale",
  "council.detail.tokens":         "tokens",
  "council.detail.latency":        "latency",
  "council.detail.voices":         "voices ({n})",
  "council.detail.winner":         "highest confidence",
  "council.voice.summary":         "summary",
  "council.voice.actions":         "recommended actions",
  "council.voice.confidence":      "confidence",
  "council.voice.unavailable":     "voice unavailable — missing key or transport offline",

  // Policy inbox (/cockpit/policy) — IDEAS #29 follow-up.
  "policy.title":                  "Approval inbox",
  "policy.eyebrow":                "operator // policy",
  "policy.subtitle":               "Every destructive action stages here for an explicit confirm or cancel. Tokens expire automatically; resolved tokens stay in the audit lane below.",
  "policy.refresh":                "Refresh",
  "policy.expire":                 "Expire stale",
  "policy.expiring":               "Expiring…",
  "policy.tab.pending":            "pending",
  "policy.tab.recent":             "recent",
  "policy.empty.pending.title":    "No pending confirmations.",
  "policy.empty.pending.body":     "Destructive actions land here for review. The autopilot policy mode skips this queue entirely; switch to confirm-mode to see them stage.",
  "policy.empty.recent.title":     "No resolved confirmations yet.",
  "policy.empty.recent.body":      "Once tokens are confirmed, cancelled, or expired they appear in this audit lane.",
  "policy.error.title":            "Policy gate offline",
  "policy.error.hint":             "Check that the TARS daemon is up at",
  "policy.action.confirm":         "Confirm",
  "policy.action.cancel":          "Cancel",
  "policy.action.confirming":      "Confirming…",
  "policy.action.cancelling":      "Cancelling…",
  "policy.action.copy":            "Copy token",
  "policy.action.copied":          "Copied",
  "policy.filter.search":          "filter by token / slug / action / requested_by",
  "policy.col.action":             "action",
  "policy.col.token":              "token",
  "policy.col.created":            "created",
  "policy.col.expires":            "expires",
  "policy.col.requestedBy":        "requested by",
  "policy.col.trace":              "trace_id",
  "policy.col.args":               "arguments",
  "policy.col.result":             "result",
  "policy.col.status":             "status",
  "policy.detail.empty":           "Pick a confirmation from the rail to inspect.",
  "policy.detail.eyebrow":         "confirmation detail",
  "policy.detail.armed":           "Confirming this token will execute the action immediately under your operator identity.",
  "policy.confirm.modal.title":    "Confirm destructive action?",
  "policy.confirm.modal.body":     "This will run {action} with the staged arguments and emit a meeet receipt under trace_id {trace}. There is no undo.",
  "policy.confirm.modal.proceed":  "Yes, run it",
  "policy.confirm.modal.cancel":   "Cancel",
  "policy.status.pending":         "pending",
  "policy.status.confirmed":       "confirmed",
  "policy.status.cancelled":       "cancelled",
  "policy.status.expired":         "expired",
  "policy.status.failed":          "failed",

  // Operator command palette (⌘. / Ctrl+. on /cockpit) — IDEAS #20.
  "operator.palette.title":        "Operator palette",
  "operator.palette.placeholder":  "jump to a pack · invoke an action · run a playbook · snapshot awareness · open a trace",
  "operator.palette.hint.opener":  "press · to open from the cockpit",
  "operator.palette.recent":       "Recent",
  "operator.palette.empty.title":  "No matches.",
  "operator.palette.empty.body":   "Try a slug, action id, or playbook name.",
  "operator.palette.loading":      "loading operator index…",
  "operator.palette.error":        "Some panes failed to load — partial index shown.",
  "operator.palette.error.detail": "{group}: {message}",
  "operator.palette.group.packs":     "packs",
  "operator.palette.group.actions":   "actions",
  "operator.palette.group.playbooks": "playbooks",
  "operator.palette.group.awareness": "awareness",
  "operator.palette.group.traces":    "traces",
  "operator.palette.group.all":       "all",
  "operator.palette.kind.pack":       "pack",
  "operator.palette.kind.action":     "action",
  "operator.palette.kind.playbook":   "playbook",
  "operator.palette.kind.awareness":  "awareness",
  "operator.palette.kind.trace":      "trace",
  "operator.palette.invoke":          "invoke",
  "operator.palette.snapshot":        "snapshot",
  "operator.palette.run":             "run",
  "operator.palette.open":            "open",
  "operator.palette.invoking":        "invoking…",
  "operator.palette.snapshotting":    "snapshotting…",
  "operator.palette.running":         "running…",
  "operator.palette.confirm.staged":  "Action staged for approval — open the policy inbox to confirm.",
  "operator.palette.invoked.ok":      "Action completed in {ms} ms.",
  "operator.palette.invoked.fail":    "Action failed: {message}",
  "operator.palette.snapshot.ok":     "Snapshot fetched in {ms} ms.",
  "operator.palette.snapshot.fail":   "Snapshot failed: {message}",
  "operator.palette.run.ok":          "Playbook completed: {steps} steps in {ms} ms.",
  "operator.palette.run.fail":        "Playbook failed: {message}",
  "operator.palette.run.blocked":     "Playbook blocked on a destructive step — open the policy inbox to approve.",
  "operator.palette.destructive":     "destructive",
  "operator.palette.refresh":         "refresh index",
  "operator.palette.refreshing":      "refreshing…",
  "operator.palette.shortcut.open":   "{key}",
  "operator.palette.shortcut.label":  "open",
  "operator.palette.footer.nav":      "↑↓ navigate",
  "operator.palette.footer.invoke":   "↵ activate",
  "operator.palette.footer.close":    "esc · close",
  "operator.palette.footer.count":    "{n} items",
  "cockpit.nav.operator":             "operator",

  // Awareness explorer (/cockpit/awareness) — IDEAS #30 follow-up.
  "awareness.title":               "Awareness explorer",
  "awareness.eyebrow":             "operator // awareness",
  "awareness.subtitle":            "Browse every awareness source TARS exposes per pack. Snapshot live feeds on demand and drill into the raw data behind every cockpit ticker.",
  "awareness.refresh":             "Refresh packs",
  "awareness.refreshing":          "Refreshing…",
  "awareness.snapshot.run":        "Snapshot",
  "awareness.snapshot.running":    "Snapshotting…",
  "awareness.snapshot.live":       "live",
  "awareness.snapshot.config":     "config-only",
  "awareness.summary.packs":       "{packs} packs · {sources} sources",
  "awareness.error.title":         "Domain registry offline",
  "awareness.error.hint":          "Check that the TARS daemon is up at",
  "awareness.empty.packs.title":   "No packs registered.",
  "awareness.empty.packs.body":    "Activate a domain pack from the cockpit or the role picker — its awareness sources will appear here.",
  "awareness.empty.sources.title": "No awareness sources for this pack.",
  "awareness.empty.sources.body":  "This pack ships actions only — open it in the operator palette to invoke them directly.",
  "awareness.search.placeholder":  "filter sources by id, name, kind, or description",
  "awareness.detail.empty.title":  "No snapshot yet.",
  "awareness.detail.empty.body":   "Pick a source on the left and hit Snapshot to fetch live data through the meeet trace bridge.",
  "awareness.detail.eyebrow":      "snapshot detail",
  "awareness.detail.took":         "took",
  "awareness.detail.fetched":      "fetched",
  "awareness.detail.trace":        "trace",
  "awareness.detail.config.title": "source config",
  "awareness.detail.data.title":   "snapshot data",
  "awareness.detail.error.title":  "Snapshot failed",
  "awareness.detail.error.hint":   "The fetcher raised an error. Check the daemon logs for the trace_id.",
  "awareness.detail.unavailable":  "config-only source — no live snapshot is implemented yet",
  "awareness.col.kind":            "kind",
  "awareness.col.name":            "name",
  "awareness.col.fetched":         "fetched",
  "awareness.col.took":            "took",
  "awareness.unit.ms":             "ms",
  "awareness.unit.s":              "s",
  "cockpit.nav.awareness":         "awareness",

  // Steps section (audit-4 i18n coverage — Landing).
  "steps.head.tag":                "FLOW",
  "steps.head.title":              "Drop. Cluster. Specialise.",
  "steps.head.description":        "Drop any folder. TARS embeds, clusters, and wires it into a graph you can navigate at the speed of thought.",
  "steps.s1.title":                "Drop folders & files",
  "steps.s1.body":                 "MD, PDF, code, audio. Local indexing, no upload.",
  "steps.s1.cue":                  "drop · scan · index",
  "steps.s2.title":                "Embed & cluster",
  "steps.s2.body":                 "Six awareness layers light up. Each cluster picks a place in the graph.",
  "steps.s2.cue":                  "embed · cluster · pin",
  "steps.s3.title":                "Pick a domain pack",
  "steps.s3.body":                 "The core specialises into a tool for your craft — traders, business, entrepreneur or science.",
  "steps.s3.cue":                  "specialise · arm · run",

  // Rail section (live awareness streams ticker).
  "rail.aria":                     "live awareness streams",
  "rail.live":                     "LIVE",
  "rail.core":                     "SK-09 / CORE",
  "rail.stream.concept":           "concept",
  "rail.stream.memory":            "memory",
  "rail.stream.code":              "code",
  "rail.stream.calendar":          "calendar",
  "rail.stream.mac":               "mac",
  "rail.stream.voice":             "voice",
  "rail.metric.integrity":         "integrity",
  "rail.metric.streams":           "streams",
  "rail.metric.latency":           "latency",
  "rail.unit.ms":                  "ms",
  "rail.unit.percent":             "%",

  // CockpitLive — embedded live cockpit preview.
  "cockpitLive.eyebrow":           "04 / cockpit · live preview",
  "cockpitLive.live":              "LIVE",
  "cockpitLive.title.prefix":      "What you see after",
  "cockpitLive.title.gradient":    "install",
  "cockpitLive.cta.openReal":      "Open the real one",
  "cockpitLive.chrome.title":      "tars · cockpit · localhost:8765",
  "cockpitLive.booting":           "booting cockpit…",
  "cockpitLive.badge.live":        "LIVE · interaction disabled",
  "cockpitLive.footer.note":       "This is the actual cockpit running on your local TARS daemon — embedded read-only. Your data, your machine.",
  "cockpitLive.footer.cta":        "interact in full →",

  // Layers — six awareness streams (audit-5 i18n batch).
  "layers.head.tag":               "AWARENESS",
  "layers.head.title":             "Six streams, one graph.",
  "layers.head.description":       "Every signal lands on the core and gets clustered into the graph. No upload — local-first by default.",
  "layers.signal.prefix":          "signal",
  "layers.l1.tag":                 "concept",
  "layers.l1.title":               "Knowledge graph",
  "layers.l1.body":                "Files, docs and threads embedded into a graph. The concept layer is the spine.",
  "layers.l2.tag":                 "memory",
  "layers.l2.title":               "Long-term recall",
  "layers.l2.body":                "Decisions, names, projects pinned to a shell that orbits the concept core.",
  "layers.l3.tag":                 "code",
  "layers.l3.title":               "Repo awareness",
  "layers.l3.body":                "Codebases linked into the graph as a tight, ordered arm — symbol-aware.",
  "layers.l4.tag":                 "calendar",
  "layers.l4.title":               "Time-aware context",
  "layers.l4.body":                "Events become time-anchored nodes that fire when relevant.",
  "layers.l5.tag":                 "mac actions",
  "layers.l5.title":               "Hands on the OS",
  "layers.l5.body":                "Open, type, click, automate — under explicit policy.",
  "layers.l6.tag":                 "voice",
  "layers.l6.title":               "Always-on listener",
  "layers.l6.body":                "Voice intents threaded through every other layer.",

  // Domains — pack picker.
  "domains.head.tag":              "PACKS",
  "domains.head.title":            "Same core, four crafts.",
  "domains.head.description":      "Plug-in packs that turn the neural core into a focused tool — traders, business, entrepreneur, science. Hover a node to inspect.",
  "domains.armed":                 "ARMED",
  "domains.throughput.normal":     "throughput · normal",
  // NOTE: ``domains.<slug>.name`` keys already live in the
  // DomainsCards block above — don't redeclare here, just
  // reference them from the Domains pack picker.
  "domains.traders.title":         "Markets and signals at the speed of a thought.",
  "domains.traders.b1":            "Live market awareness across exchanges and feeds.",
  "domains.traders.b2":            "Signal generation with explainable model votes.",
  "domains.traders.b3":            "Risk and portfolio actions guarded by policy.",
  "domains.business.title":        "A second brain for your operating cadence.",
  "domains.business.b1":           "Deals, contacts and revenue across mail and CRM.",
  "domains.business.b2":           "KPI nodes auto-update from your data sources.",
  "domains.business.b3":           "Daily brief composed by the council each morning.",
  "domains.entrepreneur.title":    "Pipeline, leads and outreach — all in one rhythm.",
  "domains.entrepreneur.b1":       "Pipeline depth, activity and churn tracked live.",
  "domains.entrepreneur.b2":       "Outreach playbooks tuned to your tone of voice.",
  "domains.entrepreneur.b3":       "Auto content drafts across IG, TG, WA, email.",
  "domains.science.title":         "From paper pile to citation-aware council.",
  "domains.science.b1":            "arXiv, Crossref and Semantic Scholar awareness.",
  "domains.science.b2":            "Equation and dataset graph across your projects.",
  "domains.science.b3":            "Hypothesis trees with model-voted evidence.",

  // ProofStrip — count-up stat row.
  "proof.aria":                    "product proof points",
  "proof.s1.label":                "AI agents",
  "proof.s1.caption":              "Specialised + composable",
  "proof.s2.label":                "Domain packs",
  "proof.s2.caption":              "Traders · Business · Science · …",
  "proof.s3.label":                "LLM providers",
  "proof.s3.caption":              "Anthropic · OpenAI · local",
  "proof.s4.label":                "Local-first",
  "proof.s4.caption":              "Your machine, your data",

  // MeeetSection — three pillars (Wallet, $MEEET, T2T).
  "meeetSection.eyebrow":          "05 / meeet",
  "meeetSection.title.prefix":     "Plugged into",
  "meeetSection.subtitle":         "TARS isn't a standalone app — it's the local edge of the meeet.world economy. Wallet, payouts, agent commerce, all native.",
  "meeetSection.p1.tag":           "WALLET",
  "meeetSection.p1.title":         "Sign in with Solana, not email.",
  "meeetSection.p1.body":          "Phantom / Backpack connect. One TARS instance per wallet. Keys stay on your device, never round-trip through meeet.world.",
  "meeetSection.p1.statNum":       "0",
  "meeetSection.p1.statLabel":     "credentials stored server-side",
  "meeetSection.p2.tag":           "$MEEET",
  "meeetSection.p2.title":         "Earn while your agent works.",
  "meeetSection.p2.body":          "Every signed action drops $MEEET into your wallet. Council votes, awareness fetches, T2T deals — all metered, all paid out on-chain weekly.",
  "meeetSection.p2.statNum":       "12.4",
  "meeetSection.p2.statLabel":     "$MEEET / active week (avg)",
  "meeetSection.p3.tag":           "T2T",
  "meeetSection.p3.title":         "Your agent talks to my agent.",
  "meeetSection.p3.body":          "Agent-to-agent marketplace with escrow + Solana memo anchoring. Send a handshake, lock $MEEET, deliver work, receive payment automatically.",
  "meeetSection.p3.statNum":       "92%",
  "meeetSection.p3.statLabel":     "deals settled in <24h",

  // ── audit-6 · remaining Landing (no Apple) ─────────────────────
  // Section dividers on `/` (between major blocks).
  // Wave 66 — sections renumbered after cockpit removal.
  // Old: 00..11 with 05="cockpit". New: 00..10 (sequential, no gaps).
  "landing.section.00":            "00 / persona",
  "landing.section.01":            "01 / awareness",
  "landing.section.02":            "02 / packs",
  "landing.section.03":            "03 / how",
  "landing.section.04":            "04 / flow",
  "landing.section.05":            "05 / meeet",
  "landing.section.06":            "06 / council",
  "landing.section.07":            "07 / vs",
  "landing.section.08":            "08 / pricing",
  "landing.section.09":            "09 / waitlist",
  "landing.section.10":            "10 / faq",

  // MeeetWorldStrip — issuer card + footer variant.
  "meeetStrip.footer.issuedBy":    "issued by",
  "meeetStrip.footer.contract":    "contract {version}",
  "meeetStrip.card.kicker":        "issuer · sync · economy",
  "meeetStrip.card.brand":         "meeet.world",
  "meeetStrip.status.checking":    "checking…",
  "meeetStrip.status.online":      "daemon online · contract {version}",
  "meeetStrip.status.offline":     "daemon offline · stays local-only",
  "meeetStrip.cta.signIn":         "Sign in",
  "meeetStrip.cta.account":        "Account",

  // ScrollStory — scroll-pinned `/` narrative.
  "scrollStory.aria":              "how TARS works, scroll-driven",
  "scrollStory.head.num":          "04",
  "scrollStory.head.eyebrow":      "how it works",
  "scrollStory.head.title.before": "Four ways TARS pays for itself ",
  "scrollStory.head.title.grad":   "before lunch",
  "scrollStory.head.subtitle":
    "Scroll the panel — each feature unfolds in place. No app-switching, no chat-window soup, no cloud lock-in.",

  "scrollStory.s1.eyebrow":        "DAILY BRIEFING",
  "scrollStory.s1.title":
    "See everything you missed —\nbefore your first coffee.",
  "scrollStory.s1.body":
    "TARS reads your calendar, inbox, GitHub, and Slack overnight, then hands you a single brief at sign-in. No app-switching, no ten-tab triage. The cockpit shows what changed, what's blocking, and what to do first.",

  "scrollStory.s2.eyebrow":        "WATCH ME WORK",
  "scrollStory.s2.title":
    "Every action, on your screen,\nin real time.",
  "scrollStory.s2.body":
    "Background TARS doesn't run in a black box. The cockpit streams a verbose timeline as your agent moves files, drafts replies, or runs code. Pause it, replay it, or anchor a receipt to Solana — your choice, every step.",

  "scrollStory.s3.eyebrow":        "MEMORY THAT COMPOUNDS",
  "scrollStory.s3.title":
    "Your AI clone gets sharper\nevery week.",
  "scrollStory.s3.body":
    "TARS captures how you write, decide, and triage. A weekly reflection summarises what was learned and asks for confirmation before adopting new patterns. After three weeks, your AI Clone drafts replies that sound like you — opt-in, audited, deletable.",

  "scrollStory.s4.eyebrow":        "YOUR DATA, YOUR MACHINE",
  "scrollStory.s4.title":
    "Local-first, end-to-end,\nzero-knowledge sync.",
  "scrollStory.s4.body":
    "Master keyring lives in macOS Keychain or Windows DPAPI. meeet.world only ever sees ciphertext — XChaCha20-Poly1305 + X25519, contract 1.1.0. You hold the recovery seed. You can pair a second device or revoke access in one click.",

  // CouncilDemo — dual-vote visual on `/` (keys namespaced so /council page keeps `council.eyebrow` / `council.subtitle`).
  "councilDemo.eyebrow":               "06 / council",
  "council.title.before":          "Two voices, ",
  "council.title.grad":            "one verdict",
  "councilDemo.subtitle":
    "Every action passes through a council vote. Anthropic and OpenAI deliberate in parallel — confidence, latency, tokens, all logged. The operator sees both proposals before anything destructive runs.",
  "council.dualVote":              "dual-vote",
  "council.confidence":            "Confidence",
  "council.agreement":             "agreement",
  "council.tok":                   "tok",

  "council.d1.prompt":
    "Should I auto-reply to Sasha's draft?",
  "council.d1.rationale":
    "Higher-confidence voice wins under split votes. Policy gate set to confirm for outbound iMessage.",
  "council.d1.v0.stance":          "draft + hold",
  "council.d1.v0.summary":
    "Compose the reply but pause before send. The original is technical and needs your sign-off.",
  "council.d1.v1.stance":          "draft + send",
  "council.d1.v1.summary":
    "Reply directly. Sasha's prompt is procedural — confirmation overhead would break the flow.",

  "council.d2.prompt":
    "Sort ~/Downloads — auto or dry-run first?",
  "council.d2.rationale":
    "Strong agreement. Both voices voted auto. Default handler chosen.",
  "council.d2.v0.stance":          "auto",
  "council.d2.v0.summary":
    "Operation is reversible (move within same volume), low risk. Run, drop receipt, offer undo.",
  "council.d2.v1.stance":          "auto",
  "council.d2.v1.summary":
    "Sort by extension category. Receipt with full file map. Undo via reverse-receipt within 10 minutes.",

  "council.d3.prompt":
    "Run the playbook quarterly_close.json now?",
  "council.d3.rationale":
    "Both blocked. Policy gate confirms — operator must press Run.",
  "council.d3.v0.stance":          "block",
  "council.d3.v0.summary":
    "Playbook touches send_email + payment.transfer. Both are high-risk. Require explicit run.",
  "council.d3.v1.stance":          "block",
  "council.d3.v1.summary":
    "High-risk chain. Schedule for end-of-day with confirm prompts on each destructive step.",

  // CockpitPreview — static mock chrome (offline marketing fallback).
  "cockpitPreview.eyebrow":        "04 / cockpit preview",
  "cockpitPreview.chromeTitle":    "tars · cockpit · 127.0.0.1:8765",
  "cockpitPreview.live":           "live",
  "cockpitPreview.domainPacks":    "domain packs",
  "cockpitPreview.actions":        "{n} actions",
  "cockpitPreview.connectors":     "connectors",
  "cockpitPreview.phase.routing":  "Routing",
  "cockpitPreview.phase.tool":     "Tool",
  "cockpitPreview.phase.drafting": "Drafting",
  "cockpitPreview.phase.done":     "Done",
  "cockpitPreview.greeting":       "Good morning, Alien.",
  "cockpitPreview.briefMeta":
    "Tuesday, 28 April · 2 meetings · 4 unread · 3 files",
  "cockpitPreview.tile1.label":    "2 meetings today",
  "cockpitPreview.tile1.detail":   "10:00 Sync · 15:30 Review",
  "cockpitPreview.tile2.label":    "3 PRs await review",
  "cockpitPreview.tile2.detail":   "tars · relayer · agent-sdk",
  "cockpitPreview.tile3.label":    "Sasha × 4 messages",
  "cockpitPreview.tile3.detail":   "mentioned meeet brain",
  "cockpitPreview.tile4.label":    "proposal.docx",
  "cockpitPreview.tile4.detail":   "edited 4 times",
  "cockpitPreview.chatPlaceholder":
    "Show PRs waiting for review",
  "cockpitPreview.awarenessLabel": "awareness",
  "cockpitPreview.newBadge":       "12 new",

  "cockpitPreview.row1.tag":       "council",
  "cockpitPreview.row1.body":
    "two-voice vote · sonnet won 0.62",
  "cockpitPreview.row2.tag":       "policy",
  "cockpitPreview.row2.body":
    "send_email gate · awaiting confirm",
  "cockpitPreview.row3.tag":       "files",
  "cockpitPreview.row3.body":
    "proposal.docx · 4th edit today",
  "cockpitPreview.row4.tag":       "trace",
  "cockpitPreview.row4.body":
    "$MEEET 0.42 · paid out",
  "cockpitPreview.row5.tag":       "calendar",
  "cockpitPreview.row5.body":      "meeting in 23 min",
} as const;

/** Pre-typed key namespace export so consumers get autocomplete. */
export type TKey = keyof typeof STRINGS_EN;


// Wave 72 — Russian (and any other locale) dictionary removed. After the
// Wave 70 force-EN switch the RU table was dead code; keeping it risked a
// future refactor re-enabling RU and shipping stale/broken translations.
// Re-add a locale by adding an entry here AND restoring its dictionary;
// the rest of the i18n machinery (useT, t(), interpolation) needs no
// changes.
const STRINGS_BY_LOCALE = {
  en: STRINGS_EN,
} as const;

export type Locale = keyof typeof STRINGS_BY_LOCALE;
export const SUPPORTED_LOCALES: readonly Locale[] = Object.keys(
  STRINGS_BY_LOCALE,
) as Locale[];

const STORAGE_KEY = "tars.locale";

function detectInitialLocale(): Locale {
  // Wave 70 — force EN regardless of navigator.language. Russian (and any
  // other locale) dictionaries still exist for future re-enable, but the
  // public surface is EN-only per Wave 36 spec. Auto-detection was leaking
  // Russian to all macOS-RU users (including the operator), causing a
  // mixed RU/EN landing that broke trust.
  return "en";
}

function persistLocale(locale: Locale): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // Same private-mode caveat as above.
  }
}

/** Module-level locale state for non-component contexts (`t()`). */
let _CURRENT_LOCALE: Locale = "en";

if (typeof window !== "undefined") {
  // Defer initial detection so SSR / tests stay deterministic.
  _CURRENT_LOCALE = detectInitialLocale();
}

function _resolveString(key: TKey, locale: Locale): string {
  const table = STRINGS_BY_LOCALE[locale];
  // Russian table is partial — fall back to English when missing.
  return (
    (table as Partial<Record<TKey, string>>)[key] ??
    STRINGS_EN[key] ??
    String(key)
  );
}

function resolve(
  key: TKey,
  vars?: Record<string, string | number>,
  locale: Locale = _CURRENT_LOCALE,
): string {
  let s: string = _resolveString(key, locale);
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

/**
 * React context for the current locale + setter. Wrap the app in
 * ``<LocaleProvider>`` (see ``main.tsx`` / equivalent root) so
 * locale changes trigger a re-render. Components that don't need
 * to switch can keep using ``useT()`` exactly as before.
 */
interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  supported: readonly Locale[];
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

interface LocaleProviderProps {
  children: React.ReactNode;
  /**
   * Optional initial locale override — useful in tests or SSR
   * scenarios where ``window`` isn't available. Defaults to the
   * detected browser locale.
   */
  initial?: Locale;
}

export function LocaleProvider({ children, initial }: LocaleProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(
    initial ?? _CURRENT_LOCALE,
  );

  // Detect on mount in case the provider was constructed before
  // ``window`` was available (SSR rehydration path).
  useEffect(() => {
    if (initial) return;
    const detected = detectInitialLocale();
    if (detected !== locale) setLocaleState(detected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      supported: SUPPORTED_LOCALES,
      setLocale: (next) => {
        if (!(SUPPORTED_LOCALES as string[]).includes(next)) return;
        _CURRENT_LOCALE = next;
        persistLocale(next);
        setLocaleState(next);
      },
    }),
    [locale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

/** Read the current locale + change it. Throws when used outside ``<LocaleProvider>``. */
export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (ctx == null) {
    // Lenient fallback so legacy components (or tests rendering
    // a single component) still work without a provider — but the
    // setter is a no-op.
    return {
      locale: _CURRENT_LOCALE,
      supported: SUPPORTED_LOCALES,
      setLocale: () => undefined,
    };
  }
  return ctx;
}

/**
 * useT — translator hook for component contexts. Re-renders the
 * caller when the active locale changes (subscribes to
 * ``LocaleContext`` when present).
 */
export function useT() {
  const { locale } = useLocale();
  return (key: TKey, vars?: Record<string, string | number>) =>
    resolve(key, vars, locale);
}

/** Imperative read for non-component contexts (toast adapters etc). */
export function t(key: TKey, vars?: Record<string, string | number>): string {
  return resolve(key, vars, _CURRENT_LOCALE);
}

/**
 * Test-only setter for the module-level locale. Production code
 * MUST use ``setLocale`` from ``useLocale()`` so React re-renders.
 */
export function _setLocaleForTests(next: Locale): void {
  _CURRENT_LOCALE = next;
}

/**
 * Test-only accessor exposing the underlying string tables. Used
 * by ``src/lib/i18n.test.ts`` to assert orphan-key parity and
 * coverage thresholds. Production code MUST NOT depend on this —
 * use ``useT()`` / ``t()`` instead.
 */
export const __testTables = {
  en: STRINGS_EN as Record<string, string>,
};
