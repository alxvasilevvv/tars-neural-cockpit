import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { SectionHead } from "@/components/SectionHead";
import { DomainsScene } from "@/three/DomainsScene";
import { CornerFrame, StatusLozenge, BarStack } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";

interface Pack {
  num: string;
  slug: string;
  name: string;
  title: string;
  bullets: string[];
  schema: string;
  color: string;
}

const PACKS: Pack[] = [
  {
    num: "01",
    slug: "traders",
    name: "Traders",
    title: "Markets and signals at the speed of a thought.",
    bullets: [
      "Live market awareness across exchanges and feeds.",
      "Signal generation with explainable model votes.",
      "Risk and portfolio actions guarded by policy.",
    ],
    schema: "BTC · ETH · SOL · NDX",
    color: "#CA8A04",
  },
  {
    num: "02",
    slug: "business",
    name: "Business",
    title: "A second brain for your operating cadence.",
    bullets: [
      "Deals, contacts and revenue across mail and CRM.",
      "KPI nodes auto-update from your data sources.",
      "Daily brief composed by the council each morning.",
    ],
    schema: "CRM · GSHEETS · MAIL · CAL",
    color: "#00FFFF",
  },
  {
    num: "03",
    slug: "mlm",
    name: "MLM",
    title: "Downline as a graph, not a spreadsheet.",
    bullets: [
      "Network depth, activity and retention tracked live.",
      "Recruiting playbooks tuned to your tone of voice.",
      "Auto content for newcomers across IG, TG, WA.",
    ],
    schema: "NETWORK · RANKS · CONTENT",
    color: "#CA8A04",
  },
  {
    num: "04",
    slug: "science",
    name: "Science",
    title: "From paper pile to citation-aware council.",
    bullets: [
      "arXiv, Crossref and Semantic Scholar awareness.",
      "Equation and dataset graph across your projects.",
      "Hypothesis trees with model-voted evidence.",
    ],
    schema: "ARXIV · DATASETS · LATEX",
    color: "#00FFFF",
  },
];

export function Domains() {
  const [active, setActive] = useState<string>("traders");
  const pack = PACKS.find((p) => p.slug === active) ?? PACKS[0];

  return (
    <section
      id="domains"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-36"
    >
      <SectionHead
        num="02"
        tag="PACKS"
        title="Same core, four crafts."
        description="Plug-in packs that turn the neural core into a focused tool — traders, business, MLM, science. Hover a node to inspect."
      />

      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line lg:grid-cols-[1.2fr_1fr]">
        {/* Orbital scene */}
        <div className="relative h-[480px] bg-[radial-gradient(60%_60%_at_50%_50%,rgba(202,138,4,0.06),transparent_70%)] md:h-[560px]">
          <DomainsScene activeSlug={active} onActivate={setActive} />
          {/* Decorative corner ticks */}
          <CornerFrame className="rounded-[14px]" />
          {/* Ring label on the canvas */}
          <div className="pointer-events-none absolute left-5 top-4 z-10 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            ORBIT // 04 NODES
          </div>
          <div className="pointer-events-none absolute bottom-4 right-5 z-10 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            HOVER · ACTIVATE
          </div>
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
                  <span className="font-semibold">{p.name}</span>
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
                <span className="text-ink">{pack.name}</span>
                <StatusLozenge label="ARMED" tone="accent" className="ml-auto" />
              </header>
              <h3 className="mb-5 max-w-[24ch] font-display text-[22px] font-medium uppercase leading-[1.18] tracking-[0.02em] text-ink">
                {pack.title}
              </h3>
              <ul className="mb-6 grid gap-2.5 text-[13.5px] leading-[1.6] text-ink-2">
                {pack.bullets.map((b, idx) => (
                  <li key={idx} className="grid grid-cols-[18px_1fr] items-start gap-2.5">
                    <span
                      className="mt-0.5 font-mono-tech text-[12px]"
                      style={{ color: pack.color }}
                    >
                      +
                    </span>
                    <span>{b}</span>
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
                <span className="text-ink-2">throughput · normal</span>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
