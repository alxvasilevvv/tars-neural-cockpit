import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { SectionHead } from "@/components/SectionHead";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";

const STEPS = [
  {
    num: "01",
    title: "Drop folders & files",
    body: "MD, PDF, code, audio. Local indexing, no upload.",
    cue: "drop · scan · index",
  },
  {
    num: "02",
    title: "Embed & cluster",
    body: "Six awareness layers light up. Each cluster picks a place in the graph.",
    cue: "embed · cluster · pin",
  },
  {
    num: "03",
    title: "Pick a domain pack",
    body: "The core specialises into a tool for your craft — traders, business, entrepreneur or science.",
    cue: "specialise · arm · run",
  },
];

export function Steps() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.85", "end 0.45"],
    // Defer to useEffect — see Layers.tsx for context.
    layoutEffect: false,
  });
  const lineScale = useTransform(scrollYProgress, [0, 1], [0, 1]);

  return (
    <section
      id="how"
      ref={ref}
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-32"
    >
      <SectionHead
        num="03"
        tag="FLOW"
        title="Drop. Cluster. Specialise."
        description="Drop any folder. TARS embeds, clusters, and wires it into a graph you can navigate at the speed of thought."
      />

      <div className="relative">
        {/* Connecting horizontal line behind the steps (desktop only) */}
        <div className="absolute left-0 right-0 top-[68px] hidden md:block">
          <div className="relative h-px bg-line">
            <motion.div
              style={{ scaleX: lineScale, transformOrigin: "left" }}
              className="h-full"
            >
              <div
                className="h-full"
                style={{
                  background:
                    "linear-gradient(90deg, var(--color-accent) 0%, var(--color-hud) 50%, transparent 100%)",
                  boxShadow: "0 0 12px var(--color-accent-soft)",
                }}
              />
            </motion.div>
          </div>
        </div>

        <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-[14px] border border-line bg-line md:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.li
              key={s.num}
              initial={{ opacity: 0, y: 36 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{
                duration: 0.7,
                delay: i * 0.12,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="relative bg-bg-1 p-8 md:p-10"
            >
              <CornerFrame />

              {/* Massive kinetic numeral */}
              <motion.span
                aria-hidden
                initial={{ opacity: 0, y: 24, letterSpacing: "0.2em" }}
                whileInView={{
                  opacity: 1,
                  y: 0,
                  letterSpacing: "-0.04em",
                }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.9, delay: i * 0.12 + 0.18 }}
                className="block font-display text-[clamp(5rem,12vw,9rem)] font-medium leading-[0.9] text-accent opacity-90"
                style={{
                  textShadow: "0 0 32px var(--color-accent-soft)",
                }}
              >
                {s.num}
              </motion.span>

              <header className="mb-2 mt-2 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
                <StatusLozenge label={s.cue} tone={i % 2 === 0 ? "accent" : "hud"} />
              </header>
              <h4 className="mb-2 font-display text-[20px] font-semibold uppercase tracking-[0.02em] text-ink">
                {s.title}
              </h4>
              <p className="text-[13.5px] leading-[1.65] text-ink-2">{s.body}</p>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
