import { motion } from "framer-motion";

/**
 * <WorkspaceCard /> — list entry for the /workspaces page (Wave 110).
 *
 * Single workspace summary: slug, name, plan, member count, archived
 * lozenge, click-to-open detail panel.
 */
export interface WorkspaceCardData {
  id: string;
  slug: string;
  name: string;
  plan: string;
  is_active: boolean;
  member_count?: number;
  pending_invite_count?: number;
}

export function WorkspaceCard({
  workspace,
  selected,
  onSelect,
}: {
  workspace: WorkspaceCardData;
  selected?: boolean;
  onSelect?: (id: string) => void;
}) {
  const planLabel = workspace.plan.toUpperCase();
  return (
    <motion.button
      type="button"
      onClick={() => onSelect?.(workspace.id)}
      whileHover={{ y: -1 }}
      className={[
        "group relative w-full overflow-hidden rounded-xl border bg-bg-1/40 px-4 py-3 text-left transition-colors",
        selected
          ? "border-[color:var(--brand-indigo)] ring-1 ring-[color:var(--brand-indigo)]/40"
          : "border-line/60 hover:border-[color:var(--brand-indigo)]/40",
      ].join(" ")}
      aria-pressed={selected ? "true" : "false"}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
            {workspace.slug}
          </p>
          <h3 className="mt-0.5 truncate font-display text-[16px] font-medium text-ink">
            {workspace.name}
          </h3>
        </div>
        <span
          className="rounded-full border border-line/60 px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.5px] text-ink-2"
          aria-label={`Plan ${planLabel}`}
        >
          {planLabel}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2 font-mono-tech text-[10.5px] uppercase tracking-[1px] text-ink-3">
        <div>
          <dt className="opacity-70">members</dt>
          <dd className="text-ink-2">{workspace.member_count ?? "—"}</dd>
        </div>
        <div>
          <dt className="opacity-70">pending</dt>
          <dd className="text-ink-2">{workspace.pending_invite_count ?? 0}</dd>
        </div>
        <div>
          <dt className="opacity-70">status</dt>
          <dd className="text-ink-2">{workspace.is_active ? "active" : "archived"}</dd>
        </div>
      </dl>
    </motion.button>
  );
}

export default WorkspaceCard;
