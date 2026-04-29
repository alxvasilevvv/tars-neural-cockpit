/**
 * ChatPane — primary conversation surface for the cockpit (Phase L1).
 *
 * Three column layout (desktop) collapses to a single column on mobile:
 *
 *   ┌──────────────┬─────────────────────────────┐
 *   │ thread list  │   message stream + composer │
 *   └──────────────┴─────────────────────────────┘
 *
 * Functionality is the focus here — Claude's lane is the visual
 * polish (motion, copy, hover states). The data wiring stays close
 * to the K-tier endpoints already in place: every assistant turn
 * lights up the cost ledger, the policy gate, and the meeet event
 * stream.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  File,
  FileCode,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
} from "lucide-react";

import {
  useDropZone,
  useThreadAttachments,
  type ThreadAttachmentsHook,
} from "@/lib/attachments";
import {
  archiveThread,
  createThread,
  listThreads,
  patchThread,
  useChatThread,
  type ChatAttachment,
  type ChatMessage,
  type ChatSourceCitation,
  type ChatThread,
  type ChatToolCall,
  type RetrievedChunkRef,
} from "@/lib/chat";
import {
  useMicTranscription,
  usePersonas,
  useVoiceHealth,
  useVoicePlayback,
  type VoiceProviderId,
} from "@/lib/voice";
import { ThreadTimeline } from "@/components/ThreadTimeline";
import { t as tt } from "@/lib/i18n";

interface ChatPaneProps {
  /**
   * Optional pack to bias new threads towards (e.g. "ops_room").
   * Has no effect on threads already created with a different pack.
   */
  defaultPackSlug?: string;
}

const POLL_THREADS_MS = 12000;

export function ChatPane({ defaultPackSlug }: ChatPaneProps = {}) {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hook = useChatThread(activeId);
  const voice = useVoicePlayback();
  const { personas } = usePersonas();
  const { data: voiceHealth } = useVoiceHealth();

  const loadThreads = useCallback(async () => {
    setRefreshing(true);
    try {
      const list = await listThreads({ archived: false, limit: 50 });
      setThreads(list);
      if (list.length && !list.some((t) => t.id === activeId)) {
        setActiveId(list[0].id);
      }
    } catch (exc) {
      setError(String((exc as Error)?.message ?? exc));
    } finally {
      setRefreshing(false);
    }
  }, [activeId]);

  useEffect(() => {
    void loadThreads();
    const handle = window.setInterval(() => void loadThreads(), POLL_THREADS_MS);
    return () => window.clearInterval(handle);
  }, [loadThreads]);

  // Wired by the ⌘K command palette: when an operator picks a chunk
  // or message hit, jump the active thread to the one that owns it.
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ threadId: string }>).detail;
      if (!detail?.threadId) return;
      setActiveId(detail.threadId);
      void loadThreads();
    };
    window.addEventListener("tars:open-thread", handler);
    return () => window.removeEventListener("tars:open-thread", handler);
  }, [loadThreads]);

  const createNew = useCallback(async () => {
    try {
      const thr = await createThread({
        title: "New conversation",
        packSlug: defaultPackSlug,
      });
      setThreads((prev) => [thr, ...prev]);
      setActiveId(thr.id);
    } catch (exc) {
      setError(String((exc as Error)?.message ?? exc));
    }
  }, [defaultPackSlug]);

  const renameActive = useCallback(
    async (title: string) => {
      if (!activeId) return;
      try {
        const next = await patchThread(activeId, { title });
        setThreads((prev) =>
          prev.map((t) => (t.id === activeId ? next : t)),
        );
      } catch (exc) {
        setError(String((exc as Error)?.message ?? exc));
      }
    },
    [activeId],
  );

  const archiveActive = useCallback(async () => {
    if (!activeId) return;
    try {
      await archiveThread(activeId);
      setThreads((prev) => prev.filter((t) => t.id !== activeId));
      setActiveId(null);
    } catch (exc) {
      setError(String((exc as Error)?.message ?? exc));
    }
  }, [activeId]);

  return (
    <section className="mt-6 rounded-[14px] border border-line bg-bg-1">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line/60 px-5 py-3 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        <span>conversation // chat L1 · voice L4.1</span>
        <div className="flex items-center gap-3">
          <VoiceControls
            voice={voice}
            personas={personas ?? []}
            health={voiceHealth}
          />
          <span className="text-ink-3">
            {refreshing ? "syncing" : `${threads.length} threads`}
            {error ? ` · ${error}` : ""}
          </span>
        </div>
      </header>

      <div className="grid gap-0 md:grid-cols-[260px_1fr]">
        <ThreadList
          threads={threads}
          activeId={activeId}
          onPick={setActiveId}
          onCreate={createNew}
        />
        <div className="border-t border-line md:border-l md:border-t-0">
          {activeId ? (
            <>
              <ConversationView
                hook={hook}
                voice={voice}
                onRename={renameActive}
                onArchive={archiveActive}
              />
              <div className="px-4 pb-4 md:px-5 md:pb-5">
                <ThreadTimeline threadId={activeId} />
              </div>
            </>
          ) : (
            <EmptyState onCreate={createNew} />
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------
// Voice picker + status
// ---------------------------------------------------------------------

const PROVIDER_LABELS: Record<VoiceProviderId, string> = {
  auto: "auto",
  elevenlabs: "elevenlabs",
  openai: "openai",
  mac_say: "mac · say",
};

function VoiceControls({
  voice,
  personas,
  health,
}: {
  voice: ReturnType<typeof useVoicePlayback>;
  personas: { id: string; name: string; short: string }[];
  health: ReturnType<typeof useVoiceHealth>["data"];
}) {
  const available = health?.engines ?? {
    elevenlabs: false,
    openai: false,
    mac_say: false,
  };
  const anyOnline = !!health?.any_available;

  return (
    <div className="flex flex-wrap items-center gap-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
      <label className="flex items-center gap-1">
        voice
        <select
          aria-label="voice persona"
          value={voice.personaId}
          onChange={(e) => voice.setPersonaId(e.target.value)}
          className="rounded border border-line bg-[rgba(0,0,0,0.4)] px-2 py-1 text-ink"
        >
          {(personas.length
            ? personas
            : [{ id: "jarvis", name: "J.A.R.V.I.S.", short: "" }]
          ).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-1">
        provider
        <select
          aria-label="voice provider"
          value={voice.provider}
          onChange={(e) => voice.setProvider(e.target.value as VoiceProviderId)}
          className="rounded border border-line bg-[rgba(0,0,0,0.4)] px-2 py-1 text-ink"
        >
          <option value="auto">auto</option>
          <option value="elevenlabs" disabled={!available.elevenlabs}>
            {PROVIDER_LABELS.elevenlabs}
            {available.elevenlabs ? "" : " · offline"}
          </option>
          <option value="openai" disabled={!available.openai}>
            {PROVIDER_LABELS.openai}
            {available.openai ? "" : " · offline"}
          </option>
          <option value="mac_say" disabled={!available.mac_say}>
            {PROVIDER_LABELS.mac_say}
            {available.mac_say ? "" : " · offline"}
          </option>
        </select>
      </label>
      <label className="flex items-center gap-1 cursor-pointer">
        <input
          type="checkbox"
          checked={voice.autoplay}
          onChange={(e) => voice.setAutoplay(e.target.checked)}
          className="accent-accent"
        />
        autoplay
      </label>
      <button
        type="button"
        onClick={() => voice.setMuted(!voice.muted)}
        className={`rounded border px-2 py-1 ${
          voice.muted
            ? "border-alert text-alert"
            : "border-line text-ink-2 hover:border-accent hover:text-accent"
        }`}
      >
        {voice.muted ? "muted" : "live"}
      </button>
      {!anyOnline ? (
        <span className="text-alert">no engine</span>
      ) : voice.lastProvider ? (
        <span className="text-accent">via {voice.lastProvider}</span>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------

function ThreadList({
  threads,
  activeId,
  onPick,
  onCreate,
}: {
  threads: ChatThread[];
  activeId: string | null;
  onPick: (id: string) => void;
  onCreate: () => void;
}) {
  return (
    <aside className="flex flex-col gap-2 p-3">
      <button
        type="button"
        onClick={onCreate}
        className="w-full rounded border border-line bg-[rgba(0,0,0,0.4)] px-3 py-2 text-left font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink hover:border-accent hover:text-accent transition-colors"
      >
        + new thread
      </button>
      {threads.length === 0 ? (
        <p className="px-1 font-mono-tech text-[10.5px] text-ink-3">
          {tt("chat.threads.empty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {threads.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => onPick(t.id)}
                className={`w-full rounded border px-2 py-2 text-left transition-colors ${
                  t.id === activeId
                    ? "border-accent text-ink"
                    : "border-line/60 text-ink-2 hover:border-line hover:text-ink"
                }`}
              >
                <div className="font-display text-[13px] tracking-[-0.01em] text-ink">
                  {t.title || "Untitled"}
                </div>
                <div className="font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
                  {t.pack_slug || "no pack"} · {fmtRelative(t.updated_at)}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------

function ConversationView({
  hook,
  voice,
  onRename,
  onArchive,
}: {
  hook: ReturnType<typeof useChatThread>;
  voice: ReturnType<typeof useVoicePlayback>;
  onRename: (title: string) => void;
  onArchive: () => void;
}) {
  const { thread, messages, turn, busy, error, send, cancel } = hook;
  const [draft, setDraft] = useState("");
  const mic = useMicTranscription();
  const attachments = useThreadAttachments(thread?.id ?? null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const visible = useMemo(() => {
    const arr: ChatMessage[] = [...messages];
    if (turn.pendingOperator) arr.push(turn.pendingOperator);
    if (turn.draftAssistant) arr.push(turn.draftAssistant);
    return arr;
  }, [messages, turn]);

  const submit = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      const text = draft.trim();
      if (!text) return;
      setDraft("");
      await send(text);
    },
    [draft, send],
  );

  const handleFilesPicked = useCallback(
    (files: File[]) => {
      void attachments.upload(files);
    },
    [attachments],
  );

  const drop = useDropZone({
    onFiles: handleFilesPicked,
    disabled: !thread?.id,
  });

  // Mic → composer text mirror.
  useEffect(() => {
    if (mic.transcript) setDraft(mic.transcript);
  }, [mic.transcript]);

  // Autoplay the most recent finalised assistant reply once per id.
  const lastSpokenIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!voice.autoplay || voice.muted) return;
    const lastTars = [...messages].reverse().find((m) => m.role === "tars");
    if (!lastTars || lastTars.id === lastSpokenIdRef.current) return;
    if (!lastTars.content || !lastTars.content.trim()) return;
    lastSpokenIdRef.current = lastTars.id;
    void voice.play(lastTars.content);
  }, [messages, voice]);

  return (
    <div
      className={`relative flex h-full min-h-[420px] flex-col transition-colors ${
        drop.isDraggingOver ? "bg-accent/5" : ""
      }`}
      onDragOver={drop.onDragOver}
      onDragEnter={drop.onDragEnter}
      onDragLeave={drop.onDragLeave}
      onDrop={drop.onDrop}
    >
      <div className="flex items-center justify-between border-b border-line/40 px-4 py-2">
        <input
          aria-label="thread title"
          className="bg-transparent font-display text-[15px] tracking-[-0.01em] text-ink outline-none"
          value={thread?.title ?? ""}
          placeholder="thread title"
          onChange={(e) => onRename(e.target.value)}
        />
        <button
          type="button"
          onClick={onArchive}
          className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-alert"
        >
          archive
        </button>
      </div>

      <AttachmentChipStrip attachments={attachments} />

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {visible.length === 0 ? (
          <p className="font-mono-tech text-[10.5px] text-ink-3">
            ask anything — tools are policy-gated, costs land in the
            ledger. Drop a PDF, csv, or markdown to ground the
            conversation in your files.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {visible.map((m) => (
              <li key={m.id}>
                <MessageBubble
                  message={m}
                  liveRetrieval={
                    turn.draftAssistant?.id === m.id ? turn.retrieved : []
                  }
                  onSpeak={
                    m.role === "tars" && m.content?.trim()
                      ? () => voice.play(m.content)
                      : undefined
                  }
                  speaking={voice.speaking}
                />
              </li>
            ))}
            {turn.toolCalls.map((tc) => (
              <li key={tc.id}>
                <ToolCallCard call={tc} />
              </li>
            ))}
          </ul>
        )}
        {turn.usage ? (
          <div className="mt-3 rounded border border-line/60 bg-[rgba(0,0,0,0.4)] p-2 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
            usage · {turn.usage.model ?? "?"} · in {turn.usage.tokens_in} ·
            out {turn.usage.tokens_out}
            {turn.usage.cost_usd != null
              ? ` · $${turn.usage.cost_usd.toFixed(6)}`
              : ""}
            {turn.usage.route ? ` · ${turn.usage.route}` : ""}
          </div>
        ) : null}
        {error ? (
          <p className="mt-2 font-mono-tech text-[10.5px] text-alert">
            {error}
          </p>
        ) : null}
      </div>

      <form onSubmit={submit} className="border-t border-line/60 p-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files && e.target.files.length) {
              handleFilesPicked(Array.from(e.target.files));
              e.target.value = "";
            }
          }}
          aria-label="upload attachment"
        />
        <div className="flex items-center gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void submit();
              }
            }}
            placeholder={tt("chat.composer.placeholder")}
            rows={2}
            className="flex-1 resize-none rounded border border-line bg-[rgba(0,0,0,0.4)] p-2 font-display text-[13px] text-ink outline-none focus:border-accent"
          />
          <div className="flex flex-col gap-2">
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              className="rounded border border-accent bg-accent/10 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-accent disabled:opacity-40"
            >
              send
            </button>
            {busy ? (
              <button
                type="button"
                onClick={cancel}
                className="rounded border border-line px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 hover:text-alert"
              >
                cancel
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!thread?.id || attachments.busy}
              title="attach file"
              className="rounded border border-line px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 hover:border-accent hover:text-accent disabled:opacity-40"
            >
              {attachments.busy ? "…upload" : "+ file"}
            </button>
            {mic.supported ? (
              <button
                type="button"
                onClick={mic.listening ? mic.stop : mic.start}
                title={
                  mic.listening
                    ? "stop dictation"
                    : "dictate via Web Speech (browser-native)"
                }
                className={`rounded border px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] ${
                  mic.listening
                    ? "border-alert text-alert"
                    : "border-line text-ink-2 hover:border-accent hover:text-accent"
                }`}
              >
                {mic.listening ? "● rec" : "🎙 mic"}
              </button>
            ) : null}
          </div>
        </div>
        {mic.error ? (
          <p className="mt-2 font-mono-tech text-[10.5px] text-alert">
            mic · {mic.error}
          </p>
        ) : null}
        {attachments.error ? (
          <p className="mt-2 font-mono-tech text-[10.5px] text-alert">
            upload · {attachments.error}
          </p>
        ) : null}
      </form>

      {drop.isDraggingOver ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center border-2 border-dashed border-accent bg-accent/5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-accent">
          drop to attach · pdf · md · txt · json · csv · up to 25 MB
        </div>
      ) : null}
    </div>
  );
}

function AttachmentChipStrip({
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

function MessageBubble({
  message,
  onSpeak,
  speaking,
  liveRetrieval = [],
}: {
  message: ChatMessage;
  onSpeak?: () => void;
  speaking?: boolean;
  liveRetrieval?: RetrievedChunkRef[];
}) {
  const isOperator = message.role === "operator";
  const isTool = message.role === "tool";
  const persistedSources = useMemo<ChatSourceCitation[]>(() => {
    const raw = (message.extra as { sources?: unknown })?.sources;
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (s): s is ChatSourceCitation =>
        !!s && typeof (s as ChatSourceCitation).citation_id === "string",
    );
  }, [message.extra]);
  const showLive = liveRetrieval.length > 0 && persistedSources.length === 0;

  return (
    <article
      className={`rounded border ${
        isOperator
          ? "border-accent/40 bg-accent/5"
          : isTool
            ? "border-line/60 bg-[rgba(0,0,0,0.45)]"
            : "border-line bg-bg-2"
      } p-3`}
    >
      <header className="mb-1 flex items-baseline justify-between gap-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
        <span>
          {isOperator
            ? "operator"
            : isTool
              ? `tool · ${message.extra?.action_id || ""}`
              : "tars"}
        </span>
        <span className="flex items-center gap-2">
          {message.voice_model ? `${message.voice_model} · ` : ""}
          {message.cost_usd != null ? `$${message.cost_usd.toFixed(6)}` : ""}
          {onSpeak ? (
            <button
              type="button"
              onClick={onSpeak}
              title="speak with selected voice"
              className={`ml-1 rounded border px-1.5 py-0.5 ${
                speaking
                  ? "border-accent text-accent"
                  : "border-line text-ink-2 hover:border-accent hover:text-accent"
              }`}
            >
              ▶ speak
            </button>
          ) : null}
        </span>
      </header>
      <div className="font-display text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap">
        {message.content}
      </div>
      {persistedSources.length > 0 ? (
        <SourcesFooter sources={persistedSources} />
      ) : showLive ? (
        <SourcesFooter
          sources={liveRetrieval.map((r) => ({
            citation_id: r.citation_id,
            chunk_id: r.chunk.id,
            attachment_id: r.chunk.attachment_id,
            filename: r.chunk.filename,
            heading: r.chunk.heading,
            page: r.chunk.page,
            score: r.score,
          }))}
          previews={Object.fromEntries(
            liveRetrieval.map((r) => [r.citation_id, r.chunk.text]),
          )}
        />
      ) : null}
    </article>
  );
}

function SourcesFooter({
  sources,
  previews,
}: {
  sources: ChatSourceCitation[];
  previews?: Record<string, string>;
}) {
  if (!sources.length) return null;
  return (
    <details className="mt-2 rounded border border-line/40 bg-[rgba(0,0,0,0.3)] p-2">
      <summary className="cursor-pointer font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
        sources · {sources.length}
      </summary>
      <ul className="mt-2 flex flex-col gap-1 font-mono-tech text-[10px] text-ink-2">
        {sources.map((s) => (
          <li key={s.chunk_id}>
            <span className="text-accent">[{s.citation_id}]</span>{" "}
            <span className="text-ink">{s.filename ?? s.attachment_id}</span>
            {s.heading ? <span className="text-ink-3"> · {s.heading}</span> : null}
            {s.page ? <span className="text-ink-3"> · p{s.page}</span> : null}
            {previews?.[s.citation_id] ? (
              <p className="mt-0.5 max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-[rgba(0,0,0,0.4)] p-1 text-ink-3">
                {previews[s.citation_id].slice(0, 320)}
                {previews[s.citation_id].length > 320 ? "…" : ""}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ToolCallCard({ call }: { call: ChatToolCall }) {
  const tone =
    call.status === "completed"
      ? "border-accent/50 text-accent"
      : call.status === "failed"
        ? "border-alert text-alert"
        : call.status === "queued"
          ? "border-line text-ink-2"
          : "border-line/60 text-ink-2";
  return (
    <article className={`rounded border ${tone} bg-[rgba(0,0,0,0.4)] p-3`}>
      <header className="mb-1 flex items-baseline justify-between font-mono-tech text-[9.5px] uppercase tracking-[1.8px]">
        <span>
          tool · {call.slug}.{call.action_id}
        </span>
        <span className="text-ink-3">{call.status}</span>
      </header>
      <pre className="overflow-x-auto rounded bg-[rgba(0,0,0,0.4)] p-2 font-mono-tech text-[10.5px] text-ink-2">
        {JSON.stringify(call.args, null, 2)}
      </pre>
      {call.result ? (
        <details className="mt-2">
          <summary className="cursor-pointer font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
            result
          </summary>
          <pre className="mt-1 overflow-x-auto rounded bg-[rgba(0,0,0,0.4)] p-2 font-mono-tech text-[10.5px] text-ink-2">
            {JSON.stringify(call.result, null, 2)}
          </pre>
        </details>
      ) : null}
      {call.error ? (
        <p className="mt-2 font-mono-tech text-[10.5px] text-alert">
          {call.error}
        </p>
      ) : null}
      {call.policy_token ? (
        <p className="mt-2 font-mono-tech text-[10.5px] text-ink-3">
          awaiting confirmation · token {call.policy_token.slice(0, 12)}…
        </p>
      ) : null}
    </article>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 p-6 text-center">
      <h3 className="font-display text-[18px] tracking-[-0.01em] text-ink">
        Pick a thread or start a new one
      </h3>
      <p className="max-w-sm font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3">
        every conversation lights up the policy gate, the cost ledger,
        and the meeet event stream automatically.
      </p>
      <button
        type="button"
        onClick={onCreate}
        className="rounded border border-accent bg-accent/10 px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-accent"
      >
        new thread
      </button>
    </div>
  );
}

function fmtRelative(ts: number): string {
  if (!ts) return "—";
  const diffSec = Date.now() / 1000 - ts;
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}
