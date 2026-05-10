// SYNC: claude-w101-inbox
/**
 * <InboxRow /> — Wave 101.
 *
 * Single row in the unified HIL queue table on /inbox. The row
 * surfaces (time, action, resource, $-impact, reason) plus the
 * three terminal verbs Approve / Deny / Detail. Click the row body
 * to open the side panel; the action buttons stop propagation so
 * an accidental row-click doesn't fire the gated action.
 *
 * Category colour comes from the `category` field (wallet=indigo,
 * outreach=violet, code=cyan, live_trading=red, other=neutral).
 */

import type { CSSProperties, KeyboardEvent } from "react";
import { Eye, Check, X } from "lucide-react";

export type InboxCategory = "wallet" | "outreach" | "code" | "live_trading" | "other";

export interface InboxItem {
  id: string;
  token: string;
  time: number;
  slug: string;
  action: string;
  action_id: string;
  resource: string;
  dollar_impact: number | null;
  category: InboxCategory;
  reason: string | null;
  status: string;
  expires_at: number | null;
  requested_by: string | null;
  thread_id: string | null;
  trace_id: string | null;
  args: Record<string, unknown>;
}

export const CATEGORY_COLOR: Record<InboxCategory, string> = {
  wallet: "var(--brand-indigo, #6366f1)",
  outreach: "var(--brand-violet, #8b5cf6)",
  code: "var(--brand-cyan, #06b6d4)",
  live_trading: "var(--color-danger, #ef4444)",
  other: "var(--ink-3, #94a3b8)",
};

export const CATEGORY_LABEL: Record<InboxCategory, string> = {
  wallet: "Wallet",
  outreach: "Outreach",
  code: "Code",
  live_trading: "Live trading",
  other: "Other",
};

function formatTime(ts: number): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDollar(v: number | null): string {
  if (v === null || v === undefined) return "—";
  if (v === 0) return "$0";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

export interface InboxRowProps {
  item: InboxItem;
  selected?: boolean;
  onSelect: (item: InboxItem) => void;
  onApprove: (item: InboxItem) => void;
  onDeny: (item: InboxItem) => void;
  onDetail: (item: InboxItem) => void;
}

export function InboxRow({ item, selected, onSelect, onApprove, onDeny, onDetail }: InboxRowProps) {
  const color = CATEGORY_COLOR[item.category];
  const stylePin: CSSProperties = { backgroundColor: color };
  const onKey = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(item);
    }
  };
  return (
    <tr
      role="row"
      tabIndex={0}
      aria-selected={selected ? true : undefined}
      data-testid={`inbox-row-${item.id}`}
      onClick={() => onSelect(item)}
      onKeyDown={onKey}
      className={`group cursor-pointer border-b border-line/50 transition-colors hover:bg-bg-2/40 focus:bg-bg-2/40 focus:outline-none ${
        selected ? "bg-bg-2/40" : ""
      }`}
    >
      <td className="py-3 pl-4 pr-2 align-top">
        <div className="flex items-center gap-2">
          <span aria-hidden className="block h-2 w-2 rounded-full" style={stylePin} />
          <span className="font-mono-tech text-[11px] text-ink-2">{formatTime(item.time)}</span>
        </div>
      </td>
      <td className="px-2 py-3 align-top font-mono-tech text-[12px] text-ink">
        {item.action}
      </td>
      <td className="px-2 py-3 align-top text-[12.5px] text-ink-2">
        <span className="break-all">{item.resource}</span>
      </td>
      <td className="px-2 py-3 align-top font-mono-tech text-[11.5px] text-ink-2">
        {formatDollar(item.dollar_impact)}
      </td>
      <td className="px-2 py-3 align-top text-[12px] text-ink-3">
        {item.reason ?? "—"}
      </td>
      <td className="py-3 pl-2 pr-4 align-top">
        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            onClick={() => onApprove(item)}
            aria-label="Approve"
            className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-bg-2/40 px-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            style={{ borderColor: color }}
          >
            <Check size={11} strokeWidth={2} aria-hidden />
            Approve
          </button>
          <button
            type="button"
            onClick={() => onDeny(item)}
            aria-label="Deny"
            className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-bg-2/40 px-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            <X size={11} strokeWidth={2} aria-hidden />
            Deny
          </button>
          <button
            type="button"
            onClick={() => onDetail(item)}
            aria-label="Detail"
            className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-bg-2/40 px-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            <Eye size={11} strokeWidth={2} aria-hidden />
            Detail
          </button>
        </div>
      </td>
    </tr>
  );
}
