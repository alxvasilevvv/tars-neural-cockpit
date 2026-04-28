import { motion, useMotionValue, animate } from "framer-motion";
import { useEffect, useState } from "react";
import { Reticle, Crosshair, StatusLozenge, CornerFrame, BarStack } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";

/**
 * Four floating HUD plates around the hero stage.
 * Each plate is a small data module — IDs, mini-bars, status pills.
 * Hidden under 880px to keep mobile clean.
 */

function Plate({
  className,
  children,
  delay = 0,
  origin = "tl",
}: {
  className?: string;
  children: React.ReactNode;
  delay?: number;
  origin?: "tl" | "tr" | "bl" | "br";
}) {
  const xFrom = origin.endsWith("l") ? -8 : 8;
  return (
    <motion.aside
      initial={{ opacity: 0, x: xFrom, y: origin.startsWith("t") ? -6 : 6 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration: 0.9, delay, ease: [0.22, 1, 0.36, 1] }}
      className={`pointer-events-none absolute hidden md:block ${className ?? ""}`}
    >
      <div className="relative w-[220px] rounded-[6px] border border-line bg-[rgba(0,0,0,0.55)] px-3.5 py-2.5 backdrop-blur-md">
        <CornerFrame />
        {children}
      </div>
    </motion.aside>
  );
}

function CountUp({
  to,
  format,
  duration = 2.2,
  delay = 0.8,
  className,
}: {
  to: number;
  format: (v: number) => string;
  duration?: number;
  delay?: number;
  className?: string;
}) {
  const v = useMotionValue(0);
  const [text, setText] = useState(format(0));
  useEffect(() => {
    const c = animate(v, to, {
      duration,
      delay,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setText(format(latest)),
    });
    return () => c.stop();
  }, [to, duration, delay, format, v]);
  return <span className={className}>{text}</span>;
}

export function HudPlates() {
  return (
    <>
      {/* TL — system identity + uplink reticle */}
      <Plate
        origin="tl"
        delay={0.2}
        className="left-[clamp(16px,4vw,80px)] top-[140px]"
      >
        <header className="mb-2 flex items-center justify-between gap-2 font-mono-tech text-[9px] uppercase tracking-[2.6px] text-ink-2">
          <span className="text-ink">SYS//TARS-09</span>
          <Reticle size={14} className="text-hud" />
        </header>
        <div className="grid grid-cols-[1fr_auto] items-end gap-2">
          <div>
            <div className="font-mono-tech text-[9px] uppercase tracking-[2.4px] text-ink-2">uplink integrity</div>
            <CountUp
              to={99.4}
              format={(v) => v.toFixed(2)}
              duration={2.4}
              delay={0.9}
              className="font-display text-[20px] font-semibold tracking-[0.02em] text-accent"
            />
            <em className="ml-0.5 font-mono-tech text-[10px] not-italic text-ink-2">%</em>
          </div>
          <BarStack
            values={[0.2, 0.45, 0.7, 0.55, 0.8, 0.62, 0.95, 0.7]}
            height={22}
            width={64}
            color="var(--color-accent)"
          />
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <StatusLozenge label="ONLINE" tone="success" />
          <StatusLozenge label="LOCAL" tone="muted" />
        </div>
      </Plate>

      {/* TR — coordinates + crosshair */}
      <Plate
        origin="tr"
        delay={0.32}
        className="right-[clamp(16px,4vw,80px)] top-[140px]"
      >
        <header className="mb-2 flex items-center justify-between gap-2 font-mono-tech text-[9px] uppercase tracking-[2.6px] text-ink-2">
          <Crosshair size={14} className="text-hud" />
          <span className="text-ink">CORE.LOCK</span>
        </header>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
          <span>lat</span>
          <span className="text-right text-ink tabular-nums">42.31°N</span>
          <span>lon</span>
          <span className="text-right text-ink tabular-nums">71.06°W</span>
          <span>z</span>
          <span className="text-right text-ink tabular-nums">+128 m</span>
          <span>t</span>
          <span className="text-right text-ink tabular-nums">04:21:08</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <StatusLozenge label="LOCKED" tone="hud" />
        </div>
      </Plate>

      {/* BL — awareness streams (live waveforms) */}
      <Plate
        origin="bl"
        delay={0.44}
        className="left-[clamp(16px,4vw,80px)] bottom-[120px]"
      >
        <header className="mb-2 flex items-center justify-between gap-2 font-mono-tech text-[9px] uppercase tracking-[2.6px] text-ink-2">
          <span className="text-ink">AWARENESS//06</span>
          <span className="text-accent">LIVE</span>
        </header>
        <ul className="grid gap-1 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
          {["concept", "memory", "code", "calendar", "mac", "voice"].map((s, i) => (
            <li key={s} className="flex items-center justify-between gap-2">
              <span className="text-ink">{s}</span>
              <Waveform
                bars={14}
                width={70}
                height={10}
                color={i % 3 === 0 ? "var(--color-accent)" : "var(--color-hud)"}
                className="opacity-90"
              />
            </li>
          ))}
        </ul>
      </Plate>

      {/* BR — tracking ID + run state */}
      <Plate
        origin="br"
        delay={0.56}
        className="right-[clamp(16px,4vw,80px)] bottom-[120px]"
      >
        <header className="mb-2 flex items-center justify-between gap-2 font-mono-tech text-[9px] uppercase tracking-[2.6px] text-ink-2">
          <span className="text-ink">TRACE//SK-09</span>
          <span className="text-accent tabular-nums">0.04ms</span>
        </header>
        <div className="font-mono-tech text-[11px] tabular-nums text-ink">
          trc_<span className="text-accent">1777384</span>800687_<span className="text-hud">XS3o4ppEr68</span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 font-mono-tech text-[9.5px] uppercase tracking-[2.2px] text-ink-2">
          <div>
            <div>cpu</div>
            <div className="text-ink tabular-nums">12%</div>
          </div>
          <div>
            <div>gpu</div>
            <div className="text-ink tabular-nums">38%</div>
          </div>
          <div>
            <div>ram</div>
            <div className="text-ink tabular-nums">2.4G</div>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <StatusLozenge label="STREAMING" tone="accent" />
        </div>
      </Plate>
    </>
  );
}
