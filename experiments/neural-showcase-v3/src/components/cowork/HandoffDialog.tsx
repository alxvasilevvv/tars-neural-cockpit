/**
 * <HandoffDialog /> — Wave 129
 *
 * Modal that lets a session owner generate a one-time handoff link.
 * Wraps `createHandoff` from `@/lib/cowork`; renders the resulting
 * token as a copyable URL `/cowork/handoff/<token>` plus the TTL
 * countdown.
 *
 * Closed by default; the page passes `open` + `onClose`. The mock
 * fallback path inside `createHandoff` makes this demo-able even
 * with no backend.
 */

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Mail, X } from "lucide-react";
import { createHandoff } from "@/lib/cowork";

interface HandoffDialogProps {
  open: boolean;
  sessionId: string;
  fromUserId: string;
  onClose: () => void;
}

export function HandoffDialog({
  open,
  sessionId,
  fromUserId,
  onClose,
}: HandoffDialogProps) {
  const [toEmail, setToEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state every time the dialog opens fresh.
  useEffect(() => {
    if (!open) return;
    setToEmail("");
    setToken(null);
    setExpiresAt(null);
    setCopied(false);
    setError(null);
  }, [open]);

  // Close on ESC.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    const result = await createHandoff(sessionId, {
      from_user_id: fromUserId,
      to_email: toEmail.trim() || undefined,
    });
    setBusy(false);
    if (!result) {
      setError("Could not generate handoff. Please try again.");
      return;
    }
    setToken(result.token);
    setExpiresAt(result.expires_at);
  }

  function handleCopy(text: string) {
    try {
      void navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Clipboard unavailable — select and copy manually.");
    }
  }

  const handoffUrl = token
    ? `${
        typeof window !== "undefined" ? window.location.origin : ""
      }/cowork/handoff/${token}`
    : "";

  const ttlMin = expiresAt
    ? Math.max(0, Math.floor((expiresAt - Date.now() / 1000) / 60))
    : 0;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-sm"
          onClick={onClose}
          data-testid="cowork-handoff-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="Handoff this session"
        >
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="w-[min(520px,92vw)] overflow-hidden rounded-[14px] border border-line bg-bg-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line px-6 py-4">
              <h3 className="font-display text-[16px] font-medium text-ink">
                Hand off this session
              </h3>
              <button
                type="button"
                onClick={onClose}
                className="grid h-7 w-7 place-items-center rounded-md text-ink-2 transition hover:bg-bg-2 hover:text-ink"
                aria-label="Close"
              >
                <X size={14} strokeWidth={1.8} />
              </button>
            </div>

            <div className="px-6 py-5">
              {!token ? (
                <>
                  <p className="mb-4 text-[13.5px] leading-[1.6] text-ink-2">
                    Generate a one-time link the recipient can use to take
                    ownership of this session. Links expire in 15 minutes.
                  </p>
                  <label className="mb-2 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
                    Recipient email (optional)
                  </label>
                  <div className="relative mb-4">
                    <Mail
                      size={14}
                      strokeWidth={1.6}
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
                    />
                    <input
                      type="email"
                      autoFocus
                      value={toEmail}
                      onChange={(e) => setToEmail(e.target.value)}
                      placeholder="someone@example.com"
                      className="w-full rounded-md border border-line bg-bg-2 px-9 py-2 text-[13.5px] text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none"
                      data-testid="cowork-handoff-email"
                    />
                  </div>
                  {error && (
                    <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12.5px] text-red-300">
                      {error}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={busy}
                    className="w-full rounded-md border border-line bg-accent px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-bg-0 transition hover:bg-accent/90 disabled:opacity-50"
                    data-testid="cowork-handoff-generate"
                  >
                    {busy ? "Generating…" : "Generate handoff link"}
                  </button>
                </>
              ) : (
                <>
                  <p className="mb-4 text-[13.5px] leading-[1.6] text-ink-2">
                    Send this link to the recipient. It can be used once and
                    expires in {ttlMin} min.
                  </p>
                  <label className="mb-2 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
                    One-time handoff link
                  </label>
                  <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-bg-2 px-3 py-2">
                    <code
                      className="flex-1 truncate text-[12.5px] text-ink"
                      data-testid="cowork-handoff-url"
                    >
                      {handoffUrl}
                    </code>
                    <button
                      type="button"
                      onClick={() => handleCopy(handoffUrl)}
                      className="grid h-7 w-7 place-items-center rounded-md text-ink-2 transition hover:bg-bg-1 hover:text-ink"
                      aria-label="Copy handoff link"
                    >
                      <Copy size={13} strokeWidth={1.6} />
                    </button>
                  </div>
                  {copied && (
                    <div className="mb-3 font-mono-tech text-[10px] uppercase tracking-[2px] text-success">
                      Copied to clipboard
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={onClose}
                    className="w-full rounded-md border border-line bg-bg-2 px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition hover:bg-bg-1"
                  >
                    Done
                  </button>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
