// SYNC: claude-w102-files
/**
 * <BulkUploadDropzone /> — Wave 102. Drag-drop zone with per-file
 * progress. We POST a single multipart with all files (the server
 * accepts batches up to ~1 GB cumulative) and surface the
 * succeed/fail counts back to the parent so it can refresh the
 * grid.
 */

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { UploadCloud, FileText, X, CheckCircle2, AlertTriangle } from "lucide-react";

export interface BulkUploadDropzoneProps {
  /** Called after a successful upload with the API response. */
  onUploaded: (result: UploadResult) => void;
  /** Optional category to attach to all files in this batch. */
  category?: string;
  /** Trigger LLM auto-categorisation pass after ingest. */
  autoCategorize?: boolean;
  className?: string;
}

interface UploadResult {
  uploaded: number;
  failed: number;
  errors: { filename: string | null; error: string }[];
}

interface FileSlot {
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  message?: string;
}

const MAX_FILE_BYTES = 100 * 1024 * 1024;

export function BulkUploadDropzone({
  onUploaded,
  category,
  autoCategorize,
  className = "",
}: BulkUploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [slots, setSlots] = useState<FileSlot[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const queue = (incoming: FileList | File[]) => {
    const next: FileSlot[] = [];
    for (const f of Array.from(incoming)) {
      if (f.size > MAX_FILE_BYTES) {
        next.push({ file: f, status: "error", message: "File over 100 MB" });
        continue;
      }
      next.push({ file: f, status: "pending" });
    }
    setSlots(next);
  };

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    queue(e.target.files);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (!e.dataTransfer?.files || e.dataTransfer.files.length === 0) return;
    queue(e.dataTransfer.files);
  };

  const upload = async () => {
    if (slots.length === 0 || busy) return;
    setBusy(true);
    setSlots((cur) =>
      cur.map((s) => (s.status === "pending" ? { ...s, status: "uploading" } : s)),
    );
    const fd = new FormData();
    for (const slot of slots) {
      if (slot.status === "error") continue;
      fd.append("files", slot.file, slot.file.name);
    }
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (autoCategorize) params.set("auto", "1");
    try {
      const r = await fetch(`/api/files/upload${params.toString() ? `?${params}` : ""}`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const body = await r.json();
      const errMap = new Map<string, string>(
        (body.errors || []).map((e: { filename: string; error: string }) => [e.filename, e.error]),
      );
      setSlots((cur) =>
        cur.map((s) => {
          if (s.status === "error") return s;
          const err = errMap.get(s.file.name);
          if (err) return { ...s, status: "error", message: err };
          return { ...s, status: "done" };
        }),
      );
      onUploaded({
        uploaded: body.uploaded ?? 0,
        failed: body.failed ?? 0,
        errors: body.errors ?? [],
      });
    } catch (err) {
      setSlots((cur) =>
        cur.map((s) =>
          s.status === "uploading"
            ? { ...s, status: "error", message: String(err) }
            : s,
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  const clear = () => setSlots([]);

  return (
    <div className={className}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          dragOver
            ? "border-accent bg-accent/5"
            : "border-line/60 bg-bg-1/40"
        }`}
      >
        <UploadCloud size={28} className="text-accent" aria-hidden />
        <p className="text-sm text-ink">Drop files here or click to pick</p>
        <p className="text-xs text-ink-2">
          Up to 100 MB per file · 1 GB per batch
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-1 rounded-md border border-line/60 px-3 py-1.5 text-xs text-ink hover:border-accent hover:text-accent"
        >
          Pick files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={onPick}
          aria-label="Pick files to upload"
        />
      </div>

      {slots.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5">
          {slots.map((slot, i) => (
            <div
              key={`${slot.file.name}-${i}`}
              className="flex items-center gap-2 rounded border border-line/40 bg-bg-1/40 px-2 py-1 text-xs"
            >
              <FileText size={12} className="text-ink-2" aria-hidden />
              <span className="flex-1 truncate text-ink">{slot.file.name}</span>
              <span className="text-ink-2">{Math.round(slot.file.size / 1024)} KB</span>
              {slot.status === "done" && (
                <CheckCircle2 size={12} className="text-emerald-400" aria-hidden />
              )}
              {slot.status === "uploading" && (
                <span className="text-ink-2">…</span>
              )}
              {slot.status === "error" && (
                <span className="flex items-center gap-1 text-red-400" title={slot.message}>
                  <AlertTriangle size={12} aria-hidden />
                </span>
              )}
            </div>
          ))}
          <div className="mt-1 flex gap-2">
            <button
              type="button"
              onClick={upload}
              disabled={busy}
              className="rounded-md bg-accent px-3 py-1.5 text-xs text-bg-0 disabled:opacity-50"
            >
              {busy ? "Uploading…" : `Upload ${slots.length} file${slots.length === 1 ? "" : "s"}`}
            </button>
            <button
              type="button"
              onClick={clear}
              disabled={busy}
              className="flex items-center gap-1 rounded-md border border-line/60 px-3 py-1.5 text-xs text-ink-2 hover:border-accent hover:text-ink"
            >
              <X size={11} aria-hidden /> Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
