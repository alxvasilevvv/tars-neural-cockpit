/**
 * <WorkshopCohort /> — Wave 89
 *
 * Real-time facilitator dashboard at /workshop/cohort. Shows the
 * meeet.world team running a workshop what every attendee is doing
 * right now: phase, last action, errors, idle time, plus a live
 * activity stream and a broadcast composer.
 *
 * Mock data shipped for facilitator demo before W2-PR2 backend lands.
 * When `/api/cohort/*` endpoints exist, swap mock fallback for real
 * (same hook contract — see `src/lib/cohort.ts`).
 *
 * Design conventions:
 *   - Defensive `initial: opacity: 1` on motion wrappers (Wave 70
 *     pattern — keeps the page legible if framer hydrates late).
 *   - Phase tint on every row + stat tile so the four phases read at
 *     a glance: intake=cyan, design=violet, test=indigo, deploy=green.
 *   - All copy lives behind STRINGS_EN["cohort.*"] so a future locale
 *     re-enable picks them up automatically.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Bell,
  Download,
  Filter,
  Radio,
  Send,
  TriangleAlert,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { WorkshopTutorial } from "@/components/WorkshopTutorial";
import { AttendeeDetail } from "@/components/cohort/AttendeeDetail";
import {
  ACTIVE_THRESHOLD_MIN,
  type Attendee,
  type CohortEvent,
  type Phase,
  broadcast,
  computeStats,
  createCohort,
  phaseLabel,
  phaseTint,
  toCSV,
  useCohortStream,
  usePollAttendees,
} from "@/lib/cohort";

type SortKey =
  | "name"
  | "email"
  | "phase"
  | "lastAction"
  | "playbooksRun"
  | "errors"
  | "idleMin";
type SortDir = "asc" | "desc";

type FilterChip = "all" | "active" | "idle" | "error" | Phase;

const ALL_FILTERS: FilterChip[] = [
  "all",
  "active",
  "idle",
  "error",
  "intake",
  "design",
  "test",
  "deploy",
];

const ERROR_THRESHOLD = 1; // Risk alerts panel: anyone with > this on the board.

// ── page ────────────────────────────────────────────────────────────

export function WorkshopCohort() {
  const t = useT();
  useDocumentMeta({
    title: "Workshop cohort · TARS",
    description:
      "Live facilitator dashboard: see what every attendee is doing right now during a TARS workshop.",
  });

  // Wave 94 — read selected cohort from `?cohort=...` URL param so
  // a facilitator can deep-link / bookmark a specific session. When
  // no cohort is set, the hooks fall back to mock data and we render
  // an "empty state" CTA at the bottom of the page.
  const [cohortId, setCohortId] = useState<string | undefined>(() => {
    if (typeof window === "undefined") return undefined;
    const param = new URL(window.location.href).searchParams.get("cohort");
    return param ?? undefined;
  });

  // Keep state in sync if the user pastes a different URL into the bar.
  useEffect(() => {
    function syncFromUrl(): void {
      const param = new URL(window.location.href).searchParams.get("cohort");
      setCohortId(param ?? undefined);
    }
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  const { rows, source } = usePollAttendees(cohortId);
  const events = useCohortStream(rows, cohortId);
  const stats = useMemo(() => computeStats(rows), [rows]);

  const [createPending, setCreatePending] = useState(false);
  const onCreateCohort = useCallback(async () => {
    if (createPending) return;
    setCreatePending(true);
    const fresh = await createCohort({
      name: `Workshop ${new Date().toLocaleDateString()}`,
    });
    setCreatePending(false);
    if (fresh) {
      const next = new URL(window.location.href);
      next.searchParams.set("cohort", fresh.id);
      window.history.pushState({}, "", next.toString());
      setCohortId(fresh.id);
    } else {
      // Backend miss — fallback to mock so demo still loads.
      setCohortId(undefined);
    }
  }, [createPending]);

  const [sortKey, setSortKey] = useState<SortKey>("idleMin");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [filter, setFilter] = useState<FilterChip>("all");
  const [selected, setSelected] = useState<Attendee | null>(null);
  const [broadcastText, setBroadcastText] = useState("");
  const [broadcastState, setBroadcastState] = useState<
    "idle" | "sending" | "sent" | "error"
  >("idle");

  // Cohort fixture timestamp — pinned at first render so the header
  // doesn't re-format every tick. Real backend will return the actual
  // `started_at` from the cohort record.
  const [cohortStartedAt] = useState(() => {
    const d = new Date();
    d.setHours(d.getHours() - 1, d.getMinutes() - 23, 0, 0);
    return d;
  });

  const filtered = useMemo(() => {
    let out = rows;
    switch (filter) {
      case "all":
        break;
      case "active":
        out = out.filter((r) => r.idleMin <= ACTIVE_THRESHOLD_MIN);
        break;
      case "idle":
        out = out.filter((r) => r.idleMin > ACTIVE_THRESHOLD_MIN);
        break;
      case "error":
        out = out.filter((r) => r.errors > 0);
        break;
      default:
        out = out.filter((r) => r.phase === filter);
    }
    const sorted = [...out].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return sorted;
  }, [rows, filter, sortKey, sortDir]);

  const riskRows = useMemo(
    () => rows.filter((r) => r.errors >= ERROR_THRESHOLD),
    [rows],
  );

  const onSort = useCallback(
    (key: SortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey],
  );

  const onBroadcast = useCallback(async () => {
    if (!broadcastText.trim() || broadcastState === "sending") return;
    setBroadcastState("sending");
    const res = await broadcast(broadcastText.trim(), cohortId);
    if (res.ok) {
      setBroadcastState("sent");
      setBroadcastText("");
      window.setTimeout(() => setBroadcastState("idle"), 1800);
    } else {
      setBroadcastState("error");
      window.setTimeout(() => setBroadcastState("idle"), 1800);
    }
  }, [broadcastText, broadcastState]);

  const onExportCSV = useCallback(() => {
    const csv = toCSV(rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.download = `workshop-cohort-${ts}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [rows]);

  return (
    <div className="relative min-h-[calc(100vh-72px)] overflow-hidden bg-bg-0 text-ink">
      {/* Ambient backdrop — softer than the marketing surface so the
          dense table reads first. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 40% 30% at 12% 4%, rgba(99,102,241,0.06) 0%, transparent 60%),
            radial-gradient(ellipse 40% 30% at 92% 96%, rgba(34,197,94,0.05) 0%, transparent 60%)
          `,
        }}
      />

      <article className="mx-auto max-w-[1400px] px-6 pb-24 pt-14 md:px-10 md:pt-20">
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <Breadcrumbs
            items={[
              { label: "Home", to: "/" },
              { label: "Workshop", to: "/workshop" },
              { label: t("cohort.crumb") },
            ]}
          />
        </motion.div>

        {/* Wave 94 — empty state when no cohort is selected and the
            backend isn't returning rows. Renders inline above the
            normal header so the CTA is the first thing the operator
            sees on a fresh cockpit. */}
        {!cohortId && source === "mock" && (
          <div className="mt-8 rounded-md border border-line bg-bg-1 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-display text-[1.15rem] text-ink">
                  No cohort selected
                </div>
                <div className="mt-1 text-[13px] text-ink-2">
                  Showing demo data. Create a real cohort to start tracking
                  attendees, or append <code>?cohort=...</code> to the URL.
                </div>
              </div>
              <button
                type="button"
                onClick={onCreateCohort}
                disabled={createPending}
                className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors hover:bg-[var(--brand-indigo)]/15 disabled:opacity-50"
              >
                {createPending ? "Creating…" : "Create cohort"}
              </button>
            </div>
          </div>
        )}

        {/* Header */}
        <motion.header
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="mt-8 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-7"
        >
          <div>
            <div className="mb-2 flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>W89</span>
              <span>{t("cohort.eyebrow")}</span>
            </div>
            <h1
              className="font-display font-medium leading-[0.98] tracking-[-0.02em] text-ink"
              style={{ fontSize: "clamp(1.8rem, 3.6vw, 2.5rem)" }}
            >
              {t("cohort.title")}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-4 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
              <span>
                {t("cohort.header.started", {
                  time: cohortStartedAt.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  }),
                })}
              </span>
              <span>·</span>
              <span>{t("cohort.header.attendees", { n: stats.total })}</span>
              <span>·</span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="relative inline-block h-2 w-2 rounded-full"
                  style={{ background: "#22c55e" }}
                >
                  <span
                    aria-hidden
                    className="absolute inset-0 animate-ping rounded-full"
                    style={{ background: "#22c55e", opacity: 0.5 }}
                  />
                </span>
                {t("cohort.header.live")}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById("cohort-broadcast-textarea");
                if (el) (el as HTMLTextAreaElement).focus();
              }}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors hover:bg-[var(--brand-indigo)]/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
            >
              <Bell size={13} aria-hidden />
              {t("cohort.header.broadcast_cta")}
            </button>
          </div>
        </motion.header>

        {/* Stat row */}
        <section
          aria-label={t("cohort.stats.aria")}
          className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-5"
        >
          <StatCard
            label={t("cohort.stats.active")}
            value={String(stats.activeNow)}
            sublabel={t("cohort.stats.active_sub")}
            accent="#22c55e"
            highlight
          />
          {(["intake", "design", "test", "deploy"] as Phase[]).map((p) => (
            <StatCard
              key={p}
              label={`${t("cohort.phase")} ${phaseLabel(p)}`}
              value={`${stats.byPhase[p].pct}%`}
              sublabel={t("cohort.stats.attendees_n", {
                n: stats.byPhase[p].count,
              })}
              accent={phaseTint(p)}
            />
          ))}
        </section>

        {/* Main grid: table + right rail */}
        <section className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          {/* Left column: filters + table */}
          <div className="space-y-4">
            {/* Filter chips */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
                <Filter size={11} aria-hidden />
                {t("cohort.filter.label")}
              </span>
              {ALL_FILTERS.map((f) => {
                const active = filter === f;
                return (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFilter(f)}
                    className={`rounded-full border px-3 py-1 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)] ${
                      active
                        ? "border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/15 text-ink"
                        : "border-line bg-bg-1/40 text-ink-2 hover:border-ink-3 hover:text-ink"
                    }`}
                  >
                    {filterLabel(f, t)}
                  </button>
                );
              })}
              <span className="ml-auto font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                {t("cohort.filter.showing", {
                  n: filtered.length,
                  total: rows.length,
                })}
              </span>
            </div>

            {/* Attendee table */}
            <div
              data-tutorial-id="cohort-table"
              className="overflow-hidden rounded-md border border-line bg-bg-1/40 backdrop-blur-sm"
            >
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left">
                  <thead className="bg-bg-2/40">
                    <tr>
                      <Th
                        label={t("cohort.table.name")}
                        active={sortKey === "name"}
                        dir={sortDir}
                        onClick={() => onSort("name")}
                      />
                      <Th
                        label={t("cohort.table.email")}
                        active={sortKey === "email"}
                        dir={sortDir}
                        onClick={() => onSort("email")}
                      />
                      <Th
                        label={t("cohort.table.phase")}
                        active={sortKey === "phase"}
                        dir={sortDir}
                        onClick={() => onSort("phase")}
                      />
                      <Th
                        label={t("cohort.table.last_action")}
                        active={sortKey === "lastAction"}
                        dir={sortDir}
                        onClick={() => onSort("lastAction")}
                      />
                      <Th
                        label={t("cohort.table.playbooks")}
                        active={sortKey === "playbooksRun"}
                        dir={sortDir}
                        onClick={() => onSort("playbooksRun")}
                        align="right"
                      />
                      <Th
                        label={t("cohort.table.errors")}
                        active={sortKey === "errors"}
                        dir={sortDir}
                        onClick={() => onSort("errors")}
                        align="right"
                      />
                      <Th
                        label={t("cohort.table.idle")}
                        active={sortKey === "idleMin"}
                        dir={sortDir}
                        onClick={() => onSort("idleMin")}
                        align="right"
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => setSelected(r)}
                        className="cursor-pointer border-t border-line/60 transition-colors hover:bg-bg-2/40 focus-within:bg-bg-2/40"
                        style={{
                          boxShadow: `inset 3px 0 0 0 ${phaseTint(r.phase)}`,
                        }}
                      >
                        <td className="px-3 py-3 text-[13px] text-ink">
                          <button
                            type="button"
                            className="text-left underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelected(r);
                            }}
                          >
                            {r.name}
                          </button>
                        </td>
                        <td className="px-3 py-3 font-mono-tech text-[11.5px] text-ink-2">
                          {r.email}
                        </td>
                        <td className="px-3 py-3">
                          <span
                            className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1.6px]"
                            style={{
                              borderColor: phaseTint(r.phase),
                              color: phaseTint(r.phase),
                            }}
                          >
                            {phaseLabel(r.phase)}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-[12.5px] text-ink-2">
                          {r.lastAction}
                        </td>
                        <td className="px-3 py-3 text-right font-mono-tech text-[12px] tabular-nums text-ink">
                          {r.playbooksRun}
                        </td>
                        <td
                          className="px-3 py-3 text-right font-mono-tech text-[12px] tabular-nums"
                          style={{
                            color:
                              r.errors > 0
                                ? "var(--alert, #ef4444)"
                                : "var(--ink-3)",
                          }}
                        >
                          {r.errors}
                        </td>
                        <td className="px-3 py-3 text-right font-mono-tech text-[12px] tabular-nums text-ink-2">
                          {r.idleMin}m
                        </td>
                      </tr>
                    ))}
                    {filtered.length === 0 && (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-4 py-10 text-center font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3"
                        >
                          {t("cohort.table.empty")}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bottom: CSV export */}
            <div
              data-tutorial-id="cohort-export"
              className="flex items-center justify-between gap-3 pt-2"
            >
              <p className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
                {t("cohort.export.note")}
              </p>
              <button
                type="button"
                onClick={onExportCSV}
                className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-line bg-bg-1/50 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                <Download size={12} aria-hidden />
                {t("cohort.export.csv")}
              </button>
            </div>
          </div>

          {/* Right rail */}
          <aside className="space-y-4">
            {/* Broadcast composer */}
            <div
              data-tutorial-id="cohort-broadcast"
              className="rounded-md border border-line bg-bg-1/40 p-4 backdrop-blur-sm"
            >
              <h3 className="mb-2 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
                <Send size={11} aria-hidden />
                {t("cohort.broadcast.title")}
              </h3>
              <textarea
                id="cohort-broadcast-textarea"
                value={broadcastText}
                onChange={(e) => setBroadcastText(e.target.value)}
                rows={3}
                placeholder={t("cohort.broadcast.placeholder")}
                aria-label={t("cohort.broadcast.title")}
                className="w-full resize-none rounded-sm border border-line bg-bg-0 px-3 py-2 text-[13px] text-ink placeholder:text-ink-3 focus:border-[var(--brand-indigo)] focus:outline-none"
              />
              <div className="mt-2 flex items-center justify-between gap-3">
                <span
                  aria-live="polite"
                  className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3"
                >
                  {broadcastState === "sending" && t("cohort.broadcast.sending")}
                  {broadcastState === "sent" && t("cohort.broadcast.sent")}
                  {broadcastState === "error" && t("cohort.broadcast.error")}
                </span>
                <button
                  type="button"
                  onClick={onBroadcast}
                  disabled={
                    !broadcastText.trim() || broadcastState === "sending"
                  }
                  className="inline-flex min-h-[36px] items-center gap-2 rounded-sm border border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:bg-[var(--brand-indigo)]/15 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
                >
                  <Send size={11} aria-hidden />
                  {t("cohort.broadcast.send")}
                </button>
              </div>
            </div>

            {/* Risk alerts */}
            <div
              data-tutorial-id="cohort-risk"
              className="rounded-md border border-line bg-bg-1/40 p-4 backdrop-blur-sm"
            >
              <h3 className="mb-2 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
                <TriangleAlert
                  size={11}
                  aria-hidden
                  style={{ color: "var(--alert, #ef4444)" }}
                />
                {t("cohort.alerts.title")}
              </h3>
              {riskRows.length === 0 ? (
                <p className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
                  {t("cohort.alerts.empty")}
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {riskRows.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => setSelected(r)}
                        className="flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-left text-[12.5px] text-ink transition-colors hover:bg-bg-2/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-alert"
                      >
                        <span>{r.name}</span>
                        <span
                          className="font-mono-tech text-[10px] uppercase tracking-[1.6px]"
                          style={{ color: "var(--alert, #ef4444)" }}
                        >
                          {t("cohort.alerts.errors_n", { n: r.errors })}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Live activity stream */}
            <div className="rounded-md border border-line bg-bg-1/40 p-4 backdrop-blur-sm">
              <h3 className="mb-2 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
                <Radio size={11} aria-hidden />
                {t("cohort.stream.title")}
              </h3>
              {events.length === 0 ? (
                <p className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
                  {t("cohort.stream.empty")}
                </p>
              ) : (
                <ol
                  className="max-h-[380px] space-y-2 overflow-y-auto pr-1"
                  aria-live="polite"
                >
                  {events.map((e) => (
                    <li
                      key={e.id}
                      className="border-l-2 pl-2 text-[12.5px] leading-[1.45] text-ink"
                      style={{ borderColor: streamTint(e) }}
                    >
                      {e.message}
                      <div className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                        {fmtRel(e.at)}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </aside>
        </section>
      </article>

      {/* Wave 92 — anchor for the cohort tutorial step that points at the
          attendee detail panel. The detail itself only mounts when an
          attendee is picked, so we expose a marker on the page so the
          tour always has something to highlight. */}
      <span
        data-tutorial-id="cohort-detail"
        aria-hidden
        className="pointer-events-none fixed bottom-4 right-4 inline-block h-2 w-2 rounded-full opacity-0"
      />
      <AttendeeDetail attendee={selected} onClose={() => setSelected(null)} />

      {/* Wave 92 — first-run interactive tour for facilitators (5 steps). */}
      <WorkshopTutorial pageKey="workshop-cohort" />
    </div>
  );
}

// ── small UI helpers ────────────────────────────────────────────────

interface ThProps {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  align?: "left" | "right";
}

function Th({ label, active, dir, onClick, align = "left" }: ThProps) {
  return (
    <th
      scope="col"
      className={`px-3 py-3 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3 ${align === "right" ? "text-right" : "text-left"}`}
    >
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)] ${active ? "text-ink" : ""}`}
        aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      >
        {label}
        {active && <span aria-hidden>{dir === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  sublabel: string;
  accent: string;
  highlight?: boolean;
}

function StatCard({
  label,
  value,
  sublabel,
  accent,
  highlight = false,
}: StatCardProps) {
  return (
    <div
      className="relative overflow-hidden rounded-md border border-line bg-bg-1/40 p-4 backdrop-blur-sm"
      style={
        highlight
          ? {
              boxShadow: `inset 0 0 0 1px ${accent}40`,
              background:
                "linear-gradient(180deg, rgba(34,197,94,0.06) 0%, transparent 100%)",
            }
          : undefined
      }
    >
      <div
        aria-hidden
        className="absolute left-0 top-0 h-full w-[3px]"
        style={{ background: accent }}
      />
      <div className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        {label}
      </div>
      <div
        className="mt-1 font-display font-medium tracking-[-0.01em] text-ink"
        style={{ fontSize: "clamp(1.6rem, 2.4vw, 2.1rem)" }}
      >
        {value}
      </div>
      <div className="mt-0.5 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
        {sublabel}
      </div>
    </div>
  );
}

function filterLabel(
  f: FilterChip,
  t: (key: TKey, vars?: Record<string, string | number>) => string,
): string {
  switch (f) {
    case "all":
      return t("cohort.filter.all");
    case "active":
      return t("cohort.filter.active");
    case "idle":
      return t("cohort.filter.idle");
    case "error":
      return t("cohort.filter.error");
    default:
      return phaseLabel(f);
  }
}

function streamTint(e: CohortEvent): string {
  switch (e.kind) {
    case "error":
      return "var(--alert, #ef4444)";
    case "hil_gate":
      return "var(--brand-violet)";
    case "phase_advance":
      return "#22c55e";
    case "join":
      return "var(--brand-cyan)";
    default:
      return "var(--brand-indigo)";
  }
}

function fmtRel(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return `${h}h ago`;
  } catch {
    return iso;
  }
}

export default WorkshopCohort;
