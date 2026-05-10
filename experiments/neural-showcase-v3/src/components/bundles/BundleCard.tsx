// SYNC: claude-w107-bundles
/**
 * <BundleCard /> — single vertical bundle in the /bundles grid.
 *
 * Displays the bundle name, org-type, description and a counts
 * strip (playbooks / schedules / widgets). Clicking the card
 * triggers ``onPreview``; clicking the install pill triggers
 * ``onInstallNow`` (the parent decides whether to skip the
 * preview modal).
 */

import { motion } from "framer-motion";
import { Sparkles, Calendar, LayoutGrid, FileText, Mail } from "lucide-react";
import type { Bundle } from "./types";

interface Props {
  bundle: Bundle;
  recommended?: boolean;
  installed?: boolean;
  onPreview: (bundle: Bundle) => void;
}

const ORG_LABEL: Record<string, string> = {
  vc_fund: "VC fund",
  hedge_fund: "Hedge fund",
  family_office: "Family office",
  saas: "SaaS",
  dao: "DAO",
  research_lab: "Research lab",
  other: "General",
};

export function BundleCard({ bundle, recommended, installed, onPreview }: Props) {
  const counts = {
    playbooks: bundle.components.playbooks.length,
    scheduled: bundle.components.scheduled.length,
    widgets: bundle.components.dashboard_widgets.length,
    reports: bundle.components.report_templates.length,
    outreach: bundle.components.outreach_templates.length,
  };
  const orgLabel = ORG_LABEL[bundle.org_type] || bundle.org_type;
  return (
    <motion.button
      type="button"
      onClick={() => onPreview(bundle)}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.99 }}
      data-bundle-id={bundle.id}
      className="group relative flex w-full flex-col gap-3 rounded-2xl border border-white/10 bg-[var(--surface-0,rgba(255,255,255,0.02))] p-5 text-left transition-colors hover:border-[var(--accent,rgba(124,58,237,0.6))]"
    >
      {recommended ? (
        <span
          className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full bg-[var(--accent,#7c3aed)]/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[var(--accent,#a78bfa)]"
        >
          <Sparkles size={10} aria-hidden /> Recommended
        </span>
      ) : null}
      {installed ? (
        <span
          className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-300"
        >
          Installed
        </span>
      ) : null}
      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-medium uppercase tracking-wider text-white/40">
          {orgLabel}
        </span>
        <h3 className="text-lg font-semibold text-white">{bundle.name}</h3>
      </div>
      <p className="text-sm leading-relaxed text-white/60 line-clamp-3">
        {bundle.description}
      </p>
      <div className="mt-2 grid grid-cols-5 gap-2 text-center text-[10px] text-white/50">
        <CountChip Icon={Sparkles} label="playbooks" value={counts.playbooks} />
        <CountChip Icon={Calendar} label="schedules" value={counts.scheduled} />
        <CountChip Icon={LayoutGrid} label="widgets" value={counts.widgets} />
        <CountChip Icon={FileText} label="reports" value={counts.reports} />
        <CountChip Icon={Mail} label="outreach" value={counts.outreach} />
      </div>
      <div className="mt-2 flex items-center justify-between border-t border-white/5 pt-3">
        <span className="text-xs text-white/40">v{bundle.version}</span>
        <span className="text-xs font-medium text-[var(--accent,#a78bfa)] group-hover:underline">
          Preview & install →
        </span>
      </div>
    </motion.button>
  );
}

function CountChip({
  Icon,
  label,
  value,
}: {
  Icon: typeof Sparkles;
  label: string;
  value: number;
}) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg bg-white/[0.02] py-2">
      <Icon size={12} className="text-white/40" aria-hidden />
      <span className="text-sm font-semibold text-white/80">{value}</span>
      <span className="leading-none">{label}</span>
    </div>
  );
}
