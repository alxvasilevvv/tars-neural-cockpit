// SYNC: claude-w103-reports
/**
 * <Reports /> — Wave 103.
 *
 * Reporting export surface at /reports. Three tabs:
 *
 *   Templates  — card grid of built-ins + custom + "+ Custom"
 *                Click a card → modal with auto-generated form +
 *                Preview / Generate.
 *   Runs       — recent renders with status, download, send.
 *   Scheduled  — cron-driven recurring runs (Wave 97 schedules
 *                whose playbook id starts with ``report:``).
 *
 * Layout variant: wide (matches Outreach + Inbox + Files).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Calendar as CalendarIcon,
  Download,
  FileText,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { TemplateCard } from "@/components/reports/TemplateCard";
import { InputFormBuilder } from "@/components/reports/InputFormBuilder";
import { PreviewPane } from "@/components/reports/PreviewPane";
import type {
  ReportRun,
  ReportTemplate,
  RunInputs,
} from "@/components/reports/types";

type Tab = "templates" | "runs" | "scheduled";

type ScheduledItem = {
  id: string;
  template_id: string;
  cron_expression: string;
  next_run_at: number | null;
  enabled: boolean;
  args: Record<string, unknown>;
};

export function Reports() {
  useDocumentMeta({
    title: "Reports — TARS",
    description:
      "Generate LP updates, board packs, KPI dashboards, audit packs and incident postmortems as PDF / PPTX / XLSX / DOCX files.",
  });

  const [tab, setTab] = useState<Tab>("templates");
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [runs, setRuns] = useState<ReportRun[]>([]);
  const [scheduled, setScheduled] = useState<ScheduledItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal state for the generate form.
  const [active, setActive] = useState<ReportTemplate | null>(null);
  const [inputs, setInputs] = useState<RunInputs>({});
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const refreshTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/reports/templates");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { templates: ReportTemplate[] };
      setTemplates(data.templates || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/reports/runs?limit=50");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { runs: ReportRun[] };
      setRuns(data.runs || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshScheduled = useCallback(async () => {
    // Scheduled items live in the Wave 97 scheduler; we filter to
    // those whose playbook id is namespaced with ``report:``.
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/scheduler/schedules");
      if (!res.ok) {
        // Endpoint may not exist on every install — surface gentle empty.
        setScheduled([]);
        return;
      }
      const data = (await res.json()) as { schedules?: ScheduledItem[] };
      const all = data.schedules || [];
      setScheduled(
        all.filter((s) => s.template_id?.startsWith?.("report:") || false),
      );
    } catch {
      setScheduled([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "templates") void refreshTemplates();
    else if (tab === "runs") void refreshRuns();
    else if (tab === "scheduled") void refreshScheduled();
  }, [tab, refreshTemplates, refreshRuns, refreshScheduled]);

  // Initial load of templates so the badge counts work.
  useEffect(() => {
    void refreshTemplates();
  }, [refreshTemplates]);

  const onSelectTemplate = useCallback((t: ReportTemplate) => {
    setActive(t);
    setInputs({});
    setPreviewHtml(null);
  }, []);

  const closeModal = useCallback(() => {
    setActive(null);
    setInputs({});
    setPreviewHtml(null);
  }, []);

  const onPreview = useCallback(async () => {
    if (!active) return;
    setPreviewLoading(true);
    try {
      const res = await fetch(
        `/api/reports/templates/${active.id}/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs }),
        },
      );
      const html = await res.text();
      setPreviewHtml(html);
    } catch (e) {
      setPreviewHtml(
        `<pre style="padding:24px;color:#a00">Preview failed: ${
          e instanceof Error ? e.message : String(e)
        }</pre>`,
      );
    } finally {
      setPreviewLoading(false);
    }
  }, [active, inputs]);

  const onGenerate = useCallback(async () => {
    if (!active) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/reports/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: active.id,
          inputs,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      closeModal();
      setTab("runs");
      await refreshRuns();
    } catch (e) {
      alert(`Generate failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSubmitting(false);
    }
  }, [active, inputs, closeModal, refreshRuns]);

  const counts = useMemo(
    () => ({
      templates: templates.length,
      runs: runs.length,
      scheduled: scheduled.length,
    }),
    [templates.length, runs.length, scheduled.length],
  );

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-10">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Reports" },
        ]}
      />
      <header className="mb-6 flex items-end justify-between gap-4">
        <div>
          <div className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
            Wave 103
          </div>
          <h1 className="text-[28px] font-light tracking-tight text-ink">
            Reports
          </h1>
          <p className="mt-1 max-w-[520px] text-[13px] text-ink-2">
            Generate LP updates, board packs, KPI dashboards and audit
            packs from a template + your data. PDF / PPTX / XLSX /
            DOCX.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void refreshTemplates();
            void refreshRuns();
            void refreshScheduled();
          }}
          className="flex items-center gap-2 rounded-sm border border-line px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[1.5px] text-ink-2 transition-colors hover:border-[var(--brand-cyan)] hover:text-ink"
          aria-label="Refresh"
        >
          <RefreshCw size={13} aria-hidden />
          Refresh
        </button>
      </header>

      <nav
        role="tablist"
        aria-label="Reports sections"
        className="mb-6 flex gap-1 border-b border-line"
      >
        {(
          [
            { id: "templates", label: `Templates · ${counts.templates}` },
            { id: "runs", label: `Runs · ${counts.runs}` },
            { id: "scheduled", label: `Scheduled · ${counts.scheduled}` },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id as Tab)}
            className={`-mb-px border-b-2 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[1.5px] transition-colors ${
              tab === t.id
                ? "border-[var(--brand-cyan)] text-ink"
                : "border-transparent text-ink-3 hover:text-ink-2"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {error && (
        <div className="mb-4 rounded-sm border border-red-500/40 bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
          {error}
        </div>
      )}

      {tab === "templates" && (
        <TemplatesGrid
          templates={templates}
          loading={loading}
          onSelect={onSelectTemplate}
        />
      )}

      {tab === "runs" && (
        <RunsTable runs={runs} loading={loading} onChanged={refreshRuns} />
      )}

      {tab === "scheduled" && (
        <ScheduledList items={scheduled} loading={loading} />
      )}

      {active && (
        <GenerateModal
          template={active}
          inputs={inputs}
          onChange={setInputs}
          onClose={closeModal}
          onPreview={onPreview}
          onGenerate={onGenerate}
          previewHtml={previewHtml}
          previewLoading={previewLoading}
          submitting={submitting}
        />
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────

function TemplatesGrid({
  templates,
  loading,
  onSelect,
}: {
  templates: ReportTemplate[];
  loading: boolean;
  onSelect: (t: ReportTemplate) => void;
}) {
  if (loading && templates.length === 0) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-[154px] animate-pulse rounded-md border border-line bg-bg-1/30"
          />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {templates.map((t) => (
        <TemplateCard key={t.id} template={t} onSelect={onSelect} />
      ))}
      <button
        type="button"
        onClick={() =>
          alert(
            "Custom templates: POST /api/reports/templates with {name, slug, kind, schema}",
          )
        }
        className="flex h-full min-h-[154px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-line bg-bg-1/10 p-4 text-ink-3 transition-colors hover:border-[var(--brand-cyan)] hover:text-ink"
      >
        <Plus size={20} aria-hidden />
        <span className="text-[12.5px]">New custom template</span>
      </button>
    </div>
  );
}

function RunsTable({
  runs,
  loading,
  onChanged,
}: {
  runs: ReportRun[];
  loading: boolean;
  onChanged: () => void;
}) {
  if (loading && runs.length === 0) {
    return <div className="text-[12.5px] text-ink-3">Loading runs…</div>;
  }
  if (runs.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-line bg-bg-1/10 p-8 text-center text-[12.5px] text-ink-3">
        No reports generated yet. Pick a template to start.
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-md border border-line">
      <table className="w-full text-[12.5px]">
        <thead className="bg-bg-1/40 text-left text-[11px] uppercase tracking-[1.5px] text-ink-3">
          <tr>
            <th className="px-3 py-2">Run</th>
            <th className="px-3 py-2">Template</th>
            <th className="px-3 py-2">Kind</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Created</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-t border-line/60">
              <td className="px-3 py-2 font-mono-tech text-[11px] text-ink-2">
                {r.id.slice(0, 12)}…
              </td>
              <td className="px-3 py-2 text-ink">{r.template_id}</td>
              <td className="px-3 py-2 text-ink-2">{r.output_kind || "—"}</td>
              <td className="px-3 py-2">
                <StatusBadge status={r.status} />
              </td>
              <td className="px-3 py-2 text-ink-3">
                {new Date(r.created_at * 1000).toLocaleString()}
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center justify-end gap-2">
                  {r.status === "done" && (
                    <a
                      href={`/api/reports/runs/${r.id}/download`}
                      className="inline-flex items-center gap-1 rounded-sm border border-line px-2 py-1 text-[11px] text-ink-2 hover:border-[var(--brand-cyan)] hover:text-ink"
                    >
                      <Download size={12} aria-hidden /> Download
                    </a>
                  )}
                  {r.status === "done" && (
                    <button
                      type="button"
                      onClick={() => onSendRun(r.id, onChanged)}
                      className="inline-flex items-center gap-1 rounded-sm border border-line px-2 py-1 text-[11px] text-ink-2 hover:border-[var(--brand-cyan)] hover:text-ink"
                    >
                      <Send size={12} aria-hidden /> Send
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function onSendRun(runId: string, onChanged: () => void) {
  const recipients = window.prompt(
    "Comma-separated recipient emails:",
    "",
  );
  if (!recipients) return;
  const list = recipients
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (list.length === 0) return;
  try {
    const res = await fetch(`/api/reports/runs/${runId}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_emails: list,
        channel: "outreach",
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    onChanged();
  } catch (e) {
    alert(`Send failed: ${e instanceof Error ? e.message : String(e)}`);
  }
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "done"
      ? "text-emerald-300 border-emerald-300/30 bg-emerald-300/10"
      : status === "failed"
        ? "text-red-300 border-red-300/30 bg-red-300/10"
        : status === "rendering"
          ? "text-amber-300 border-amber-300/30 bg-amber-300/10"
          : "text-ink-3 border-line bg-bg-1/40";
  return (
    <span
      className={`rounded-sm border px-2 py-0.5 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] ${color}`}
    >
      {status}
    </span>
  );
}

function ScheduledList({
  items,
  loading,
}: {
  items: ScheduledItem[];
  loading: boolean;
}) {
  if (loading && items.length === 0) {
    return <div className="text-[12.5px] text-ink-3">Loading…</div>;
  }
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-line bg-bg-1/10 p-8 text-center text-[12.5px] text-ink-3">
        No scheduled reports. POST to{" "}
        <code className="rounded-sm bg-bg-1/40 px-1 py-0.5">
          /api/reports/schedule
        </code>{" "}
        with a cron expression and an inputs provider to schedule one.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((s) => (
        <li
          key={s.id}
          className="flex items-center justify-between rounded-md border border-line bg-bg-1/30 px-3 py-2 text-[12.5px]"
        >
          <div className="flex items-center gap-3">
            <CalendarIcon size={14} aria-hidden style={{ color: "var(--brand-cyan)" }} />
            <span className="text-ink">{s.template_id}</span>
            <span className="font-mono-tech text-[11px] text-ink-3">
              {s.cron_expression}
            </span>
          </div>
          <span className="text-[11px] text-ink-3">
            {s.enabled ? "Enabled" : "Paused"} ·{" "}
            {s.next_run_at
              ? new Date(s.next_run_at * 1000).toLocaleString()
              : "—"}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ───────────────────────────────────────────────────────────────────

function GenerateModal({
  template,
  inputs,
  onChange,
  onClose,
  onPreview,
  onGenerate,
  previewHtml,
  previewLoading,
  submitting,
}: {
  template: ReportTemplate;
  inputs: RunInputs;
  onChange: (next: RunInputs) => void;
  onClose: () => void;
  onPreview: () => void;
  onGenerate: () => void;
  previewHtml: string | null;
  previewLoading: boolean;
  submitting: boolean;
}) {
  // Close on escape.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Generate ${template.name}`}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 8 }}
        animate={{ y: 0 }}
        className="grid max-h-[90vh] w-full max-w-[920px] grid-cols-1 overflow-hidden rounded-md border border-line bg-bg-0 shadow-xl md:grid-cols-2"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col gap-3 overflow-y-auto border-b border-line p-5 md:border-b-0 md:border-r">
          <div className="flex items-center gap-2">
            <FileText size={16} aria-hidden style={{ color: "var(--brand-cyan)" }} />
            <h2 className="text-[16px] font-medium text-ink">{template.name}</h2>
          </div>
          <p className="text-[12px] text-ink-3">{template.description}</p>
          <InputFormBuilder
            schema={template.schema}
            values={inputs}
            onChange={onChange}
          />
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto p-5">
          <div className="flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
            <Sparkles size={12} aria-hidden style={{ color: "var(--brand-cyan)" }} />
            Preview
          </div>
          <PreviewPane html={previewHtml} loading={previewLoading} />
          <div className="mt-auto flex justify-end gap-2 border-t border-line pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-sm border border-line px-3 py-1.5 text-[12px] text-ink-2 hover:text-ink"
            >
              Close
            </button>
            <button
              type="button"
              onClick={onPreview}
              disabled={previewLoading}
              className="rounded-sm border border-line px-3 py-1.5 text-[12px] text-ink-2 hover:border-[var(--brand-cyan)] hover:text-ink disabled:opacity-50"
            >
              Preview
            </button>
            <button
              type="button"
              onClick={onGenerate}
              disabled={submitting}
              className="rounded-sm border border-[var(--brand-cyan)] bg-[var(--brand-cyan)]/10 px-3 py-1.5 text-[12px] font-medium text-ink hover:bg-[var(--brand-cyan)]/20 disabled:opacity-50"
            >
              {submitting ? "Generating…" : "Generate"}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
