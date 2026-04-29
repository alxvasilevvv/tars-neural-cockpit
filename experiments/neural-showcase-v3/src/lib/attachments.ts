/**
 * Attachments client + hooks (Phase L2).
 *
 * Backend surface:
 *   POST   /api/chat/threads/{id}/attachments    (multipart upload)
 *   GET    /api/chat/threads/{id}/attachments    (list)
 *   GET    /api/chat/attachments/{id}            (describe + chunks)
 *   GET    /api/chat/attachments/{id}/download   (raw bytes)
 *   GET    /api/chat/attachments/{id}/extracted  (plain text)
 *   DELETE /api/chat/attachments/{id}
 *   POST   /api/chat/threads/{id}/retrieve       (top-K chunks for query)
 *
 * The `useThreadAttachments` hook glues a thread's attachment list +
 * upload progress + drag-and-drop helpers into a single object that the
 * <ChatPane /> can drop into its composer.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE } from "./api";
import type { ChatAttachment, RetrievedChunkRef } from "./chat";
import { getSessionId } from "./session";

export interface UploadProgress {
  id: string; // local id, not the backend's
  filename: string;
  bytes_total: number;
  state: "queued" | "uploading" | "ingesting" | "ready" | "error";
  error: string | null;
}

export interface UploadResult {
  attachment: ChatAttachment;
  duplicate: boolean;
  chunk_count: number;
  embedding_model: string | null;
}

export async function listAttachments(
  threadId: string,
): Promise<ChatAttachment[]> {
  const r = await fetch(
    `${API_BASE}/api/chat/threads/${threadId}/attachments`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { attachments: ChatAttachment[] };
  return body.attachments;
}

export async function uploadAttachment(
  threadId: string,
  file: File,
): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file, file.name);
  const r = await fetch(
    `${API_BASE}/api/chat/threads/${threadId}/attachments`,
    {
      method: "POST",
      body: form,
      headers: {
        "x-tars-session-id": getSessionId(),
      },
    },
  );
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      const body = await r.json();
      detail = body?.detail ? String(body.detail) : detail;
    } catch {
      // ignore parse failures
    }
    throw new Error(detail);
  }
  return (await r.json()) as UploadResult;
}

export async function deleteAttachment(attachmentId: string): Promise<void> {
  const r = await fetch(
    `${API_BASE}/api/chat/attachments/${attachmentId}`,
    { method: "DELETE" },
  );
  if (!r.ok && r.status !== 404) {
    throw new Error(`HTTP ${r.status}`);
  }
}

export async function retrieveChunks(
  threadId: string,
  query: string,
  topK = 6,
): Promise<RetrievedChunkRef[]> {
  const r = await fetch(
    `${API_BASE}/api/chat/threads/${threadId}/retrieve`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { chunks: RetrievedChunkRef[] };
  return body.chunks;
}

export function downloadUrl(attachmentId: string): string {
  return `${API_BASE}/api/chat/attachments/${attachmentId}/download`;
}

// --------------------------------------------------------------------
// React hook: useThreadAttachments
// --------------------------------------------------------------------

export interface ThreadAttachmentsHook {
  attachments: ChatAttachment[];
  uploads: UploadProgress[];
  busy: boolean;
  error: string | null;
  upload: (files: File[] | FileList) => Promise<void>;
  remove: (attachmentId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const SUPPORTED_HINT =
  "Supported: PDF, Markdown, plain text, JSON, CSV. Up to 25 MB.";

export function useThreadAttachments(
  threadId: string | null,
): ThreadAttachmentsHook {
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!threadId) return;
    try {
      const list = await listAttachments(threadId);
      if (cancelledRef.current) return;
      setAttachments(list);
    } catch (exc) {
      if (cancelledRef.current) return;
      setError(String((exc as Error)?.message ?? exc));
    }
  }, [threadId]);

  useEffect(() => {
    cancelledRef.current = false;
    setAttachments([]);
    setUploads([]);
    setError(null);
    if (!threadId) return undefined;
    void refresh();
    return () => {
      cancelledRef.current = true;
    };
  }, [threadId, refresh]);

  const upload = useCallback(
    async (files: File[] | FileList) => {
      if (!threadId) {
        setError(`No active thread. ${SUPPORTED_HINT}`);
        return;
      }
      const list = Array.from(files);
      if (!list.length) return;
      setBusy(true);
      setError(null);

      const queued: UploadProgress[] = list.map((f) => ({
        id: `up_${Date.now()}_${f.name}_${f.size}`,
        filename: f.name,
        bytes_total: f.size,
        state: "queued",
        error: null,
      }));
      setUploads((prev) => [...prev, ...queued]);

      for (let i = 0; i < list.length; i++) {
        const file = list[i];
        const ticket = queued[i];
        setUploads((prev) =>
          prev.map((u) =>
            u.id === ticket.id ? { ...u, state: "uploading" } : u,
          ),
        );
        try {
          const res = await uploadAttachment(threadId, file);
          if (cancelledRef.current) return;
          setUploads((prev) =>
            prev.map((u) =>
              u.id === ticket.id ? { ...u, state: "ready" } : u,
            ),
          );
          setAttachments((prev) => {
            const without = prev.filter(
              (a) => a.id !== res.attachment.id,
            );
            return [...without, res.attachment];
          });
        } catch (exc) {
          if (cancelledRef.current) return;
          const msg = String((exc as Error)?.message ?? exc);
          setUploads((prev) =>
            prev.map((u) =>
              u.id === ticket.id
                ? { ...u, state: "error", error: msg }
                : u,
            ),
          );
          setError(msg);
        }
      }

      // Auto-clear successful uploads after a beat so the chip strip
      // doesn't grow unbounded.
      setTimeout(() => {
        if (cancelledRef.current) return;
        setUploads((prev) => prev.filter((u) => u.state !== "ready"));
      }, 1500);
      setBusy(false);
    },
    [threadId],
  );

  const remove = useCallback(
    async (attachmentId: string) => {
      try {
        await deleteAttachment(attachmentId);
        setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
      } catch (exc) {
        setError(String((exc as Error)?.message ?? exc));
      }
    },
    [],
  );

  return useMemo(
    () => ({ attachments, uploads, busy, error, upload, remove, refresh }),
    [attachments, uploads, busy, error, upload, remove, refresh],
  );
}

// --------------------------------------------------------------------
// Drag and drop helper
// --------------------------------------------------------------------

export interface DropZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export interface DropZoneHandlers {
  onDragOver: (e: React.DragEvent<HTMLElement>) => void;
  onDragEnter: (e: React.DragEvent<HTMLElement>) => void;
  onDragLeave: (e: React.DragEvent<HTMLElement>) => void;
  onDrop: (e: React.DragEvent<HTMLElement>) => void;
  isDraggingOver: boolean;
}

export function useDropZone({ onFiles, disabled }: DropZoneProps): DropZoneHandlers {
  const [isDraggingOver, setDragging] = useState(false);
  const dragDepthRef = useRef(0);

  const onDragOver = useCallback(
    (e: React.DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    },
    [disabled],
  );

  const onDragEnter = useCallback(
    (e: React.DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      dragDepthRef.current += 1;
      setDragging(true);
    },
    [disabled],
  );

  const onDragLeave = useCallback(
    (e: React.DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) setDragging(false);
    },
    [disabled],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      dragDepthRef.current = 0;
      setDragging(false);
      const files = e.dataTransfer?.files;
      if (files && files.length) {
        onFiles(Array.from(files));
      }
    },
    [disabled, onFiles],
  );

  return { onDragOver, onDragEnter, onDragLeave, onDrop, isDraggingOver };
}
