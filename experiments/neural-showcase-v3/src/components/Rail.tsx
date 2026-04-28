import { motion, useMotionValue, animate } from "framer-motion";
import { useEffect, useState } from "react";
import { Waveform } from "@/components/Waveform";

const STREAMS = ["concept", "memory", "code", "calendar", "mac", "voice"];

export function Rail() {
  const [integrity, setIntegrity] = useState(87.2);
  const v = useMotionValue(87.2);

  useEffect(() => {
    const controls = animate(v, 99.4, {
      duration: 2.2,
      delay: 0.6,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setIntegrity(latest),
    });
    return () => controls.stop();
  }, [v]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
      aria-label="live awareness streams"
      className="relative z-20 mt-10 border-y border-line bg-bg-1/60 backdrop-blur-md"
    >
      <div className="mx-auto grid max-w-[1280px] grid-cols-1 items-center gap-6 px-8 py-3.5 font-mono-tech text-[11px] uppercase tracking-[2.6px] text-ink-2 md:grid-cols-[auto_1fr_auto] md:gap-8 md:px-14">
        <div className="flex items-center gap-4 justify-self-center md:justify-self-start">
          <span className="inline-flex items-center gap-2 text-alert">
            <span
              className="h-1.5 w-1.5 rounded-full bg-alert"
              style={{
                boxShadow: "0 0 10px var(--color-alert-soft)",
                animation: "pulseDot 1.6s ease-in-out infinite",
              }}
            />
            LIVE
          </span>
          <span className="text-ink">SK-09 / CORE</span>
        </div>

        <ul className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          {STREAMS.map((name) => (
            <li key={name} className="inline-flex items-center gap-1.5">
              <span
                className="h-1 w-1 rounded-full bg-accent"
                style={{ boxShadow: "0 0 8px var(--color-accent-soft)" }}
              />
              {name}
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap items-center justify-center gap-4 justify-self-center md:justify-self-end">
          <span className="inline-flex items-center gap-2">
            integrity
            <Waveform
              bars={20}
              width={84}
              height={14}
              className="opacity-90"
            />
            <strong className="font-display text-[13px] font-medium text-ink tabular-nums">
              {integrity.toFixed(1)}
              <em className="ml-0.5 text-[10px] not-italic text-ink-2">%</em>
            </strong>
          </span>
          <span className="inline-flex items-center gap-2">
            streams <strong className="font-display text-[13px] font-medium text-ink">06 / 06</strong>
          </span>
          <span className="inline-flex items-center gap-2">
            latency
            <strong className="font-display text-[13px] font-medium text-ink tabular-nums">
              0.04<em className="ml-0.5 text-[10px] not-italic text-ink-2">ms</em>
            </strong>
          </span>
        </div>
      </div>
    </motion.section>
  );
}
