// SYNC: claude-w101-inbox
/**
 * <Inbox /> — Wave 101.
 *
 * Unified HIL approval queue at /inbox. Many actions across TARS
 * (wallet sign, outreach send, code edits, paper→live promotion,
 * deletion) emit via ``policy_gate.require_confirm()`` and stage a
 * confirmation token in the policy store. This page is the operator's
 * single inbox for resolving them.
 *
 * Pages reads from ``GET /api/policy/queue`` (Wave 101 surface) every
 * 5s, with an SSE fallback to ``/api/policy/queue/stream`` once the
 * lifespan helper opens it. Approve fires the existing
 * ``POST /api/policy/confirm/{token}``; deny goes to the new
 * ``POST /api/policy/deny/{id}``.
 *
 * Layout:
 *   - Header (count, bulk-approve)
 *   - Filter chips by category
 *   - Time filter dropdown
 *   - Table (one row per pending confirmation)
 *   - Side panel (full payload + audit context) when a row is selected
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CheckCheck, Inbox as InboxIcon, RefreshCw } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { InboxRow, type InboxItem, type InboxCategory } from "@/components/inbox/InboxRow";
import { ApprovalDetail } from "@/components/inbox/ApprovalDetail";
import { BulkApproveDialog } from "@/components/inbox/BulkApproveDialog";
import { ApprovalReasonModal } from "@/components/inbox/ApprovalReasonModal";

type CategoryFilter = "all" | InboxCategory;
type TimeFilter = "hour" | "day" | "week" | "all";

const CATEGORY_FILTERS: Array<{ id: CategoryFilter; label: string }> = [
  { id: "all",          label: "All" },
  { id: "wallet",       label: "Wallet" },
  { id: "outreach",     label: "Outreach" },
  { id: "code",         label: "Code" },
  { id: "live_trading", label: "Live trading" },
  { id: "other",        label: "Other" },
];

const TIME_FILTERS: Array<{ id: TimeFilter; label: string }> = [
  { id: "hour", label: "Last hour" },
  { id: "day",  label: "Last 24h" },
  { id: "week", label: "This week" },
  { id: "all",  label: "All" },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...(init || {}),
  });
  if (!r.ok) {
    let detail: unknown = "";
    try { detail = await r.json(); } catch { /* ignore */ }
    throw new Error(`HTTP ${r.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return r.json() as Promise<T>;
}

export function Inbox() {
  const t = useT();
  useDocumentMeta({
    title: "Inbox · TARS",
    description: "Approve, deny, or bulk-resolve every pending HIL confirmation in one place.",
  });

  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [time, setTime] = useState<TimeFilter>("all");
  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [denyTarget, setDenyTarget] = useState<InboxItem | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("status", "pending");
      if (category !== "all") params.set("type", category);
      if (time !== "all") params.set("since", time);
      const r = await api<{ items?: InboxItem[]; count: number }>(
        `/api/policy/queue?${params.toString()}`,
      );
      setItems(r.items ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [category, time]);

  // Initial + filter-change fetch.
  useEffect(() => { void fetchQueue(); }, [fetchQueue]);

  // Auto-refresh every 5s (no SSE coupling — the SSE endpoint exists
  // but a 5s poll is fine for a low-traffic queue and avoids the EventSource
  // reconnect dance when the operator closes the tab).
  useEffect(() => {
    const id = window.setInterval(() => { void fetchQueue(); }, 5000);
    return () => window.clearInterval(id);
  }, [fetchQueue]);

  const filtered = items;

  const onApproveOne = useCallback(async (it: InboxItem) => {
    try {
      await api(`/api/policy/confirm/${encodeURIComponent(it.token)}`, { method: "POST" });
      setSelected((cur) => (cur?.id === it.id ? null : cur));
      await fetchQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [fetchQueue]);

  const onDenyOpen = useCallback((it: InboxItem) => {
    setDenyTarget(it);
  }, []);

  const onDenySubmit = useCallback(async (reason: string) => {
    if (!denyTarget) return;
    try {
      await api(`/api/policy/deny/${encodeURIComponent(denyTarget.token)}`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setSelected((cur) => (cur?.id === denyTarget.id ? null : cur));
      setDenyTarget(null);
      await fetchQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setDenyTarget(null);
    }
  }, [denyTarget, fetchQueue]);

  const onBulkConfirm = useCallback(async (ids: string[]) => {
    try {
      await api(`/api/policy/queue/bulk-approve`, {
        method: "POST",
        body: JSON.stringify({ ids, reason: "bulk approve from /inbox" }),
      });
      setBulkOpen(false);
      setBulkConfirm(false);
      setSelected(null);
      await fetchQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBulkOpen(false);
      setBulkConfirm(false);
    }
  }, [fetchQueue]);

  const headerCount = filtered.length;

  // Double-confirm: clicking the header button arms the dialog; the
  // dialog itself is the second confirm step.
  const onBulkClick = () => {
    if (!bulkConfirm) {
      setBulkConfirm(true);
      window.setTimeout(() => setBulkConfirm(false), 4000);
      return;
    }
    setBulkOpen(true);
  };

  return (
    <section className="relative z-10 mx-auto max-w-[1280px] px-6 pb-24 pt-28 md:px-12">
      <Breadcrumbs items={[{ label: t("inbox.crumb.home" as never) ?? "Home", to: "/" }, { label: t("inbox.crumb" as never) ?? "Inbox" }]} className="mb-6" />

      {/* Header */}
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.6px] text-ink-3">
            <InboxIcon size={11} strokeWidth={1.8} aria-hidden style={{ color: "var(--brand-indigo, #6366f1)" }} />
            <span>{t("inbox.eyebrow" as never) ?? "Wave 101"}</span>
          </div>
          <h1
            className="font-display font-medium leading-[1.04] tracking-[-0.018em] text-ink"
            style={{ fontSize: "var(--text-display-md)" }}
          >
            {t("inbox.title" as never) ?? "Inbox"}
          </h1>
          <p className="mt-1.5 text-[13px] text-ink-2">
            {(t("inbox.count" as never, { n: headerCount }) ?? `${headerCount} pending approval${headerCount === 1 ? "" : "s"}`).toString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void fetchQueue()}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line bg-bg-2/40 px-3 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            <RefreshCw size={12} strokeWidth={1.8} aria-hidden />
            {t("inbox.refresh" as never) ?? "Refresh"}
          </button>
          <button
            type="button"
            disabled={headerCount === 0}
            onClick={onBulkClick}
            data-testid="inbox-bulk-approve"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line-hot bg-accent-deep px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <CheckCheck size={12} strokeWidth={1.8} aria-hidden />
            {bulkConfirm
              ? (t("inbox.bulk.confirmAgain" as never) ?? "Click again to confirm")
              : (t("inbox.bulk.button" as never) ?? "Bulk approve all")}
          </button>
        </div>
      </header>

      {/* Filter chips */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {CATEGORY_FILTERS.map((f) => {
          const active = category === f.id;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => setCategory(f.id)}
              className={`inline-flex items-center rounded-full border px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] transition-colors ${
                active
                  ? "border-line-strong bg-bg-2/60 text-ink"
                  : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
              }`}
            >
              {f.label}
            </button>
          );
        })}
        <span className="mx-2 hidden h-5 w-px bg-line/60 md:inline-block" aria-hidden />
        <label className="ml-auto flex items-center gap-2 text-[10.5px] uppercase tracking-[2px] text-ink-3 md:ml-0">
          <span className="font-mono-tech">{t("inbox.time" as never) ?? "Time"}</span>
          <select
            value={time}
            onChange={(e) => setTime(e.target.value as TimeFilter)}
            aria-label="Time filter"
            className="rounded-md border border-line bg-bg-2/40 px-2 py-1 font-mono-tech text-[10.5px] text-ink-2"
          >
            {TIME_FILTERS.map((tf) => (
              <option key={tf.id} value={tf.id}>{tf.label}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Table + side panel grid */}
      <div className={`grid gap-6 ${selected ? "lg:grid-cols-[1fr_380px]" : "lg:grid-cols-1"}`}>
        <motion.div
          layout
          className="overflow-hidden rounded-[14px] border border-line-strong bg-bg-1"
        >
          {error && (
            <div className="border-b border-line/40 bg-[var(--color-danger,#ef4444)]/10 px-5 py-3 font-mono-tech text-[11px] text-ink-2">
              {error}
            </div>
          )}
          {loading && filtered.length === 0 && (
            <div className="px-5 py-8 text-center text-[12px] text-ink-3">
              {t("inbox.loading" as never) ?? "Loading…"}
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="px-5 py-12 text-center">
              <p className="mx-auto max-w-[44ch] text-[13px] leading-[1.55] text-ink-2">
                {t("inbox.empty" as never) ?? "No pending approvals — your agents are autonomous within their guardrails."}
              </p>
            </div>
          )}
          {filtered.length > 0 && (
            <table className="w-full">
              <thead>
                <tr className="border-b border-line/60 text-left">
                  <th className="py-2.5 pl-4 pr-2 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.time" as never) ?? "Time"}
                  </th>
                  <th className="px-2 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.action" as never) ?? "Action"}
                  </th>
                  <th className="px-2 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.resource" as never) ?? "Resource"}
                  </th>
                  <th className="px-2 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.dollar" as never) ?? "$-impact"}
                  </th>
                  <th className="px-2 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.reason" as never) ?? "Reason"}
                  </th>
                  <th className="py-2.5 pl-2 pr-4 text-right font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                    {t("inbox.col.actions" as never) ?? "Actions"}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <InboxRow
                    key={it.id}
                    item={it}
                    selected={selected?.id === it.id}
                    onSelect={setSelected}
                    onApprove={onApproveOne}
                    onDeny={onDenyOpen}
                    onDetail={setSelected}
                  />
                ))}
              </tbody>
            </table>
          )}
        </motion.div>

        {selected && (
          <ApprovalDetail
            item={selected}
            onClose={() => setSelected(null)}
            onApprove={onApproveOne}
            onDeny={onDenyOpen}
          />
        )}
      </div>

      {/* Footer note. */}
      <p className="mt-12 max-w-[64ch] text-[11.5px] leading-[1.65] text-ink-3">
        {t("inbox.footer" as never) ?? "Each approve / deny is recorded as a Wave 95 receipt (hash-chained, ed25519-signed, optionally Solana-anchored). Tune the auto-approve dollar threshold in Settings."}
      </p>

      <BulkApproveDialog
        open={bulkOpen}
        items={filtered}
        onCancel={() => setBulkOpen(false)}
        onConfirm={onBulkConfirm}
      />
      <ApprovalReasonModal
        open={denyTarget !== null}
        item={denyTarget}
        onCancel={() => setDenyTarget(null)}
        onSubmit={onDenySubmit}
      />
    </section>
  );
}
