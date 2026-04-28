import { motion } from "framer-motion";
import { SectionHead } from "@/components/SectionHead";

interface Pack {
  num: string;
  name: string;
  title: string;
  bullets: string[];
  schema: string;
}

const PACKS: Pack[] = [
  {
    num: "01",
    name: "Traders",
    title: "Markets and signals at the speed of a thought.",
    bullets: [
      "Live market awareness across exchanges and feeds.",
      "Signal generation with explainable model votes.",
      "Risk and portfolio actions guarded by policy.",
    ],
    schema: "BTC · ETH · SOL · NDX",
  },
  {
    num: "02",
    name: "Business",
    title: "A second brain for your operating cadence.",
    bullets: [
      "Deals, contacts and revenue across mail and CRM.",
      "KPI nodes auto-update from your data sources.",
      "Daily brief composed by the council each morning.",
    ],
    schema: "CRM · GSHEETS · MAIL · CAL",
  },
  {
    num: "03",
    name: "MLM",
    title: "Downline as a graph, not a spreadsheet.",
    bullets: [
      "Network depth, activity and retention tracked live.",
      "Recruiting playbooks tuned to your tone of voice.",
      "Auto content for newcomers across IG, TG, WA.",
    ],
    schema: "NETWORK · RANKS · CONTENT",
  },
  {
    num: "04",
    name: "Science",
    title: "From paper pile to citation-aware council.",
    bullets: [
      "arXiv, Crossref and Semantic Scholar awareness.",
      "Equation and dataset graph across your projects.",
      "Hypothesis trees with model-voted evidence.",
    ],
    schema: "ARXIV · DATASETS · LATEX",
  },
];

export function Domains() {
  return (
    <section
      id="domains"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-32 md:px-14 md:py-36"
    >
      <SectionHead
        num="02"
        tag="PACKS"
        title="Same core, four crafts."
        description="Plug-in packs that turn the neural core into a focused tool for your work — traders, business, MLM, science."
      />
      <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-[22px] border border-line bg-line md:grid-cols-2">
        {PACKS.map((p, i) => (
          <motion.li
            key={p.num}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{
              duration: 0.6,
              delay: (i % 2) * 0.08,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="group relative bg-bg-1 p-10 transition-colors duration-200 hover:bg-bg-2"
          >
            <span className="absolute inset-y-0 left-0 w-[2px] bg-gradient-to-b from-accent to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-70" />
            <header className="mb-4 flex items-baseline gap-3.5 font-mono-tech text-[11px] uppercase tracking-[3px]">
              <span className="text-accent">{p.num}</span>
              <span className="text-ink">{p.name}</span>
            </header>
            <h3 className="mb-4 max-w-[22ch] font-display text-[22px] font-semibold leading-[1.2] tracking-[-0.025em] text-ink">
              {p.title}
            </h3>
            <ul className="mb-6 grid gap-2.5 text-[14px] leading-[1.6] text-ink-2">
              {p.bullets.map((b, idx) => (
                <li key={idx} className="grid grid-cols-[18px_1fr] items-start gap-2.5">
                  <span className="mt-0.5 font-mono-tech text-[12px] text-accent">+</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
            <div
              aria-hidden
              className="relative grid h-11 grid-cols-8 items-end gap-1.5 border-t border-line pb-[18px] pt-3.5"
            >
              {Array.from({ length: 8 }).map((_, idx) => (
                <motion.span
                  key={idx}
                  initial={{ scaleY: 0.18 }}
                  animate={{ scaleY: [0.18, 0.85, 0.18] }}
                  transition={{
                    duration: 2.6,
                    delay: idx * 0.1,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                  className="origin-bottom rounded-[1px]"
                  style={{
                    background:
                      "linear-gradient(180deg, var(--color-accent), var(--color-accent-deep))",
                  }}
                />
              ))}
              <em className="absolute bottom-0 left-0 font-mono-tech text-[10px] uppercase not-italic tracking-[2.4px] text-ink-2">
                {p.schema}
              </em>
            </div>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}
