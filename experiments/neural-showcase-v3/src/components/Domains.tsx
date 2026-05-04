import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { SectionHead } from "@/components/SectionHead";
import { DomainsCards } from "@/components/DomainsCards";
import { CornerFrame, StatusLozenge, BarStack } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";
import { useT, type TKey } from "@/lib/i18n";

interface Pack {
  num: string;
  slug: string;
  nameKey: TKey;
  titleKey: TKey;
  bulletKeys: readonly [TKey, TKey, TKey];
  /** Schema labels stay tech jargon (BTC · ETH · …) — no i18n needed. */
  schema: string;
  color: string;
}

const PACKS: Pack[] = [
  {
    num: "01",
    slug: "traders",
    nameKey: "domains.traders.name",
    titleKey: "domains.traders.title",
    bulletKeys: [
      "domains.traders.b1",
      "domains.traders.b2",
      "domains.traders.b3",
    ],
    schema: "BTC · ETH · SOL · NDX",
    color: "#6366F1",
  },
  {
    num: "02",
    slug: "business",
    nameKey: "domains.business.name",
    titleKey: "domains.business.title",
    bulletKeys: [
      "domains.business.b1",
      "domains.business.b2",
      "domains.business.b3",
    ],
    schema: "CRM · GSHEETS · MAIL · CAL",
    color: "#8B5CF6",
  },
  {
    num: "03",
    slug: "entrepreneur",
    nameKey: "domains.entrepreneur.name",
    titleKey: "domains.entrepreneur.title",
    bulletKeys: [
      "domains.entrepreneur.b1",
      "domains.entrepreneur.b2",
      "domains.entrepreneur.b3",
    ],
    schema: "PIPELINE · LEADS · CONTENT",
    color: "#06B6D4",
  },
  {
    num: "04",
    slug: "science",
    nameKey: "domains.science.name",
    titleKey: "domains.science.title",
    bulletKeys: [
      "domains.science.b1",
      "domains.science.b2",
      "domains.science.b3",
    ],
    schema: "ARXIV · DATASETS · LATEX",
    color: "#A78BFA",
  },
];

export function Domains() {
  const [active, setActive] = useState<string>("traders");
  const pack = PACKS.find((p) => p.slug === active) ?? PACKS[0];
  const t = useT();

  return (
    <section
      id="domains"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-36"
    >
      <SectionHead
        num="02"
        tag={t("domains.head.tag")}
        title={t("domains.head.title")}
        description={t("domains.head.description")}
      />

      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line lg:grid-cols-[1.2fr_1fr]">
        {/* Pack cards — replaces the 3D scene */}
        <div className="relative">
          <DomainsCards activeSlug={active} onActivate={setActive} />
        </div>

        {/* Detail panel — animated swap on active change */}
        <div className="relative bg-bg-1 p-8 md:p-10">
          <CornerFrame />
          <div className="absolute inset-y-0 left-0 w-[2px]" style={{ background: pack.color, boxShadow: `0 0 24px ${pack.color}` }} />

          {/* Pack picker tabs */}
          <ul className="mb-6 flex flex-wrap gap-1">
            {PACKS.map((p) => (
              <li key={p.slug}>
                <button
                  type="button"
                  onClick={() => setActive(p.slug)}
                  className={`cursor-pointer rounded-md border px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] transition-colors duration-200 ${
                    p.slug === active
                      ? "text-ink"
                      : "text-ink-2 hover:text-ink"
                  }`}
                  style={{
                    borderColor:
                      p.slug === active ? p.color : "var(--color-line)",
                    background:
                      p.slug === active
                        ? `color-mix(in srgb, ${p.color} 12%, transparent)`
                        : "transparent",
                  }}
                >
                  <span className="opacity-60">{p.num}</span>{" "}
                  <span className="font-semibold">{t(p.nameKey)}</span>
                </button>
              </li>
            ))}
          </ul>

          <AnimatePresence mode="wait">
            <motion.div
              key={pack.slug}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            >
              <header className="mb-3 flex items-baseline gap-3.5 font-mono-tech text-[11px] uppercase tracking-[3px]">
                <span style={{ color: pack.color }}>{pack.num}</span>
                <span className="text-ink">{t(pack.nameKey)}</span>
                <StatusLozenge label={t("domains.armed")} tone="accent" className="ml-auto" />
              </header>
              <h3 className="mb-5 max-w-[28ch] font-display text-[24px] font-medium leading-[1.2] tracking-[-0.01em] text-ink">
                {t(pack.titleKey)}
              </h3>
              <ul className="mb-6 grid gap-2.5 text-[13.5px] leading-[1.6] text-ink-2">
                {pack.bulletKeys.map((bKey) => (
                  <li key={bKey} className="grid grid-cols-[18px_1fr] items-start gap-2.5">
                    <span
                      className="mt-0.5 font-mono-tech text-[12px]"
                      style={{ color: pack.color }}
                    >
                      +
                    </span>
                    <span>{t(bKey)}</span>
                  </li>
                ))}
              </ul>

              {/* Live signal strip */}
              <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-t border-line pt-4 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2">
                <span className="truncate">{pack.schema}</span>
                <Waveform bars={20} width={140} height={18} color={pack.color} />
              </div>

              <div className="mt-3 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px]">
                <BarStack
                  values={[0.4, 0.7, 0.5, 0.85, 0.6, 0.92, 0.7, 0.55]}
                  width={64}
                  height={14}
                  color={pack.color}
                />
                <span className="text-ink-2">{t("domains.throughput.normal")}</span>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
