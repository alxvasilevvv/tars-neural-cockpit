// SYNC: claude-w108-perf
/**
 * <PerfDashboard /> — Wave 108.
 *
 * Operations / facilitator-grade health view at /admin/perf.
 *
 * Sections:
 *   1. Latency widget grid (council / backtest / webhook / connector)
 *   2. Connector health
 *   3. Webhook delivery stats
 *   4. Receipt chain integrity
 *   5. Background jobs (scheduler / reflection / autopilot)
 *   6. Resource usage (psutil best-effort)
 *
 * Single fetch to /api/perf/summary; the FE never blocks on an
 * individual subsystem, every panel renders with available=false
 * fallbacks so a missing module never collapses the page.
 */

import { useCallback, useEffect, useState } from "react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { LatencyCard } from "@/components/perf/LatencyCard";
import { ConnectorHealthTable } from "@/components/perf/ConnectorHealthTable";
import { WebhookStatsPanel } from "@/components/perf/WebhookStatsPanel";
import { ReceiptIntegrityCard } from "@/components/perf/ReceiptIntegrityCard";
import { JobsStatusPanel } from "@/components/perf/JobsStatusPanel";
import { ResourceUsageCard } from "@/components/perf/ResourceUsageCard";
import type { PerfSummaryEnvelope } from "@/components/perf/types";

export function PerfDashboard() {
  const t = useT();
  useDocumentMeta({
    title: "Performance — TARS",
    description:
      "Operator dashboard for latency, connector health, webhook deliveries, receipt chain integrity, and background jobs.",
  });

  const [summary, setSummary] = useState<PerfSummaryEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/perf/summary?window=24h");
      const json = (await res.json()) as PerfSummaryEnvelope;
      if (!res.ok || !json?.ok) {
        throw new Error("perf_summary_failed");
      }
      setSummary(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  async function handleTestAll() {
    if (!summary) return;
    const names = summary.connectors.connectors.map((c) => c.name);
    await Promise.all(
      names.map((name) =>
        fetch(`/api/connectors/${encodeURIComponent(name)}/health`).catch(
          () => undefined,
        ),
      ),
    );
    await refresh();
  }

  async function handleReplay(deliveryId: string) {
    try {
      await fetch(`/api/webhooks/deliveries/${encodeURIComponent(deliveryId)}/replay`, {
        method: "POST",
      });
    } catch {
      /* swallow — UI just refreshes */
    }
    await refresh();
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 md:px-8">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Admin" }, { label: "Performance" }]} />
      <header className="mt-4 mb-6">
        <h1 className="font-display text-3xl text-ink">{t("perf.title")}</h1>
        <p className="mt-2 text-ink-2">{t("perf.subtitle")}</p>
        {summary?.as_of && (
          <p className="mt-1 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
            {t("perf.as_of")}{" "}
            {new Date(summary.as_of * 1000).toISOString().replace("T", " ").slice(0, 19)} UTC
          </p>
        )}
      </header>

      {error && (
        <div className="mb-4 rounded border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-[12px] text-rose-200">
          {t("perf.error")}: {error}
        </div>
      )}
      {loading && !summary && (
        <p className="text-ink-3">{t("perf.loading")}</p>
      )}

      <section aria-labelledby="perf-latency" className="mb-6">
        <h2 id="perf-latency" className="mb-3 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
          {t("perf.section.latency")}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <LatencyCard title={t("perf.op.council")} stats={summary?.latency.council} />
          <LatencyCard title={t("perf.op.backtest")} stats={summary?.latency.backtest} />
          <LatencyCard title={t("perf.op.webhook")} stats={summary?.latency.webhook} />
          <LatencyCard title={t("perf.op.connector")} stats={summary?.latency.connector} />
        </div>
      </section>

      <section className="mb-6">
        <ConnectorHealthTable data={summary?.connectors} onTestAll={handleTestAll} />
      </section>

      <section className="mb-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <WebhookStatsPanel data={summary?.webhooks} onReplay={handleReplay} />
        <ReceiptIntegrityCard data={summary?.receipts} />
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <JobsStatusPanel data={summary?.jobs} />
        <ResourceUsageCard data={summary?.resources} />
      </section>
    </div>
  );
}
