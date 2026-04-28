import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function Footer() {
  return (
    <footer
      id="cockpit"
      className="relative z-20 grid grid-cols-1 items-end gap-8 border-t border-line bg-gradient-to-b from-transparent to-bg-0/85 px-8 pb-20 pt-16 md:grid-cols-[1fr_auto] md:px-14"
    >
      <motion.a
        href="#"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        whileHover={{ x: 4 }}
        className="group inline-flex cursor-pointer items-center gap-5 font-display text-[clamp(2rem,5vw,4rem)] font-extrabold tracking-[-0.04em] text-ink transition-colors duration-200 hover:text-accent"
      >
        Open cockpit
        <span className="inline-grid h-14 w-14 place-items-center rounded-full border border-line-strong text-ink-2 transition-all duration-200 group-hover:border-accent group-hover:bg-accent-deep group-hover:text-accent">
          <ArrowRight size={18} strokeWidth={1.6} />
        </span>
      </motion.a>
      <div className="grid gap-1 text-left font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 md:text-right">
        <span>TARS · meeet.world</span>
        <span>local-first · privacy by default · trace ready</span>
      </div>
    </footer>
  );
}
