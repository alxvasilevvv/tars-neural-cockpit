// SYNC: claude-w107-bundles
/**
 * <BundlePreviewModal /> — confirm dialog for a bundle install.
 *
 * Shows the dry-run InstallReport from POST /api/bundles/{id}/preview:
 * playbooks (with availability), schedules, dashboard widgets,
 * report templates, outreach templates, connector hints. Operator
 * clicks "Install" -> parent calls POST /install.
 *
 * Renders an <InstallProgressBar /> when ``installing`` is true.
 */

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, AlertTriangle } from "lucide-react";
import { InstallProgressBar } from "./InstallProgressBar";
import type { Bundle, PreviewEnvelope } from "./types";

interface Props {
  bundle: Bundle | null;
  preview: PreviewEnvelope | null;
  loading: boolean;
  installing: boolean;
  installed: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (runFirstNow: boolean) => void;
}

export function BundlePreviewModal({
  bundle,
  preview,
  loading,
  installing,
  installed,
  error,
  onClose,
  onConfirm,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!bundle) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !installing) onClose();
    }
    window.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [bundle, installing, onClose]);

  return (
    <AnimatePresence>
      {bundle ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => {
            if (!installing) onClose();
          }}
        >
          <motion.div
            initial={{ y: 20, scale: 0.96 }}
            animate={{ y: 0, scale: 1 }}
            exit={{ y: 20, scale: 0.96 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="bundle-preview-title"
            className="relative flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-1,#0c0c12)] text-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-3 border-b border-white/5 px-6 py-4">
              <div>
                <h2 id="bundle-preview-title" className="text-lg font-semibold">
                  Install {bundle.name}
                </h2>
                <p className="mt-1 text-xs text-white/50">
                  Dry-run preview — nothing is created until you confirm.
                </p>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={onClose}
                disabled={installing}
                className="rounded-md p-1.5 text-white/60 hover:bg-white/5 disabled:opacity-40"
                aria-label="Close preview"
              >
                <X size={16} aria-hidden />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto px-6 py-5">
              {loading && !preview ? (
                <p className="text-sm text-white/60">Loading preview…</p>
              ) : null}
              {error ? (
                <p className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
                  {error}
                </p>
              ) : null}
              {preview ? (
                <div className="flex flex-col gap-5 text-sm">
                  <Section title="Playbooks" count={preview.preview.items.playbooks.length}>
                    <ul className="space-y-1">
                      {preview.preview.items.playbooks.map((p) => (
                        <li key={p.id} className="flex items-center justify-between gap-2 text-white/70">
                          <span className="font-mono text-xs">{p.id}</span>
                          {p.available === false ? (
                            <span className="inline-flex items-center gap-1 text-[10px] text-amber-300">
                              <AlertTriangle size={10} aria-hidden /> not on disk
                            </span>
                          ) : (
                            <span className="text-[10px] text-emerald-300">ready</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </Section>

                  <Section title="Scheduled jobs" count={preview.preview.items.scheduled.length}>
                    <ul className="space-y-1">
                      {preview.preview.items.scheduled.map((s, i) => (
                        <li key={i} className="flex items-center justify-between gap-2 text-white/70">
                          <span className="font-mono text-xs">{s.playbook_id}</span>
                          <code className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/60">
                            {s.cron}
                          </code>
                        </li>
                      ))}
                    </ul>
                  </Section>

                  <Section
                    title="Dashboard widgets"
                    count={preview.preview.items.dashboard_widgets.length}
                  >
                    <div className="flex flex-wrap gap-1.5">
                      {preview.preview.items.dashboard_widgets.map((w) => (
                        <span
                          key={w.id}
                          className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/70"
                        >
                          {w.id}
                        </span>
                      ))}
                    </div>
                  </Section>

                  <Section
                    title="Report templates"
                    count={preview.preview.items.report_templates.length}
                  >
                    <ul className="space-y-0.5 text-xs text-white/60">
                      {preview.preview.items.report_templates.map((r) => (
                        <li key={r.slug}>{r.slug}</li>
                      ))}
                    </ul>
                  </Section>

                  <Section
                    title="Outreach templates"
                    count={preview.preview.items.outreach_templates.length}
                  >
                    <ul className="space-y-0.5 text-xs text-white/60">
                      {preview.preview.items.outreach_templates.map((o) => (
                        <li key={o.slug}>{o.slug}</li>
                      ))}
                    </ul>
                  </Section>

                  <Section
                    title="Connector hints"
                    count={preview.preview.items.connectors_hints.length}
                  >
                    <div className="flex flex-wrap gap-1.5">
                      {preview.preview.items.connectors_hints.map((c) => (
                        <span
                          key={c.id}
                          className={
                            "rounded-full px-2 py-0.5 text-[11px] " +
                            (c.priority
                              ? "bg-[var(--accent,#7c3aed)]/20 text-[var(--accent,#a78bfa)]"
                              : "bg-white/5 text-white/60")
                          }
                        >
                          {c.id}
                          {c.priority ? " *" : ""}
                        </span>
                      ))}
                    </div>
                  </Section>

                  {preview.summary.first_run_playbook ? (
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-white/70">
                      First run will queue:{" "}
                      <span className="font-mono">{preview.summary.first_run_playbook}</span>
                    </div>
                  ) : null}

                  {preview.summary.warnings.length > 0 ? (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                      <strong className="block">Warnings ({preview.summary.warnings.length})</strong>
                      <ul className="mt-1 space-y-0.5">
                        {preview.summary.warnings.map((w) => (
                          <li key={w} className="font-mono text-[10px]">{w}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <footer className="flex items-center justify-between gap-3 border-t border-white/5 px-6 py-4">
              <InstallProgressBar
                active={installing}
                done={installed}
                label={installed ? "Installed." : "Installing…"}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={installing}
                  className="rounded-md px-3 py-1.5 text-sm text-white/70 hover:bg-white/5 disabled:opacity-40"
                >
                  {installed ? "Close" : "Cancel"}
                </button>
                {!installed ? (
                  <>
                    <button
                      type="button"
                      onClick={() => onConfirm(false)}
                      disabled={!preview || installing}
                      className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white/80 hover:bg-white/10 disabled:opacity-40"
                    >
                      Install only
                    </button>
                    <button
                      type="button"
                      onClick={() => onConfirm(true)}
                      disabled={!preview || installing}
                      className="rounded-md bg-[var(--accent,#7c3aed)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover,#6d28d9)] disabled:opacity-40"
                    >
                      Install + run first
                    </button>
                  </>
                ) : null}
              </div>
            </footer>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <header className="flex items-baseline gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">
          {title}
        </h3>
        <span className="text-xs text-white/40">{count}</span>
      </header>
      {children}
    </section>
  );
}
