// SYNC: claude-w107-bundles
/**
 * <Bundles /> — Wave 107.
 *
 * Per-org-type ready-to-demo packs. Routed at /bundles.
 *
 * Layout:
 *   [ Header (title + recommended-for-you callout) ]
 *   [ Grid of 7 BundleCards ]
 *   [ Preview modal -> Install -> progress -> redirect ]
 *
 * The recommended bundle is read from
 * ``localStorage["tars.org_type"]`` (set by the W99 onboarding
 * wizard). Operators can also force one via ?org_type=.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { BundleCard } from "@/components/bundles/BundleCard";
import { BundlePreviewModal } from "@/components/bundles/BundlePreviewModal";
import type {
  Bundle,
  BundleListEnvelope,
  InstallEnvelope,
  InstalledListEnvelope,
  PreviewEnvelope,
} from "@/components/bundles/types";

const ORG_TYPE_KEY = "tars.org_type";
const ORG_ID_KEY = "tars.org_id";

export function Bundles() {
  useDocumentMeta({
    title: "Bundles — TARS",
    description:
      "One-click vertical templates: VC fund, hedge fund, family office, SaaS, DAO, research lab. Install playbooks + schedules + dashboard + outreach in 30 seconds.",
  });
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [installedIds, setInstalledIds] = useState<Set<string>>(new Set());
  const [recommendedId, setRecommendedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [preview, setPreview] = useState<PreviewEnvelope | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [stagedBundle, setStagedBundle] = useState<Bundle | null>(null);
  const [installing, setInstalling] = useState(false);
  const [installed, setInstalled] = useState(false);

  const orgType = useMemo(() => {
    const fromQuery = params.get("org_type") || "";
    if (fromQuery) return fromQuery;
    try {
      return localStorage.getItem(ORG_TYPE_KEY) || "";
    } catch {
      return "";
    }
  }, [params]);

  const orgId = useMemo(() => {
    try {
      return localStorage.getItem(ORG_ID_KEY) || "default";
    } catch {
      return "default";
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = orgType
        ? `/api/bundles?org_type=${encodeURIComponent(orgType)}`
        : "/api/bundles";
      const res = await fetch(url);
      const json = (await res.json()) as BundleListEnvelope;
      if (!res.ok || !json?.ok) {
        throw new Error("bundle_list_failed");
      }
      setBundles(json.bundles || []);
      setRecommendedId(json.recommended?.bundle_id || null);
      // Best-effort: load installed list. Failure is non-fatal.
      try {
        const ires = await fetch(
          `/api/bundles/installed?org_id=${encodeURIComponent(orgId)}`,
        );
        const ijson = (await ires.json()) as InstalledListEnvelope;
        if (ires.ok && ijson?.ok) {
          setInstalledIds(new Set(ijson.installed.map((i) => i.bundle_id)));
        }
      } catch {
        /* noop */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "load_failed");
    } finally {
      setLoading(false);
    }
  }, [orgType, orgId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // If the URL ends in /bundles/<id>, auto-open that preview.
  useEffect(() => {
    const path = typeof window !== "undefined" ? window.location.pathname : "";
    const match = path.match(/^\/bundles\/(.+)$/);
    if (match && bundles.length > 0) {
      const found = bundles.find(
        (b) => b.id === match[1] || b.slug === match[1],
      );
      if (found) void onPreview(found);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundles]);

  const onPreview = useCallback(async (bundle: Bundle) => {
    setStagedBundle(bundle);
    setPreview(null);
    setInstalled(false);
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const res = await fetch(`/api/bundles/${bundle.id}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ org_id: orgId }),
      });
      const json = (await res.json()) as PreviewEnvelope;
      if (!res.ok || !json?.ok) {
        throw new Error("preview_failed");
      }
      setPreview(json);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "preview_failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [orgId]);

  const onConfirmInstall = useCallback(
    async (runFirstNow: boolean) => {
      if (!stagedBundle) return;
      setInstalling(true);
      setPreviewError(null);
      try {
        const res = await fetch(`/api/bundles/${stagedBundle.id}/install`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ org_id: orgId, run_first_now: runFirstNow }),
        });
        const json = (await res.json()) as InstallEnvelope;
        if (!res.ok || !json?.ok) {
          throw new Error("install_failed");
        }
        setInstalled(true);
        setInstalledIds((prev) => {
          const next = new Set(prev);
          next.add(stagedBundle.id);
          return next;
        });
        // After a short pause let the operator see the success state, then
        // route to the dashboard (or the first-run page if requested).
        setTimeout(() => {
          if (runFirstNow && json.report.first_run_id) {
            navigate("/dashboard?banner=bundle_installed");
          } else {
            navigate("/dashboard?banner=bundle_installed");
          }
        }, 900);
      } catch (err) {
        setPreviewError(err instanceof Error ? err.message : "install_failed");
      } finally {
        setInstalling(false);
      }
    },
    [stagedBundle, orgId, navigate],
  );

  const closeModal = useCallback(() => {
    setStagedBundle(null);
    setPreview(null);
    setPreviewError(null);
    setInstalled(false);
  }, []);

  const recommended = useMemo(() => {
    if (!recommendedId) return null;
    return bundles.find((b) => b.id === recommendedId) || null;
  }, [recommendedId, bundles]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-12 text-white">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Bundles" },
        ]}
      />

      <header className="flex flex-col gap-3">
        <span className="text-[11px] font-medium uppercase tracking-wider text-white/50">
          Wave 107 — vertical bundles
        </span>
        <h1 className="text-3xl font-semibold sm:text-4xl">
          Set up your cockpit in one click
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-white/60 sm:text-base">
          Each bundle wires a curated set of playbooks, scheduled jobs,
          dashboard widgets, report templates, outreach drafts and connector
          hints — everything you need to run a vertical end-to-end.
        </p>
      </header>

      {recommended ? (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start gap-3 rounded-2xl border border-[var(--accent,#7c3aed)]/30 bg-[var(--accent,#7c3aed)]/10 px-5 py-4"
          role="region"
          aria-label="Recommended bundle"
        >
          <Sparkles size={18} className="mt-0.5 text-[var(--accent,#a78bfa)]" aria-hidden />
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-white">
              Recommended for you: {recommended.name}
            </h2>
            <p className="mt-1 text-xs text-white/60">
              Based on the org type you set during onboarding.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onPreview(recommended)}
            className="rounded-md bg-[var(--accent,#7c3aed)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--accent-hover,#6d28d9)]"
          >
            Preview
          </button>
        </motion.div>
      ) : null}

      {error ? (
        <p className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
          {error}
        </p>
      ) : null}

      {loading && bundles.length === 0 ? (
        <p className="text-sm text-white/60">Loading bundles…</p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {bundles.map((b) => (
          <BundleCard
            key={b.id}
            bundle={b}
            recommended={recommendedId === b.id}
            installed={installedIds.has(b.id)}
            onPreview={onPreview}
          />
        ))}
      </div>

      <BundlePreviewModal
        bundle={stagedBundle}
        preview={preview}
        loading={previewLoading}
        installing={installing}
        installed={installed}
        error={previewError}
        onClose={closeModal}
        onConfirm={onConfirmInstall}
      />
    </div>
  );
}
