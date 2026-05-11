/**
 * CustomRoleModal — Wave 124 split out of /pages/Onboarding.tsx (was
 * 845 LOC). Modal that lets the user describe a custom role for TARS
 * to specialise on. Sent to /api/roles which synthesises a system
 * prompt overlay (P7).
 *
 * Pure refactor — no behavior change.
 */

import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useFocusTrap } from "@/lib/useFocusTrap";

interface CustomRoleModalProps {
  onClose: () => void;
  onSave: (payload: { name: string; description: string }) => void;
  initial?: { name: string; description: string };
}

function CustomRoleModal({ onClose, onSave, initial }: CustomRoleModalProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const valid = name.trim().length >= 2 && description.trim().length >= 24;
  const t = useT();

  // WCAG 2.1 AA — Section 4.1.2 Name Role Value + 2.1.2 No Keyboard Trap.
  // The modal must (a) announce itself as a modal so screen readers stop
  // exposing the page behind it, and (b) trap Tab so keyboard users can't
  // escape into the inert backdrop. Esc + backdrop click already close it.
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  // Esc closes the modal — pairs with the focus trap so keyboard users
  // always have an escape hatch (WCAG 2.1.2).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="custom role"
      tabIndex={-1}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(2,4,12,0.7)] px-4 backdrop-blur-md"
      onClick={onClose}
    >
      <motion.div
        onClick={e => e.stopPropagation()}
        initial={{ opacity: 0, y: 8, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.99 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-[560px] overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 p-6 md:p-8"
      >
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, var(--brand-indigo) 30%, var(--brand-violet) 50%, var(--brand-cyan) 70%, transparent 100%)",
          }}
        />

        <header className="mb-5 flex items-start justify-between gap-3">
          <div>
            <div className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
              {t("onboarding.modal.eyebrow")}
            </div>
            <h2 className="font-display text-[20px] leading-[1.25] text-ink">
              {t("onboarding.modal.title")}
            </h2>
            <p className="mt-2 max-w-[52ch] text-[12.5px] leading-[1.55] text-ink-2">
              {t("onboarding.modal.body")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="close"
            className="grid h-7 w-7 place-items-center rounded-full border border-line text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            <X size={13} strokeWidth={2} />
          </button>
        </header>

        <div className="mb-4">
          <label className="mb-1.5 block font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {t("onboarding.modal.name.label")}
          </label>
          <input
            value={name}
            onChange={e => setName(e.target.value.slice(0, 60))}
            placeholder={t("onboarding.modal.name.placeholder")}
            className="w-full rounded-md border border-line bg-bg-2/50 px-3 py-2.5 font-display text-[14px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
            maxLength={60}
          />
        </div>

        <div className="mb-5">
          <label className="mb-1.5 block font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            {t("onboarding.modal.desc.label")}
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value.slice(0, 500))}
            placeholder="I run a 12-person sales team in B2B SaaS, focus on enterprise deals. Daily I review pipeline in Salesforce, write outbound emails to net-new accounts, and prep weekly forecast for the CEO."
            rows={5}
            className="w-full resize-none rounded-md border border-line bg-bg-2/50 px-3 py-2.5 text-[13.5px] leading-[1.55] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
            maxLength={500}
          />
          <div className="mt-1 flex justify-between font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
            <span>{t("onboarding.modal.desc.help")}</span>
            <span className="tabular-nums">{description.length} / 500</span>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3 transition-colors hover:text-ink"
          >
            {t("onboarding.modal.cancel")}
          </button>
          <button
            type="button"
            disabled={!valid}
            onClick={() => onSave({ name: name.trim(), description: description.trim() })}
            className="inline-flex items-center gap-2 rounded-md px-5 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: "linear-gradient(135deg, var(--brand-indigo) 0%, var(--brand-violet) 100%)",
              boxShadow:
                "0 0 0 1px rgba(99,102,241,0.45), 0 10px 28px -10px rgba(99,102,241,0.55)",
            }}
          >
            {t("onboarding.modal.save")}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default CustomRoleModal;
