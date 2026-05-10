/**
 * <AttendeeDetail /> — Wave 89
 *
 * Side panel that opens when the facilitator clicks an attendee row in
 * the cohort dashboard. Shows:
 *   - header: name + email + current phase pip
 *   - timeline of actions (mock 8-12 entries with timestamps)
 *   - "Mark as needs help" button — POST /api/cohort/{id}/flag
 *   - close → returns to table
 *
 * Keyboard: Esc closes the panel. Click the dim backdrop to dismiss.
 *
 * Mock data shipped for facilitator demo before W2-PR2 backend lands.
 * When `/api/cohort/*` endpoints exist, swap mock fallback for real
 * (same hook contract).
 */

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Flag, Activity } from "lucide-react";
import {
  type Attendee,
  type TimelineEntry,
  buildTimeline,
  flagAttendee,
  phaseLabel,
  phaseTint,
} from "@/lib/cohort";
import { useT } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";

interface AttendeeDetailProps {
  attendee: Attendee | null;
  onClose: () => void;
}

export function AttendeeDetail({ attendee, onClose }: AttendeeDetailProps) {
  const t = useT();
  const [flagState, setFlagState] = useState<"idle" | "saving" | "done">("idle");

  // Reset transient flag state whenever the panel target changes.
  useEffect(() => {
    setFlagState("idle");
  }, [attendee?.id]);

  // Esc-to-close.
  useEffect(() => {
    if (!attendee) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [attendee, onClose]);

  const timeline: TimelineEntry[] = useMemo(
    () => (attendee ? buildTimeline(attendee) : []),
    [attendee],
  );

  async function onFlag(): Promise<void> {
    if (!attendee || flagState === "saving") return;
    setFlagState("saving");
    const res = await flagAttendee(attendee.id);
    setFlagState(res.ok ? "done" : "idle");
  }

  return (
    <AnimatePresence>
      {attendee && (
        <>
          {/* Backdrop */}
          <motion.button
            type="button"
            aria-label={t("cohort.detail.close")}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
          />
          {/* Panel */}
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label={`${attendee.name} — ${t("cohort.detail.title")}`}
            initial={{ opacity: 1, x: 32 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[440px] flex-col border-l border-line bg-bg-0 shadow-2xl"
          >
            {/* Header */}
            <header className="flex items-start justify-between gap-3 border-b border-line px-6 py-5">
              <div className="min-w-0">
                <div className="mb-1 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: phaseTint(attendee.phase) }}
                  />
                  {phaseLabel(attendee.phase)}
                </div>
                <h2 className="truncate font-display text-[20px] font-medium leading-tight tracking-[-0.005em] text-ink">
                  {attendee.name}
                </h2>
                <p className="truncate font-mono-tech text-[11px] text-ink-2">
                  {attendee.email}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("cohort.detail.close")}
                className="inline-flex h-9 w-9 items-center justify-center rounded-sm border border-line bg-bg-1/50 text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                <X size={14} aria-hidden />
              </button>
            </header>

            {/* Quick stats strip */}
            <div className="grid grid-cols-3 gap-px border-b border-line bg-line/40">
              <Stat
                label={t("cohort.detail.playbooks")}
                value={String(attendee.playbooksRun)}
              />
              <Stat
                label={t("cohort.detail.errors")}
                value={String(attendee.errors)}
                tone={attendee.errors > 0 ? "alert" : "neutral"}
              />
              <Stat
                label={t("cohort.detail.idle")}
                value={`${attendee.idleMin}m`}
              />
            </div>

            {/* Timeline */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <h3 className="mb-3 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
                <Activity size={11} aria-hidden />
                {t("cohort.detail.timeline")}
              </h3>
              <ol className="space-y-3">
                {timeline.map((e, i) => (
                  <li
                    key={`${e.at}-${i}`}
                    className="relative pl-5 text-[13px] leading-[1.5] text-ink"
                  >
                    <span
                      aria-hidden
                      className="absolute left-0 top-[7px] h-1.5 w-1.5 rounded-full"
                      style={{
                        background:
                          e.kind === "error"
                            ? "var(--alert, #ef4444)"
                            : e.kind === "phase_advance"
                              ? "var(--brand-cyan)"
                              : "var(--brand-indigo)",
                      }}
                    />
                    <div>{e.label}</div>
                    <div className="mt-0.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                      {fmtTime(e.at)}
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            {/* Footer actions */}
            <footer className="flex items-center justify-between gap-3 border-t border-line px-6 py-4">
              <button
                type="button"
                onClick={onFlag}
                disabled={flagState === "saving" || flagState === "done"}
                className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-line bg-bg-1/50 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-alert hover:text-ink disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-alert"
              >
                <Flag size={12} aria-hidden />
                {flagState === "done"
                  ? t("cohort.detail.flagged")
                  : flagState === "saving"
                    ? t("cohort.detail.flagging")
                    : t("cohort.detail.flag")}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 underline-offset-4 hover:text-ink hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                {t("cohort.detail.close")}
              </button>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "alert";
}) {
  return (
    <div className="bg-bg-0 px-4 py-3">
      <div className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
        {label}
      </div>
      <div
        className="mt-0.5 font-display text-[18px] font-medium tracking-[-0.005em]"
        style={{ color: tone === "alert" ? "var(--alert, #ef4444)" : undefined }}
      >
        {value}
      </div>
    </div>
  );
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

// Re-export TKey so consumers picking up the same i18n surface stay
// in lock-step without repeating the import.
export type _TKey = TKey;
