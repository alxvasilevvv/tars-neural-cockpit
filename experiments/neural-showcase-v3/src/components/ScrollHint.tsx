import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * ScrollHint — small bouncing chevron at the bottom of the viewport
 * that fades out after the operator scrolls past 80px. Pure visual
 * affordance — common pattern on premium landing pages so users
 * don't think the page ends at the hero fold.
 *
 * Hidden when:
 *   - User has scrolled past 80px (they got the message)
 *   - prefers-reduced-motion is on
 *   - Viewport is very short (< 600px tall)
 */
export function ScrollHint() {
  const [visible, setVisible] = useState(true);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setReduced(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
    const onScroll = () => {
      if (window.scrollY > 80) setVisible(false);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (reduced) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-none fixed bottom-6 left-1/2 z-30 -translate-x-1/2 hidden md:flex"
          aria-hidden
        >
          <motion.div
            animate={{ y: [0, 6, 0] }}
            transition={{
              duration: 2.2,
              ease: "easeInOut",
              repeat: Infinity,
            }}
            className="flex flex-col items-center gap-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3"
          >
            <span>scroll</span>
            <ChevronDown size={14} strokeWidth={1.6} />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
