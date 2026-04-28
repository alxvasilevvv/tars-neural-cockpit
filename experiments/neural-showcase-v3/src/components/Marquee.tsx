import { motion } from "framer-motion";

/**
 * Infinite horizontal ticker — a HUD "thought stream" rolling under the
 * hero. Items are rendered twice in a row, then translated -50% on a
 * linear loop so the seam is invisible.
 */
export function Marquee({
  items,
  speed = 32,
  className,
  separator = "·",
}: {
  items: string[];
  speed?: number;
  className?: string;
  separator?: string;
}) {
  const row = (
    <div className="flex items-center gap-6 px-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 whitespace-nowrap">
      {items.map((it, i) => (
        <span key={i} className="inline-flex items-center gap-3">
          <span className="text-ink-3">{separator}</span>
          <span>{it}</span>
        </span>
      ))}
    </div>
  );

  const duration = (items.join(" ").length * 0.18) / (speed / 30);

  return (
    <div
      className={`relative overflow-hidden border-y border-line bg-[rgba(0,0,0,0.45)] py-2.5 backdrop-blur-md ${className ?? ""}`}
      aria-hidden="true"
    >
      {/* edge fades */}
      <span
        className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24"
        style={{ background: "linear-gradient(90deg, var(--color-bg-0), transparent)" }}
      />
      <span
        className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24"
        style={{ background: "linear-gradient(-90deg, var(--color-bg-0), transparent)" }}
      />
      <motion.div
        className="flex w-max"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration, ease: "linear", repeat: Infinity }}
      >
        {row}
        {row}
      </motion.div>
    </div>
  );
}
