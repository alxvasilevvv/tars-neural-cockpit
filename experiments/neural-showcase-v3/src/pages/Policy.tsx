/**
 * /cockpit/policy — operator-grade approval inbox.
 *
 * IDEAS #29 follow-up — backend `/api/policy/{pending,recent,confirm,
 * cancel,expire}` shipped Phase K-D; this page is the design-side
 * surface that finally renders the destructive-action queue without
 * burying it in `<OperatorStrip />`.
 *
 * Anatomy:
 *
 *   - Sticky header: back to cockpit, refresh, expire-stale (admin),
 *     and a route-status pill.
 *   - Tab strip: pending / recent. Each tab carries its own count.
 *   - Filter strip: free-text search box (matches token / slug /
 *     action / requested_by / trace_id substrings, case-insensitive).
 *   - Two-column workspace:
 *     - Left rail: confirmation list with status pill, slug.action,
 *       requested_by, age, and (for pending) time-to-expire.
 *     - Right pane: drill-down detail with copy-to-clipboard token,
 *       full args / result / metadata, and the confirm/cancel
 *       affordances behind a "are you sure?" modal so the operator
 *       can never one-click a destructive action by mistake.
 *
 * Polling:
 *
 *   - Pending tab refreshes every 4 s.
 *   - Recent tab refreshes every 8 s (audit history doesn't change
 *     as often).
 *   - Optimistic updates after confirm / cancel — re-fetch fires in
 *     the background so the rail catches up within one tick.
 *
 * URL state:
 *
 *   - `?tab=pending|recent` — picks the tab.
 *   - `?selected=<token>` — deep-links a specific confirmation.
 *   - `?q=...` — pre-fills the search box.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Copy,
  Loader2,
  Plug,
  RefreshCcw,
  Search,
  ShieldAlert,
} from "lucide-react";

import { useDocumentMeta } from "@/lib/meta";
import { useT, type TKey } from "@/lib/i18n";
import {
  cancelToken,
  confirmToken,
  expireStale,
  usePendingConfirmations,
  useRecentConfirmations,
  type PendingConfirmation,
} from "@/lib/policy";
import { API_BASE } from "@/lib/api";
import {
  ALL_STATUSES,
  fmtAge,
  fmtTimeLeft,
  matchesQuery,
  statusTone,
} from "@/lib/policyFmt";
import { BrandHairline } from "@/components/BrandHairline";

type TFn = (key: TKey, vars?: Record<string, string | number>) => string;
type Tab = "pending" | "recent";

function readTab(raw: string | null | undefined): Tab {
  return raw === "recent" ? "recent" : "pending";
}

export function Policy() {
  const t = useT();
  useDocumentMeta({
    title: "Policy inbox",
    description:
      "Approval inbox for destructive actions — confirm, cancel, audit. Backed by the local TARS policy gate.",
    ogImage: "https://tars.meeet.world/og-cockpit.svg",
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const tab = readTab(searchParams.get("tab"));
  const selected = searchParams.get("selected");
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

  const setTab = useCallback(
    (next: Tab) => updateUrl({ tab: next === "pending" ? null : next }),
    [updateUrl],
  );
  const setSelected = useCallback(
    (id: string | null) => updateUrl({ selected: id }),
    [updateUrl],
  );
  const setSearch = useCallback(
    (q: string) => updateUrl({ q: q === "" ? null : q }),
    [updateUrl],
  );

  const { pending, loading: pendingLoading, error: pendingError, refresh: refreshPending } =
    usePendingConfirmations(4000);
  const { recent, loading: recentLoading, error: recentError, refresh: refreshRecent } =
    useRecentConfirmations({ limit: 100, intervalMs: 8000 });

  const list = tab === "pending" ? pending : recent;
  const loading = tab === "pending" ? pendingLoading : recentLoading;
  const error = tab === "pending" ? pendingError : recentError;

  const filtered = useMemo(
    () => list.filter((c) => matchesQuery(c, search)),
    [list, search],
  );

  // Promote the newest confirmation when nothing is selected.
  useEffect(() => {
    if (!selected && filtered.length > 0) {
      setSelected(filtered[0]!.token);
    }
  }, [selected, filtered, setSelected]);

  const selectedConfirmation = useMemo(
    () =>
      // Search both lists — operator may deep-link a recent token
      // while the pending tab is active.
      pending.find((c) => c.token === selected) ??
      recent.find((c) => c.token === selected) ??
      null,
    [pending, recent, selected],
  );

  const [busyToken, setBusyToken] = useState<string | null>(null);
  const [busyKind, setBusyKind] = useState<"confirm" | "cancel" | null>(null);
  const [showModal, setShowModal] = useState(false);

  const refreshBoth = useCallback(async () => {
    await Promise.all([refreshPending(), refreshRecent()]);
  }, [refreshPending, refreshRecent]);

  const onConfirm = useCallback(
    async (token: string) => {
      setBusyToken(token);
      setBusyKind("confirm");
      try {
        await confirmToken(token);
      } catch (e) {
        console.warn("confirm failed", e);
      } finally {
        setBusyToken(null);
        setBusyKind(null);
        setShowModal(false);
        void refreshBoth();
      }
    },
    [refreshBoth],
  );

  const onCancel = useCallback(
    async (token: string) => {
      setBusyToken(token);
      setBusyKind("cancel");
      try {
        await cancelToken(token);
      } catch (e) {
        console.warn("cancel failed", e);
      } finally {
        setBusyToken(null);
        setBusyKind(null);
        void refreshBoth();
      }
    },
    [refreshBoth],
  );

  const [expiring, setExpiring] = useState(false);
  const onExpireStale = useCallback(async () => {
    if (expiring) return;
    setExpiring(true);
    try {
      await expireStale();
      await refreshBoth();
    } catch (e) {
      console.warn("expire failed", e);
    } finally {
      setExpiring(false);
    }
  }, [expiring, refreshBoth]);

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
              {t("policy.eyebrow")}
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            <button
              type="button"
              onClick={onExpireStale}
              disabled={expiring}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 transition-colors hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
            >
              {expiring ? (
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
              ) : (
                <ShieldAlert size={11} strokeWidth={1.6} />
              )}
              <span>{expiring ? t("policy.expiring") : t("policy.expire")}</span>
            </button>
            <button
              type="button"
              onClick={() => void refreshBoth()}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 transition-colors hover:border-line-strong hover:text-ink"
            >
              {loading ? (
                <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
              ) : (
                <RefreshCcw size={11} strokeWidth={1.6} />
              )}
              <span>{t("policy.refresh")}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="mb-8">
        <div className="mb-3 inline-flex items-center gap-2.5 font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-indigo)" }}>OPERATOR</span>
          <span aria-hidden className="opacity-50">//</span>
          <span>POLICY</span>
          <span aria-hidden className="opacity-50">//</span>
          <span style={{ color: "var(--brand-cyan)" }}>v9.0</span>
        </div>
        <h1
          className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
          style={{ fontSize: "var(--text-display-md)" }}
        >
          {t("policy.title")}
        </h1>
        <p className="mt-3 max-w-[80ch] font-mono-tech text-[12px] uppercase tracking-[2.4px] text-ink-2">
          {t("policy.subtitle")}
        </p>
      </div>

      <TabStrip
        tab={tab}
        onTab={setTab}
        pendingCount={pending.length}
        recentCount={recent.length}
        t={t}
      />

      <FilterStrip search={search} onSearch={setSearch} t={t} />

      {error && (
        <div className="mb-6 rounded-md border border-alert/40 bg-alert/[0.04] p-4 font-mono-tech text-[12px] text-alert">
          <header className="mb-1 flex items-center gap-2 font-display text-[13px] uppercase tracking-[0.04em]">
            <Plug size={13} strokeWidth={1.6} />
            {t("policy.error.title")}
          </header>
          <p>
            {t("policy.error.hint")} <code className="text-ink-2">{API_BASE}</code>
          </p>
          <p className="mt-1 text-ink-3">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
        <ConfirmationList
          confirmations={filtered}
          selected={selected}
          onSelect={setSelected}
          loading={loading && list.length === 0}
          unfilteredCount={list.length}
          tab={tab}
          t={t}
        />
        <div className="min-h-[200px]">
          {selectedConfirmation ? (
            <ConfirmationDetail
              confirmation={selectedConfirmation}
              onConfirm={() => setShowModal(true)}
              onCancel={() => void onCancel(selectedConfirmation.token)}
              busyKind={
                busyToken === selectedConfirmation.token ? busyKind : null
              }
              t={t}
            />
          ) : (
            <EmptyDetail tab={tab} t={t} />
          )}
        </div>
      </div>

      {showModal && selectedConfirmation && (
        <ConfirmModal
          confirmation={selectedConfirmation}
          busy={busyKind === "confirm" && busyToken === selectedConfirmation.token}
          onProceed={() => void onConfirm(selectedConfirmation.token)}
          onClose={() => setShowModal(false)}
          t={t}
        />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TabStrip({
  tab,
  onTab,
  pendingCount,
  recentCount,
  t,
}: {
  tab: Tab;
  onTab: (next: Tab) => void;
  pendingCount: number;
  recentCount: number;
  t: TFn;
}) {
  return (
    <div role="tablist" className="mb-4 flex items-center gap-1.5">
      {(["pending", "recent"] as const).map((id) => {
        const active = tab === id;
        const count = id === "pending" ? pendingCount : recentCount;
        return (
          <button
            key={id}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onTab(id)}
            className={`rounded-md border px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2.4px] transition-colors ${
              active
                ? "border-line-hot bg-accent-deep text-accent"
                : "border-line text-ink-2 hover:border-line-strong hover:text-ink"
            }`}
          >
            {t(`policy.tab.${id}` as TKey)} · {count}
          </button>
        );
      })}
    </div>
  );
}

function FilterStrip({
  search,
  onSearch,
  t,
}: {
  search: string;
  onSearch: (s: string) => void;
  t: TFn;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <label className="ml-auto flex w-full max-w-md items-center gap-2 rounded-md border border-line bg-bg-1 px-3 py-1.5">
        <Search size={12} strokeWidth={1.6} className="text-ink-3" aria-hidden />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder={t("policy.filter.search")}
          className="w-full bg-transparent font-mono-tech text-[11px] tracking-[0.6px] text-ink outline-none placeholder:text-ink-3"
        />
      </label>
    </div>
  );
}

function ConfirmationList({
  confirmations,
  selected,
  onSelect,
  loading,
  unfilteredCount,
  tab,
  t,
}: {
  confirmations: PendingConfirmation[];
  selected: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  unfilteredCount: number;
  tab: Tab;
  t: TFn;
}) {
  return (
    <aside className="grid gap-1 self-start rounded-[14px] border border-line bg-bg-1 p-3">
      <div className="mb-1 px-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        {t(`policy.tab.${tab}` as TKey)} · {confirmations.length}
        {unfilteredCount > confirmations.length && (
          <span className="ml-2 text-ink-3">/ {unfilteredCount}</span>
        )}
      </div>
      {loading && (
        <div className="flex items-center gap-2 px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          loading…
        </div>
      )}
      {!loading && confirmations.length === 0 && (
        <div className="px-2 py-3 font-mono-tech text-[11px] text-ink-3">
          {tab === "pending"
            ? t("policy.empty.pending.title")
            : t("policy.empty.recent.title")}
        </div>
      )}
      <ul className="grid max-h-[60vh] gap-1 overflow-auto">
        {confirmations.map((c) => {
          const tone = statusTone(c.status);
          const active = c.token === selected;
          return (
            <li key={c.token}>
              <button
                type="button"
                onClick={() => onSelect(c.token)}
                className={`group block w-full cursor-pointer rounded-md border px-3 py-2 text-left transition-colors duration-200 ${
                  active
                    ? "border-line-hot bg-accent-deep"
                    : "border-line bg-transparent hover:border-line-strong"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink">
                    {c.slug}.{c.action_id}
                  </span>
                  <span
                    className={`shrink-0 rounded-md border px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
                  >
                    {t(`policy.status.${c.status}` as TKey)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                  <span>{fmtAge(c.created_at)}</span>
                  {c.status === "pending" && (
                    <>
                      <span aria-hidden>·</span>
                      <span>{fmtTimeLeft(c.expires_at)}</span>
                    </>
                  )}
                </div>
                {c.requested_by && (
                  <div className="mt-1 truncate font-mono-tech text-[10px] tracking-[1.4px] text-ink-2">
                    {c.requested_by}
                  </div>
                )}
                <div className="mt-0.5 truncate font-mono-tech text-[9.5px] tracking-[1.4px] text-ink-3">
                  {c.token}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function ConfirmationDetail({
  confirmation: c,
  onConfirm,
  onCancel,
  busyKind,
  t,
}: {
  confirmation: PendingConfirmation;
  onConfirm: () => void;
  onCancel: () => void;
  busyKind: "confirm" | "cancel" | null;
  t: TFn;
}) {
  const [copied, setCopied] = useState(false);
  const onCopy = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    void navigator.clipboard.writeText(c.token).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  }, [c.token]);

  const tone = statusTone(c.status);
  const isPending = c.status === "pending";

  return (
    <div
      data-testid="confirmation-detail"
      data-token={c.token}
      className="rounded-[14px] border border-line bg-bg-1 p-5"
    >
      <header className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
            {t("policy.detail.eyebrow")}
          </span>
          <code className="font-mono-tech text-[12px] tracking-[0.4px] text-ink">
            {c.slug}.{c.action_id}
          </code>
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-line px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            title={t("policy.action.copy")}
            aria-label={t("policy.action.copy")}
          >
            {copied ? (
              <>
                <Check size={10} strokeWidth={1.6} />
                {t("policy.action.copied")}
              </>
            ) : (
              <Copy size={10} strokeWidth={1.6} />
            )}
          </button>
        </div>
        <span
          className={`shrink-0 rounded-md border px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${tone.cls}`}
        >
          {t(`policy.status.${c.status}` as TKey)}
        </span>
      </header>

      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 font-mono-tech text-[11px] text-ink-2 md:grid-cols-3">
        <Stat label={t("policy.col.token")} value={c.token} />
        <Stat label={t("policy.col.created")} value={fmtAge(c.created_at)} />
        <Stat
          label={t("policy.col.expires")}
          value={isPending ? fmtTimeLeft(c.expires_at) : fmtAge(c.resolved_at)}
        />
        <Stat label={t("policy.col.requestedBy")} value={c.requested_by ?? "—"} />
        <Stat label={t("policy.col.trace")} value={c.trace_id ?? "—"} />
        <Stat label={t("policy.col.status")} value={t(`policy.status.${c.status}` as TKey)} />
      </dl>

      {isPending && (
        <div className="mb-4 rounded-md border border-[color:var(--brand-amber,#FBBF24)]/40 bg-[color:var(--brand-amber,#FBBF24)]/[0.04] p-3 font-mono-tech text-[11px] text-[color:var(--brand-amber,#FBBF24)]">
          <ShieldAlert size={12} strokeWidth={1.8} className="mr-1 inline" />
          {t("policy.detail.armed")}
        </div>
      )}

      <h3 className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
        {t("policy.col.args")}
      </h3>
      <pre className="mb-4 max-h-[280px] overflow-auto rounded-md border border-line bg-bg-0/40 p-3 font-mono-tech text-[10.5px] leading-snug text-ink-2">
        {JSON.stringify(c.args, null, 2)}
      </pre>

      {c.result && Object.keys(c.result).length > 0 && (
        <>
          <h3 className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            {t("policy.col.result")}
          </h3>
          <pre className="mb-4 max-h-[280px] overflow-auto rounded-md border border-line bg-bg-0/40 p-3 font-mono-tech text-[10.5px] leading-snug text-ink-2">
            {JSON.stringify(c.result, null, 2)}
          </pre>
        </>
      )}

      {isPending && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onConfirm}
            disabled={busyKind != null}
            className="cursor-pointer rounded border border-line-hot bg-accent-deep px-4 py-2 font-display text-[12px] uppercase tracking-[0.16em] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyKind === "confirm"
              ? t("policy.action.confirming")
              : t("policy.action.confirm")}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={busyKind != null}
            className="cursor-pointer rounded border border-line px-4 py-2 font-display text-[12px] uppercase tracking-[0.16em] text-ink-2 hover:border-alert hover:text-alert disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyKind === "cancel"
              ? t("policy.action.cancelling")
              : t("policy.action.cancel")}
          </button>
        </div>
      )}
    </div>
  );
}

function ConfirmModal({
  confirmation: c,
  busy,
  onProceed,
  onClose,
  t,
}: {
  confirmation: PendingConfirmation;
  busy: boolean;
  onProceed: () => void;
  onClose: () => void;
  t: TFn;
}) {
  // Trap focus + close on ESC.
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-0/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-labelledby="policy-confirm-title"
        aria-describedby="policy-confirm-body"
        tabIndex={-1}
        className="m-4 w-full max-w-md rounded-[14px] border border-line bg-bg-1 p-6 outline-none"
      >
        <h2
          id="policy-confirm-title"
          className="mb-2 font-display text-[18px] tracking-[-0.01em] text-ink"
        >
          {t("policy.confirm.modal.title")}
        </h2>
        <p
          id="policy-confirm-body"
          className="mb-4 font-mono-tech text-[11.5px] tracking-[1.2px] text-ink-2"
        >
          {t("policy.confirm.modal.body", {
            action: `${c.slug}.${c.action_id}`,
            trace: c.trace_id ?? "—",
          })}
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="cursor-pointer rounded border border-line px-4 py-2 font-display text-[12px] uppercase tracking-[0.16em] text-ink-2 hover:border-line-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("policy.confirm.modal.cancel")}
          </button>
          <button
            type="button"
            onClick={onProceed}
            disabled={busy}
            className="cursor-pointer rounded border border-line-hot bg-accent-deep px-4 py-2 font-display text-[12px] uppercase tracking-[0.16em] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
            autoFocus
          >
            {busy ? t("policy.action.confirming") : t("policy.confirm.modal.proceed")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="font-mono-tech text-[9px] uppercase tracking-[2.4px] text-ink-3">
        {label}
      </dt>
      <dd className="mt-0.5 truncate font-mono-tech text-[12px] text-ink">{value}</dd>
    </div>
  );
}

function EmptyDetail({ tab, t }: { tab: Tab; t: TFn }) {
  return (
    <div className="flex h-full min-h-[260px] items-center justify-center rounded-[14px] border border-dashed border-line p-10 text-center">
      <div>
        <p className="font-mono-tech text-[11.5px] uppercase tracking-[2px] text-ink-3">
          {t("policy.detail.empty")}
        </p>
        <p className="mt-2 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-3">
          {tab === "pending"
            ? t("policy.empty.pending.body")
            : t("policy.empty.recent.body")}
        </p>
      </div>
    </div>
  );
}

// Re-export so the regression test can pin the canonical status set
// the page renders against the typed `ConfirmationStatus` union.
export { ALL_STATUSES };
