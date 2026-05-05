import { motion } from "framer-motion";
import { Check, Minus } from "lucide-react";
import { SectionHead } from "@/components/SectionHead";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { useT, type TKey } from "@/lib/i18n";

/**
 * Pricing — three tiers + a lifetime banner below.
 *
 * Pricing logic mirrors the $MEEET economy (task #58): local install is
 * always free under MIT; Pro unlocks the cloud-bound features (T2T, AI
 * Clone training, council voting at higher tiers, $MEEET earn);
 * Business adds team & compliance.
 */

interface Tier {
  slug: "free" | "pro" | "business";
  num: string;
  /** Translation keys — resolved at render via `useT()`. */
  nameKey: TKey;
  taglineKey: TKey;
  price: string;
  priceSubKey: TKey;
  meeetPriceKey?: TKey;
  bullets: { ok: boolean; text: string }[];
  ctaKey: TKey;
  href: string;
  color: string;
  recommended?: boolean;
  /**
   * Bug #3 from docs/SYSTEM_AUDIT_2026-05-02.md — paid tiers display
   * a "Coming soon" overlay instead of pretending checkout works.
   * The Pro/Business CTAs deep-link to the waitlist anchor; the
   * lifetime banner uses a separate "lifetime.comingSoon" copy. Flip
   * to false once SOL / $MEEET on-chain checkout lands and the
   * backend ``TARS_PAYMENT_MODE`` defaults to ``onchain``.
   */
  comingSoon?: boolean;
}

const TIERS: Tier[] = [
  {
    slug: "free",
    num: "00",
    nameKey: "pricing.tier.free.name",
    taglineKey: "pricing.tier.free.tagline",
    price: "$0",
    priceSubKey: "pricing.tier.free.priceSub",
    bullets: [
      { ok: true, text: "Single device, unlimited usage on-device" },
      { ok: true, text: "Daily Briefing + Mac Operator + Memory ledger" },
      { ok: true, text: "All 4 packs — traders / business / entrepreneur / science" },
      { ok: true, text: "Bring-your-own LLM keys" },
      { ok: false, text: "T2T, AI Clone, council voting" },
      { ok: false, text: "$MEEET earn / cloud sync" },
    ],
    ctaKey: "pricing.tier.free.cta",
    href: "/install",
    color: "#06B6D4",
  },
  {
    slug: "pro",
    num: "01",
    nameKey: "pricing.tier.pro.name",
    taglineKey: "pricing.tier.pro.tagline",
    price: "$19",
    priceSubKey: "pricing.tier.pro.priceSub",
    meeetPriceKey: "pricing.tier.pro.meeetPrice",
    bullets: [
      { ok: true, text: "Everything in Free" },
      { ok: true, text: "$10/mo cloud LLM budget · or BYO key for $9/mo" },
      { ok: true, text: "Cloud sync across devices (E2E encrypted)" },
      { ok: true, text: "T2T — 50 agent-to-agent deals/mo" },
      { ok: true, text: "AI Clone — your tone, your rhythm" },
      { ok: true, text: "Two-voice council · 100 votes/day" },
      { ok: true, text: "Earn $MEEET while your agent works" },
    ],
    ctaKey: "pricing.tier.pro.cta",
    href: "#waitlist",
    color: "#6366F1",
    recommended: true,
    comingSoon: true,
  },
  {
    slug: "business",
    num: "02",
    nameKey: "pricing.tier.business.name",
    taglineKey: "pricing.tier.business.tagline",
    price: "$79",
    priceSubKey: "pricing.tier.business.priceSub",
    bullets: [
      { ok: true, text: "Everything in Pro" },
      { ok: true, text: "$40/seat cloud LLM budget · pooled across team" },
      { ok: true, text: "Unlimited T2T deals + council votes" },
      { ok: true, text: "Shared agent sessions — multiplayer" },
      { ok: true, text: "Receipt-anchored audit + SSO + RBAC" },
      { ok: true, text: "Priority support + private Discord" },
      { ok: true, text: "Custom skill SDK + private marketplace" },
    ],
    ctaKey: "pricing.tier.business.cta",
    href: "mailto:hello@meeet.world?subject=TARS%20Business%20enquiry",
    color: "#8B5CF6",
    comingSoon: true,
  },
];

export function Pricing() {
  const t = useT();
  return (
    <section
      id="pricing"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-36"
    >
      <SectionHead
        num="08"
        tag={t("pricing.tag")}
        title={t("pricing.title")}
        description={t("pricing.description")}
      />

      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line lg:grid-cols-3">
        {TIERS.map((tier) => (
          <motion.div
            key={tier.slug}
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="relative bg-bg-1 p-8 md:p-10"
            style={{
              background: tier.recommended
                ? `linear-gradient(180deg, color-mix(in srgb, ${tier.color} 7%, var(--color-bg-1)) 0%, var(--color-bg-1) 60%)`
                : undefined,
            }}
          >
            <CornerFrame />

            {/* Tier accent hairline on top */}
            <div
              aria-hidden
              className="absolute inset-x-0 top-0 h-px"
              style={{
                background: tier.color,
                boxShadow: `0 0 16px ${tier.color}`,
                opacity: tier.recommended ? 1 : 0.5,
              }}
            />

            <header className="mb-6 flex items-center justify-between font-mono-tech text-[11px] uppercase tracking-[3px]">
              <div className="flex items-center gap-3">
                <span style={{ color: tier.color }}>{tier.num}</span>
                <span className="text-ink">{t(tier.nameKey)}</span>
              </div>
              <div className="flex items-center gap-2">
                {tier.comingSoon && (
                  <StatusLozenge
                    label={t("pricing.comingSoon.badge")}
                    tone="hud"
                  />
                )}
                {tier.recommended && (
                  <StatusLozenge
                    label={t("pricing.recommended")}
                    tone="accent"
                  />
                )}
              </div>
            </header>

            <h3 className="mb-6 max-w-[18ch] font-display text-[22px] font-medium uppercase leading-[1.18] tracking-[0.02em] text-ink">
              {t(tier.taglineKey)}
            </h3>

            <div className="mb-7 flex items-baseline gap-2.5 border-b border-line pb-6">
              <span
                className="font-display text-[44px] font-medium leading-none tabular-nums"
                style={{ color: tier.color }}
              >
                {tier.price}
              </span>
              <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2">
                <div>{t(tier.priceSubKey)}</div>
                {tier.meeetPriceKey && (
                  <div className="mt-0.5" style={{ color: "var(--color-meeet-violet, #8B5CF6)" }}>
                    {t(tier.meeetPriceKey)}
                  </div>
                )}
              </div>
            </div>

            <ul className="mb-8 grid gap-2.5 text-[13px] leading-[1.55]">
              {tier.bullets.map((b, idx) => (
                <li
                  key={idx}
                  className="grid grid-cols-[16px_1fr] items-start gap-2.5"
                >
                  <span
                    className="mt-0.5"
                    style={{ color: b.ok ? tier.color : "var(--color-ink-3)" }}
                  >
                    {b.ok ? (
                      <Check size={14} strokeWidth={2.4} />
                    ) : (
                      <Minus size={14} strokeWidth={2} />
                    )}
                  </span>
                  <span className={b.ok ? "text-ink/95" : "text-ink-3 line-through decoration-1"}>
                    {b.text}
                  </span>
                </li>
              ))}
            </ul>

            <a
              href={tier.href}
              className="group inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-3 font-mono-tech text-[11px] uppercase tracking-[2.6px] transition-colors duration-200"
              style={{
                borderColor: tier.color,
                color: tier.recommended ? "var(--color-bg-0)" : tier.color,
                background: tier.recommended ? tier.color : "transparent",
                boxShadow: tier.recommended ? `0 0 24px ${tier.color}55` : undefined,
              }}
              title={tier.comingSoon ? t("pricing.comingSoon.tooltip") : undefined}
              aria-describedby={
                tier.comingSoon ? `${tier.slug}-coming-soon` : undefined
              }
            >
              {t(tier.ctaKey)}
              <span className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
            </a>
            {tier.comingSoon && (
              <p
                id={`${tier.slug}-coming-soon`}
                className="mt-3 text-center font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3"
              >
                {t("pricing.comingSoon.tooltip")}
              </p>
            )}
          </motion.div>
        ))}
      </div>

      {/* Lifetime banner */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
        className="relative mt-px overflow-hidden rounded-[14px] border border-line bg-bg-1"
      >
        <CornerFrame />
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
            boxShadow: "0 0 18px rgba(139,92,246,0.45)",
          }}
        />
        <div className="grid grid-cols-1 items-center gap-6 p-8 md:grid-cols-[auto_1fr_auto] md:gap-10 md:p-10">
          <div className="font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <div className="mb-2 flex items-center gap-3">
              <span style={{ color: "#8B5CF6" }}>03</span>
              <span className="text-ink">{t("pricing.lifetime.tag")}</span>
              <StatusLozenge label={t("pricing.lifetime.badge")} tone="hud" />
            </div>
            <div className="font-display text-[40px] font-medium leading-none tabular-nums text-ink">
              $299
            </div>
            <div className="mt-1 text-[10px] tracking-[2.4px] text-ink-2">
              {t("pricing.lifetime.priceSub")}
            </div>
          </div>
          <p className="max-w-[46ch] text-[14px] leading-[1.6] text-ink-2">
            {t("pricing.lifetime.body")}
          </p>
          <div className="flex flex-col items-center gap-2 md:items-end">
            <StatusLozenge
              label={t("pricing.comingSoon.badge")}
              tone="hud"
            />
            <a
              href="#waitlist"
              className="group inline-flex items-center justify-center gap-2 rounded-md border px-6 py-3.5 font-mono-tech text-[11px] uppercase tracking-[2.6px] text-ink transition-colors duration-200"
              style={{
                borderColor: "#8B5CF6",
                background:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
                boxShadow: "0 0 24px rgba(139,92,246,0.4)",
              }}
              title={t("pricing.comingSoon.tooltip")}
            >
              {t("pricing.lifetime.cta")}
              <span className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
            </a>
            <span className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
              {t("pricing.lifetime.comingSoon")}
            </span>
          </div>
        </div>
      </motion.div>

      {/* Footnote — billing notes */}
      <p className="mt-6 text-center font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        {t("pricing.footnote")}
      </p>
    </section>
  );
}
