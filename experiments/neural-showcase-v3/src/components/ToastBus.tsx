import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Sparkles,
  X,
} from "lucide-react";
import { useToasts, toast as toastApi, type Toast, type ToastTone } from "@/lib/toast";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * <ToastBus /> — singleton stack renderer. Mount once in <AppShell />.
 *
 * Reads the toast list from `lib/toast.ts`'s pub/sub. Each toast is
 * an inert AnimatePresence motion.li. Pause-on-hover suspends the
 * auto-dismiss timer; hover-leave resumes from where it was.
 *
 * Layout:
 *   - Bottom-right on desktop, full-width bottom on mobile.
 *   - Stacks newest-first (top), z-stacked with -y offset.
 *   - Max 4 visible (lib enforces).
 *
 * A11y: each toast is a `role="status"` for non-error tones, and
 * `role="alert"` + `aria-live="assertive"` for error/warn so they
 * preempt screen-reader output.
 */

const ICONS: Record<ToastTone, typeof CheckCircle2> = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  error: XCircle,
  announce: Sparkles,
};

const ACCENT: Record<ToastTone, string> = {
  info: "var(--brand-cyan)",
  success: "var(--color-success)",
  warn: "#f59e0b",
  error: "var(--color-alert)",
  announce: "var(--brand-violet)",
};

export function ToastBus() {
  const list = useToasts();

  return (
    <ul
      aria-label="notifications"
      className="pointer-events-none fixed inset-x-0 bottom-3 z-[70] mx-auto flex max-w-[440px] flex-col-reverse gap-2 px-3 sm:right-4 sm:left-auto sm:bottom-6 sm:mx-0 sm:px-0"
    >
      <AnimatePresence initial={false}>
        {list.map(t => (
          <ToastItem key={t.id} toast={t} />
        ))}
      </AnimatePresence>
    </ul>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  const [paused, setPaused] = useState(false);
  const [remaining, setRemaining] = useState(toast.duration);

  // Auto-dismiss with pause-on-hover. Sticky toasts (duration=0) skip.
  useEffect(() => {
    if (toast.duration <= 0 || paused) return;
    const start = Date.now();
    const id = window.setTimeout(() => {
      toastApi.dismiss(toast.id);
    }, remaining);
    return () => {
      window.clearTimeout(id);
      const elapsed = Date.now() - start;
      setRemaining(prev => Math.max(0, prev - elapsed));
    };
  }, [paused, remaining, toast.duration, toast.id]);

  const Icon = ICONS[toast.tone];
  const accent = ACCENT[toast.tone];
  const role = toast.tone === "error" || toast.tone === "warn" ? "alert" : "status";
  const ariaLive = toast.tone === "error" || toast.tone === "warn" ? "assertive" : "polite";

  return (
    <motion.li
      role={role}
      aria-live={ariaLive}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.99, transition: { duration: 0.22 } }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto relative overflow-hidden rounded-[12px] border border-line bg-bg-1/95 backdrop-blur-md"
      style={{
        boxShadow:
          "0 24px 60px -20px rgba(0,0,0,0.7), 0 0 0 1px rgba(99,102,241,0.06)",
      }}
    >
      <BrandHairline />
      <div className="grid grid-cols-[28px_1fr_24px] items-start gap-3 px-4 py-3">
        <span
          className="mt-0.5 grid h-7 w-7 place-items-center rounded-md"
          style={{
            background: `color-mix(in srgb, ${accent} 14%, transparent)`,
            color: accent,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${accent} 35%, transparent)`,
          }}
          aria-hidden
        >
          <Icon size={14} strokeWidth={1.8} />
        </span>
        <div className="min-w-0">
          <div className="font-mono-tech text-[12.5px] leading-[1.45] text-ink">
            {toast.text}
          </div>
          {toast.hint && (
            <div className="mt-0.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
              {toast.hint}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => toastApi.dismiss(toast.id)}
          aria-label="Dismiss notification"
          className="grid h-6 w-6 place-items-center rounded-md text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink"
        >
          <X size={11} strokeWidth={2} aria-hidden />
        </button>
      </div>
      {/* Progress bar — hidden when paused or sticky */}
      {toast.duration > 0 && !paused && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-px"
          style={{ background: accent, transformOrigin: "0 0" }}
          initial={{ scaleX: 1 }}
          animate={{ scaleX: 0 }}
          transition={{ duration: remaining / 1000, ease: "linear" }}
        />
      )}
    </motion.li>
  );
}
