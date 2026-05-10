import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { WorkspaceRole } from "./RoleChip";

/**
 * <InviteMemberDialog /> — modal to invite a member by email + role
 * (Wave 110).
 *
 * Lightweight: focus-trapped via autofocus + escape key, no portal —
 * sits at the page level. POSTs to ``/api/workspaces/{id}/invites``
 * via the parent's ``onInvite`` callback.
 */
const ROLE_OPTIONS: WorkspaceRole[] = [
  "admin",
  "designer",
  "analyst",
  "viewer",
];

export function InviteMemberDialog({
  open,
  onClose,
  onInvite,
}: {
  open: boolean;
  onClose: () => void;
  onInvite: (email: string, role: string) => Promise<void> | void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("designer");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset state every time we open.
  useEffect(() => {
    if (open) {
      setEmail("");
      setRole("designer");
      setError(null);
      setSubmitting(false);
      // Defer focus until the modal is mounted.
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Escape closes the dialog.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onInvite(email.trim().toLowerCase(), role);
      onClose();
    } catch (err) {
      setError((err as Error).message || "Failed to send invite");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-bg-0/70 backdrop-blur-sm px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="invite-modal-title"
          onClick={onClose}
        >
          <motion.form
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.18 }}
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSubmit}
            className="w-full max-w-md rounded-2xl border border-line bg-bg-1 p-6 shadow-2xl"
          >
            <h2
              id="invite-modal-title"
              className="font-display text-[18px] font-medium text-ink"
            >
              Invite member
            </h2>
            <p className="mt-1 text-[12px] text-ink-3">
              They'll receive a one-time link tied to this workspace.
            </p>
            <label className="mt-5 block">
              <span className="font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                Email
              </span>
              <input
                ref={inputRef}
                type="email"
                value={email}
                required
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@example.com"
                className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-2/40 px-3 py-2 text-[13px] text-ink placeholder:text-ink-3 focus:border-[color:var(--brand-indigo)] focus:outline-none"
              />
            </label>
            <label className="mt-4 block">
              <span className="font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                Role
              </span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as WorkspaceRole)}
                className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-2/40 px-3 py-2 text-[13px] text-ink focus:border-[color:var(--brand-indigo)] focus:outline-none"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            {error && (
              <p
                role="alert"
                className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[12px] text-red-300"
              >
                {error}
              </p>
            )}
            <div className="mt-6 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="rounded-md border border-line/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-2 transition-colors hover:border-line"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-[color:var(--brand-indigo)] px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-bg-0 transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {submitting ? "Sending…" : "Send invite"}
              </button>
            </div>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default InviteMemberDialog;
