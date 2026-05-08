import { motion } from "framer-motion";

/**
 * Decorative section divider — a thin animated horizon line with
 * tech markers, sweeping a faint gradient when it scrolls into view.
 */
export function SectionDivider({ label }: { label?: string }) {
  return (
    <div className="relative z-20 mx-auto max-w-[1280px] px-8 md:px-14">
      {/* Wave 67 — animate (not whileInView) so dividers always render
          with full layout height even when IntersectionObserver fires
          late or fails (e.g. inside heavy parents like ScrollStory's
          400vh pinned context). Prevents intermittent collapsed-divider
          gaps that broke section rhythm after Wave 66 cockpit removal. */}
      <motion.div
        initial={{ opacity: 0, scaleX: 0.4 }}
        animate={{ opacity: 1, scaleX: 1 }}
        transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        className="origin-center"
      >
        <div className="flex items-center gap-3 py-6 font-mono-tech text-[9.5px] uppercase tracking-[3px] text-ink-3">
          <span
            className="inline-block h-1 w-1 rounded-full"
            style={{ background: "var(--color-hud)", boxShadow: "0 0 8px var(--color-hud-soft)" }}
          />
          <span
            className="h-px flex-1"
            style={{
              background:
                "linear-gradient(90deg, transparent, var(--color-line-strong) 18%, var(--color-line-strong) 82%, transparent)",
            }}
          />
          {label && (
            <>
              <span className="whitespace-nowrap">{label}</span>
              <span
                className="h-px flex-1"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, var(--color-line-strong) 18%, var(--color-line-strong) 82%, transparent)",
                }}
              />
            </>
          )}
          <span
            className="inline-block h-1 w-1 rounded-full"
            style={{ background: "var(--color-accent)", boxShadow: "0 0 8px var(--color-accent-soft)" }}
          />
        </div>
      </motion.div>
    </div>
  );
}
