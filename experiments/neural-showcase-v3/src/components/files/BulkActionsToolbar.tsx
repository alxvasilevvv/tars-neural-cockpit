// SYNC: claude-w102-files
/**
 * <BulkActionsToolbar /> — Wave 102. Sticks to the bottom of /files
 * when ≥1 file is selected and offers Tag / Categorize / Pin /
 * Delete actions over the active selection set.
 */

import { useState } from "react";
import { Tag, FolderOpen, Pin, Trash2, X } from "lucide-react";

export interface BulkActionsToolbarProps {
  count: number;
  onClear: () => void;
  onAddTag: (tag: string) => Promise<void> | void;
  onCategorize: (slug: string) => Promise<void> | void;
  onPin: (next: boolean) => Promise<void> | void;
  onDelete: (reason: string) => Promise<void> | void;
  categories: { slug: string; label: string }[];
}

export function BulkActionsToolbar({
  count,
  onClear,
  onAddTag,
  onCategorize,
  onPin,
  onDelete,
  categories,
}: BulkActionsToolbarProps) {
  const [open, setOpen] = useState<string | null>(null);
  const [tag, setTag] = useState("");
  const [reason, setReason] = useState("");

  if (count === 0) return null;

  return (
    <div
      role="toolbar"
      aria-label="Bulk file actions"
      className="fixed bottom-4 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 rounded-full border border-line/60 bg-bg-1/95 px-3 py-1.5 shadow-lg backdrop-blur"
    >
      <span className="rounded-full bg-accent/20 px-2 py-0.5 text-xs text-accent">
        {count} selected
      </span>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(open === "tag" ? null : "tag")}
          className="flex items-center gap-1 rounded-full px-2 py-1 text-xs text-ink-1 hover:bg-bg-0"
        >
          <Tag size={12} aria-hidden /> Tag
        </button>
        {open === "tag" && (
          <div className="absolute bottom-full left-0 mb-2 flex gap-1 rounded-md border border-line/60 bg-bg-1 p-2 shadow-lg">
            <input
              type="text"
              value={tag}
              onChange={(e) => setTag(e.target.value.slice(0, 32))}
              placeholder="tag name"
              className="rounded border border-line/60 bg-bg-0 px-2 py-1 text-xs text-ink"
            />
            <button
              type="button"
              onClick={async () => {
                if (tag.trim()) {
                  await onAddTag(tag.trim());
                  setTag("");
                  setOpen(null);
                }
              }}
              className="rounded bg-accent px-2 py-1 text-xs text-bg-0"
            >
              Add
            </button>
          </div>
        )}
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(open === "cat" ? null : "cat")}
          className="flex items-center gap-1 rounded-full px-2 py-1 text-xs text-ink-1 hover:bg-bg-0"
        >
          <FolderOpen size={12} aria-hidden /> Categorize
        </button>
        {open === "cat" && (
          <div className="absolute bottom-full left-0 mb-2 max-h-64 w-44 overflow-auto rounded-md border border-line/60 bg-bg-1 p-1 shadow-lg">
            {categories.map((c) => (
              <button
                key={c.slug}
                type="button"
                onClick={async () => {
                  await onCategorize(c.slug);
                  setOpen(null);
                }}
                className="block w-full rounded px-2 py-1 text-left text-xs text-ink hover:bg-accent/10 hover:text-accent"
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => onPin(true)}
        className="flex items-center gap-1 rounded-full px-2 py-1 text-xs text-ink-1 hover:bg-bg-0"
      >
        <Pin size={12} aria-hidden /> Pin
      </button>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(open === "del" ? null : "del")}
          className="flex items-center gap-1 rounded-full px-2 py-1 text-xs text-red-300 hover:bg-red-500/10"
        >
          <Trash2 size={12} aria-hidden /> Delete
        </button>
        {open === "del" && (
          <div className="absolute bottom-full right-0 mb-2 flex w-64 flex-col gap-1 rounded-md border border-line/60 bg-bg-1 p-2 shadow-lg">
            <p className="text-[11px] text-ink-2">
              Soft-delete {count} file{count === 1 ? "" : "s"}? Pinned files are kept.
            </p>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 200))}
              placeholder="reason (optional)"
              className="rounded border border-line/60 bg-bg-0 px-2 py-1 text-xs text-ink"
            />
            <div className="flex justify-end gap-1">
              <button
                type="button"
                onClick={() => setOpen(null)}
                className="rounded px-2 py-1 text-xs text-ink-2 hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  await onDelete(reason);
                  setReason("");
                  setOpen(null);
                }}
                className="rounded bg-red-500 px-2 py-1 text-xs text-white"
              >
                Soft-delete
              </button>
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onClear}
        className="ml-1 rounded-full p-1 text-ink-2 hover:bg-bg-0 hover:text-ink"
        aria-label="Clear selection"
      >
        <X size={12} aria-hidden />
      </button>
    </div>
  );
}
