import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { HeroScene } from "@/three/HeroScene";

const word = {
  hidden: { y: "110%" },
  show: { y: "0%" },
};

const titleLine = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};

export function Hero() {
  return (
    <section className="relative z-20 mx-auto max-w-[1280px] px-8 pb-32 pt-12 text-center md:px-14 md:pb-32 md:pt-16">
      {/* WebGL reactor lives behind the hero text. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-[-12%] -top-[6vh] -z-20 h-[110vh]"
      >
        <HeroScene />
      </div>
      {/* Spotlight darkening so type stays legible over WebGL. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-[-12%] inset-y-[-4%] -z-10"
        style={{
          background:
            "radial-gradient(62% 68% at 50% 38%, rgba(6,7,13,0.78) 0%, rgba(6,7,13,0.42) 36%, transparent 76%)",
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="mb-8 inline-flex items-center gap-2.5 rounded-full border border-line bg-white/[0.02] px-3.5 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[3.4px] text-ink-2"
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

      <h1 className="font-display text-[clamp(3.4rem,8.5vw,9rem)] font-extrabold leading-[0.92] tracking-[-0.05em] text-ink">
        <motion.span
          variants={titleLine}
          initial="hidden"
          animate="show"
          className="block overflow-hidden pb-[0.06em]"
        >
          {"Your machine,".split(" ").map((w, i) => (
            <motion.span
              key={i}
              variants={word}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
              className="mr-[0.18em] inline-block last:mr-0"
            >
              {w}
            </motion.span>
          ))}
        </motion.span>
        <motion.span
          variants={titleLine}
          initial="hidden"
          animate="show"
          transition={{ delayChildren: 0.18 }}
          className="block overflow-hidden pb-[0.06em]"
        >
          <motion.span
            variants={word}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="inline-block text-accent"
            style={{ textShadow: "0 0 24px var(--color-accent-soft)" }}
          >
            awakened.
          </motion.span>
        </motion.span>
      </h1>

      <motion.p
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="mx-auto mt-8 max-w-[560px] text-[16px] leading-[1.68] text-ink-2"
      >
        TARS routes files, calendar, code, voice and Mac actions through a
        single neural core, then specialises into packs for traders, business,
        MLM founders and scientists.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.65, ease: [0.22, 1, 0.36, 1] }}
        className="mt-11 flex flex-wrap items-center justify-center gap-3"
      >
        <a
          href="#cockpit"
          className="group inline-flex cursor-pointer items-center gap-2.5 rounded-xl border border-line-hot bg-gradient-to-b from-accent-deep to-accent-deep/40 px-5 py-3.5 font-display text-[13.5px] font-medium text-accent transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:from-accent/20 hover:shadow-[0_0_0_1px_var(--color-accent-soft),0_12px_32px_-10px_var(--color-accent-soft)]"
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
          className="inline-flex cursor-pointer items-center gap-2.5 rounded-xl border border-line bg-white/[0.02] px-5 py-3.5 font-display text-[13.5px] font-medium text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-white/[0.04]"
        >
          Explore domains
        </a>
      </motion.div>
    </section>
  );
}
