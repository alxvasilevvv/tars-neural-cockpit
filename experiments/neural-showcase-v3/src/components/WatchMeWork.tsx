import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef } from "react";
import { X, Anchor, Activity, Clock, Cpu } from "lucide-react";
import { RobotAvatar, type RobotState } from "@/components/RobotAvatar";
import { BrandHairline } from "@/components/BrandHairline";
import { sound } from "@/lib/sound";
import { useFocusTrap } from "@/lib/useFocusTrap";

/**
 * <WatchMeWork /> — full-screen "operator cinema" mode.
 *
 * Pulls the operator out of the cockpit's dense UI and gives them a
 * single-page experience: a large TARS-9 in the centre, a left rail
 * of cinematic timeline events streaming past, a right rail with
 * the headline metrics. Activated from the cockpit (Cmd+Shift+W or a
 * button on the robot panel), dismissed with Esc.
 *
 * Driven entirely by the existing trace events the cockpit already
 * keeps in state — this surface is a presenter, not a fetcher. The
 * caller passes `events`, `state`, and a few headline numbers; the
 * component owns layout + motion only.
 *
 * Performance budget: zero new fetches, zero images, ~2 KB gzipped
 * extra. Uses framer-motion translate + opacity only (GPU). Respects
 * prefers-reduced-motion via the global media query in index.css.
 */

export interface WatchMeWorkEvent {
  at: string; // HH:MM:SS or ISO time
  kind: "request" | "ok" | "error";
  text: string;
  trace_id?: string | null;
  took_ms?: number;
}

export interface WatchMeWorkProps {
  open: boolean;
  onClose: () => void;
  /** Most recent events first (cockpit's trace[] is already in this shape) */
  events: WatchMeWorkEvent[];
  /** Drives the robot's halo / scan rate */
  state?: RobotState;
  /** Optional metrics — falls back to derived from events when absent */
  uptimeS?: number | null;
  totalEvents?: number;
  avgLatencyMs?: number | null;
}

export function WatchMeWork({
  open,
  onClose,
  events,
  state = "idle",
  uptimeS,
  totalEvents,
  avgLatencyMs,
}: WatchMeWorkProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, open);

  // Esc-to-close + lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  // Soundboard — when WatchMeWork is open AND sound is unmuted, play a
  // subtle cue per *new* event. We track the most-recent event signature
  // so re-renders without new events stay silent. `sound.on` gates by
  // user opt-in (started muted to satisfy autoplay policies).
  const lastSigRef = useRef<string | null>(null);
  useEffect(() => {
    if (!open || !sound.on) return;
    const head = events[0];
    if (!head) return;
    const sig = `${head.at}|${head.kind}|${head.text.slice(0, 16)}`;
    if (sig === lastSigRef.current) return;
    lastSigRef.current = sig;
    if (head.kind === "ok") sound.confirm();
    else if (head.kind === "error") sound.click();
    else sound.tick();
  }, [open, events]);

  // Derive event-rate (events per minute) from the last 10 events'
  // timestamps. Pure presentation, never wrong-but-helpful: only shown
  // once we have ≥3 events with parseable HH:MM:SS.
  const eventsPerMin = derivePerMinute(events);
  const errors = events.filter(e => e.kind === "error").length;
  const total = totalEvents ?? events.length;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={dialogRef}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          aria-label="watch me work"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.32 }}
          className="fixed inset-0 z-[100] overflow-hidden bg-bg-0"
        >
          {/* Ambient brand mesh — radial gradient anchored top-left,
              second one bottom-right. Both are static blurred radials,
              cheap on GPU vs animated meshes. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(40% 35% at 14% 14%, color-mix(in srgb, var(--brand-indigo) 22%, transparent) 0%, transparent 70%), radial-gradient(45% 40% at 86% 86%, color-mix(in srgb, var(--brand-cyan) 18%, transparent) 0%, transparent 75%)",
            }}
          />

          <BrandHairline />

          {/* Top bar */}
          <header className="relative z-10 flex items-center justify-between px-6 py-4 md:px-10">
            <div className="inline-flex items-center gap-2.5 font-mono-tech text-[10.5px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
              <span aria-hidden className="opacity-50">//</span>
              <span>WATCH ME WORK</span>
              <span aria-hidden className="opacity-50">//</span>
              <RunningPill state={state} />
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close watch-me-work"
              className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-1/60 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
            >
              <X size={11} strokeWidth={1.8} aria-hidden />
              <span>esc</span>
            </button>
          </header>

          {/* Main 3-column cinema */}
          <div className="relative z-10 grid h-[calc(100vh-72px)] grid-cols-1 gap-6 px-6 pb-8 md:px-10 lg:grid-cols-[320px_1fr_320px]">
            {/* Left — streaming timeline */}
            <aside
              aria-label="trace timeline"
              className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/40 backdrop-blur-md"
            >
              <BrandHairline />
              <header className="flex items-center justify-between border-b border-line/60 px-5 py-3.5">
                <span className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2">
                  <Activity
                    size={12}
                    strokeWidth={1.7}
                    aria-hidden
                    style={{ color: "var(--brand-violet)" }}
                  />
                  trace · live
                </span>
                <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 tabular-nums">
                  {events.length} {events.length === 1 ? "event" : "events"}
                </span>
              </header>
              <ol
                className="grid gap-1 overflow-auto px-5 py-4 font-mono-tech text-[11.5px]"
                style={{ maxHeight: "calc(100vh - 220px)" }}
              >
                <AnimatePresence initial={false}>
                  {events.length === 0 && (
                    <motion.li
                      key="empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="px-1 py-2 text-ink-3"
                    >
                      no events yet · run an action
                    </motion.li>
                  )}
                  {events.map((e, i) => (
                    <motion.li
                      key={`${e.at}-${i}-${e.text.slice(0, 6)}`}
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                      className="grid grid-cols-[60px_auto_1fr_auto] items-baseline gap-2 border-b border-line/40 py-1.5"
                    >
                      <span className="text-ink-3 tabular-nums">{e.at}</span>
                      <KindGlyph kind={e.kind} />
                      <span
                        className={
                          e.kind === "error"
                            ? "truncate text-alert"
                            : e.kind === "ok"
                              ? "truncate text-ink"
                              : "truncate text-accent"
                        }
                        title={e.text}
                      >
                        {e.text}
                      </span>
                      {typeof e.took_ms === "number" && (
                        <span className="text-ink-3 tabular-nums">
                          {e.took_ms.toFixed(1)}ms
                        </span>
                      )}
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ol>
            </aside>

            {/* Center — TARS-9 hero */}
            <div className="relative grid place-items-center">
              <div className="flex flex-col items-center gap-6">
                <RobotAvatar state={state} width={300} />
                <div className="text-center">
                  <div className="font-display text-[20px] tracking-[-0.005em] text-ink">
                    TARS-9
                  </div>
                  <div className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[3px] text-ink-3">
                    {state === "thinking" && "running an action"}
                    {state === "ok" && "last invoke ok"}
                    {state === "error" && "last invoke errored"}
                    {state === "idle" && "awaiting your command"}
                    {state === "listening" && "listening · voice mode"}
                    {state === "speaking" && "speaking · response stream"}
                  </div>
                </div>
              </div>
            </div>

            {/* Right — headline metrics */}
            <aside
              aria-label="metrics"
              className="grid gap-4 self-start"
            >
              <BigMetric
                Icon={Cpu}
                label="contract"
                value="1.1.0"
                accent="var(--brand-indigo)"
              />
              <BigMetric
                Icon={Clock}
                label="uptime"
                value={uptimeS != null ? formatUptime(uptimeS) : "—"}
                accent="var(--brand-violet)"
              />
              <BigMetric
                Icon={Activity}
                label="events / min"
                value={eventsPerMin != null ? `${eventsPerMin}` : "—"}
                accent="var(--brand-cyan)"
              />
              <BigMetric
                Icon={Anchor}
                label="errors · total"
                value={`${errors} · ${total}`}
                accent={errors > 0 ? "var(--color-alert)" : "var(--brand-orchid)"}
              />
              {avgLatencyMs != null && (
                <BigMetric
                  Icon={Activity}
                  label="avg latency"
                  value={`${avgLatencyMs.toFixed(0)}ms`}
                  accent="var(--brand-orchid)"
                />
              )}
            </aside>
          </div>

          {/* Bottom hint */}
          <footer
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-3 z-10 flex justify-center font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3"
          >
            press <kbd className="mx-1 inline-block border border-line/60 bg-bg-1 px-1.5 py-0.5">esc</kbd> to exit
          </footer>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ─── Subcomponents ─────────────────────────────────────────────── */

function KindGlyph({ kind }: { kind: WatchMeWorkEvent["kind"] }) {
  const color =
    kind === "error"
      ? "var(--color-alert)"
      : kind === "ok"
        ? "var(--color-success)"
        : "var(--brand-indigo)";
  const symbol = kind === "error" ? "×" : kind === "ok" ? "←" : "→";
  return (
    <span
      aria-hidden
      className="inline-block w-3 text-center tabular-nums"
      style={{ color }}
    >
      {symbol}
    </span>
  );
}

function RunningPill({ state }: { state: RobotState }) {
  const color =
    state === "thinking"
      ? "var(--brand-violet)"
      : state === "ok"
        ? "var(--color-success)"
        : state === "error"
          ? "var(--color-alert)"
          : state === "listening"
            ? "var(--brand-cyan)"
            : state === "speaking"
              ? "var(--brand-orchid)"
              : "var(--color-success)";
  const label =
    state === "thinking"
      ? "running"
      : state === "listening"
        ? "listening"
        : state === "speaking"
          ? "speaking"
          : "ready";
  return (
    <span className="inline-flex items-center gap-1.5" style={{ color }}>
      <motion.span
        className="h-1 w-1 rounded-full"
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
      />
      <span>{label}</span>
    </span>
  );
}

function BigMetric({
  Icon,
  label,
  value,
  accent,
}: {
  Icon: typeof Activity;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-5 py-5 backdrop-blur-md">
      <BrandHairline />
      <div className="flex items-center justify-between">
        <span
          className="inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3"
        >
          <Icon
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: accent }}
          />
          {label}
        </span>
      </div>
      <div
        className="mt-3 font-display font-medium leading-none tabular-nums"
        style={{ fontSize: "clamp(1.6rem, 3vw, 2.2rem)", color: accent }}
      >
        {value}
      </div>
    </div>
  );
}

/* ─── Helpers ───────────────────────────────────────────────────── */

function formatUptime(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

/** Best-effort events-per-minute from HH:MM:SS strings. */
function derivePerMinute(events: WatchMeWorkEvent[]): number | null {
  const parsed = events
    .slice(0, 10)
    .map(e => parseHms(e.at))
    .filter((n): n is number => n != null);
  if (parsed.length < 3) return null;
  const youngest = Math.max(...parsed);
  const oldest = Math.min(...parsed);
  const spanS = (youngest - oldest) / 1000;
  if (spanS <= 0) return null;
  return Math.round((parsed.length / spanS) * 60);
}

function parseHms(s: string): number | null {
  // Accept HH:MM:SS or ISO; fall back to null.
  const hms = /^(\d{2}):(\d{2}):(\d{2})$/.exec(s);
  if (hms) {
    const today = new Date();
    today.setHours(+hms[1], +hms[2], +hms[3], 0);
    return today.getTime();
  }
  const iso = Date.parse(s);
  return Number.isNaN(iso) ? null : iso;
}
