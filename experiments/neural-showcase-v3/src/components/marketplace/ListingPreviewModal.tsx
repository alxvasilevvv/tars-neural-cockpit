// SYNC: claude-w106-marketplace
/**
 * Wave 106 — listing preview modal.
 *
 * Triggered by clicking a card body. Shows the long-form
 * description, sample inputs/outputs surfaced by the
 * /preview endpoint, and the listing-specific external preview
 * URL when present.
 */

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import type { Listing, ListingPreview } from "./types";
import { useT } from "@/lib/i18n";

type Props = {
  listing: Listing | null;
  onClose: () => void;
  onInstall: (l: Listing) => void;
};

export function ListingPreviewModal({ listing, onClose, onInstall }: Props) {
  const t = useT();
  const [preview, setPreview] = useState<ListingPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!listing) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/marketplace/listings/${listing.id}/preview`, { method: "POST" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body) => {
        if (cancelled) return;
        setPreview(body.preview ?? null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [listing]);

  if (!listing) return null;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label={`${listing.name} preview`}
    >
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-2xl rounded-md border border-line/60 bg-bg-1 p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-3">
              {t("marketplace.preview.title")}
            </p>
            <h2 className="mt-1 text-[18px] font-semibold text-ink">
              {listing.name}
            </h2>
            <p className="mt-1 text-[11px] text-ink-3">
              {t("marketplace.author.by", { handle: listing.author.handle || "anon" })}
              {" · v"}
              {listing.version}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close preview"
            className="rounded p-1 text-ink-3 hover:bg-bg-0 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
          {listing.description}
        </p>

        {loading ? (
          <p className="mt-4 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
            Loading preview…
          </p>
        ) : error ? (
          <p className="mt-4 text-[11px] text-rose-300">{error}</p>
        ) : preview ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded border border-line/60 bg-bg-0/40 p-3">
              <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.preview.inputs")}
              </p>
              <pre className="mt-1 max-h-32 overflow-auto text-[11px] text-ink-2">
                {JSON.stringify(preview.inputs ?? {}, null, 2)}
              </pre>
            </div>
            <div className="rounded border border-line/60 bg-bg-0/40 p-3">
              <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.preview.outputs")}
              </p>
              <pre className="mt-1 max-h-32 overflow-auto text-[11px] text-ink-2">
                {JSON.stringify(preview.outputs ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-between gap-3">
          {listing.preview_url ? (
            <a
              href={listing.preview_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 hover:text-accent"
            >
              <ExternalLink className="h-3 w-3" />
              {listing.preview_url}
            </a>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-line/60 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-accent/40 hover:text-accent"
            >
              {t("marketplace.cta.cancel")}
            </button>
            <button
              type="button"
              disabled={listing.installed}
              onClick={() => onInstall(listing)}
              className="rounded bg-accent/20 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-accent hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {listing.installed
                ? t("marketplace.cta.installed")
                : t("marketplace.cta.install")}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
