// SYNC: claude-w96-dashboard
/**
 * <Dashboard /> - Wave 96.
 *
 * Personal workspace at /dashboard. Renders a 12-col CSS grid of
 * widgets pulled from existing TARS systems (calendar, slack, gmail,
 * github, wallet, receipts, backtest, cohorts, HIL inbox, playbooks).
 *
 * State + persistence in `src/lib/dashboard.ts`. This page is the
 * "shell" - it owns greeting, edit-mode toggle, the add-widget dialog,
 * and dispatches each widget instance to the right component.
 */

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Pencil, Plus, RotateCcw, Check } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import {
  DEFAULT_LAYOUTS,
  ROLE_LABEL,
  WIDGET_REGISTRY,
  availableWidgets,
  timeOfDayGreeting,
  useDashboard,
  type DashboardRole,
  type WidgetInstance,
  type WidgetType,
} from "@/lib/dashboard";
import { CalendarTodayWidget } from "@/components/dashboard/widgets/CalendarTodayWidget";
import { SlackMentionsWidget } from "@/components/dashboard/widgets/SlackMentionsWidget";
import { GmailUnreadWidget } from "@/components/dashboard/widgets/GmailUnreadWidget";
import { GitHubPRsWidget } from "@/components/dashboard/widgets/GitHubPRsWidget";
import { WalletBalanceWidget } from "@/components/dashboard/widgets/WalletBalanceWidget";
import { RecentReceiptsWidget } from "@/components/dashboard/widgets/RecentReceiptsWidget";
import { BacktestSummaryWidget } from "@/components/dashboard/widgets/BacktestSummaryWidget";
import { ActiveCohortsWidget } from "@/components/dashboard/widgets/ActiveCohortsWidget";
import { HilInboxWidget } from "@/components/dashboard/widgets/HilInboxWidget";
import { PlaybookRunsWidget } from "@/components/dashboard/widgets/PlaybookRunsWidget";

const SIZE_CLASS: Record<3 | 4 | 6 | 12, string> = {
  3:  "md:col-span-3",
  4:  "md:col-span-4",
  6:  "md:col-span-6",
  12: "md:col-span-12",
};

function renderWidget(w: WidgetInstance, editMode: boolean, onRemove: () => void) {
  const props = { editMode, onRemove };
  switch (w.type) {
    case "calendar-today":   return <CalendarTodayWidget   {...props} />;
    case "slack-mentions":   return <SlackMentionsWidget   {...props} />;
    case "gmail-unread":     return <GmailUnreadWidget     {...props} />;
    case "github-prs":       return <GitHubPRsWidget       {...props} />;
    case "wallet-balance":   return <WalletBalanceWidget   {...props} />;
    case "recent-receipts":  return <RecentReceiptsWidget  {...props} />;
    case "backtest-summary": return <BacktestSummaryWidget {...props} />;
    case "active-cohorts":   return <ActiveCohortsWidget   {...props} />;
    case "hil-inbox":        return <HilInboxWidget        {...props} />;
    case "playbook-runs":    return <PlaybookRunsWidget    {...props} />;
  }
}

export function Dashboard() {
  useDocumentMeta({
    title: "Dashboard - TARS",
    description: "Configurable workspace - calendar, mentions, PRs, receipts, backtests, cohorts.",
  });

  const dash = useDashboard();
  const [editMode, setEditMode] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState(dash.layout.displayName);

  const greeting = useMemo(() => timeOfDayGreeting(), []);
  const widgets = dash.layout.widgets;

  return (
    <section className="relative z-10 mx-auto max-w-[1320px] px-6 pb-24 pt-32 md:px-12">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: "Dashboard" }]} className="mb-6" />

      <header className="mb-10 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-indigo)]" aria-hidden />
            <span>your day at a glance</span>
          </div>
          <h1
            className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            {greeting},{" "}
            {editingName ? (
              <input
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                onBlur={() => { dash.setDisplayName(draftName.trim() || "Operator"); setEditingName(false); }}
                onKeyDown={(e) => { if (e.key === "Enter") (e.currentTarget as HTMLInputElement).blur(); }}
                className="rounded border border-line bg-bg-1 px-2 py-1 text-[0.7em] text-ink outline-none focus:border-[var(--brand-indigo)]"
                autoFocus
                aria-label="Display name"
              />
            ) : (
              <button type="button" onClick={() => { setDraftName(dash.layout.displayName); setEditingName(true); }} className="underline-offset-4 hover:underline" aria-label="Edit display name">
                {dash.layout.displayName}
              </button>
            )}
            .
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editMode ? (
            <>
              <button type="button" onClick={() => setPaletteOpen(true)} className="inline-flex items-center gap-1.5 rounded border border-[var(--brand-indigo)]/60 bg-[var(--brand-indigo)]/10 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink hover:bg-[var(--brand-indigo)]/20">
                <Plus size={11} aria-hidden /> Add widget
              </button>
              <button type="button" onClick={() => dash.reset()} className="inline-flex items-center gap-1.5 rounded border border-line bg-bg-1 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 hover:text-ink">
                <RotateCcw size={11} aria-hidden /> Reset
              </button>
              <button type="button" onClick={() => setEditMode(false)} className="inline-flex items-center gap-1.5 rounded border border-emerald-500/60 bg-emerald-500/10 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-emerald-300 hover:bg-emerald-500/20">
                <Check size={11} aria-hidden /> Done
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setEditMode(true)} className="inline-flex items-center gap-1.5 rounded border border-line bg-bg-1 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 hover:text-ink">
              <Pencil size={11} aria-hidden /> Edit
            </button>
          )}
        </div>
      </header>

      {widgets.length === 0 ? (
        <EmptyState onPick={(role) => dash.reset(role)} />
      ) : (
        <motion.div
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-1 gap-4 md:grid-cols-12"
        >
          {widgets.map((w) => (
            <div key={w.id} className={`col-span-1 ${SIZE_CLASS[w.size]}`}>
              {renderWidget(w, editMode, () => dash.removeWidget(w.id))}
            </div>
          ))}
        </motion.div>
      )}

      {paletteOpen ? (
        <WidgetPalette
          existing={new Set(widgets.map((w) => w.type))}
          onAdd={(t) => { dash.addWidget(t); setPaletteOpen(false); }}
          onClose={() => setPaletteOpen(false)}
        />
      ) : null}
    </section>
  );
}

// -- empty state ----------------------------------------------------

function EmptyState({ onPick }: { onPick: (role: DashboardRole) => void }) {
  return (
    <div className="rounded-xl border border-dashed border-line/80 bg-bg-1/40 p-10 text-center">
      <h2 className="mb-2 font-display text-[24px] text-ink">Your dashboard is empty</h2>
      <p className="mb-6 text-[13px] text-ink-2">Pick a starter set tuned to how you work.</p>
      <ul className="mx-auto grid max-w-[680px] grid-cols-2 gap-2 md:grid-cols-5">
        {(Object.keys(DEFAULT_LAYOUTS) as DashboardRole[]).map((role) => (
          <li key={role}>
            <button
              type="button"
              onClick={() => onPick(role)}
              className="w-full rounded border border-line bg-bg-0/60 px-3 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 hover:border-[var(--brand-indigo)]/60 hover:text-ink"
            >
              {ROLE_LABEL[role]}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// -- widget palette modal -------------------------------------------

function WidgetPalette({
  existing,
  onAdd,
  onClose,
}: {
  existing: Set<WidgetType>;
  onAdd: (t: WidgetType) => void;
  onClose: () => void;
}) {
  const items = availableWidgets();
  return (
    <div role="dialog" aria-modal="true" aria-label="Add widget" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6" onClick={onClose}>
      <div className="max-h-[80vh] w-full max-w-[760px] overflow-y-auto rounded-lg border border-line bg-bg-1 p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <header className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-[20px] text-ink">Add a widget</h2>
          <button type="button" onClick={onClose} className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3 hover:text-ink">Close</button>
        </header>
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {items.map((meta) => {
            const added = existing.has(meta.type);
            return (
              <li key={meta.type}>
                <button
                  type="button"
                  onClick={() => onAdd(meta.type)}
                  className="block w-full rounded border border-line bg-bg-0/60 px-3 py-3 text-left transition-colors hover:border-[var(--brand-indigo)]/60"
                >
                  <div className="mb-1 flex items-baseline justify-between">
                    <span className="text-[13px] text-ink">{meta.name}</span>
                    {added ? <span className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">added</span> : null}
                  </div>
                  <p className="text-[11.5px] text-ink-2">{meta.description}</p>
                  <p className="mt-1.5 font-mono-tech text-[9.5px] uppercase tracking-[1.5px] text-ink-3">requires {WIDGET_REGISTRY[meta.type].requires}</p>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
