// SYNC: claude-w106-marketplace
/**
 * Wave 106 — single listing card in the browse grid.
 *
 * Click the body to open the preview modal; the install button
 * is a separate hit target so the parent doesn't need to debounce
 * a confirmation modal vs preview-on-hover.
 */

import { motion } from "framer-motion";
import { CheckCircle2, Eye, Star, Tag } from "lucide-react";
import type { Listing } from "./types";
import { useT } from "@/lib/i18n";

const KIND_LABEL_KEY: Record<Listing["kind"], string> = {
  playbook: "marketplace.kind.playbook",
  skill: "marketplace.kind.skill",
  template: "marketplace.kind.template",
  report_template: "marketplace.kind.report_template",
};

type Props = {
  listing: Listing;
  onPreview: (l: Listing) => void;
  onInstall: (l: Listing) => void;
};

export function ListingCard({ listing, onPreview, onInstall }: Props) {
  const t = useT();
  const isInstalled = listing.installed === true;
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="flex flex-col gap-3 rounded-md border border-line/60 bg-bg-1/40 p-4 text-left"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="rounded border border-line/60 px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
          {t(KIND_LABEL_KEY[listing.kind] as Parameters<typeof t>[0]) ?? listing.kind}
        </span>
        {isInstalled ? (
          <span className="inline-flex items-center gap-1 rounded bg-accent/10 px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-accent">
            <CheckCircle2 className="h-3 w-3" />
            {t("marketplace.installed.badge")}
          </span>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => onPreview(listing)}
        className="text-left"
        aria-label={`Preview ${listing.name}`}
      >
        <h3 className="text-[14px] font-semibold text-ink">{listing.name}</h3>
        <p className="mt-1 text-[10px] text-ink-3">
          {t("marketplace.author.by", { handle: listing.author.handle || "anon" })}
          {" · v"}
          {listing.version}
        </p>
        <p className="mt-2 line-clamp-3 text-[12px] leading-relaxed text-ink-2">
          {listing.description}
        </p>
      </button>

      <div className="flex flex-wrap items-center gap-1.5">
        {listing.tags.slice(0, 3).map((tg) => (
          <span
            key={tg}
            className="inline-flex items-center gap-1 rounded bg-bg-0/60 px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3"
          >
            <Tag className="h-2.5 w-2.5" />
            {tg}
          </span>
        ))}
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 pt-2">
        <span className="inline-flex items-center gap-1 text-[11px] text-ink-2">
          <Star className="h-3.5 w-3.5 text-accent" />
          {listing.ratings.avg.toFixed(1)}
          <span className="text-[10px] text-ink-3">
            ({listing.ratings.count})
          </span>
        </span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onPreview(listing)}
            className="inline-flex items-center gap-1 rounded border border-line/60 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-accent/40 hover:text-accent"
          >
            <Eye className="h-3 w-3" />
            {t("marketplace.cta.preview")}
          </button>
          <button
            type="button"
            disabled={isInstalled}
            onClick={() => onInstall(listing)}
            className="inline-flex items-center gap-1 rounded bg-accent/15 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-accent transition-opacity hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isInstalled
              ? t("marketplace.cta.installed")
              : t("marketplace.cta.install")}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
