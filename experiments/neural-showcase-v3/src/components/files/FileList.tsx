// SYNC: claude-w102-files
/**
 * <FileList /> — Wave 102 list view (table) for /files. Has a
 * checkbox column + bulk-select header. The `selectedIds` set is
 * owned by the page so the bulk actions toolbar shares state.
 */

import type { FileItem } from "./types";
import { Pin, MoreVertical } from "lucide-react";

export interface FileListProps {
  files: FileItem[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (next: boolean) => void;
  onOpen: (file: FileItem) => void;
  onMenu: (file: FileItem, e: React.MouseEvent) => void;
}

export function FileList({
  files,
  selectedIds,
  onToggle,
  onToggleAll,
  onOpen,
  onMenu,
}: FileListProps) {
  if (files.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-md border border-dashed border-line/60 text-sm text-ink-2">
        No files in this view.
      </div>
    );
  }
  const allSelected =
    files.length > 0 && files.every((f) => selectedIds.has(f.id));
  return (
    <div className="overflow-x-auto rounded-md border border-line/60">
      <table className="min-w-full text-sm">
        <thead className="bg-bg-1 text-xs uppercase tracking-wider text-ink-2">
          <tr>
            <th className="w-8 px-2 py-2">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => onToggleAll(e.target.checked)}
                aria-label="Select all visible files"
                className="h-3.5 w-3.5 accent-accent"
              />
            </th>
            <th className="px-2 py-2 text-left">Name</th>
            <th className="px-2 py-2 text-left">Category</th>
            <th className="px-2 py-2 text-left">Tags</th>
            <th className="px-2 py-2 text-right">Size</th>
            <th className="px-2 py-2 text-right">Added</th>
            <th className="w-8 px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => {
            const isSelected = selectedIds.has(file.id);
            return (
              <tr
                key={file.id}
                className={`border-t border-line/40 ${
                  isSelected ? "bg-accent/5" : "hover:bg-bg-1/50"
                }`}
              >
                <td className="px-2 py-1.5">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => onToggle(file.id)}
                    aria-label={`Select ${file.filename ?? "file"}`}
                    className="h-3.5 w-3.5 accent-accent"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <button
                    type="button"
                    onClick={() => onOpen(file)}
                    className="flex items-center gap-1.5 truncate text-left text-ink hover:text-accent"
                    title={file.filename ?? undefined}
                  >
                    {file.pinned && (
                      <Pin size={11} className="text-accent" aria-hidden />
                    )}
                    <span className="truncate">{file.filename || "untitled"}</span>
                  </button>
                  {file.match_snippet && (
                    <div
                      className="mt-0.5 line-clamp-1 text-[10px] text-ink-2"
                      // eslint-disable-next-line react/no-danger
                      dangerouslySetInnerHTML={{ __html: file.match_snippet }}
                    />
                  )}
                </td>
                <td className="px-2 py-1.5 text-xs text-ink-1">{file.category}</td>
                <td className="px-2 py-1.5">
                  <div className="flex flex-wrap gap-1">
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
                </td>
                <td className="px-2 py-1.5 text-right text-xs text-ink-2">
                  {bytes(file.bytes_total)}
                </td>
                <td className="px-2 py-1.5 text-right text-xs text-ink-2">
                  {age(file.created_at)}
                </td>
                <td className="px-2 py-1.5">
                  <button
                    type="button"
                    onClick={(e) => onMenu(file, e)}
                    className="rounded p-0.5 text-ink-2 hover:bg-bg-0 hover:text-ink"
                    aria-label="File actions"
                  >
                    <MoreVertical size={14} aria-hidden />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function bytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function age(epoch: number): string {
  const s = Math.max(0, Date.now() / 1000 - epoch);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`;
  return `${Math.floor(s / 86400 / 7)}w`;
}
