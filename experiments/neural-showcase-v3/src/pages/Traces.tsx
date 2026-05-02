/**
 * /cockpit/traces — local trace viewer.
 *
 * IDEAS #15 follow-up — backend `/api/meeet/traces` +
 * `/api/meeet/events?trace_id=…` shipped Phase L8; this page is the
 * design-side surface that finally renders the operator's local
 * "black box".
 *
 * Anatomy:
 *
 *   - Sticky header: back-to-cockpit, refresh, rebuild rollup,
 *     online/offline status pill.
 *   - Filter strip: route lozenges (all / edge / cloud / fallback /
 *     mixed) + free-text search box (`trace_id`, kind prefix, or
 *     session_id substring match).
 *   - Two-column workspace:
 *     - Left rail: trace list with kind summary, route pill, cost,
 *       duration, error count.
 *     - Right pane: drill-down — copy-to-clipboard trace_id, full
 *       summary card, and the underlying events list pulled from
 *       `/api/meeet/events?trace_id=…`.
 *   - Empty / loading / error states at every level so the operator
 *     never sees a frozen panel.
 *
 * Polling:
 *
 *   - Trace list refreshes every 5s by default (override via
 *     ``intervalMs`` prop).
 *   - Detail events refresh on row select; manual refresh button on
 *     the detail header re-fetches without flipping selection.
 *
 * URL state:
 *
 *   - `?selected=<trace_id>` deep-links a specific trace.
 *   - `?route=cloud` pre-selects a route filter.
 *   - `?q=...` pre-fills the free-text search.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  Plug,
  RefreshCcw,
  Search,
  Copy,
  Check,
} from "lucide-react";

import { useDocumentMeta } from "@/lib/meta";
import { useT, type TKey } from "@/lib/i18n";

type TFn = (key: TKey, vars?: Record<string, string | number>) => string;
import {
  listEvents,
  refreshTraces,
  useTraceSummaries,
  type MeeetEvent,
  type TraceSummary,
} from "@/lib/meeet";
import {
  ROUTE_FILTERS,
  formatCostUsd as fmtCostUsd,
  formatDurationMs as fmtDurationMs,
  formatTs,
  readRouteFilter,
  routeToTone,
  type RouteFilter,
} from "@/lib/traces";
import { API_BASE } from "@/lib/api";
import { BrandHairline } from "@/components/BrandHairline";

const formatDurationMs = (ms: number | null | undefined, t: TFn) =>
  fmtDurationMs(ms, { ms: t("traces.unit.ms"), s: t("traces.unit.s") });

const formatCostUsd = (usd: number, t: TFn) =>
  fmtCostUsd(usd, t("traces.unit.usd"));

export function Traces() {
  const t = useT();
  useDocumentMeta({
    title: "Traces",
    description:
      "Local trace viewer — every TARS action through the meeet bridge, rolled up by trace_id with cost, route, and contradictions.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const selected = searchParams.get("selected");
  const search = searchParams.get("q") ?? "";
  const routeFilter = readRouteFilter(searchParams.get("route"));

  const updateUrl = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      for (const [k, v] of Object.entries(patch)) {
        if (v == null || v === "" || v === "all") next.delete(k);
        else next.set(k, v);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setSelected = useCallback(
    (id: string | null) => updateUrl({ selected: id }),
    [updateUrl],
  );
  const setRoute = useCallback(
    (r: RouteFilter) => updateUrl({ route: r === "all" ? null : r }),
    [updateUrl],
  );
  const setSearch = useCallback(
    (q: string) => updateUrl({ q: q === "" ? null : q }),
    [updateUrl],
  );

  const { traces, loading, error, refresh } = useTraceSummaries({
    limit: 200,
    intervalMs: 5000,
    primary_route: routeFilter === "all" ? undefined : routeFilter,
  });

  // Promote the newest trace into selection when nothing is selected
  // and we just got fresh data — so the right pane never opens empty
  // on a populated bridge.
  useEffect(() => {
    if (!selected && traces.length > 0) {
      setSelected(traces[0]!.trace_id);
    }
  }, [selected, traces, setSelected]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return traces;
    return traces.filter(
      (s) =>
        s.trace_id.toLowerCase().includes(q) ||
        s.kinds.some((k) => k.toLowerCase().includes(q)) ||
        (s.last_session_id ?? "").toLowerCase().includes(q),
    );
  }, [traces, search]);

  const [rebuilding, setRebuilding] = useState(false);
  const onRebuild = useCallback(async () => {
    if (rebuilding) return;
    setRebuilding(true);
    try {
      await refreshTraces();
      await refresh();
    } catch (e) {
      // Swallow; the inline error pane covers the visible error path.
      console.warn("rebuild failed", e);
    } finally {
      setRebuilding(false);
    }
  }, [rebuilding, refresh]);

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
              {t("traces.eyebrow")}
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            <button
              type="button"
              onClick={onRebuild}
              disabled={rebuilding}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 transition-colors hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
              title={t("traces.rebuild")}
            >
              {rebuilding ? (
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
              ) : (
                <RefreshCcw size={11} strokeWidth={1.6} />
              )}
              <span>{rebuilding ? t("traces.rebuilding") : t("traces.rebuild")}</span>
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 transition-colors hover:border-line-strong hover:text-ink"
            >
              {loading ? (
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
              ) : (
                <RefreshCcw size={11} strokeWidth={1.6} />
              )}
              <span>{loading ? t("traces.refreshing") : t("traces.refresh")}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="mb-8">
        <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
          <span aria-hidden className="opacity-50">//</span>
          <span>TRACES</span>
          <span aria-hidden className="opacity-50">//</span>
          <span style={{ color: "var(--brand-cyan)" }}>v9.0</span>
        </div>
        <h1
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "var(--text-display-md)" }}
        >
          {t("traces.title")}
        </h1>
        <p className="mt-3 max-w-[80ch] font-mono-tech text-[12px] uppercase tracking-[2.4px] text-ink-2">
          {t("traces.subtitle")}
        </p>
      </div>

      <FilterStrip
        route={routeFilter}
        onRoute={setRoute}
        search={search}
        onSearch={setSearch}
        t={t}
      />

      {error && (
        <div className="mb-6 rounded-md border border-alert/40 bg-alert/[0.04] p-4 font-mono-tech text-[12px] text-alert">
          <header className="mb-1 flex items-center gap-2 font-display text-[13px] uppercase tracking-[0.04em]">
            <Plug size={13} strokeWidth={1.6} />
            {t("traces.error.title")}
          </header>
          <p>
            {t("traces.error.hint")} <code className="text-ink-2">{API_BASE}</code>
          </p>
          <p className="mt-1 text-ink-3">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[360px_1fr]">
        <TraceList
          traces={filtered}
          selected={selected}
          onSelect={setSelected}
          loading={loading && traces.length === 0}
          unfilteredCount={traces.length}
          t={t}
        />
        <div className="min-h-[200px]">
          {selected ? (
            <TraceDetail traceId={selected} t={t} />
          ) : !loading && traces.length === 0 ? (
            <EmptyState t={t} />
          ) : (
            <EmptyDetail t={t} />
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
  route,
  onRoute,
  search,
  onSearch,
  t,
}: {
  route: RouteFilter;
  onRoute: (r: RouteFilter) => void;
  search: string;
  onSearch: (s: string) => void;
  t: TFn;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
          {t("traces.filter.route")}
        </span>
        {ROUTE_FILTERS.map((r) => {
          const active = r === route;
          return (
            <button
              key={r}
              type="button"
              onClick={() => onRoute(r)}
              className={`rounded-md border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] transition-colors ${
                active
                  ? "border-line-hot bg-accent-deep text-accent"
                  : "border-line text-ink-2 hover:border-line-strong hover:text-ink"
              }`}
            >
              {t(`traces.filter.route.${r}` as TKey)}
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
          placeholder={t("traces.filter.search")}
          className="w-full bg-transparent font-mono-tech text-[11px] tracking-[0.6px] text-ink outline-none placeholder:text-ink-3"
        />
      </label>
    </div>
  );
}

function TraceList({
  traces,
  selected,
  onSelect,
  loading,
  unfilteredCount,
  t,
}: {
  traces: TraceSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  unfilteredCount: number;
  t: TFn;
}) {
  return (
    <aside className="grid gap-1 self-start rounded-[14px] border border-line bg-bg-1 p-3">
      <div className="mb-1 px-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        {t("traces.col.trace")} · {traces.length}
        {unfilteredCount > traces.length && (
          <span className="ml-2 text-ink-3">/ {unfilteredCount}</span>
        )}
      </div>
      {loading && (
        <div className="flex items-center gap-2 px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          loading…
        </div>
      )}
      {!loading && traces.length === 0 && (
        <div className="px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          {t("traces.empty.title")}
        </div>
      )}
      <ul className="grid max-h-[60vh] gap-1 overflow-auto">
        {traces.map((s) => {
          const tone = routeToTone(s.primary_route);
          const active = s.trace_id === selected;
          return (
            <li key={s.trace_id}>
              <button
                type="button"
                onClick={() => onSelect(s.trace_id)}
                className={`group block w-full cursor-pointer rounded-md border px-3 py-2 text-left transition-colors duration-200 ${
                  active
                    ? "border-line-hot bg-accent-deep"
                    : "border-line bg-transparent hover:border-line-strong"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono-tech text-[10px] uppercase tracking-[2px] text-ink">
                    {s.trace_id}
                  </span>
                  <span
                    className={`shrink-0 rounded-md border px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
                  >
                    {tone.label}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                  <span>{s.event_count} ev</span>
                  <span aria-hidden>·</span>
                  <span>{formatCostUsd(s.total_cost_usd, t)}</span>
                  <span aria-hidden>·</span>
                  <span>{formatDurationMs(s.duration_ms, t)}</span>
                  {s.error_count > 0 && (
                    <>
                      <span aria-hidden>·</span>
                      <span className="text-alert">err {s.error_count}</span>
                    </>
                  )}
                </div>
                <div className="mt-1 line-clamp-2 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
                  {s.kinds.slice(0, 4).join(" · ")}
                  {s.kinds.length > 4 && ` · +${s.kinds.length - 4}`}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function TraceDetail({
  traceId,
  t,
}: {
  traceId: string;
  t: TFn;
}) {
  const [summary, setSummary] = useState<TraceSummary | null>(null);
  const [events, setEvents] = useState<MeeetEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Pull both endpoints in parallel — the summary is one row, the
      // events list can run to ~hundreds, so we cap it on the client.
      const [s, evs] = await Promise.all([
        fetch(`${API_BASE}/api/meeet/traces/${encodeURIComponent(traceId)}`)
          .then(async (r) => {
            if (r.status === 404) return null;
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const d = (await r.json()) as { trace?: TraceSummary };
            return d.trace ?? null;
          }),
        listEvents({ trace_id: traceId, limit: 500 }),
      ]);
      if (!cancelled.current) {
        setSummary(s);
        setEvents(evs);
      }
    } catch (e) {
      if (!cancelled.current) setError((e as Error).message);
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  }, [traceId]);

  useEffect(() => {
    cancelled.current = false;
    void refresh();
    return () => {
      cancelled.current = true;
    };
  }, [refresh]);

  const onCopy = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    void navigator.clipboard.writeText(traceId).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  }, [traceId]);

  const tone = routeToTone(summary?.primary_route ?? null);

  return (
    <div
      data-testid="trace-detail"
      data-trace-id={traceId}
      className="rounded-[14px] border border-line bg-bg-1 p-5"
    >
      <header className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
            {t("traces.detail.eyebrow")}
          </span>
          <code className="font-mono-tech text-[12px] tracking-[0.4px] text-ink">
            {traceId}
          </code>
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-line px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            title={t("traces.detail.copy")}
            aria-label={t("traces.detail.copy")}
          >
            {copied ? (
              <>
                <Check size={10} strokeWidth={1.6} />
                {t("traces.detail.copied")}
              </>
            ) : (
              <Copy size={10} strokeWidth={1.6} />
            )}
          </button>
        </div>
        <span
          className={`shrink-0 rounded-md border px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
        >
          {tone.label}
        </span>
      </header>

      {error && (
        <div className="mb-3 rounded-md border border-alert/40 bg-alert/[0.04] p-3 font-mono-tech text-[11px] text-alert">
          {error}
        </div>
      )}

      {loading && !summary && (
        <div className="flex items-center gap-2 px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          loading trace…
        </div>
      )}

      {summary && (
        <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 font-mono-tech text-[11px] text-ink-2 md:grid-cols-3">
          <Stat label={t("traces.col.cost")} value={formatCostUsd(summary.total_cost_usd, t)} />
          <Stat
            label={t("traces.col.tokens")}
            value={`${summary.tokens_in.toLocaleString()} → ${summary.tokens_out.toLocaleString()}`}
          />
          <Stat label={t("traces.col.duration")} value={formatDurationMs(summary.duration_ms, t)} />
          <Stat label={t("traces.col.started")} value={formatTs(summary.started_at)} />
          <Stat
            label={t("traces.detail.session")}
            value={summary.last_session_id ?? "—"}
          />
          <Stat
            label={t("traces.detail.contradictions")}
            value={String(summary.contradictions)}
          />
        </dl>
      )}

      <h3 className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
        {t("traces.detail.events", { n: events.length })}
      </h3>
      <ol className="grid gap-1.5">
        {events.map((e) => (
          <li
            key={e.id}
            className="rounded-md border border-line bg-bg-0/40 px-3 py-2"
          >
            <div className="flex items-center justify-between gap-3 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
              <span>{e.kind}</span>
              <span>{formatTs(e.ts)}</span>
            </div>
            {Object.keys(e.payload).length > 0 && (
              <pre className="mt-1.5 overflow-x-auto font-mono-tech text-[10px] leading-snug text-ink-2">
                {JSON.stringify(e.payload, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono-tech text-[9px] uppercase tracking-[2.4px] text-ink-3">
        {label}
      </dt>
      <dd className="mt-0.5 font-mono-tech text-[12px] text-ink">{value}</dd>
    </div>
  );
}

function EmptyState({ t }: { t: TFn }) {
  return (
    <div className="rounded-[14px] border border-dashed border-line p-10 text-center">
      <h3 className="font-display text-[18px] tracking-[-0.01em] text-ink">
        {t("traces.empty.title")}
      </h3>
      <p className="mt-2 font-mono-tech text-[11.5px] tracking-[1.4px] text-ink-3">
        {t("traces.empty.body")}
      </p>
    </div>
  );
}

function EmptyDetail({ t }: { t: TFn }) {
  return (
    <div className="flex h-full min-h-[260px] items-center justify-center rounded-[14px] border border-dashed border-line p-10 font-mono-tech text-[11.5px] uppercase tracking-[2px] text-ink-3">
      {t("traces.detail.empty")}
    </div>
  );
}
