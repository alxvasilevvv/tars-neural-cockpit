/**
 * AttachmentChipStrip — extracted from ChatPane (Wave 72).
 *
 * Renders the row of attachment / upload chips above the message
 * stream in the cockpit chat surface. The actual data wiring lives
 * in ``@/lib/attachments`` (``useThreadAttachments`` →
 * ``ThreadAttachmentsHook``); this component is purely
 * presentational.
 *
 * Imported by ``ChatPane`` (the only consumer today). Kept in a
 * standalone file so the strip — and its supporting chip / mime
 * icon / image-thumb helpers — can be referenced or restyled
 * without diffing through the 1000+ line chat surface.
 */

import { useState } from "react";
import {
  File,
  FileCode,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
} from "lucide-react";

import type { ThreadAttachmentsHook } from "@/lib/attachments";
import type { ChatAttachment } from "@/lib/chat";

export function AttachmentChipStrip({
  attachments,
}: {
  attachments: ThreadAttachmentsHook;
}) {
  if (
    !attachments.attachments.length &&
    !attachments.uploads.length
  ) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line/40 px-4 py-2">
      <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
        attached
      </span>
      {attachments.attachments.map((att) => (
        <AttachmentChip
          key={att.id}
          attachment={att}
          onRemove={() => void attachments.remove(att.id)}
        />
      ))}
      {attachments.uploads.map((up) => (
        <UploadChip key={up.id} upload={up} />
      ))}

      {/* Local CSS for upload pulse — shared between in-flight states */}
      <style>{`
        @keyframes attUploadPulse {
          0%, 100% { opacity: 0.55; }
          50%      { opacity: 1; }
        }
        .att-upload-pulse { animation: attUploadPulse 1.4s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .att-upload-pulse { animation: none; opacity: 0.85; }
        }
      `}</style>
    </div>
  );
}

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"]);

/** True when filename looks like a raster/vector image. */
function isImage(filename?: string | null): boolean {
  const ext = (filename?.split(".").pop() ?? "").toLowerCase();
  return IMAGE_EXTS.has(ext);
}

/** Pick a Lucide icon based on filename extension. */
function MimeIcon({ filename, size = 11, color }: { filename?: string | null; size?: number; color?: string }) {
  const ext = (filename?.split(".").pop() ?? "").toLowerCase();
  const className = "shrink-0";
  const props = { size, strokeWidth: 1.6, className, style: color ? { color } : undefined };
  if (["pdf"].includes(ext))                                  return <FileText {...props} />;
  if (["json"].includes(ext))                                 return <FileJson {...props} />;
  if (["csv", "tsv", "xls", "xlsx"].includes(ext))            return <FileSpreadsheet {...props} />;
  if (IMAGE_EXTS.has(ext))                                    return <FileImage {...props} />;
  if (["js", "ts", "tsx", "jsx", "py", "rs", "go", "java", "rb", "sh"].includes(ext)) return <FileCode {...props} />;
  if (["md", "txt", "log"].includes(ext))                     return <FileText {...props} />;
  return <File {...props} />;
}

/**
 * Inline image thumbnail for attachment chips. Pulls the raw bytes
 * from the existing `/api/attachments/<id>/download` endpoint (L2
 * surface). Falls back to the mime icon on load error so the chip
 * never breaks.
 */
function ImageThumb({
  attachmentId,
  filename,
  size = 16,
  color,
}: {
  attachmentId?: string;
  filename?: string | null;
  size?: number;
  color?: string;
}) {
  const [errored, setErrored] = useState(false);
  if (!attachmentId || errored) {
    return <MimeIcon filename={filename} size={size - 4} color={color} />;
  }
  return (
    <img
      src={`/api/attachments/${encodeURIComponent(attachmentId)}/download`}
      alt={filename ?? "image"}
      onError={() => setErrored(true)}
      className="shrink-0 rounded-sm border border-line object-cover"
      style={{ width: size, height: size }}
    />
  );
}

function UploadChip({ upload }: { upload: { id: string; filename: string; state: "queued" | "uploading" | "ingesting" | "ready" | "error"; error?: string | null } }) {
  const state = upload.state;
  const tone =
    state === "error"
      ? { border: "var(--color-alert)", fg: "var(--color-alert)" }
      : state === "ready"
        ? { border: "var(--color-success)", fg: "var(--color-success)" }
        : state === "ingesting"
          ? { border: "rgba(139,92,246,0.45)", fg: "var(--color-meeet-violet, #8B5CF6)" }
          : state === "uploading"
            ? { border: "rgba(99,102,241,0.45)", fg: "var(--color-accent)" }
            : { border: "var(--color-line-strong)", fg: "var(--color-ink-3)" };
  const inFlight = state === "queued" || state === "uploading" || state === "ingesting";
  return (
    <span
      title={upload.error ?? `${upload.filename} · ${state}`}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] ${
        inFlight ? "att-upload-pulse" : ""
      }`}
      style={{ borderColor: tone.border, color: tone.fg }}
    >
      <MimeIcon filename={upload.filename} color={tone.fg} />
      <span className="max-w-[140px] truncate">{upload.filename}</span>
      <span className="text-ink-3">·</span>
      <span>{state}</span>
    </span>
  );
}

function AttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: ChatAttachment;
  onRemove: () => void;
}) {
  // P8 signal — when the vision pipeline OCR'd an image successfully
  // it backfills `char_count` from the OCR text. Imaging mime + char_count
  // > 0 = "this image contributed real text to the index".
  const ocrFromImage =
    isImage(attachment.filename) && attachment.char_count > 0;

  // Pipeline status surfaces here as a coloured ring on the chip.
  // `ready` → no ring (success is the default). `error` → red ring +
  // tooltip carries the error string. Anything else (extract_pending,
  // chunk_pending) → pulsing accent ring.
  const status = attachment.status;
  const statusTone =
    status === "error"
      ? { ring: "var(--color-alert)", label: "error", pulse: false }
      : status !== "ready"
        ? { ring: "var(--color-accent)", label: status, pulse: true }
        : null;

  const titleParts = [
    attachment.filename ?? attachment.id,
    `${(attachment.bytes_total / 1024).toFixed(1)} KB`,
    `${attachment.char_count.toLocaleString()} chars indexed`,
  ];
  if (ocrFromImage) titleParts.push("OCR ok");
  if (status !== "ready") titleParts.push(status);
  if (attachment.error) titleParts.push(attachment.error);

  return (
    <span
      className="group inline-flex items-center gap-1.5 rounded-full border bg-[rgba(0,0,0,0.4)] px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-2 transition-colors duration-150 hover:border-line-strong hover:bg-[rgba(99,102,241,0.06)] hover:text-ink"
      style={{
        borderColor: statusTone ? statusTone.ring : "var(--color-line)",
        animation: statusTone?.pulse ? "attUploadPulse 1.4s ease-in-out infinite" : undefined,
      }}
      title={titleParts.join(" · ")}
    >
      {isImage(attachment.filename) ? (
        <ImageThumb attachmentId={attachment.id} filename={attachment.filename} size={16} />
      ) : (
        <MimeIcon filename={attachment.filename} color="var(--color-accent)" />
      )}
      <span className="max-w-[160px] truncate">{attachment.filename ?? "untitled"}</span>
      <span className="text-ink-3">
        · {(attachment.bytes_total / 1024).toFixed(1)} KB
      </span>
      {ocrFromImage && (
        <span
          aria-label="OCR text extracted from image"
          className="rounded-sm px-1 py-px text-[8.5px] tabular-nums"
          style={{
            background: "color-mix(in srgb, var(--color-meeet-violet, #8B5CF6) 18%, transparent)",
            color: "var(--color-meeet-violet, #8B5CF6)",
            letterSpacing: "1.2px",
          }}
        >
          OCR
        </span>
      )}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`remove ${attachment.filename}`}
        className="ml-0.5 grid h-4 w-4 place-items-center rounded-full text-ink-3 transition-colors duration-150 hover:bg-alert/15 hover:text-alert"
      >
        ×
      </button>
    </span>
  );
}

