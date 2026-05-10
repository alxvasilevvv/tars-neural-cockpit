// SYNC: claude-w106-marketplace
/**
 * Wave 106 — confirmation dialog before POST /install.
 *
 * Mirrors the pattern used by Reports + Outreach send confirms:
 * the parent owns the listing being staged and the busy state.
 */

import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";
import type { Listing } from "./types";
import { useT } from "@/lib/i18n";

type Props = {
  listing: Listing | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function InstallConfirmDialog({ listing, busy, onConfirm, onCancel }: Props) {
  const t = useT();
  if (!listing) return null;

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label={`Install ${listing.name}`}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.18 }}
        className="w-full max-w-md rounded-md border border-line/60 bg-bg-1 p-5"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-4 w-4 text-accent" />
          <div className="flex-1">
            <h3 className="text-[14px] font-semibold text-ink">
              {t("marketplace.confirm.title", { name: listing.name })}
            </h3>
            <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
              {t("marketplace.confirm.body")}
            </p>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="rounded border border-line/60 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-accent/40 hover:text-accent disabled:opacity-40"
          >
            {t("marketplace.cta.cancel")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="rounded bg-accent/20 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-accent hover:bg-accent/30 disabled:opacity-40"
          >
            {busy ? "…" : t("marketplace.cta.confirm")}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
