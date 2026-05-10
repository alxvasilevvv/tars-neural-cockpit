// SYNC: claude-w106-marketplace
/**
 * Wave 106 — submit + display aggregate ratings.
 *
 * Local-only for v0 (the ratings sqlite lives at
 * ~/.tars/marketplace/ratings.sqlite). The aggregate is fetched
 * from /api/marketplace/listings/{id}/ratings.
 */

import { useCallback, useEffect, useState } from "react";
import { Star } from "lucide-react";
import type { RatingsAggregate } from "./types";
import { useT } from "@/lib/i18n";

type Props = {
  listingId: string;
  raterEmail?: string;
};

export function RatingsUI({ listingId, raterEmail = "" }: Props) {
  const t = useT();
  const [aggregate, setAggregate] = useState<RatingsAggregate | null>(null);
  const [score, setScore] = useState(5);
  const [comment, setComment] = useState("");
  const [thanks, setThanks] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`/api/marketplace/listings/${listingId}/ratings`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setAggregate(body.aggregate ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [listingId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const submit = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(`/api/marketplace/listings/${listingId}/rate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ score, comment, rater_email: raterEmail }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setAggregate(body.aggregate ?? null);
      setThanks(true);
      window.setTimeout(() => setThanks(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }, [listingId, score, comment, raterEmail]);

  return (
    <section className="rounded border border-line/60 bg-bg-1/40 p-3">
      <header className="flex items-center justify-between">
        <p className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          {t("marketplace.ratings.title")}
        </p>
        {aggregate ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-ink-2">
            <Star className="h-3 w-3 text-accent" />
            {aggregate.avg.toFixed(1)}
            <span className="text-[10px] text-ink-3">
              {" "}
              {t("marketplace.ratings.count", { n: aggregate.count })}
            </span>
          </span>
        ) : null}
      </header>

      <div className="mt-2 flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setScore(n)}
            aria-label={`${n} stars`}
            className="rounded p-1 hover:bg-bg-0/60"
          >
            <Star
              className={`h-4 w-4 ${
                n <= score ? "text-accent" : "text-ink-3"
              }`}
              fill={n <= score ? "currentColor" : "none"}
            />
          </button>
        ))}
      </div>

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder={t("marketplace.ratings.placeholder")}
        rows={2}
        className="mt-2 w-full rounded border border-line/60 bg-bg-0/40 p-2 font-sans text-[12px] text-ink placeholder:text-ink-3 focus:border-accent/40 focus:outline-none"
      />

      <div className="mt-2 flex items-center justify-between">
        {thanks ? (
          <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-accent">
            {t("marketplace.ratings.thanks")}
          </span>
        ) : (
          <span className="text-[10px] text-rose-300">{error ?? ""}</span>
        )}
        <button
          type="button"
          disabled={submitting}
          onClick={() => void submit()}
          className="rounded bg-accent/20 px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-accent hover:bg-accent/30 disabled:opacity-40"
        >
          {t("marketplace.ratings.submit")}
        </button>
      </div>
    </section>
  );
}
