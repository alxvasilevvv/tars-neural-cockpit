// SYNC: claude-w106-marketplace
/**
 * <Marketplace /> — Wave 106.
 *
 * Discovery + install surface for community playbooks, skills,
 * and report templates. Routed at /marketplace (variant=wide).
 *
 * Layout:
 *   [ Header (title + search + Refresh registry) ]
 *   [ Sidebar (category chips + kind filter + rating filter) | Card grid ]
 *   [ Tabs: Browse | My library ]
 *
 * v0 deliberately skips payouts — ratings are local-only (see
 * backend/core/marketplace/ratings.py) and price tags are
 * forward-compat placeholders for v9.3.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { RefreshCw, Search, Sparkles, Library } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { ListingCard } from "@/components/marketplace/ListingCard";
import { ListingPreviewModal } from "@/components/marketplace/ListingPreviewModal";
import { InstallConfirmDialog } from "@/components/marketplace/InstallConfirmDialog";
import { MyLibraryTab } from "@/components/marketplace/MyLibraryTab";
import type {
  InstalledItem,
  Listing,
  ListingKind,
  RegistryEnvelope,
  InstalledEnvelope,
} from "@/components/marketplace/types";
import { useT } from "@/lib/i18n";

type Tab = "browse" | "library";

const KIND_OPTIONS: Array<{ value: ListingKind; key: string }> = [
  { value: "playbook", key: "marketplace.kind.playbook" },
  { value: "skill", key: "marketplace.kind.skill" },
  { value: "report_template", key: "marketplace.kind.report_template" },
  { value: "template", key: "marketplace.kind.template" },
];

const SOURCE_LABEL_KEY: Record<string, string> = {
  remote: "marketplace.source.remote",
  cache: "marketplace.source.cache",
  seed: "marketplace.source.seed",
};

export function Marketplace() {
  const t = useT();
  useDocumentMeta({
    title: "Marketplace — TARS",
    description:
      "Community-published playbooks, skills, and report templates. Browse, preview and install in one click.",
  });

  const [tab, setTab] = useState<Tab>("browse");
  const [listings, setListings] = useState<Listing[]>([]);
  const [installed, setInstalled] = useState<InstalledItem[]>([]);
  const [source, setSource] = useState<string>("seed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [kind, setKind] = useState<ListingKind | null>(null);
  const [minRating, setMinRating] = useState<number | null>(null);

  // Modals
  const [preview, setPreview] = useState<Listing | null>(null);
  const [stagedInstall, setStagedInstall] = useState<Listing | null>(null);
  const [installing, setInstalling] = useState(false);

  const refreshListings = useCallback(
    async (force = false) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (search) params.set("q", search);
        if (category) params.set("category", category);
        if (kind) params.set("kind", kind);
        if (minRating != null) params.set("min_rating", String(minRating));
        if (force) params.set("force_refresh", "true");
        const res = await fetch(
          `/api/marketplace/listings?${params.toString()}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as RegistryEnvelope;
        setListings(body.listings || []);
        setSource(body.source || "seed");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [search, category, kind, minRating],
  );

  const refreshInstalled = useCallback(async () => {
    try {
      const res = await fetch("/api/marketplace/installed");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as InstalledEnvelope;
      setInstalled(body.installed || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refreshListings();
    void refreshInstalled();
  }, [refreshListings, refreshInstalled]);

  const forceRefresh = useCallback(async () => {
    setLoading(true);
    try {
      await fetch("/api/marketplace/registry/refresh", { method: "POST" });
      await refreshListings(true);
    } finally {
      setLoading(false);
    }
  }, [refreshListings]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    listings.forEach((l) => set.add(l.category));
    return Array.from(set).sort();
  }, [listings]);

  const handleInstallStart = useCallback((l: Listing) => {
    setPreview(null);
    setStagedInstall(l);
  }, []);

  const handleInstallConfirm = useCallback(async () => {
    if (!stagedInstall) return;
    setInstalling(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/marketplace/listings/${stagedInstall.id}/install`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ target: "personal" }),
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refreshListings();
      await refreshInstalled();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setInstalling(false);
      setStagedInstall(null);
    }
  }, [stagedInstall, refreshListings, refreshInstalled]);

  const handleUninstall = useCallback(
    async (listingId: string) => {
      try {
        const res = await fetch(
          `/api/marketplace/installed/${listingId}/uninstall`,
          { method: "POST" },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await refreshInstalled();
        await refreshListings();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [refreshInstalled, refreshListings],
  );

  return (
    <div className="mx-auto max-w-[1280px] px-6 py-10 md:px-10 md:py-14">
      <Breadcrumbs
        items={[
          { label: t("marketplace.crumb.home"), href: "/" },
          { label: t("marketplace.crumb") },
        ]}
      />

      <header className="mt-4 flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-3">
            {t("marketplace.eyebrow")}
          </p>
          <h1 className="mt-1 text-[28px] font-bold tracking-tight text-ink">
            {t("marketplace.title")}
          </h1>
          <p className="mt-1 max-w-xl text-[12px] leading-relaxed text-ink-2">
            {t("marketplace.subtitle")}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
              <input
                type="search"
                placeholder={t("marketplace.search.placeholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-72 rounded border border-line/60 bg-bg-1/60 py-1.5 pl-8 pr-3 font-sans text-[12px] text-ink placeholder:text-ink-3 focus:border-accent/40 focus:outline-none"
              />
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={() => void forceRefresh()}
              className="inline-flex items-center gap-1 rounded border border-line/60 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-accent/40 hover:text-accent disabled:opacity-40"
            >
              <RefreshCw
                className={`h-3 w-3 ${loading ? "animate-spin" : ""}`}
              />
              {loading ? t("marketplace.refreshing") : t("marketplace.refresh")}
            </button>
          </div>
          <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
            {t(SOURCE_LABEL_KEY[source] as Parameters<typeof t>[0]) ?? source}
          </p>
        </div>
      </header>

      <nav
        className="mt-6 flex items-center gap-2 border-b border-line/60"
        role="tablist"
        aria-label="Marketplace tabs"
      >
        {(
          [
            { value: "browse" as const, icon: Sparkles, key: "marketplace.tab.browse" },
            { value: "library" as const, icon: Library, key: "marketplace.tab.library" },
          ] as const
        ).map(({ value, icon: Icon, key }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`flex items-center gap-2 border-b-2 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] ${
              tab === value
                ? "border-accent text-accent"
                : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {t(key as Parameters<typeof t>[0])}
          </button>
        ))}
      </nav>

      {error ? (
        <p className="mt-4 rounded border border-rose-300/30 bg-rose-300/10 px-3 py-2 text-[11px] text-rose-200">
          {error}
        </p>
      ) : null}

      {tab === "browse" ? (
        <div className="mt-6 grid gap-6 md:grid-cols-[200px_1fr]">
          <aside className="flex flex-col gap-4">
            <section>
              <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.filter.categories")}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setCategory(null)}
                  className={`rounded px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] ${
                    category === null
                      ? "bg-accent/15 text-accent"
                      : "border border-line/60 text-ink-2 hover:text-accent"
                  }`}
                >
                  All
                </button>
                {categories.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCategory(c)}
                    className={`rounded px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] ${
                      category === c
                        ? "bg-accent/15 text-accent"
                        : "border border-line/60 text-ink-2 hover:text-accent"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </section>

            <section>
              <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.filter.kind")}
              </p>
              <div className="mt-2 flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => setKind(null)}
                  className={`rounded px-2 py-1 text-left font-mono-tech text-[10px] uppercase tracking-[2px] ${
                    kind === null
                      ? "bg-accent/15 text-accent"
                      : "text-ink-2 hover:text-accent"
                  }`}
                >
                  {t("marketplace.filter.allKinds")}
                </button>
                {KIND_OPTIONS.map((k) => (
                  <button
                    key={k.value}
                    type="button"
                    onClick={() => setKind(k.value)}
                    className={`rounded px-2 py-1 text-left font-mono-tech text-[10px] uppercase tracking-[2px] ${
                      kind === k.value
                        ? "bg-accent/15 text-accent"
                        : "text-ink-2 hover:text-accent"
                    }`}
                  >
                    {t(k.key as Parameters<typeof t>[0])}
                  </button>
                ))}
              </div>
            </section>

            <section>
              <p className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.filter.rating")}
              </p>
              <div className="mt-2 flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => setMinRating(null)}
                  className={`rounded px-2 py-1 text-left font-mono-tech text-[10px] uppercase tracking-[2px] ${
                    minRating === null
                      ? "bg-accent/15 text-accent"
                      : "text-ink-2 hover:text-accent"
                  }`}
                >
                  {t("marketplace.filter.allRatings")}
                </button>
                <button
                  type="button"
                  onClick={() => setMinRating(4.0)}
                  className={`rounded px-2 py-1 text-left font-mono-tech text-[10px] uppercase tracking-[2px] ${
                    minRating === 4.0
                      ? "bg-accent/15 text-accent"
                      : "text-ink-2 hover:text-accent"
                  }`}
                >
                  {t("marketplace.filter.4plus")}
                </button>
              </div>
            </section>
          </aside>

          <main>
            {listings.length === 0 ? (
              <p className="rounded border border-dashed border-line/60 p-6 text-center font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
                {t("marketplace.empty.browse")}
              </p>
            ) : (
              <motion.div
                layout
                className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
              >
                {listings.map((l) => (
                  <ListingCard
                    key={l.id}
                    listing={l}
                    onPreview={setPreview}
                    onInstall={handleInstallStart}
                  />
                ))}
              </motion.div>
            )}
          </main>
        </div>
      ) : (
        <div className="mt-6">
          <MyLibraryTab items={installed} onUninstall={handleUninstall} />
        </div>
      )}

      <ListingPreviewModal
        listing={preview}
        onClose={() => setPreview(null)}
        onInstall={handleInstallStart}
      />
      <InstallConfirmDialog
        listing={stagedInstall}
        busy={installing}
        onConfirm={() => void handleInstallConfirm()}
        onCancel={() => setStagedInstall(null)}
      />
    </div>
  );
}
