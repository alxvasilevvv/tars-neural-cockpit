import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { sound } from "@/lib/sound";
import { KineticText } from "@/components/KineticText";

export function Footer() {
  return (
    <footer
      id="cockpit"
      className="relative z-20 mt-12 grid grid-cols-1 items-end gap-10 border-t border-line bg-gradient-to-b from-transparent to-bg-0/85 px-8 pb-20 pt-24 md:px-14"
    >
      {/* Decorative tracking line */}
      <div
        aria-hidden
        className="absolute left-0 right-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, var(--color-line-strong) 14%, var(--color-line-hot) 50%, var(--color-line-strong) 86%, transparent)",
        }}
      />

      {/* Massive kinetic CTA */}
      <Link
        to="/cockpit"
        onClick={() => sound.click()}
        className="group block w-full"
      >
        <div className="grid grid-cols-1 items-end gap-6 md:grid-cols-[1fr_auto]">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-[clamp(3rem,12vw,11rem)] font-medium uppercase leading-[0.92] tracking-[0.04em] text-ink"
          >
            <span className="relative inline-block">
              {/* Liquid metal layer underneath */}
              <span
                aria-hidden
                className="absolute inset-0 -z-10 bg-clip-text text-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                style={{
                  backgroundImage:
                    "linear-gradient(118deg, transparent 30%, var(--color-accent) 48%, var(--color-hud) 56%, transparent 70%)",
                  backgroundSize: "240% 100%",
                  backgroundPosition: "left",
                  WebkitBackgroundClip: "text",
                  animation: "tars-shimmer 1.6s ease-in-out infinite",
                }}
              >
                <KineticText text="OPEN" /> <KineticText text="COCKPIT" delay={0.08} />
              </span>
              <span className="relative">
                <KineticText text="OPEN" /> <KineticText text="COCKPIT" delay={0.08} />
              </span>
            </span>
          </motion.div>

          <motion.span
            whileHover={{ x: 6 }}
            transition={{ type: "spring", stiffness: 240, damping: 22 }}
            className="inline-grid h-16 w-16 place-items-center rounded-full border border-line-strong text-ink-2 transition-all duration-200 group-hover:border-accent group-hover:bg-accent-deep group-hover:text-accent"
          >
            <ArrowRight size={20} strokeWidth={1.6} />
          </motion.span>
        </div>
      </Link>

      <div className="grid gap-1 border-t border-line pt-6 text-left font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 md:grid-cols-3">
        <span>TARS · meeet.world</span>
        <span className="md:text-center">local-first · privacy by default</span>
        <span className="md:text-right">trace_id ready · contract 1.0.0</span>
      </div>
    </footer>
  );
}
