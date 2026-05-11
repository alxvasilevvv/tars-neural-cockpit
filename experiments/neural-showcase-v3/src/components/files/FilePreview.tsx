// SYNC: claude-w102-files
/**
 * <FilePreview /> — Wave 102 modal preview.
 *
 * Type-detects the file by mime/extension and picks the best
 * inline renderer:
 *   - PDF             → <iframe src=download/>
 *   - image/*         → <img>
 *   - text-ish (md, txt, json, code) → <pre> with the extracted text
 *   - everything else → download CTA fallback
 */

import { useEffect, useState } from "react";
import { X, Download, ExternalLink } from "lucide-react";
import type { FileItem } from "./types";

const TEXT_EXT = new Set([
  "md",
  "markdown",
  "txt",
  "json",
  "yaml",
  "yml",
  "csv",
  "tsv",
  "log",
  "py",
  "ts",
  "tsx",
  "js",
  "jsx",
  "go",
  "rs",
  "html",
  "css",
  "diff",
  "patch",
  "sh",
  "sql",
]);

export interface FilePreviewProps {
  file: FileItem;
  onClose: () => void;
}

export function FilePreview({ file, onClose }: FilePreviewProps) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isPdf = (file.mime || "").toLowerCase() === "application/pdf";
  const isImage = (file.mime || "").startsWith("image/");
  const ext = (file.extension || "").toLowerCase();
  const isText =
    !isPdf &&
    !isImage &&
    (TEXT_EXT.has(ext) || (file.mime || "").startsWith("text/"));

  useEffect(() => {
    if (!isText) return;
    setLoading(true);
    fetch(`/api/chat/attachments/${file.id}/extracted`)
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      .then((t) => setText(t))
      .catch(() => setText(file.extracted_text_preview || ""))
      .finally(() => setLoading(false));
  }, [file.id, isText, file.extracted_text_preview]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Preview ${file.filename}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      onClick={onClose}
    >
      <div
        className="relative flex h-[80vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-line/60 bg-bg-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line/60 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm text-ink" title={file.filename ?? undefined}>
              {file.filename || "untitled"}
            </span>
            <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
              {file.category}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <a
              href={file.preview_url}
              download={file.filename ?? undefined}
              className="rounded p-1.5 text-ink-2 hover:bg-bg-0 hover:text-ink"
              aria-label="Download"
            >
              <Download size={14} aria-hidden />
            </a>
            <a
              href={file.preview_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded p-1.5 text-ink-2 hover:bg-bg-0 hover:text-ink"
              aria-label="Open in new tab"
            >
              <ExternalLink size={14} aria-hidden />
            </a>
            <button
              type="button"
              onClick={onClose}
              className="rounded p-1.5 text-ink-2 hover:bg-bg-0 hover:text-ink"
              aria-label="Close preview"
            >
              <X size={14} aria-hidden />
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-auto bg-bg-0/40">
          {isPdf && (
            <iframe
              title={file.filename ?? "PDF preview"}
              src={file.preview_url}
              className="h-full w-full"
            />
          )}
          {isImage && (
            <div className="flex h-full items-center justify-center p-4">
              <img
                src={file.preview_url}
                alt={file.filename ?? ""}
                loading="lazy"
                decoding="async"
                className="max-h-full max-w-full object-contain"
              />
            </div>
          )}
          {isText && (
            <pre className="whitespace-pre-wrap px-4 py-3 font-mono text-xs text-ink">
              {loading ? "Loading…" : text || file.extracted_text_preview}
            </pre>
          )}
          {!isPdf && !isImage && !isText && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-ink-2">
              <span>No inline preview for this file type.</span>
              <a
                href={file.preview_url}
                download={file.filename ?? undefined}
                className="rounded-md border border-line/60 px-3 py-1.5 text-ink hover:border-accent hover:text-accent"
              >
                Download {file.filename}
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
