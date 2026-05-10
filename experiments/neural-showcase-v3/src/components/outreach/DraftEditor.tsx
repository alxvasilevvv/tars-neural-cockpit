// SYNC: claude-w98-outreach
/**
 * <DraftEditor /> -- Wave 98.
 *
 * Modal editor for an outreach draft. Subject + body are inline-
 * editable; an "AI Clone: regenerate in your style" button hits
 * POST /api/outreach/drafts to produce a fresh body using the
 * operator's current style profile. The send button calls the
 * caller-supplied `onSend` (which fires POST /drafts/{id}/send and
 * runs through the HIL gate).
 *
 * Headless-ish: state is owned by the parent so the page can roll
 * the edits back if the user cancels.
 */

import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { Send, Sparkles, X } from "lucide-react";

export type OutreachDraft = {
  id: string;
  template_id: string;
  recipient: { email?: string; name?: string; company?: string };
  context?: Record<string, unknown>;
  subject: string;
  body: string;
  status: "draft" | "approved" | "sent" | "failed";
  created_at: number;
  sent_at?: number | null;
  gmail_message_id?: string | null;
  error?: string | null;
};

export type DraftEditorProps = {
  draft: OutreachDraft;
  onClose: () => void;
  onSave: (patch: { subject?: string; body?: string; status?: string }) => Promise<void> | void;
  onSend: () => Promise<void> | void;
  onRegenerate: () => Promise<void> | void;
  busy?: boolean;
};

export function DraftEditor({ draft, onClose, onSave, onSend, onRegenerate, busy }: DraftEditorProps) {
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [dirty, setDirty] = useState(false);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSubject(draft.subject);
    setBody(draft.body);
    setDirty(false);
  }, [draft.id, draft.subject, draft.body]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function handleBackdrop(e: MouseEvent<HTMLDivElement>) {
    if (e.target === overlayRef.current) onClose();
  }

  async function handleSave() {
    await onSave({ subject, body });
    setDirty(false);
  }

  async function handleApprove() {
    await onSave({ subject, body, status: "approved" });
    setDirty(false);
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8"
      role="dialog"
      aria-modal="true"
      aria-label="Edit outreach draft"
    >
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d12] shadow-[0_24px_72px_rgba(0,0,0,0.55)]">
        <header className="flex items-center justify-between border-b border-white/5 px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-white/50">
              {draft.status} - {draft.recipient.name || draft.recipient.email}
            </p>
            <h2 className="mt-1 text-lg font-medium text-white">
              {draft.recipient.email}
              {draft.recipient.company ? <span className="text-white/40"> - {draft.recipient.company}</span> : null}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-white/60 transition hover:bg-white/5 hover:text-white"
            aria-label="Close editor"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-4 px-6 py-5">
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-white/50">Subject</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => { setSubject(e.target.value); setDirty(true); }}
              className="mt-2 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400"
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-white/50">Body</span>
            <textarea
              value={body}
              onChange={(e) => { setBody(e.target.value); setDirty(true); }}
              rows={14}
              className="mt-2 w-full resize-y rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-[13px] leading-relaxed text-white/90 outline-none focus:border-indigo-400"
              disabled={busy}
            />
          </label>
          {draft.error ? (
            <p className="rounded-lg border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs text-rose-200">
              Last send error: {draft.error}
            </p>
          ) : null}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/5 px-6 py-4">
          <button
            type="button"
            onClick={() => void onRegenerate()}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/80 transition hover:border-indigo-400 hover:text-white disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Regenerate in your style
          </button>
          <div className="flex items-center gap-2">
            {dirty ? (
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={busy}
                className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/80 transition hover:border-white/30 hover:text-white disabled:opacity-50"
              >
                Save edits
              </button>
            ) : null}
            {draft.status === "draft" ? (
              <button
                type="button"
                onClick={() => void handleApprove()}
                disabled={busy}
                className="rounded-lg border border-emerald-400/40 bg-emerald-400/10 px-3 py-2 text-xs font-medium text-emerald-200 transition hover:bg-emerald-400/20 disabled:opacity-50"
              >
                Approve
              </button>
            ) : null}
            {draft.status === "approved" ? (
              <button
                type="button"
                onClick={() => void onSend()}
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-lg border border-indigo-400/50 bg-indigo-500/30 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-500/45 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                Send via Gmail
              </button>
            ) : null}
          </div>
        </footer>
      </div>
    </div>
  );
}

export default DraftEditor;
