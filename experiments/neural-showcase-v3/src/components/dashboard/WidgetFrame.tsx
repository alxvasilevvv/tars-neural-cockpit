// SYNC: claude-w96-dashboard
/**
 * WidgetFrame - common shell for every dashboard widget.
 *
 * Provides title row, refresh button, last-updated stamp, settings
 * affordance, and (in edit mode) the remove "x" in the corner. The
 * actual widget content is passed as `children` so the child only
 * needs to render its data + states.
 */

import type { ReactNode } from "react";
import { Loader2, RefreshCcw, X } from "lucide-react";

export interface WidgetFrameProps {
  title: string;
  /** Lucide icon component, rendered at 13px in the title row. */
  Icon?: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  /** Last successful update; falsy => "never". */
  updatedAt?: number | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  /** When true, edit affordances (drag handle, remove X) appear. */
  editMode?: boolean;
  onRemove?: () => void;
  children: ReactNode;
  /** Optional aria-label for the outer article. */
  ariaLabel?: string;
}

function fmtAgo(ts: number | null | undefined): string {
  if (!ts) return "never";
  const sec = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (sec < 5)   return "just now";
  if (sec < 60)  return `${sec}s ago`;
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

export function WidgetFrame({
  title,
  Icon,
  updatedAt,
  loading,
  error,
  onRefresh,
  editMode,
  onRemove,
  children,
  ariaLabel,
}: WidgetFrameProps) {
  return (
    <article
      aria-label={ariaLabel ?? title}
      className={`group relative flex h-full min-h-[160px] flex-col rounded-lg border bg-bg-1/60 p-4 backdrop-blur-sm transition-colors ${
        editMode
          ? "border-dashed border-[var(--brand-indigo)]/60"
          : "border-line/70 hover:border-line"
      }`}
    >
      <header className="mb-3 flex items-center gap-2">
        {Icon ? (
          <Icon
            size={13}
            strokeWidth={1.7}
            className="shrink-0 text-[var(--brand-indigo)]"
          />
        ) : null}
        <h3 className="flex-1 truncate font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2">
          {title}
        </h3>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            aria-label={`Refresh ${title}`}
            className="rounded p-1 text-ink-3 transition-colors hover:bg-line/60 hover:text-ink disabled:opacity-50"
          >
            {loading ? (
              <Loader2 size={11} className="animate-spin" aria-hidden />
            ) : (
              <RefreshCcw size={11} aria-hidden />
            )}
          </button>
        ) : null}
        {editMode && onRemove ? (
          <button
            type="button"
            onClick={onRemove}
            aria-label={`Remove ${title} widget`}
            className="rounded border border-line/60 bg-bg-0/70 p-1 text-ink-3 transition-colors hover:border-red-500/60 hover:text-red-400"
          >
            <X size={11} aria-hidden />
          </button>
        ) : null}
      </header>

      <div className="flex-1 text-[12.5px] text-ink-2">
        {error ? (
          <p
            role="alert"
            className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-[11.5px] text-amber-300"
          >
            {error}
          </p>
        ) : (
          children
        )}
      </div>

      <footer className="mt-3 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
        <span>updated {fmtAgo(updatedAt)}</span>
        {editMode ? <span aria-hidden>:: drag</span> : null}
      </footer>
    </article>
  );
}
