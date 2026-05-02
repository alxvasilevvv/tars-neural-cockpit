/**
 * /cockpit/awareness — awareness explorer.
 *
 * IDEAS #30 follow-up — backend
 * `GET /api/domains/<slug>/awareness/<id>/snapshot` shipped Phase
 * K-A; this page is the design-side surface that finally lets the
 * operator browse every awareness source per pack and snapshot live
 * feeds on demand.
 *
 * Anatomy:
 *   - Sticky header: back-to-cockpit, refresh packs, eyebrow.
 *   - Pack rail (left): every active pack with awareness-source count
 *     badge and live-source pulse.
 *   - Sources rail (middle): filter + list of awareness sources for
 *     the selected pack.
 *   - Snapshot pane (right): pretty-printed snapshot envelope, with
 *     config preview, took_ms / trace_id / fetched-ago badges, and
 *     error envelopes for `fetcher_unavailable` + 500s.
 *
 * URL state:
 *   - `?slug=<pack>` deep-links a specific pack.
 *   - `?source=<id>` deep-links a source on the selected pack.
 *   - `?q=...` pre-fills the source filter.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  Plug,
  RefreshCcw,
  Search,
  PlayCircle,
} from "lucide-react";

import { useDocumentMeta } from "@/lib/meta";
import { useT, type TKey } from "@/lib/i18n";
import {
  API_BASE,
  listDomains,
  snapshotAwareness,
  type AwarenessSource,
  type DomainPack,
} from "@/lib/api";
import {
  emptySnapshotState,
  filterAwareness,
  fmtAgo,
  fmtTookMs,
  kindTone,
  liveSourceCount,
  pickSlug,
  prettyJson,
  snapshotKey,
  totalSourceCount,
  type SnapshotEnvelope,
  type SnapshotState,
} from "@/lib/awarenessFmt";
import { BrandHairline } from "@/components/BrandHairline";

type TFn = (key: TKey, vars?: Record<string, string | number>) => string;

export function Awareness() {
  const t = useT();
  useDocumentMeta({
    title: "Awareness",
    description:
      "Awareness explorer — every awareness source per pack, snapshotable on demand through the meeet trace bridge.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const slugParam = searchParams.get("slug");
  const sourceParam = searchParams.get("source");
  const search = searchParams.get("q") ?? "";

  const updateUrl = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      for (const [k, v] of Object.entries(patch)) {
        if (v == null || v === "") next.delete(k);
        else next.set(k, v);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setSlug = useCallback(
    (s: string | null) => updateUrl({ slug: s, source: null }),
    [updateUrl],
  );
  const setSource = useCallback(
    (s: string | null) => updateUrl({ source: s }),
    [updateUrl],
  );
  const setSearch = useCallback(
    (q: string) => updateUrl({ q: q === "" ? null : q }),
    [updateUrl],
  );

  // --- Pack list -----------------------------------------------------
  const [packs, setPacks] = useState<DomainPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshPacks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listDomains();
      setPacks(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshPacks();
  }, [refreshPacks]);

  const slug = useMemo(
    () => pickSlug(packs.map(p => p.slug), slugParam),
    [packs, slugParam],
  );

  const selectedPack = useMemo(
    () => packs.find(p => p.slug === slug) ?? null,
    [packs, slug],
  );

  const filteredSources = useMemo(
    () => filterAwareness(selectedPack?.awareness ?? [], search),
    [selectedPack, search],
  );

  // Promote first source into selection when nothing is selected and
  // we just got fresh data.
  useEffect(() => {
    if (!selectedPack) return;
    if (sourceParam) return;
    const first = filteredSources[0];
    if (first) setSource(first.id);
  }, [selectedPack, sourceParam, filteredSources, setSource]);

  const selectedSource = useMemo(
    () =>
      selectedPack?.awareness?.find(s => s.id === sourceParam) ?? null,
    [selectedPack, sourceParam],
  );

  // --- Snapshot state per (slug, source_id) -------------------------
  const [snapshots, setSnapshots] = useState<Record<string, SnapshotState>>(
    {},
  );

  const runSnapshot = useCallback(
    async (packSlug: string, source: AwarenessSource) => {
      const key = snapshotKey(packSlug, source.id);
      setSnapshots(prev => ({
        ...prev,
        [key]: {
          ...(prev[key] ?? emptySnapshotState()),
          loading: true,
          error: null,
        },
      }));
      try {
        const env = (await snapshotAwareness(
          packSlug,
          source.id,
        )) as unknown as SnapshotEnvelope;
        setSnapshots(prev => ({
          ...prev,
          [key]: {
            loading: false,
            lastFetchedAt: Date.now(),
            envelope: env,
            error: null,
          },
        }));
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setSnapshots(prev => ({
          ...prev,
          [key]: {
            loading: false,
            lastFetchedAt: Date.now(),
            envelope: null,
            error: message,
          },
        }));
      }
    },
    [],
  );

  const totalSources = useMemo(() => totalSourceCount(packs), [packs]);

  // --- Render --------------------------------------------------------
  return (
    <section className="relative z-20 mx-auto min-h-screen max-w-[1480px] px-6 pb-24 pt-6 md:px-12">
      <Header
        t={t}
        loading={loading}
        onRefresh={() => void refreshPacks()}
        packCount={packs.length}
        sourceCount={totalSources}
      />

      {error ? (
        <ErrorBanner t={t} message={error} />
      ) : packs.length === 0 && !loading ? (
        <EmptyPacks t={t} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_320px_1fr]">
          <PackRail
            t={t}
            packs={packs}
            selectedSlug={slug}
            onSelect={setSlug}
          />
          <SourceRail
            t={t}
            pack={selectedPack}
            sources={filteredSources}
            search={search}
            setSearch={setSearch}
            selectedId={sourceParam}
            onSelect={setSource}
            snapshots={snapshots}
          />
          <SnapshotPane
            t={t}
            pack={selectedPack}
            source={selectedSource}
            state={
              selectedPack && selectedSource
                ? snapshots[snapshotKey(selectedPack.slug, selectedSource.id)] ??
                  emptySnapshotState()
                : null
            }
            onRunSnapshot={runSnapshot}
          />
        </div>
      )}
    </section>
  );
}

// --- Subcomponents ---------------------------------------------------

function Header({
  t,
  loading,
  onRefresh,
  packCount,
  sourceCount,
}: {
  t: TFn;
  loading: boolean;
  onRefresh: () => void;
  packCount: number;
  sourceCount: number;
}) {
  return (
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
            {t("awareness.eyebrow")}
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
          <span>
            {t("awareness.summary.packs", {
              packs: packCount,
              sources: sourceCount,
            })}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 transition-colors hover:border-line-strong hover:text-ink"
          >
            {loading ? (
              <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
            ) : (
              <RefreshCcw size={11} strokeWidth={1.6} />
            )}
            <span>
              {loading ? t("awareness.refreshing") : t("awareness.refresh")}
            </span>
          </button>
        </div>
      </div>
      <div className="mt-2">
        <h1
          className="font-display font-medium leading-[0.98] tracking-[-0.018em] text-ink"
          style={{ fontSize: "clamp(1.4rem, 3vw, 2.1rem)" }}
        >
          {t("awareness.title")}
        </h1>
        <p className="mt-1 max-w-[80ch] font-display text-[12.5px] leading-[1.6] text-ink-2">
          {t("awareness.subtitle")}
        </p>
      </div>
    </div>
  );
}

function ErrorBanner({ t, message }: { t: TFn; message: string }) {
  return (
    <div className="rounded-[14px] border border-alert/40 bg-alert/[0.06] px-4 py-6 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-alert">
      <div className="mb-1 flex items-center gap-2 font-display text-[14px] tracking-normal">
        <Plug size={14} strokeWidth={1.6} aria-hidden />
        <span>{t("awareness.error.title")}</span>
      </div>
      <p className="text-ink-3">
        {t("awareness.error.hint")} <code className="text-ink-2">{API_BASE}</code>
      </p>
      <pre className="mt-2 whitespace-pre-wrap font-mono-tech text-[10px] text-ink-3">
        {message}
      </pre>
    </div>
  );
}

function EmptyPacks({ t }: { t: TFn }) {
  return (
    <div className="rounded-[14px] border border-line bg-bg-1/60 px-4 py-10 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
      <p className="mb-2 font-display text-[14px] tracking-normal text-ink-2">
        {t("awareness.empty.packs.title")}
      </p>
      <p>{t("awareness.empty.packs.body")}</p>
    </div>
  );
}

function PackRail({
  t,
  packs,
  selectedSlug,
  onSelect,
}: {
  t: TFn;
  packs: DomainPack[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}) {
  return (
    <aside className="rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-md">
      <header className="border-b border-line/40 px-4 py-3 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
        packs
      </header>
      <ul role="listbox" aria-label="domain packs">
        {packs.map(p => {
          const live = liveSourceCount(p.awareness);
          const total = (p.awareness ?? []).length;
          const active = p.slug === selectedSlug;
          return (
            <li key={p.slug}>
              <button
                type="button"
                onClick={() => onSelect(p.slug)}
                className={`flex w-full items-center justify-between gap-3 border-l-2 px-4 py-2.5 text-left transition-colors ${
                  active
                    ? "border-accent bg-accent/[0.06]"
                    : "border-transparent hover:bg-bg-2"
                }`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-display text-[13.5px] text-ink">
                    {p.name}
                  </span>
                  <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                    {p.slug}
                    {p.composite ? " · composite" : ""}
                  </span>
                </span>
                <span className="shrink-0 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                  <span className="text-ink-2">{total}</span>
                  {live > 0 ? (
                    <span className="ml-1 text-accent" title="live sources">
                      · {live} {t("awareness.snapshot.live")}
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function SourceRail({
  t,
  pack,
  sources,
  search,
  setSearch,
  selectedId,
  onSelect,
  snapshots,
}: {
  t: TFn;
  pack: DomainPack | null;
  sources: AwarenessSource[];
  search: string;
  setSearch: Dispatch<SetStateAction<string>> | ((q: string) => void);
  selectedId: string | null;
  onSelect: (id: string) => void;
  snapshots: Record<string, SnapshotState>;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  return (
    <aside className="rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-md">
      <header className="flex items-center gap-2 border-b border-line/40 px-3 py-2.5">
        <Search size={12} strokeWidth={1.6} className="text-ink-3" aria-hidden />
        <input
          ref={inputRef}
          value={search}
          onChange={e =>
            typeof setSearch === "function"
              ? (setSearch as (q: string) => void)(e.target.value)
              : null
          }
          placeholder={t("awareness.search.placeholder")}
          aria-label={t("awareness.search.placeholder")}
          className="flex-1 bg-transparent font-display text-[12.5px] text-ink outline-none placeholder:text-ink-3"
        />
      </header>
      {!pack ? (
        <p className="px-4 py-6 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
          —
        </p>
      ) : sources.length === 0 ? (
        <div className="px-4 py-6 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
          <p className="mb-1 font-display text-[12.5px] tracking-normal text-ink-2">
            {t("awareness.empty.sources.title")}
          </p>
          <p>{t("awareness.empty.sources.body")}</p>
        </div>
      ) : (
        <ul role="listbox" aria-label="awareness sources">
          {sources.map(s => {
            const tone = kindTone(s.kind);
            const active = s.id === selectedId;
            const state =
              snapshots[snapshotKey(pack.slug, s.id)] ?? emptySnapshotState();
            return (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className={`flex w-full items-start gap-3 border-l-2 px-4 py-2.5 text-left transition-colors ${
                    active
                      ? "border-accent bg-accent/[0.06]"
                      : "border-transparent hover:bg-bg-2"
                  }`}
                >
                  <span
                    className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] ${tone.cls}`}
                  >
                    {tone.label}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-display text-[13px] text-ink">
                      {s.name || s.id}
                    </span>
                    <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                      {s.id}
                      {s.live
                        ? ` · ${t("awareness.snapshot.live")}`
                        : ` · ${t("awareness.snapshot.config")}`}
                      {state.lastFetchedAt
                        ? ` · ${fmtAgo(state.lastFetchedAt)}`
                        : ""}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

function SnapshotPane({
  t,
  pack,
  source,
  state,
  onRunSnapshot,
}: {
  t: TFn;
  pack: DomainPack | null;
  source: AwarenessSource | null;
  state: SnapshotState | null;
  onRunSnapshot: (slug: string, source: AwarenessSource) => Promise<void>;
}) {
  if (!pack || !source || !state) {
    return (
      <article className="rounded-[14px] border border-line bg-bg-1/60 px-6 py-12 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3 backdrop-blur-md">
        <p className="mb-2 font-display text-[14px] tracking-normal text-ink-2">
          {t("awareness.detail.empty.title")}
        </p>
        <p>{t("awareness.detail.empty.body")}</p>
      </article>
    );
  }

  const tone = kindTone(source.kind);
  const env = state.envelope;
  const failed = Boolean(state.error || (env && env.ok === false));

  return (
    <article className="rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-md">
      <header className="border-b border-line/40 px-5 py-4">
        <div className="mb-1 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
          <span>{t("awareness.detail.eyebrow")}</span>
          <span aria-hidden className="opacity-50">
            //
          </span>
          <span>{pack.slug}</span>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate font-display text-[20px] tracking-[-0.012em] text-ink">
              {source.name || source.id}
            </h2>
            <p className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3">
              {source.id}
            </p>
            {source.description ? (
              <p className="mt-2 max-w-[70ch] font-display text-[13px] leading-[1.55] text-ink-2">
                {source.description}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
            <span
              className={`rounded-full border px-2 py-0.5 ${tone.cls}`}
            >
              {tone.label}
            </span>
            <button
              type="button"
              onClick={() => void onRunSnapshot(pack.slug, source)}
              disabled={state.loading || !source.live}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-3 py-1.5 transition-colors hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
              title={
                source.live
                  ? t("awareness.snapshot.run")
                  : t("awareness.detail.unavailable")
              }
            >
              {state.loading ? (
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
              ) : (
                <PlayCircle size={11} strokeWidth={1.6} />
              )}
              <span>
                {state.loading
                  ? t("awareness.snapshot.running")
                  : t("awareness.snapshot.run")}
              </span>
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
          <span>
            {t("awareness.detail.took")} ·{" "}
            <span className="text-ink-2">
              {fmtTookMs(env?.took_ms ?? null)}
            </span>
          </span>
          <span>
            {t("awareness.detail.fetched")} ·{" "}
            <span className="text-ink-2">{fmtAgo(state.lastFetchedAt)}</span>
          </span>
          {env?.trace_id ? (
            <span>
              {t("awareness.detail.trace")} ·{" "}
              <code className="text-ink-2">
                {env.trace_id.slice(0, 12)}
              </code>
            </span>
          ) : null}
        </div>
      </header>

      {failed ? (
        <div className="border-b border-alert/40 bg-alert/[0.06] px-5 py-4 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-alert">
          <p className="mb-1 font-display text-[13px] tracking-normal">
            {t("awareness.detail.error.title")}
          </p>
          <p className="text-ink-3">
            {t("awareness.detail.error.hint")}
          </p>
          {state.error ? (
            <pre className="mt-2 whitespace-pre-wrap text-[10px] text-alert">
              {state.error}
            </pre>
          ) : null}
          {env?.error ? (
            <pre className="mt-2 whitespace-pre-wrap text-[10px] text-alert">
              {env.error}
              {env.hint ? `\n\n${env.hint}` : ""}
            </pre>
          ) : null}
        </div>
      ) : null}

      <section className="grid gap-5 px-5 py-5 md:grid-cols-2">
        <div>
          <h3 className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {t("awareness.detail.config.title")}
          </h3>
          <pre className="max-h-[400px] overflow-y-auto rounded-md border border-line bg-bg-2/40 p-3 font-mono-tech text-[10.5px] leading-[1.55] text-ink-2">
            {prettyJson(source.config) || "—"}
          </pre>
        </div>
        <div>
          <h3 className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {t("awareness.detail.data.title")}
          </h3>
          <pre className="max-h-[400px] overflow-y-auto rounded-md border border-line bg-bg-2/40 p-3 font-mono-tech text-[10.5px] leading-[1.55] text-ink-2">
            {env?.data
              ? prettyJson(env.data)
              : env?.ok === false
                ? "—"
                : "—"}
          </pre>
        </div>
      </section>
    </article>
  );
}
