// SYNC: claude-w101-inbox
/**
 * <ApprovalReasonModal /> — Wave 101.
 *
 * Modal that opens when the operator clicks Deny on any /inbox row.
 * Reason is required (`disabled` until non-empty); the backend at
 * POST /api/policy/deny/{id} re-checks and returns 422 with
 * `reason_required` if a hand-rolled curl tries to submit empty.
 *
 * Five quick-pick chips cover the most common deny reasons so the
 * operator can resolve a row in one click; the textarea is for the
 * "other" case.
 */

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { InboxItem } from "./InboxRow";

const QUICK_REASONS = [
  "Wrong recipient",
  "Out of policy",
  "Awaiting review",
  "Suspicious pattern",
  "Test fixture",
];

export interface ApprovalReasonModalProps {
  open: boolean;
  item: InboxItem | null;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}

export function ApprovalReasonModal({ open, item, onCancel, onSubmit }: ApprovalReasonModalProps) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) setReason("");
  }, [open, item?.id]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open || !item) return null;

  const trimmed = reason.trim();
  const ready = trimmed.length >= 3;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="deny-reason-title"
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-bg-0/80 p-6 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="mt-24 w-full max-w-[520px] rounded-[14px] border border-line-strong bg-bg-1 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="deny-reason-title" className="font-display text-[16px] text-ink">
              Why deny this action?
            </h2>
            <p className="mt-1 text-[12px] text-ink-2">
              <code className="font-mono-tech">{item.action}</code> · {item.resource}
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Cancel deny"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-line text-ink-3 hover:border-line-strong hover:text-ink"
          >
            <X size={13} strokeWidth={1.8} aria-hidden />
          </button>
        </header>

        <div className="mb-3 flex flex-wrap gap-1.5">
          {QUICK_REASONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setReason(q)}
              className={`inline-flex items-center rounded-full border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] transition-colors ${
                reason === q
                  ? "border-line-strong text-ink"
                  : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
              }`}
            >
              {q}
            </button>
          ))}
        </div>

        <label className="mb-1.5 block font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          Reason (required)
        </label>
        <textarea
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          aria-label="Deny reason"
          className="w-full rounded-md border border-line bg-bg-2/40 p-3 font-mono-tech text-[12px] text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none"
          placeholder="One short sentence about why this should not run."
        />

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-9 items-center rounded-md border border-line bg-bg-2/40 px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!ready}
            onClick={() => onSubmit(trimmed)}
            className="inline-flex h-9 items-center rounded-md border border-line-hot bg-accent-deep px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Submit deny
          </button>
        </div>
      </div>
    </div>
  );
}
