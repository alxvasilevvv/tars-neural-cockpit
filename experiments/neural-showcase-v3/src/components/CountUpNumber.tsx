import { animate, useInView, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useRef } from "react";

/**
 * CountUpNumber — primitive animated counter using framer-motion's
 * `animate()` driving a `MotionValue<number>`. Triggers once when the
 * element enters the viewport. Respects `prefers-reduced-motion`.
 *
 * Wave 7 polish: replaces static stat numbers across the marketing
 * surface (Pitch slide 0, ProofStrip on landing) with a premium
 * count-up animation. No external deps.
 *
 * Usage:
 *   <CountUpNumber value={28} duration={1.4} />
 *   <CountUpNumber value={14} suffix="+" />
 */
export function CountUpNumber({
  value,
  from = 0,
  duration = 1.6,
  delay = 0,
  decimals = 0,
  suffix = "",
  prefix = "",
  className,
  /** ms to wait once visible before kicking off (overrides delay if set) */
  startDelay,
  /** if true, restart animation on every viewport entry instead of just first */
  every = false,
}: {
  value: number;
  from?: number;
  duration?: number;
  delay?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
  startDelay?: number;
  every?: boolean;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: !every, margin: "-10% 0px" });
  const mv = useMotionValue(from);
  const display = useTransform(mv, (n) =>
    `${prefix}${n.toFixed(decimals)}${suffix}`,
  );

  useEffect(() => {
    if (!inView) return;
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion) {
      // Snap to final state, no animation.
      mv.set(value);
      if (ref.current) {
        ref.current.textContent = `${prefix}${value.toFixed(decimals)}${suffix}`;
      }
      return;
    }

    const t = setTimeout(() => {
      const controls = animate(mv, value, {
        duration,
        ease: [0.22, 1, 0.36, 1],
        delay,
      });
      return () => controls.stop();
    }, startDelay ?? 0);

    return () => clearTimeout(t);
  }, [inView, value, duration, delay, startDelay, decimals, mv, prefix, suffix]);

  // Subscribe to motion value → render text imperatively for perf.
  useEffect(() => {
    if (!ref.current) return;
    const unsub = display.on("change", (latest) => {
      if (ref.current) ref.current.textContent = latest;
    });
    return () => unsub();
  }, [display]);

  return (
    <span ref={ref} className={className} aria-label={`${prefix}${value}${suffix}`}>
      {`${prefix}${from.toFixed(decimals)}${suffix}`}
    </span>
  );
}
