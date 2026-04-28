import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { Waveform } from "@/components/Waveform";
import {
  subscribeAwareness,
  type AwarenessEvent,
  type AwarenessHello,
} from "@/lib/awareness";

interface PulseSlot {
  cpu: number;
  ram: number;
  ticks: number;
  uptime_s: number;
}

const ZERO: PulseSlot = { cpu: 0, ram: 0, ticks: 0, uptime_s: 0 };

export function AwarenessTicker() {
  const [pulse, setPulse] = useState<PulseSlot>(ZERO);
  const [hello, setHello] = useState<AwarenessHello | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "down">(
    "connecting",
  );

  useEffect(() => {
    const dispose = subscribeAwareness({
      onOpen: () => setStatus("live"),
      onError: () => setStatus("down"),
      onEvent: (e: AwarenessEvent) => {
        if (e.kind === "hello") setHello(e);
        else if (e.kind === "system.pulse") {
          setPulse({
            cpu: e.cpu,
            ram: e.ram,
            ticks: e.tick + 1,
            uptime_s: e.uptime_s,
          });
        } else if (e.kind === "domain.heartbeat") {
          setRecent((rs) => [`${e.slug} · q${e.queue_depth}`, ...rs].slice(0, 6));
        } else if (e.kind === "bye") {
          setStatus("down");
        }
      },
    });
    return dispose;
  }, []);

  const tone =
    status === "live" ? "success" : status === "down" ? "alert" : "muted";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="relative grid grid-cols-1 gap-px overflow-hidden rounded-[10px] border border-line bg-line md:grid-cols-[260px_1fr_260px]"
    >
      {/* Identity */}
      <div className="relative bg-bg-1 p-4">
        <CornerFrame />
        <div className="mb-2 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          <span>awareness // sse</span>
          <StatusLozenge
            label={status === "live" ? "LIVE" : status === "down" ? "DOWN" : "WAIT"}
            tone={tone}
          />
        </div>
        <div className="font-display text-[14px] uppercase tracking-[0.04em] text-ink">
          {hello?.service ?? "tars"} <span className="text-ink-2">v{hello?.version ?? "—"}</span>
        </div>
        <div className="mt-1 truncate font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
          trace {hello?.trace_id?.slice(0, 16) ?? "—"}
        </div>
      </div>

      {/* Pulses */}
      <div className="relative bg-bg-1 p-4">
        <CornerFrame />
        <div className="mb-2 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          <span>system pulse · tick {pulse.ticks.toString().padStart(3, "0")}</span>
          <span className="text-ink tabular-nums">
            uptime {pulse.uptime_s.toFixed(1)}s
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Bar label="CPU" value={pulse.cpu} color="var(--color-accent)" />
          <Bar label="RAM" value={pulse.ram} color="var(--color-hud)" />
        </div>
      </div>

      {/* Recent heartbeats */}
      <div className="relative bg-bg-1 p-4">
        <CornerFrame />
        <div className="mb-2 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
          <span>domain heartbeats</span>
          <Waveform
            bars={14}
            width={56}
            height={12}
            color="var(--color-accent)"
          />
        </div>
        <ul className="grid gap-1 font-mono-tech text-[10.5px] tracking-[0.6px] text-ink-2">
          {recent.length === 0 && (
            <li className="text-ink-3">…awaiting first frame</li>
          )}
          {recent.map((r, i) => (
            <li
              key={`${r}-${i}`}
              className={i === 0 ? "text-accent" : "text-ink-2"}
            >
              {r}
            </li>
          ))}
        </ul>
      </div>
    </motion.div>
  );
}

function Bar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const pct = Math.max(0, Math.min(value, 1));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-3">
        <span>{label}</span>
        <span className="tabular-nums text-ink">{(pct * 100).toFixed(1)}%</span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-sm bg-[rgba(255,255,255,0.06)]">
        <motion.span
          className="absolute inset-y-0 left-0"
          style={{
            background: color,
            boxShadow: `0 0 12px ${color}`,
          }}
          animate={{ width: `${pct * 100}%` }}
          transition={{ type: "spring", stiffness: 220, damping: 26 }}
        />
      </div>
    </div>
  );
}
