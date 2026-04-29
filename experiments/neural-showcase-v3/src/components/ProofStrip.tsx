import { motion } from "framer-motion";
import { CountUpNumber } from "@/components/CountUpNumber";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * ProofStrip — concise stat row that proves TARS is a real, finished
 * product, not a demo. 4 cells, each with a count-up number animated on
 * viewport entry. Slots between TrustStrip and MeetTars on the landing.
 *
 * Numbers must match `docs/CHANGELOG_AGENTS.md` and `/pitch` slide 0
 * (single source of truth). When you change one, audit the other.
 */

interface Stat {
  num: number;
  suffix?: string;
  label: string;
  caption: string;
  color: string;
}

const STATS: Stat[] = [
  {
    num: 28,
    label: "AI agents",
    caption: "Specialised + composable",
    color: "#6366F1",
  },
  {
    num: 14,
    label: "Native skills",
    caption: "Wallet · Quest · Arena · …",
    color: "#8B5CF6",
  },
  {
    num: 6,
    label: "LLM providers",
    caption: "Anthropic · OpenAI · local",
    color: "#06B6D4",
  },
  {
    num: 100,
    suffix: "%",
    label: "Local-first",
    caption: "Your machine, your data",
    color: "#A78BFA",
  },
];

export function ProofStrip() {
  return (
    <section
      aria-label="product proof points"
      className="relative z-20 mx-auto -mt-2 max-w-[1180px] px-6 pb-10 pt-2 md:px-12"
    >
      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/50 backdrop-blur-md">
        <BrandHairline />

        <dl className="grid grid-cols-2 divide-x divide-line/50 md:grid-cols-4">
          {STATS.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-20% 0px" }}
              transition={{
                duration: 0.55,
                ease: [0.22, 1, 0.36, 1],
                delay: i * 0.07,
              }}
              className="px-4 py-5 sm:px-5 sm:py-6 md:px-7 md:py-7"
              role="group"
              aria-label={`${s.num}${s.suffix ?? ""} ${s.label} — ${s.caption}`}
            >
              <div
                className="font-display font-medium leading-none tabular-nums"
                style={{
                  fontSize: "clamp(1.9rem, 3.6vw, 2.7rem)",
                  color: s.color,
                }}
              >
                <CountUpNumber
                  value={s.num}
                  suffix={s.suffix ?? ""}
                  duration={1.4}
                  delay={i * 0.08}
                />
              </div>
              <dt className="mt-2 font-display text-[14px] tracking-[-0.005em] text-ink">
                {s.label}
              </dt>
              <dd className="mt-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.4px] text-ink-3 sm:text-[10px] sm:tracking-[2px]">
                {s.caption}
              </dd>
            </motion.div>
          ))}
        </dl>
      </div>
    </section>
  );
}
