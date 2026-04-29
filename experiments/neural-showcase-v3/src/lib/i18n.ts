/**
 * i18n — single-language string table for the marketing surface.
 *
 * TARS ships in English only. The `useT()` / `t()` indirection is kept
 * so we have a single source of truth for marketing copy (handy for
 * editorial review, search-and-replace, and a future i18n
 * reintroduction if global launch ever needs it). Today it's just an
 * English lookup with `{var}` interpolation.
 *
 * Adding strings:
 *   1. Add the key + English value to `STRINGS` below.
 *   2. Reference it via `useT()(key)` (in components) or `t(key)`
 *      (in non-component contexts).
 *
 * Interpolation:
 *   useT()("waitlist.position", { n: 1247 })  // → "You're #1247 on the list."
 */

const STRINGS = {
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
  "pricing.tier.pro.cta":          "Start Pro",
  "pricing.tier.business.name":    "Business",
  "pricing.tier.business.tagline": "Teams, audit, control.",
  "pricing.tier.business.priceSub":"per seat / month",
  "pricing.tier.business.cta":     "Talk to sales",
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

  // Common chrome
  "common.back":                   "back to home",

  // Cockpit chat — operator-facing strings on the highest-visibility surfaces.
  "chat.composer.placeholder":     "message TARS — ⌘↵ to send · drop files to ground answers",
  "chat.threads.empty":            "no threads yet — start a conversation to populate the list",
} as const;

/** Pre-typed key namespace export so consumers get autocomplete. */
export type TKey = keyof typeof STRINGS;

/** Resolve a key, applying `{var}` interpolation if `vars` is given. */
function resolve(key: TKey, vars?: Record<string, string | number>): string {
  let s: string = STRINGS[key] ?? String(key);
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

/**
 * useT — translator hook for component contexts. Returns the same
 * lookup function on every render; safe to call inline.
 */
export function useT() {
  return resolve;
}

/** Imperative read for non-component contexts (toast adapters etc). */
export function t(key: TKey, vars?: Record<string, string | number>): string {
  return resolve(key, vars);
}
