// SYNC: claude-w106-marketplace
/**
 * Wave 106 — "My library" tab body.
 *
 * Lists locally-installed items with uninstall + per-listing
 * rating UI. Pure presentation; the parent page polls the
 * /api/marketplace/installed endpoint.
 */

import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import type { InstalledItem } from "./types";
import { RatingsUI } from "./RatingsUI";
import { useT } from "@/lib/i18n";

type Props = {
  items: InstalledItem[];
  onUninstall: (listingId: string) => void;
};

export function MyLibraryTab({ items, onUninstall }: Props) {
  const t = useT();
  if (items.length === 0) {
    return (
      <p className="rounded border border-dashed border-line/60 p-6 text-center font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        {t("marketplace.empty.library")}
      </p>
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((it) => {
        const snap = it.listing_snapshot ?? {};
        const name =
          (typeof snap.name === "string" && snap.name) || it.listing_id;
        const author =
          snap.author && typeof snap.author === "object"
            ? snap.author.handle ?? "anon"
            : "anon";
        return (
          <motion.div
            key={it.listing_id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
            className="flex flex-col gap-3 rounded-md border border-line/60 bg-bg-1/40 p-4"
          >
            <header className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-[14px] font-semibold text-ink">{name}</h3>
                <p className="text-[10px] text-ink-3">
                  {t("marketplace.author.by", { handle: author })}
                  {" · v"}
                  {it.version}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onUninstall(it.listing_id)}
                className="inline-flex items-center gap-1 rounded border border-line/60 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-rose-300/60 hover:text-rose-300"
              >
                <Trash2 className="h-3 w-3" />
                {t("marketplace.cta.uninstall")}
              </button>
            </header>
            <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
              {it.installed_path}
            </p>
            <RatingsUI listingId={it.listing_id} />
          </motion.div>
        );
      })}
    </div>
  );
}
