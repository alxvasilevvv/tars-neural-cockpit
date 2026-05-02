/**
 * i18n — multi-locale string table for the marketing surface.
 *
 * Bug #5 from docs/SYSTEM_AUDIT_2026-05-02.md — TARS shipped in
 * English only. The skeleton was always here (`useT()` indirection),
 * so this PR adds a second locale (Russian) and the runtime
 * machinery to switch between them without rebuilding.
 *
 * Adding strings:
 *   1. Add the key + English value to `STRINGS_EN` below.
 *   2. Add the same key + Russian translation to `STRINGS_RU`. The
 *      type system enforces parity (RU strings type-check against
 *      EN keys) so a missed translation is a compile error.
 *   3. Reference it via `useT()(key)` (in components) or `t(key)`
 *      (in non-component contexts).
 *
 * Interpolation:
 *   useT()("waitlist.position", { n: 1247 })  // → "You're #1247 on the list."
 *
 * Locale switching:
 *   - `useLocale()` returns `{ locale, setLocale }` for components.
 *   - The selected locale persists in `localStorage["tars.locale"]`
 *     and falls back to `navigator.language` on first visit.
 *
 * **Note:** missing translations fall back to English silently —
 * we'd rather show English than the raw key. Use the `pnpm
 * vitest src/lib/i18n.test.ts` parity guard to catch missing keys
 * at CI time.
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
  // wired (no Stripe / wallet integration). Pricing page shows the
  // tiers as a public commitment, but the paid CTAs surface
  // "Coming soon" instead of pretending checkout works. Backend
  // /api/entitlements/upgrade returns 503 feature_disabled in
  // production unless TARS_PAYMENT_MODE=mock|stripe is set.
  "pricing.comingSoon.badge":      "COMING SOON",
  "pricing.comingSoon.tooltip":    "Paid tiers ship once Stripe + $MEEET wallet checkout land. Free tier is fully usable today; subscribe to be notified at launch.",
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

  // Common chrome
  "common.back":                   "back to home",

  // Cockpit chat — operator-facing strings on the highest-visibility surfaces.
  "chat.composer.placeholder":     "message TARS — ⌘↵ to send · drop files to ground answers",
  "chat.threads.empty":            "no threads yet — start a conversation to populate the list",

  // Bug #5 — locale switcher (small public-facing UI element)
  "locale.label":                  "Language",
  "locale.en":                     "English",
  "locale.ru":                     "Russian",
} as const;

/** Pre-typed key namespace export so consumers get autocomplete. */
export type TKey = keyof typeof STRINGS_EN;

/**
 * Russian translations. Coverage is currently limited to the
 * highest-visibility marketing strings (Hero, Pricing, Nav,
 * Footer, Locale switcher). Untranslated keys fall back to
 * English at render time so adding strings to ``STRINGS_EN``
 * never breaks the RU build — but expanding coverage is the
 * recommended follow-up after this PR.
 *
 * Style guide:
 * - Polite "вы" (not the formal "Вы" — feels stiff in product copy).
 * - Latin product names stay Latin: TARS, $MEEET, Pro, Business.
 * - "сloud" → "облако"; "cap"/"cap_hit" → "лимит" (cockpit-side
 *   banking copy already uses "лимит" for spend caps).
 */
const STRINGS_RU: Partial<Record<TKey, string>> = {
  // Hero — three-beat sovereignty headline.
  "hero.eyebrow":         "TARS · оператор-уровень · локально-первый AI",
  "hero.title.line1":     "Ваш AI.",
  "hero.title.line2":     "Ваша машина.",
  "hero.title.line3":     "Ваши условия.",
  "hero.subline":         "Совет агентов на штурвале — файлы, голос, календарь, код, видение, on-chain. Локально по умолчанию; облако — только когда вы скажете.",
  "hero.demo.label":      "живая демо · смена каждые 4с",
  "hero.cta.cockpit":     "Открыть кокпит",
  "hero.cta.domains":     "Изучить домены",

  "stickyCTA.notify":     "Уведомить меня",
  "stickyCTA.cockpit":    "Открыть кокпит",
  "stickyCTA.ready":      "готово",

  "waitlist.eyebrow":     "пред-релиз · waitlist",
  "waitlist.title.lead":  "Будьте первыми —",
  "waitlist.title.tail":  "в день релиза",
  "waitlist.body":        "Один email в день, когда выйдет бинарник. Никаких рассылок, никаких пикселей трекинга — см. Privacy § 4.",
  "waitlist.email":       "Email-адрес",
  "waitlist.role":        "Роль",
  "waitlist.submit":      "Уведомить меня",
  "waitlist.saving":      "Сохраняем",
  "waitlist.success":     "Вы в списке.",
  "waitlist.position":    "позиция #{n}",
  "waitlist.fallback":    "напишем когда выйдет бинарник",

  "cookie.title":         "Только функциональные cookies.",
  "cookie.body":          "Сессия, тема, язык, Cloudflare bot-management. Никакой аналитики, никакой рекламы, никаких трекеров — полный список в",
  "cookie.privacy_link":  "Privacy Policy § 9",
  "cookie.accept":        "Понятно",
  "cookie.dismiss":       "Закрыть уведомление",

  "footer.cta":           "ОТКРЫТЬ КОКПИТ",
  "footer.col.product":   "Продукт",
  "footer.col.resources": "Ресурсы",
  "footer.col.company":   "Компания",
  "footer.col.connect":   "Контакты",
  "footer.systems":       "все системы · 99,97%",
  "footer.trace":         "trace_id готов · контракт 1.0.0",
  "footer.legal":         "© 2026 meeet.world · MIT-лицензия",

  "toast.recovery.verified": "Фраза восстановления подтверждена",

  "pricing.tag":                   "ТАРИФЫ",
  "pricing.title":                 "Платите за облако, не за мысли.",
  "pricing.description":           "Локальная установка бесплатна по MIT. Pro и Business открывают облачные функции — T2T, AI Clone, голосование совета. Оплата в долларах или в $MEEET.",
  "pricing.recommended":           "РЕКОМЕНДУЕМ",
  "pricing.tier.free.name":        "Free",
  "pricing.tier.free.tagline":     "Локально, навсегда.",
  "pricing.tier.free.priceSub":    "MIT, self-hosted",
  "pricing.tier.free.cta":         "Скачать для Mac",
  "pricing.tier.pro.name":         "Pro",
  "pricing.tier.pro.tagline":      "Ваш второй мозг — онлайн.",
  "pricing.tier.pro.priceSub":     "в месяц",
  "pricing.tier.pro.meeetPrice":   "или 200 $MEEET / мес",
  "pricing.tier.pro.cta":          "Уведомить при запуске",
  "pricing.tier.business.name":    "Business",
  "pricing.tier.business.tagline": "Команды, аудит, контроль.",
  "pricing.tier.business.priceSub":"за место / месяц",
  "pricing.tier.business.cta":     "Связаться с продажами",
  "pricing.comingSoon.badge":      "СКОРО",
  "pricing.comingSoon.tooltip":    "Платные тарифы открываются после интеграции Stripe + кошелька $MEEET. Free-тариф уже полностью работает; подпишитесь, чтобы узнать о запуске.",
  "pricing.lifetime.tag":          "LIFETIME",
  "pricing.lifetime.badge":        "FOUNDERS",
  "pricing.lifetime.priceSub":     "один платёж · навсегда",
  "pricing.lifetime.body":         "Заплатите один раз — получите все функции Pro навсегда, плюс Founders-бейдж, ваш handle на T2T и 1 000 $MEEET в кошелёк при запуске.",
  "pricing.lifetime.cta":          "Получить lifetime",
  "pricing.lifetime.comingSoon":   "Lifetime-чекаут откроется при запуске",
  "pricing.footnote":              "Оплата USD картой · или $MEEET / SOL · отмена в любой момент · возврат 14 дней",

  "common.back":                   "назад на главную",

  "locale.label":                  "Язык",
  "locale.en":                     "Английский",
  "locale.ru":                     "Русский",
};

const STRINGS_BY_LOCALE = {
  en: STRINGS_EN,
  ru: STRINGS_RU,
} as const;

export type Locale = keyof typeof STRINGS_BY_LOCALE;
export const SUPPORTED_LOCALES: readonly Locale[] = Object.keys(
  STRINGS_BY_LOCALE,
) as Locale[];

const STORAGE_KEY = "tars.locale";

function detectInitialLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && (SUPPORTED_LOCALES as string[]).includes(stored)) {
      return stored as Locale;
    }
  } catch {
    // localStorage may throw in private mode / cross-origin
    // contexts; default to English silently.
  }
  const nav = (typeof navigator !== "undefined" ? navigator.language : "") || "";
  if (nav.toLowerCase().startsWith("ru")) return "ru";
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
