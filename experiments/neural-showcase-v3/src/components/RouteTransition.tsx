import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * RouteTransition — brand-triad sweep ribbon that flashes briefly
 * across the viewport during route changes.
 *
 * Augments the existing AnimatePresence opacity/y page transition
 * with a deliberate "shared element": a 2px-tall horizontal gradient
 * line that sweeps left → right, peaks for ~120ms, fades out. Reads
 * as a teleport between contexts rather than a fade.
 *
 * Honours `prefers-reduced-motion` — when reduced, mounts nothing
 * (the page-level fade still happens, but no extra motion).
 */
export function RouteTransition() {
  const loc = useLocation();
  const [phase, setPhase] = useState<"idle" | "sweeping">("idle");
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setReduced(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  }, []);

  useEffect(() => {
    if (reduced) return;
    setPhase("sweeping");
    const t = setTimeout(() => setPhase("idle"), 720);
    return () => clearTimeout(t);
  }, [loc.pathname, reduced]);

  if (reduced) return null;

  return (
    <AnimatePresence>
      {phase === "sweeping" && (
        <motion.span
          aria-hidden
          key={loc.pathname}
          initial={{ x: "-110%", opacity: 1 }}
          animate={{ x: "110%", opacity: [1, 1, 0] }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-none fixed inset-x-0 top-[72px] z-[55] h-[2px]"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 35%, #8B5CF6 50%, #06B6D4 65%, transparent 100%)",
            boxShadow:
              "0 0 16px rgba(99,102,241,0.55), 0 0 32px rgba(139,92,246,0.4)",
          }}
        />
      )}
    </AnimatePresence>
  );
}
