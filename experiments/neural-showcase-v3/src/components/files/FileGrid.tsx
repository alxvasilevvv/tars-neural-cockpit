// SYNC: claude-w102-files
/**
 * <FileGrid /> — Wave 102 grid view for /files.
 *
 * Renders a responsive grid of file cards. Each card has a
 * thumbnail (image preview when mime is image/*, otherwise an
 * extension chip), filename, size, age, and a 3-dot menu hooked
 * to the parent's per-card action handler.
 */

import type { FileItem } from "./types";
import { Pin, MoreVertical, FileText, Image as ImageIcon } from "lucide-react";

export interface FileGridProps {
  files: FileItem[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onOpen: (file: FileItem) => void;
  onMenu: (file: FileItem, e: React.MouseEvent) => void;
}

export function FileGrid({
  files,
  selectedIds,
  onToggle,
  onOpen,
  onMenu,
}: FileGridProps) {
  if (files.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-md border border-dashed border-line/60 text-sm text-ink-2">
        No files in this view.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {files.map((file) => {
        const isImage = (file.mime || "").startsWith("image/");
        const isSelected = selectedIds.has(file.id);
        return (
          <article
            key={file.id}
            className={`group relative flex flex-col overflow-hidden rounded-lg border bg-bg-1 transition-shadow hover:shadow-md ${
              isSelected ? "border-accent ring-1 ring-accent/40" : "border-line/60"
            }`}
          >
            <button
              type="button"
              onClick={() => onOpen(file)}
              className="relative flex h-32 w-full items-center justify-center bg-bg-0/50"
              aria-label={`Open ${file.filename || "file"}`}
            >
              {isImage && file.thumbnail_url ? (
                <img
                  src={file.thumbnail_url}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center gap-1 text-ink-2">
                  {isImage ? (
                    <ImageIcon size={28} aria-hidden />
                  ) : (
                    <FileText size={28} aria-hidden />
                  )}
                  <span className="text-[10px] uppercase tracking-wider">
                    {file.extension || file.mime?.split("/").pop() || "file"}
                  </span>
                </div>
              )}
              {file.pinned && (
                <span
                  className="absolute right-2 top-2 rounded-full bg-bg-1/80 p-1 text-accent"
                  title="Pinned"
                >
                  <Pin size={11} aria-hidden />
                </span>
              )}
            </button>
            <div className="flex flex-col gap-1 p-2">
              <div className="flex items-start justify-between gap-1">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => onToggle(file.id)}
                  aria-label={`Select ${file.filename}`}
                  className="mt-1 h-3.5 w-3.5 accent-accent"
                />
                <button
                  type="button"
                  onClick={(e) => onMenu(file, e)}
                  className="rounded p-0.5 text-ink-2 hover:bg-bg-0 hover:text-ink"
                  aria-label="File actions"
                >
                  <MoreVertical size={14} aria-hidden />
                </button>
              </div>
              <div className="truncate text-xs text-ink" title={file.filename ?? undefined}>
                {file.filename || "untitled"}
              </div>
              <div className="flex justify-between text-[10px] text-ink-2">
                <span>{formatBytes(file.bytes_total)}</span>
                <span>{formatAge(file.created_at)}</span>
              </div>
              {file.tags.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {file.tags.slice(0, 3).map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent"
                    >
                      {t}
                    </span>
                  ))}
                  {file.tags.length > 3 && (
                    <span className="text-[10px] text-ink-2">+{file.tags.length - 3}</span>
                  )}
                </div>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatAge(epoch: number): string {
  const s = Math.max(0, Date.now() / 1000 - epoch);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400 / 7)}w`;
  return `${Math.floor(s / 86400 / 30)}mo`;
}
