import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  subscribeAwareness,
  type AwarenessEvent,
  type AwarenessHello,
} from "@/lib/awareness";

/**
 * AwarenessTicker v2 — single-line ticker bar.
 *
 * Per `AGENT_HANDOFF.md → Owned by Claude Code (design)` item 7:
 * dropped the 3-pane card strip in favour of a slim 36-40px row
 * that reads as live telemetry rather than a dashboard panel.
 *
 * Slots (left → right):
 *   1. status pill (LIVE/DOWN/WAIT)
 *   2. identity (service · version · short trace_id)
 *   3. tick counter + uptime
 *   4. CPU bar (mini-meter)
 *   5. RAM bar (mini-meter)
 *   6. heartbeat marquee — recent domain heartbeats scrolling right→left
 *
 * Functional contract preserved — same `subscribeAwareness()` source.
 */

interface Pulse {
  cpu: number;
  ram: number;
  ticks: number;
  uptime_s: number;
}
const ZERO: Pulse = { cpu: 0, ram: 0, ticks: 0, uptime_s: 0 };

type Status = "connecting" | "live" | "down";

export function AwarenessTicker() {
  const [pulse, setPulse] = useState<Pulse>(ZERO);
  const [hello, setHello] = useState<AwarenessHello | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("connecting");

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
          setRecent(rs => [`${e.slug} · q${e.queue_depth}`, ...rs].slice(0, 12));
        } else if (e.kind === "bye") {
          setStatus("down");
        }
      },
    });
    return dispose;
  }, []);

  const statusTone =
    status === "live"
      ? { color: "var(--color-success)", label: "LIVE" }
      : status === "down"
        ? { color: "var(--color-alert)", label: "DOWN" }
        : { color: "var(--color-ink-3)", label: "WAIT" };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      role="status"
      aria-label="awareness telemetry"
      className="relative flex items-center gap-4 overflow-hidden rounded-[10px] border border-line bg-bg-1/70 px-3 py-2 font-mono-tech text-[10px] uppercase tracking-[2px] backdrop-blur-sm md:gap-5 md:px-4"
      style={{ minHeight: 38 }}
    >
      {/* Top brand-triad hairline */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(99,102,241,0.6) 30%, rgba(139,92,246,0.6) 50%, rgba(6,182,212,0.6) 70%, transparent 100%)",
          opacity: status === "live" ? 1 : 0.32,
        }}
      />

      {/* 1. Status pill */}
      <span
        className="inline-flex shrink-0 items-center gap-1.5"
        style={{ color: statusTone.color }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background: statusTone.color,
            boxShadow: status === "live" ? "0 0 8px var(--color-success)" : undefined,
            animation:
              status === "live" ? "pulseDot 1.6s ease-in-out infinite" : undefined,
          }}
          aria-hidden
        />
        {statusTone.label}
      </span>

      <Sep />

      {/* 2. Identity */}
      <span className="hidden shrink-0 items-baseline gap-2 text-ink-2 sm:inline-flex">
        <span className="text-ink">{hello?.service ?? "tars"}</span>
        <span className="text-ink-3">v{hello?.version ?? "—"}</span>
        <span className="text-ink-3">·</span>
        <span className="text-ink-3" title={hello?.trace_id ?? ""}>
          trc {hello?.trace_id?.slice(0, 8) ?? "—"}
        </span>
      </span>

      <Sep className="hidden sm:block" />

      {/* 3. Tick + uptime */}
      <span className="hidden shrink-0 items-baseline gap-2 text-ink-2 md:inline-flex">
        <span className="text-ink-3">tick</span>
        <span className="tabular-nums text-ink">
          {pulse.ticks.toString().padStart(3, "0")}
        </span>
        <span className="text-ink-3">·</span>
        <span className="tabular-nums text-ink">
          {pulse.uptime_s.toFixed(1)}s
        </span>
      </span>

      <Sep className="hidden md:block" />

      {/* 4. CPU mini-meter */}
      <MiniMeter label="CPU" value={pulse.cpu} color="#6366F1" />

      {/* 5. RAM mini-meter */}
      <MiniMeter label="RAM" value={pulse.ram} color="#06B6D4" />

      <Sep />

      {/* 6. Heartbeat marquee */}
      <div className="relative min-w-0 flex-1 overflow-hidden">
        {recent.length === 0 ? (
          <span className="text-ink-3">…awaiting first frame</span>
        ) : (
          <div
            className="flex animate-[tickerScroll_24s_linear_infinite] items-baseline gap-6 whitespace-nowrap will-change-transform"
            aria-live="polite"
          >
            {recent.concat(recent).map((r, i) => (
              <span
                key={`${r}-${i}`}
                className={i % recent.length === 0 ? "text-accent" : "text-ink-2"}
              >
                <span className="text-ink-3 mr-1">▸</span>
                {r}
              </span>
            ))}
          </div>
        )}
        {/* Right-edge fade */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-12"
          style={{
            background:
              "linear-gradient(to right, transparent, var(--color-bg-1) 80%)",
          }}
        />
      </div>

      <style>{`
        @keyframes tickerScroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: reduce) {
          [class*="animate-[tickerScroll"] { animation: none !important; }
        }
      `}</style>
    </motion.div>
  );
}

function Sep({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`shrink-0 ${className ?? ""}`}
      style={{ width: 1, height: 14, background: "var(--color-line-strong)" }}
    />
  );
}

function MiniMeter({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(value, 1));
  return (
    <span className="inline-flex shrink-0 items-center gap-2 text-ink-3">
      <span>{label}</span>
      <span
        className="relative inline-block h-1.5 w-12 overflow-hidden rounded-sm"
        style={{ background: "rgba(255,255,255,0.06)" }}
      >
        <motion.span
          className="absolute inset-y-0 left-0"
          style={{
            background: color,
            boxShadow: `0 0 8px ${color}55`,
          }}
          animate={{ width: `${pct * 100}%` }}
          transition={{ type: "spring", stiffness: 220, damping: 26 }}
        />
      </span>
      <span className="w-9 tabular-nums text-ink">{(pct * 100).toFixed(0)}%</span>
    </span>
  );
}
