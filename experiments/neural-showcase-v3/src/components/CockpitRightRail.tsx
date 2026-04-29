import { motion, AnimatePresence } from "framer-motion";
import { Activity, Anchor, Layers, Zap, Maximize2, Mic, MicOff, AlertCircle, Gauge } from "lucide-react";
import { RobotAvatar, type RobotState } from "@/components/RobotAvatar";
import { BrandHairline } from "@/components/BrandHairline";
import { useMicLevel } from "@/lib/micLevel";
import { useHealthLatency, type LatencyTier } from "@/lib/healthLatency";
import { OnlineCounter } from "@/components/OnlineCounter";

/**
 * <CockpitRightRail /> — operator-side companion strip. Sticky on
 * xl+ viewports, stacks under the workspace on smaller. Three panels:
 *
 *   1. RobotAvatar — TARS-9, derives state from {running, lastError}
 *   2. PulsePanel — six concentric live counters (uptime, latency,
 *      open agents, …). Reads from `health` so we don't double-fetch.
 *   3. ReceiptsFeed — last 5 anchor receipts (mock-shaped today;
 *      brother's `/api/receipts/recent` will land here verbatim).
 *
 * The rail is intentionally *quiet* — no big CTAs, no decoration that
 * competes with the workspace. Operators glance at it; they don't
 * stare. Every animated element respects prefers-reduced-motion.
 */

interface PulseFact {
  Icon: typeof Activity;
  label: string;
  value: string;
  accent: string;
}

interface Receipt {
  id: string;
  what: string;
  ts: string;
  ok: boolean;
}

// Mock receipts — replace with brother's `/api/receipts/recent` when it
// lands. The shape is intentionally small (id / text / time / ok) to
// avoid bikeshedding the wire format too early.
const MOCK_RECEIPTS: Receipt[] = [
  { id: "rcp_a91f0c2", what: "files.move · 47 → ~/Downloads", ts: "08:42:04", ok: true },
  { id: "rcp_82d4e88", what: "calendar.brief · 3 events", ts: "08:14:11", ok: true },
  { id: "rcp_71b09f5", what: "wallet.sign_solana · 0.5 SOL", ts: "07:55:32", ok: true },
  { id: "rcp_60a2c1d", what: "github.review · PR #142", ts: "07:42:07", ok: true },
  { id: "rcp_4f9e3b2", what: "research.summarise · arxiv:2305", ts: "06:55:18", ok: true },
];

export interface CockpitRightRailProps {
  /** Derive the robot's state from the workspace */
  running?: boolean;
  lastError?: string | null;
  lastOk?: boolean | null;
  /** Optional uptime + meeet-online flags from the existing /health call */
  uptimeS?: number | null;
  meeetOnline?: boolean | null;
  /** Voice mode — when true, robot enters `listening` state */
  voiceListening?: boolean;
  onToggleVoice?: () => void;
  /** Open the cinematic Watch-me-work overlay */
  onWatchMeWork?: () => void;
  /** Hide on small viewports — caller decides via Tailwind responsive class */
  className?: string;
}

export function CockpitRightRail({
  running,
  lastError,
  lastOk,
  uptimeS,
  meeetOnline,
  voiceListening,
  onToggleVoice,
  onWatchMeWork,
  className = "",
}: CockpitRightRailProps) {
  // Resolve robot state from the workspace signals. Priority order:
  // running > error > ok > listening > idle. Voice never preempts an
  // in-flight invocation — the operator's command is the source of truth.
  const state: RobotState = running
    ? "thinking"
    : lastError
      ? "error"
      : lastOk
        ? "ok"
        : voiceListening
          ? "listening"
          : "idle";

  // Live mic capture — only requests permission while the operator
  // explicitly toggles voice on. Stops the OS-level mic LED the
  // moment they toggle off (see lib/micLevel.ts teardown).
  const mic = useMicLevel(!!voiceListening);

  // Live /health latency — 5s polling, 60s sliding window. Pauses
  // when the tab is hidden so we don't drain battery in background.
  const latency = useHealthLatency(true);

  const facts: PulseFact[] = [
    {
      Icon: Zap,
      label: "uptime",
      value: uptimeS != null ? formatUptime(uptimeS) : "—",
      accent: "var(--brand-indigo)",
    },
    {
      Icon: Layers,
      label: "contract",
      value: "1.1.0",
      accent: "var(--brand-violet)",
    },
    {
      Icon: Activity,
      label: "meeet",
      value: meeetOnline === null ? "—" : meeetOnline ? "online" : "local",
      accent: meeetOnline ? "var(--brand-cyan)" : "var(--color-ink-3)",
    },
  ];

  return (
    <aside
      aria-label="cockpit status rail"
      className={`flex flex-col gap-4 ${className}`}
    >
      {/* Robot panel — biggest visual moment of the rail */}
      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-5 py-6 backdrop-blur-md">
        <BrandHairline />
        <div className="flex flex-col items-center text-center">
          <RobotStateLine
            state={state}
            uptimeS={uptimeS}
            running={!!running}
          />
          <RobotAvatar
            state={state}
            width={148}
            audioLevel={mic.status === "live" ? mic.level : 0}
            trackCursor
          />
          <RobotCallSign state={state} />

          {/* Mic-status hint — only when there's something to say */}
          {voiceListening && mic.status !== "live" && (
            <div
              role="status"
              className="mt-3 inline-flex items-center gap-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2px]"
              style={{
                color:
                  mic.status === "denied" || mic.status === "unsupported"
                    ? "var(--color-alert)"
                    : "var(--color-ink-3)",
              }}
            >
              {mic.status === "denied" || mic.status === "unsupported" ? (
                <AlertCircle size={11} strokeWidth={1.8} aria-hidden />
              ) : (
                <Mic size={11} strokeWidth={1.8} aria-hidden />
              )}
              <span>
                {mic.status === "requesting" && "asking permission…"}
                {mic.status === "denied" && "mic denied · synthetic pulse"}
                {mic.status === "unsupported" && "no audio · synthetic pulse"}
                {mic.status === "off" && "starting…"}
              </span>
            </div>
          )}

          {/* Robot toolbar — voice toggle + Watch-me-work launcher.
              Two compact pill buttons under the call-sign, only render
              when handlers are wired (callers can omit either). */}
          {(onToggleVoice || onWatchMeWork) && (
            <div className="mt-5 flex w-full items-center justify-center gap-2">
              {onToggleVoice && (
                <button
                  type="button"
                  onClick={onToggleVoice}
                  aria-pressed={!!voiceListening}
                  aria-label={voiceListening ? "Disable voice mode" : "Enable voice mode"}
                  className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] transition-all duration-150"
                  style={{
                    borderColor: voiceListening
                      ? "var(--brand-cyan)"
                      : "var(--color-line)",
                    background: voiceListening
                      ? "color-mix(in srgb, var(--brand-cyan) 12%, transparent)"
                      : "transparent",
                    color: voiceListening
                      ? "var(--brand-cyan)"
                      : "var(--color-ink-3)",
                  }}
                >
                  {voiceListening ? (
                    <Mic size={11} strokeWidth={1.8} aria-hidden />
                  ) : (
                    <MicOff size={11} strokeWidth={1.8} aria-hidden />
                  )}
                  <span>{voiceListening ? "listening" : "voice"}</span>
                </button>
              )}
              {onWatchMeWork && (
                <button
                  type="button"
                  onClick={onWatchMeWork}
                  aria-label="Open Watch-me-work full-screen mode"
                  className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3 transition-all duration-150 hover:border-line-strong hover:text-ink"
                >
                  <Maximize2 size={11} strokeWidth={1.8} aria-hidden />
                  <span>watch</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Pulse facts — four lozenges + a live latency sparkline. */}
      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-md">
        <BrandHairline />
        <ul className="grid gap-px bg-line">
          {facts.map(f => (
            <li
              key={f.label}
              className="grid grid-cols-[20px_1fr_auto] items-center gap-3 bg-bg-1 px-4 py-3"
            >
              <span style={{ color: f.accent }} aria-hidden>
                <f.Icon size={13} strokeWidth={1.7} />
              </span>
              <span className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                {f.label}
              </span>
              <span
                className="font-mono-tech text-[12px] tabular-nums text-ink"
                style={{ color: f.accent }}
              >
                {f.value}
              </span>
            </li>
          ))}
          <li className="grid grid-cols-[20px_1fr_auto_auto] items-center gap-3 bg-bg-1 px-4 py-3">
            <span style={{ color: latencyAccent(latency.tier) }} aria-hidden>
              <Gauge size={13} strokeWidth={1.7} />
            </span>
            <span className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
              latency
            </span>
            <LatencySparkline samples={latency.samples} />
            <span
              className="font-mono-tech text-[12px] tabular-nums"
              style={{ color: latencyAccent(latency.tier) }}
              title="Round-trip to /health, last successful probe"
            >
              {latency.latest != null ? `${latency.latest}ms` : "—"}
            </span>
          </li>
        </ul>
      </div>

      {/* Recent receipts feed */}
      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-md">
        <BrandHairline />
        <header className="flex items-center justify-between border-b border-line/60 px-4 py-3">
          <span className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2">
            <Anchor size={12} strokeWidth={1.7} aria-hidden />
            recent receipts
          </span>
          <OnlineCounter />
        </header>
        <ol className="divide-y divide-line/60">
          {MOCK_RECEIPTS.map((r, i) => (
            <motion.li
              key={r.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 * i, duration: 0.35 }}
              className="grid grid-cols-[1fr_auto] items-baseline gap-3 px-4 py-2.5"
            >
              <div className="min-w-0">
                <div className="truncate font-mono text-[11.5px] text-ink">
                  {r.what}
                </div>
                <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                  {r.id}
                </div>
              </div>
              <div className="text-right font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3 tabular-nums">
                {r.ts}
              </div>
            </motion.li>
          ))}
        </ol>
        <footer className="border-t border-line/60 px-4 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
          anchored · solana memo
        </footer>
      </div>
    </aside>
  );
}

/* ─── Subcomponents ─────────────────────────────────────────────── */

function RobotStateLine({
  state,
  uptimeS,
  running,
}: {
  state: RobotState;
  uptimeS: number | null | undefined;
  running: boolean;
}) {
  const label =
    state === "thinking"
      ? "thinking"
      : state === "ok"
        ? "ok"
        : state === "error"
          ? "error"
          : "ready";
  const dotColor =
    state === "thinking"
      ? "var(--brand-violet)"
      : state === "ok"
        ? "var(--color-success)"
        : state === "error"
          ? "var(--color-alert)"
          : "var(--color-success)";

  return (
    <div className="mb-5 inline-flex items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-3">
      <motion.span
        className="h-1.5 w-1.5 rounded-full"
        style={{
          background: dotColor,
          boxShadow: `0 0 10px ${dotColor}`,
        }}
        animate={{
          opacity: running ? [1, 0.4, 1] : [1, 0.7, 1],
        }}
        transition={{
          duration: running ? 1.0 : 2.4,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <span>{label}</span>
      {uptimeS != null && (
        <>
          <span aria-hidden className="opacity-50">·</span>
          <span className="tabular-nums">{formatUptime(uptimeS)}</span>
        </>
      )}
    </div>
  );
}

function RobotCallSign({ state }: { state: RobotState }) {
  const tag =
    state === "thinking"
      ? "running an action"
      : state === "ok"
        ? "last invoke ok"
        : state === "error"
          ? "last invoke errored"
          : "awaiting your command";
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={state}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="mt-5 flex flex-col items-center gap-1.5"
      >
        <div className="font-display text-[15px] tracking-[-0.005em] text-ink">
          TARS-9
        </div>
        <div className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          {tag}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function formatUptime(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function latencyAccent(tier: LatencyTier): string {
  switch (tier) {
    case "fast": return "var(--color-success)";
    case "ok":   return "var(--brand-cyan)";
    case "slow": return "#f59e0b";
    case "down": return "var(--color-alert)";
  }
}

/**
 * LatencySparkline — 60×16 px line chart with point dots. Auto-scales
 * Y axis to the max non-null sample so the curve always uses the
 * full height. Failed probes (`null` samples) draw nothing — the
 * line skips the gap, no fake floor value misleads the operator.
 */
function LatencySparkline({ samples }: { samples: (number | null)[] }) {
  const W = 60;
  const H = 16;
  const max = Math.max(50, ...samples.filter((n): n is number => n != null));
  const slot = W / Math.max(1, samples.length - 1);

  // Build the polyline path, skipping null gaps so we get multiple
  // segments instead of an artificial drop to 0.
  const segments: string[] = [];
  let cur = "";
  samples.forEach((v, i) => {
    if (v == null) {
      if (cur) {
        segments.push(cur);
        cur = "";
      }
      return;
    }
    const x = i * slot;
    const y = H - (v / max) * (H - 2) - 1;
    cur += cur ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  if (cur) segments.push(cur);

  // Last sample for the cap-dot
  let lastIdx = -1;
  for (let i = samples.length - 1; i >= 0; i--) {
    if (samples[i] != null) {
      lastIdx = i;
      break;
    }
  }
  const last = lastIdx >= 0 ? samples[lastIdx]! : null;
  const lastTier =
    last == null
      ? "down"
      : last < 200
        ? "fast"
        : last < 500
          ? "ok"
          : last < 1500
            ? "slow"
            : "down";
  const stroke = latencyAccent(lastTier);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      role="img"
      aria-label={`last ${samples.length} probes`}
      className="overflow-visible"
    >
      <title>Last {samples.length} /health probes (left = oldest)</title>
      {segments.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke={stroke}
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.85"
        />
      ))}
      {/* failed-probe markers — small ✕ ticks at the baseline */}
      {samples.map((v, i) =>
        v == null ? (
          <circle
            key={`miss-${i}`}
            cx={i * slot}
            cy={H - 1.5}
            r="0.9"
            fill="var(--color-alert)"
            opacity="0.55"
          />
        ) : null,
      )}
      {/* Latest-sample emphasis */}
      {lastIdx >= 0 && last != null && (
        <circle
          cx={lastIdx * slot}
          cy={H - (last / max) * (H - 2) - 1}
          r="1.6"
          fill={stroke}
        />
      )}
    </svg>
  );
}

