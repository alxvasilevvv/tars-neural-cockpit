// SYNC: claude-w101-inbox
/**
 * <BulkApproveDialog /> — Wave 101.
 *
 * Double-confirm modal for the "Bulk approve all" header button on
 * /inbox. Shows the operator exactly what's about to fire AND the
 * safety check (refuses to bulk-approve any single staged action
 * with $-impact > $10k). The backend re-checks the same ceiling so
 * a stale page can't slip a $50k confirmation through.
 *
 * Operator flow:
 *   1. Click "Bulk approve all" in the Inbox header
 *   2. This dialog opens, lists every approve-eligible item +
 *      every rejected (high-$) item with its $-impact label
 *   3. Operator must click "Confirm bulk approve" to fire
 */

import { useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";
import type { InboxItem } from "./InboxRow";
import { CATEGORY_COLOR } from "./InboxRow";

const BULK_CEILING_USD = 10_000;

export interface BulkApproveDialogProps {
  open: boolean;
  items: InboxItem[];
  onCancel: () => void;
  onConfirm: (eligibleIds: string[]) => void;
}

export function BulkApproveDialog({ open, items, onCancel, onConfirm }: BulkApproveDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const eligible = items.filter(
    (i) => i.dollar_impact === null || i.dollar_impact <= BULK_CEILING_USD,
  );
  const rejected = items.filter(
    (i) => i.dollar_impact !== null && i.dollar_impact > BULK_CEILING_USD,
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="bulk-approve-title"
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-bg-0/80 p-6 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="mt-16 w-full max-w-[640px] rounded-[14px] border border-line-strong bg-bg-1 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="bulk-approve-title" className="font-display text-[18px] text-ink">
              Bulk approve {eligible.length} action{eligible.length === 1 ? "" : "s"}
            </h2>
            <p className="mt-1 text-[12px] text-ink-2">
              Each item below will be marked confirmed in the audit trail. The actual
              gated action runs through its own outbox; bulk approve never auto-fires
              wallet sigs or live-trade promotions.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Cancel bulk approve"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-line text-ink-3 hover:border-line-strong hover:text-ink"
          >
            <X size={13} strokeWidth={1.8} aria-hidden />
          </button>
        </header>

        {rejected.length > 0 && (
          <div className="mb-4 rounded-md border border-[var(--color-danger,#ef4444)]/40 bg-[var(--color-danger,#ef4444)]/10 p-3 text-[11.5px] text-ink-2">
            <div className="mb-1.5 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2px]">
              <AlertTriangle size={11} strokeWidth={1.8} aria-hidden style={{ color: "var(--color-danger, #ef4444)" }} />
              <span>{rejected.length} item{rejected.length === 1 ? "" : "s"} excluded — over ${BULK_CEILING_USD.toLocaleString()}</span>
            </div>
            <ul className="ml-4 list-disc text-ink-3">
              {rejected.map((r) => (
                <li key={r.id} className="mb-0.5">
                  <code className="font-mono-tech">{r.action}</code> · {r.resource} · ${r.dollar_impact?.toLocaleString()}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-ink-3">Approve these one-at-a-time so the audit trail records a per-token decision.</p>
          </div>
        )}

        <ul className="mb-5 max-h-[40vh] overflow-y-auto rounded-md border border-line/60 bg-bg-2/40">
          {eligible.length === 0 && (
            <li className="px-3 py-4 text-center text-[12px] text-ink-3">
              No items eligible for bulk approve.
            </li>
          )}
          {eligible.map((it) => (
            <li
              key={it.id}
              className="flex items-center gap-3 border-b border-line/40 px-3 py-2 text-[12px] last:border-0"
            >
              <span aria-hidden className="block h-2 w-2 rounded-full" style={{ backgroundColor: CATEGORY_COLOR[it.category] }} />
              <code className="font-mono-tech text-ink">{it.action}</code>
              <span className="flex-1 truncate text-ink-2">{it.resource}</span>
              <span className="font-mono-tech text-[10.5px] text-ink-3">
                {it.dollar_impact === null ? "—" : `$${it.dollar_impact.toLocaleString()}`}
              </span>
            </li>
          ))}
        </ul>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-9 items-center rounded-md border border-line bg-bg-2/40 px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={eligible.length === 0}
            onClick={() => onConfirm(eligible.map((i) => i.id))}
            className="inline-flex h-9 items-center rounded-md border border-line-hot bg-accent-deep px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Confirm bulk approve
          </button>
        </div>
      </div>
    </div>
  );
}
