/**
 * /cockpit/planner — operator surface for inspecting and replaying
 * planner runs. Built on top of `lib/planner.ts` and the
 * `<PlanFullPanel />` drawer.
 *
 * Anatomy:
 *
 *   - Sticky brand-hairline header with a back link to `/cockpit`.
 *   - Filter strip: status pill (proposed / approved / running /
 *     completed / aborted / rejected / all) + plan-id quick search
 *     box. Filters are URL-state-friendly via local React state for
 *     now; the full querystring sync happens in a follow-up.
 *   - Two-column workspace:
 *     - Left: list of plans (`listPlans`) with status pill, pack
 *       slug, and goal one-liner. Click selects.
 *     - Right: `<PlanFullPanel />` for the selected plan; renders
 *       the full envelope, lifetime usage, and rerun / abort
 *       buttons.
 *   - Live: a single SSE subscription on `/api/planner/events` (no
 *     plan filter) refreshes the list whenever a `planner.cloned`,
 *     `plan.proposed`, or `planner.deleted` event fires.
 *
 * Empty / loading / error states are present at every level so the
 * operator never sees a frozen panel.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Plug, Search } from "lucide-react";

import { useDocumentMeta } from "@/lib/meta";
import { listPlans, subscribePlannerEvents, type Plan, type PlanStatus, type PlannerEvent } from "@/lib/planner";
import { BrandHairline } from "@/components/BrandHairline";
import { PlanFullPanel, statusTone } from "@/components/PlanFullPanel";

const STATUS_FILTERS: Array<PlanStatus | "all"> = [
  "all",
  "proposed",
  "approved",
  "running",
  "completed",
  "aborted",
  "rejected",
];

const TONE_TO_PILL_CLASS: Record<ReturnType<typeof statusTone>, string> = {
  muted: "border-line text-ink-3",
  accent: "border-line-strong text-accent",
  success: "border-line-strong text-[color:var(--color-success)]",
  alert: "border-alert/60 text-alert",
  warning: "border-line-strong text-[color:var(--brand-amber,#FBBF24)]",
};

export function Planner() {
  useDocumentMeta({
    title: "Planner",
    description:
      "Operator console for the TARS planner — inspect runs, replay plans, and watch lifetime usage roll up live.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });

  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<PlanStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listPlans({
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 100,
      });
      setPlans(r.plans);
      // Keep the current selection if it still matches; otherwise pick the
      // newest plan in the filtered list, so the right pane is never empty.
      setSelected((prev) => {
        if (prev && r.plans.some((p) => p.id === prev)) return prev;
        return r.plans[0]?.id ?? null;
      });
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  // Live: refresh the list on plan-creation / clone / delete events.
  useEffect(() => {
    const cleanup = subscribePlannerEvents(
      {},
      {
        onEvent: (e: PlannerEvent) => {
          if (
            e.kind === "plan.proposed" ||
            e.kind === "planner.cloned" ||
            e.kind === "planner.deleted" ||
            e.kind === "planner.synthesis.completed"
          ) {
            void refetch();
          }
        },
      },
    );
    return cleanup;
  }, [refetch]);

  const filteredPlans = useMemo(() => {
    if (!plans) return [];
    const q = search.trim().toLowerCase();
    if (!q) return plans;
    return plans.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.goal.toLowerCase().includes(q) ||
        (p.pack_slug ?? "").toLowerCase().includes(q),
    );
  }, [plans, search]);

  return (
    <section className="relative z-20 mx-auto min-h-screen max-w-[1480px] px-6 pb-24 pt-6 md:px-12">
      <div className="relative mb-8 overflow-hidden rounded-[14px] border border-line bg-bg-1/60 px-4 py-3 backdrop-blur-md md:px-6">
        <BrandHairline />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/cockpit"
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:text-ink"
            >
              <ArrowLeft size={12} strokeWidth={1.6} aria-hidden />
              cockpit
            </Link>
            <span className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-3">
              operator // planner
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {loading ? (
              <>
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
                refreshing…
              </>
            ) : (
              <span>{plans?.length ?? 0} plans</span>
            )}
          </div>
        </div>
      </div>

      <div className="mb-8">
        <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
          <span aria-hidden className="opacity-50">//</span>
          <span>PLANNER</span>
          <span aria-hidden className="opacity-50">//</span>
          <span style={{ color: "var(--brand-cyan)" }}>v9.0</span>
        </div>
        <h1
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "var(--text-display-md)" }}
        >
          Inspect a plan. Replay it.
        </h1>
        <p className="mt-3 max-w-[60ch] font-mono-tech text-[12px] uppercase tracking-[2.4px] text-ink-2">
          Pick a plan from the left rail; the right pane hydrates from
          /api/planner/{"{id}"}/full and stays live via the SSE stream.
        </p>
      </div>

      <FilterStrip
        status={statusFilter}
        onStatus={setStatusFilter}
        search={search}
        onSearch={setSearch}
      />

      {error && (
        <div className="mb-6 rounded-md border border-alert/40 bg-alert/[0.04] p-4 font-mono-tech text-[12px] text-alert">
          <header className="mb-1 flex items-center gap-2 font-display text-[13px] uppercase tracking-[0.04em]">
            <Plug size={13} strokeWidth={1.6} />
            backend offline
          </header>
          <p>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <PlanList
          plans={filteredPlans}
          selected={selected}
          onSelect={setSelected}
          loading={loading && !plans}
          unfilteredCount={plans?.length ?? 0}
        />
        <div className="min-h-[200px]">
          {selected ? (
            <PlanFullPanel
              planId={selected}
              onClose={() => setSelected(null)}
            />
          ) : (
            <EmptyRightPane />
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FilterStrip({
  status,
  onStatus,
  search,
  onSearch,
}: {
  status: PlanStatus | "all";
  onStatus: (s: PlanStatus | "all") => void;
  search: string;
  onSearch: (s: string) => void;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {STATUS_FILTERS.map((s) => {
          const active = s === status;
          return (
            <button
              key={s}
              type="button"
              onClick={() => onStatus(s)}
              className={`rounded-md border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] transition-colors ${
                active
                  ? "border-line-hot bg-accent-deep text-accent"
                  : "border-line text-ink-2 hover:border-line-strong hover:text-ink"
              }`}
            >
              {s}
            </button>
          );
        })}
      </div>
      <label className="ml-auto flex w-full max-w-xs items-center gap-2 rounded-md border border-line bg-bg-1 px-3 py-1.5">
        <Search size={12} strokeWidth={1.6} className="text-ink-3" aria-hidden />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="filter by id / goal / pack"
          className="w-full bg-transparent font-mono-tech text-[11px] tracking-[0.6px] text-ink outline-none placeholder:text-ink-3"
        />
      </label>
    </div>
  );
}

function PlanList({
  plans,
  selected,
  onSelect,
  loading,
  unfilteredCount,
}: {
  plans: Plan[];
  selected: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  unfilteredCount: number;
}) {
  return (
    <aside className="grid gap-1 self-start rounded-[14px] border border-line bg-bg-1 p-3">
      <div className="mb-1 px-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        plans · {plans.length}
        {unfilteredCount > plans.length && (
          <span className="ml-2 text-ink-3">/ {unfilteredCount}</span>
        )}
      </div>
      {loading && (
        <div className="flex items-center gap-2 px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          loading…
        </div>
      )}
      {!loading && plans.length === 0 && (
        <div className="px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          no plans match
        </div>
      )}
      <ul className="grid max-h-[60vh] gap-1 overflow-auto">
        {plans.map((p) => {
          const tone = statusTone(p.status);
          const active = p.id === selected;
          return (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onSelect(p.id)}
                className={`group block w-full cursor-pointer rounded-md border px-3 py-2 text-left transition-colors duration-200 ${
                  active
                    ? "border-line-hot bg-accent-deep"
                    : "border-line bg-transparent hover:border-line-strong"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono-tech text-[10px] uppercase tracking-[2px] text-ink">
                    {p.id}
                  </span>
                  <span
                    className={`shrink-0 rounded-md border px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${TONE_TO_PILL_CLASS[tone]}`}
                  >
                    {p.status}
                  </span>
                </div>
                {p.pack_slug && (
                  <div className="mt-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-accent">
                    {p.pack_slug}
                  </div>
                )}
                <div className="mt-1 line-clamp-2 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
                  {p.goal}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function EmptyRightPane() {
  return (
    <div className="flex h-full min-h-[260px] items-center justify-center rounded-[14px] border border-dashed border-line p-10 font-mono-tech text-[11.5px] uppercase tracking-[2px] text-ink-3">
      pick a plan from the rail to inspect / rerun
    </div>
  );
}
