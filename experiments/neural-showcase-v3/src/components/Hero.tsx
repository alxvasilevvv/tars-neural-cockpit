import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { HeroScene } from "@/three/HeroScene";
import { HudPlates } from "@/components/HudPlates";
import { Marquee } from "@/components/Marquee";
import { KineticText } from "@/components/KineticText";

const TICKER = [
  "indexing 2,348 docs",
  "council voting · 0.04ms",
  "memory shell · pinned",
  "calendar awareness · live",
  "voice intent · stand-by",
  "trace_id propagated",
  "domain pack · traders",
  "domain pack · science",
  "MeshDistort · gold reactor",
  "fresnel · cyan skeleton",
  "policy engine · armed",
  "MAC actions · sandboxed",
];

export function Hero() {
  return (
    <section className="relative z-20 min-h-[760px] overflow-hidden pb-10 pt-2 md:min-h-[860px]">
      {/* WebGL reactor lives behind the hero text. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -top-[8vh] -z-20 h-[120vh]"
      >
        <HeroScene />
      </div>

      {/* Spotlight darkening so type stays legible over WebGL. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-[-10%] inset-y-[-4%] -z-10"
        style={{
          background:
            "radial-gradient(58% 58% at 50% 42%, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.5) 36%, transparent 76%)",
        }}
      />

      {/* Floating HUD plates around the hero stage */}
      <HudPlates />

      {/* Centered hero content */}
      <div className="relative z-30 mx-auto max-w-[1280px] px-8 pt-6 text-center md:px-14 md:pt-10">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="mb-7 inline-flex items-center gap-2.5 rounded-full border border-line bg-white/[0.02] px-3.5 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[3.4px] text-ink-2"
        >
          <span
            className="h-1.5 w-1.5 rounded-full bg-alert"
            style={{
              boxShadow: "0 0 10px var(--color-alert-soft)",
              animation: "pulseDot 1.6s ease-in-out infinite",
            }}
          />
          Phase 09 · Neural · meeet.world
        </motion.div>

        <h1 className="font-display text-[clamp(3.4rem,8.5vw,9rem)] font-medium leading-[0.96] tracking-[0.01em] text-ink">
          <span className="block">
            <KineticText text="Your machine," />
          </span>
          <span className="block">
            <KineticText
              text="awakened."
              accentWords={["awakened"]}
              delay={0.2}
            />
          </span>
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.85, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mt-9 max-w-[560px] text-[15.5px] leading-[1.7] text-ink-2"
        >
          TARS routes files, calendar, code, voice and Mac actions through a
          single neural core, then specialises into packs for traders,
          business, MLM founders and scientists.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 1.0, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 flex flex-wrap items-center justify-center gap-3"
        >
          <a
            href="#cockpit"
            className="group inline-flex cursor-pointer items-center gap-2.5 rounded-md border border-line-hot bg-gradient-to-b from-accent-deep to-accent-deep/40 px-5 py-3.5 font-display text-[12.5px] uppercase tracking-[0.18em] text-accent transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:from-accent/20 hover:shadow-[0_0_0_1px_var(--color-accent-soft),0_12px_32px_-10px_var(--color-accent-soft)]"
          >
            <span>Open cockpit</span>
            <ArrowRight
              size={16}
              className="transition-transform duration-200 group-hover:translate-x-0.5"
              strokeWidth={1.6}
            />
          </a>
          <a
            href="#domains"
            className="inline-flex cursor-pointer items-center gap-2.5 rounded-md border border-line bg-white/[0.02] px-5 py-3.5 font-display text-[12.5px] uppercase tracking-[0.18em] text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-white/[0.04]"
          >
            Explore domains
          </a>
        </motion.div>
      </div>

      {/* Live thought-stream marquee under the hero */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 1.4 }}
        className="relative z-30 mt-14"
      >
        <Marquee items={TICKER} speed={28} />
      </motion.div>
    </section>
  );
}
