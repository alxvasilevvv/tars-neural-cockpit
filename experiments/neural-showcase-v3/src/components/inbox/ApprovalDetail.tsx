// SYNC: claude-w101-inbox
/**
 * <ApprovalDetail /> — Wave 101.
 *
 * Side panel that opens when the operator clicks an InboxRow. Shows
 * the full args payload as JSON, the originating agent (slug +
 * action), audit context (token, trace_id, thread_id, requested_by,
 * expires_at), and the approve/deny buttons inline so the operator
 * can decide without scrolling back to the row.
 *
 * The panel sits in-line in the Inbox grid (not a true overlay) so
 * the row stays visible — this matches the cockpit traces panel
 * pattern.
 */

import { useEffect } from "react";
import { ChevronRight, Check, X } from "lucide-react";
import type { InboxItem } from "./InboxRow";
import { CATEGORY_COLOR, CATEGORY_LABEL } from "./InboxRow";

function formatDateTime(ts: number | null): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function formatTimeLeft(expires_at: number | null): string {
  if (!expires_at) return "no expiry";
  const left = expires_at - Date.now() / 1000;
  if (left <= 0) return "expired";
  if (left < 60) return `${Math.round(left)}s left`;
  if (left < 3600) return `${Math.round(left / 60)}m left`;
  return `${Math.round(left / 3600)}h left`;
}

export interface ApprovalDetailProps {
  item: InboxItem;
  onClose: () => void;
  onApprove: (item: InboxItem) => void;
  onDeny: (item: InboxItem) => void;
}

export function ApprovalDetail({ item, onClose, onApprove, onDeny }: ApprovalDetailProps) {
  // Esc to close.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const color = CATEGORY_COLOR[item.category];
  return (
    <aside
      role="region"
      aria-label="Approval detail"
      className="rounded-[14px] border border-line-strong bg-bg-1 p-5"
    >
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div
            className="mb-2 inline-flex items-center gap-2 rounded-md border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px]"
            style={{ borderColor: color, color }}
          >
            <span aria-hidden className="block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
            {CATEGORY_LABEL[item.category]}
          </div>
          <h2 className="font-display text-[16px] leading-[1.25] text-ink">{item.action}</h2>
          <p className="mt-1 break-all text-[12px] text-ink-2">{item.resource}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-line text-ink-3 hover:border-line-strong hover:text-ink"
        >
          <ChevronRight size={14} strokeWidth={1.8} aria-hidden />
        </button>
      </header>

      <dl className="grid grid-cols-1 gap-2 text-[11.5px] text-ink-2">
        <DetailRow label="Token" value={<code className="font-mono-tech text-ink">{item.token}</code>} />
        <DetailRow label="Created" value={formatDateTime(item.time)} />
        <DetailRow label="Expires" value={`${formatDateTime(item.expires_at)} · ${formatTimeLeft(item.expires_at)}`} />
        <DetailRow label="Requested by" value={item.requested_by ?? "—"} />
        <DetailRow label="Trace" value={item.trace_id ?? "—"} />
        <DetailRow label="Thread" value={item.thread_id ?? "—"} />
        <DetailRow
          label="$-impact"
          value={item.dollar_impact === null ? "—" : `$${item.dollar_impact.toLocaleString()}`}
        />
        <DetailRow label="Reason" value={item.reason ?? "—"} />
      </dl>

      <h3 className="mt-5 mb-2 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">Payload</h3>
      <pre
        data-testid="approval-detail-payload"
        className="max-h-[40vh] overflow-auto rounded-md border border-line/60 bg-bg-2/40 p-3 font-mono-tech text-[11px] text-ink-2"
      >
        {JSON.stringify(item.args, null, 2)}
      </pre>

      <div className="mt-5 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => onDeny(item)}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line bg-bg-2/40 px-3 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 hover:border-line-strong hover:text-ink"
        >
          <X size={12} strokeWidth={1.8} aria-hidden />
          Deny
        </button>
        <button
          type="button"
          onClick={() => onApprove(item)}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line-hot bg-accent-deep px-3 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-accent hover:bg-accent/15"
        >
          <Check size={12} strokeWidth={1.8} aria-hidden />
          Approve
        </button>
      </div>
    </aside>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] items-baseline gap-3 border-b border-line/30 pb-1.5 last:border-0">
      <dt className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">{label}</dt>
      <dd className="break-all text-ink-2">{value}</dd>
    </div>
  );
}
