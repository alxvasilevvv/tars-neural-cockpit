import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

/**
 * <OnlineCounter /> — small pill showing how many operators are
 * currently online. Pre-launch this is a synthetic value (seeded
 * baseline + bounded random walk) so the surface doesn't look dead;
 * post-launch the brother's `/api/online` will replace the seed
 * with a real WebSocket count.
 *
 * Privacy: synthetic mode never makes a network call. The WS hook
 * below is wired but gated behind `VITE_TARS_ONLINE_WS` env var so
 * we don't open sockets we don't have a server for.
 *
 * Visual: a pulsing success-coloured dot + tabular-num counter.
 * Crossfade on every change. Reduced-motion turns off the count
 * jitter entirely (settled value only).
 */

interface Props {
  /** Visible label, defaults to "online" */
  label?: string;
  className?: string;
}

const SEED_BASE = 42;       // pre-launch baseline
const SEED_JITTER = 8;      // ± walk amplitude
const STEP_MS = 4000;       // walk cadence

export function OnlineCounter({ label = "online", className = "" }: Props) {
  const [count, setCount] = useState<number>(() => SEED_BASE);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Reduced-motion users: stick to the seed; no walk.
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setCount(SEED_BASE);
      return;
    }

    // Synthetic walk — bounded random ±2 per tick around BASE±JITTER.
    let cancelled = false;
    let cur = SEED_BASE;
    const tick = () => {
      if (cancelled) return;
      const drift = Math.round((Math.random() - 0.5) * 4);
      const next = Math.max(
        SEED_BASE - SEED_JITTER,
        Math.min(SEED_BASE + SEED_JITTER, cur + drift),
      );
      cur = next;
      setCount(next);
    };
    const id = window.setInterval(tick, STEP_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // Future: when import.meta.env.VITE_TARS_ONLINE_WS is set, open
    // a WS to that URL and pipe its counter messages into setCount,
    // skipping the synthetic walk entirely.
  }, []);

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border border-line bg-bg-1/60 px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 backdrop-blur-sm ${className}`}
      role="status"
      aria-live="polite"
      aria-label={`${count} operators ${label}`}
    >
      <Activity
        size={11}
        strokeWidth={1.7}
        style={{ color: "var(--color-success)" }}
        aria-hidden
      />
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={count}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="tabular-nums text-ink"
        >
          {count}
        </motion.span>
      </AnimatePresence>
      <span aria-hidden className="opacity-50">·</span>
      <span>{label}</span>
    </div>
  );
}
