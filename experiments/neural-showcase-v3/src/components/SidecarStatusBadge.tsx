import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, CheckCircle2, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSidecarStatus } from "@/lib/useSidecarStatus";

/**
 * <SidecarStatusBadge /> — visible only inside the Tauri desktop
 * shell when the FastAPI sidecar isn't healthy. Browser-build users
 * never see it (the underlying hook returns `unknown` outside Tauri).
 *
 * Placement: render once inside `<AppShell />` after `<ToastBus />`.
 *
 * UX spec:
 *   - "ready"    → the badge briefly slides in (✓ "Backend ready"),
 *                  auto-dismisses after 2.5s.
 *   - "starting" → a tiny pill in the bottom-left corner with a
 *                  spinner. Operator-only, no big visual weight.
 *   - "failed"   → an amber banner pinned bottom-left with the
 *                  failure stage + error excerpt + "How to fix"
 *                  link. Stays visible until either retry succeeds
 *                  (event flips to "ready") or user dismisses.
 *   - "exited"   → red banner with same shape as failed — backend
 *                  was running and crashed mid-session.
 *   - "unknown"  → renders nothing.
 *
 * Wave 60 desktop UX polish.
 */
export function SidecarStatusBadge() {
  const state = useSidecarStatus();
  const [dismissed, setDismissed] = useState(false);
  const [showReady, setShowReady] = useState(false);

  // Auto-dismiss the success badge after 2.5s.
  useEffect(() => {
    if (state.status !== "ready") return;
    setShowReady(true);
    const t = setTimeout(() => setShowReady(false), 2500);
    return () => clearTimeout(t);
  }, [state.status]);

  // Reset dismissed flag whenever status flips back to a problem
  // (so a *new* failure surfaces even if user dismissed an earlier one).
  useEffect(() => {
    if (state.status === "failed" || state.status === "exited") {
      setDismissed(false);
    }
  }, [state.status]);

  if (state.status === "unknown") return null;

  return (
    <AnimatePresence>
      {state.status === "starting" && (
        <motion.div
          key="starting"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.2 }}
          className="fixed bottom-4 left-4 z-40 inline-flex items-center gap-2 rounded-full border border-line bg-bg-1/85 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 backdrop-blur-md"
          role="status"
          aria-live="polite"
        >
          <Loader2 size={11} strokeWidth={2} className="animate-spin" aria-hidden />
          <span>Starting backend…</span>
        </motion.div>
      )}

      {state.status === "ready" && showReady && (
        <motion.div
          key="ready"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.2 }}
          className="fixed bottom-4 left-4 z-40 inline-flex items-center gap-2 rounded-full border border-line bg-bg-1/85 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] backdrop-blur-md"
          style={{ color: "var(--color-success)" }}
          role="status"
          aria-live="polite"
        >
          <CheckCircle2 size={11} strokeWidth={2} aria-hidden />
          <span>
            Backend ready · :{state.started?.port ?? 8765}
            {state.started?.took_ms ? ` · ${state.started.took_ms}ms` : ""}
          </span>
        </motion.div>
      )}

      {(state.status === "failed" || state.status === "exited") && !dismissed && (
        <motion.div
          key="failed"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className={`fixed bottom-4 left-4 z-40 max-w-[420px] overflow-hidden rounded-[12px] border bg-bg-1/95 backdrop-blur-md ${
            state.status === "exited"
              ? "border-[color:var(--color-alert-soft)]"
              : "border-line-strong"
          }`}
          role="alert"
          aria-live="assertive"
        >
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-px"
            style={{
              background:
                state.status === "exited"
                  ? "var(--color-alert)"
                  : "var(--brand-amber)",
            }}
          />
          <div className="flex items-start gap-3 p-4">
            <span
              className="grid h-7 w-7 shrink-0 place-items-center rounded-md"
              style={{
                background:
                  state.status === "exited"
                    ? "color-mix(in srgb, var(--color-alert) 14%, transparent)"
                    : "color-mix(in srgb, var(--brand-amber) 14%, transparent)",
                color:
                  state.status === "exited"
                    ? "var(--color-alert)"
                    : "var(--brand-amber)",
              }}
              aria-hidden
            >
              <AlertTriangle size={13} strokeWidth={1.7} />
            </span>
            <div className="flex-1 min-w-0">
              <div
                className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.4px]"
                style={{
                  color:
                    state.status === "exited"
                      ? "var(--color-alert)"
                      : "var(--brand-amber)",
                }}
              >
                {state.status === "exited"
                  ? "backend crashed"
                  : `backend ${describeStage(state.failed?.stage)}`}
              </div>
              <p className="font-mono-tech text-[12px] leading-[1.55] text-ink">
                {state.status === "exited"
                  ? exitedDetail(state.exited)
                  : failedDetail(state.failed)}
              </p>
              <a
                href="https://docs.tars.meeet.world/troubleshooting#backend"
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 font-mono-tech text-[10.5px] uppercase tracking-[2px] underline-offset-4 hover:underline"
                style={{ color: "var(--color-accent)" }}
              >
                troubleshooting →
              </a>
            </div>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              aria-label="Dismiss backend status"
              className="grid h-7 w-7 place-items-center rounded-full border border-line text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
            >
              <X size={11} strokeWidth={2} />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function describeStage(stage: string | undefined): string {
  switch (stage) {
    case "spawn":
      return "spawn failed";
    case "health_timeout":
      return "didn't respond";
    case "early_exit":
      return "exited too early";
    default:
      return "unavailable";
  }
}

function failedDetail(
  payload:
    | { stage: string; error: string; took_ms: number; pid?: number | null }
    | undefined,
): string {
  if (!payload) return "The local FastAPI sidecar isn't reachable.";
  const trimmed = payload.error.length > 140
    ? `${payload.error.slice(0, 137)}…`
    : payload.error;
  return `${trimmed} (after ${payload.took_ms}ms)`;
}

function exitedDetail(
  payload: { pid: number; ran_ms: number; exit_code?: number | null; signal?: string | null } | undefined,
): string {
  if (!payload) return "The local FastAPI sidecar exited unexpectedly.";
  const reason = payload.signal
    ? `signal ${payload.signal}`
    : typeof payload.exit_code === "number"
      ? `exit code ${payload.exit_code}`
      : "no exit code";
  const ran = payload.ran_ms < 1000
    ? `${payload.ran_ms}ms`
    : `${Math.round(payload.ran_ms / 1000)}s`;
  return `Backend exited after ${ran} — ${reason}.`;
}
