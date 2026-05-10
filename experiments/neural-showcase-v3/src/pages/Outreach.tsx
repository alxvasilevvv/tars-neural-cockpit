// SYNC: claude-w98-outreach
/**
 * <Outreach /> -- Wave 98.
 *
 * Operator-facing page at /outreach. Three columns -- Drafts (status
 * = draft), Awaiting send (approved), Recent sends (last 7 days) --
 * plus a Templates section listing the five built-ins + custom and
 * a Campaigns section with progress bars.
 *
 * Backend lives at /api/outreach/* (see backend/core/outreach +
 * web_extras/routers/outreach.py). The lifespan helpers seed the
 * five starter templates on first hit so a cold install renders
 * the templates strip immediately.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Mail,
  Plus,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { DraftEditor, type OutreachDraft } from "@/components/outreach/DraftEditor";

type OutreachTemplate = {
  id: string;
  name: string;
  slug: string;
  use_case: string;
  system_prompt: string;
  variables: string[];
  default_subject_template: string;
  created_at: number;
};

type OutreachCampaign = {
  id: string;
  name: string;
  template_id: string;
  recipients: Array<Record<string, unknown>>;
  schedule_at: number | null;
  status: "planning" | "sending" | "done" | "aborted";
  drafts_generated: number;
  drafts_approved: number;
  drafts_sent: number;
  created_at: number;
};

const SEVEN_DAYS_S = 7 * 24 * 60 * 60;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...(init || {}) });
  if (!r.ok) {
    let detail: unknown = "";
    try { detail = await r.json(); } catch { /* ignore */ }
    throw new Error(`HTTP ${r.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return r.json() as Promise<T>;
}

function formatAgo(ts: number | null | undefined): string {
  if (!ts) return "-";
  const d = Date.now() / 1000 - ts;
  if (d < 60) return `${Math.round(d)}s ago`;
  if (d < 3600) return `${Math.round(d / 60)}m ago`;
  if (d < 86400) return `${Math.round(d / 3600)}h ago`;
  return `${Math.round(d / 86400)}d ago`;
}

export function Outreach() {
  useDocumentMeta({
    title: "Outreach - TARS",
    description: "Draft + send LP updates, founder DD, intros, follow-ups in your voice. Gmail send is HIL-gated.",
  });

  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [templates, setTemplates] = useState<OutreachTemplate[]>([]);
  const [campaigns, setCampaigns] = useState<OutreachCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<OutreachDraft | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [draftsResp, templatesResp, campaignsResp] = await Promise.all([
        api<{ drafts: OutreachDraft[] }>("/api/outreach/drafts?limit=200"),
        api<{ templates: OutreachTemplate[] }>("/api/outreach/templates"),
        api<{ campaigns: OutreachCampaign[] }>("/api/outreach/campaigns"),
      ]);
      setDrafts(draftsResp.drafts || []);
      setTemplates(templatesResp.templates || []);
      setCampaigns(campaignsResp.campaigns || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const draftsCol = useMemo(
    () => drafts.filter((d) => d.status === "draft"),
    [drafts],
  );
  const approvedCol = useMemo(
    () => drafts.filter((d) => d.status === "approved"),
    [drafts],
  );
  const sentCol = useMemo(() => {
    const cutoff = Date.now() / 1000 - SEVEN_DAYS_S;
    return drafts.filter((d) => d.status === "sent" && (d.sent_at || 0) >= cutoff);
  }, [drafts]);

  async function patchDraft(id: string, patch: { subject?: string; body?: string; status?: string }) {
    setBusy(true);
    try {
      const resp = await api<{ draft: OutreachDraft }>(`/api/outreach/drafts/${id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setDrafts((cur) => cur.map((d) => (d.id === id ? resp.draft : d)));
      if (editing && editing.id === id) setEditing(resp.draft);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function discardDraft(id: string) {
    if (!window.confirm("Discard this draft?")) return;
    setBusy(true);
    try {
      await api(`/api/outreach/drafts/${id}`, { method: "DELETE" });
      setDrafts((cur) => cur.filter((d) => d.id !== id));
      if (editing && editing.id === id) setEditing(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function sendDraft(id: string) {
    setBusy(true);
    try {
      const resp = await api<{ draft: OutreachDraft }>(`/api/outreach/drafts/${id}/send`, { method: "POST" });
      setDrafts((cur) => cur.map((d) => (d.id === id ? resp.draft : d)));
      if (editing && editing.id === id) setEditing(resp.draft);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function regenerate(d: OutreachDraft) {
    setBusy(true);
    try {
      // Fire a fresh draft against the same template + recipient + context.
      // This creates a new row; we link it back into the editor.
      const resp = await api<{ draft: OutreachDraft }>("/api/outreach/drafts", {
        method: "POST",
        body: JSON.stringify({
          template_id: d.template_id,
          recipient: d.recipient,
          context: d.context || {},
        }),
      });
      setDrafts((cur) => [resp.draft, ...cur]);
      setEditing(resp.draft);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="relative z-10 mx-auto max-w-[1320px] px-6 pb-24 pt-32 md:px-12">
      <Breadcrumbs />
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-white/55">Wave 98</p>
          <h1 className="mt-1 text-3xl font-semibold text-white">Outreach</h1>
          <p className="mt-2 max-w-xl text-sm text-white/65">
            Draft LP updates, founder DD, intros, follow-ups, and welcome touches in your voice.
            Sending is HIL-gated and rate-capped at 50 / day.
          </p>
        </div>
        <button
          type="button"
          onClick={() => alert("New campaign: POST /api/outreach/campaigns -- wire up the recipient picker UI in v9.4")}
          className="inline-flex items-center gap-2 rounded-lg border border-indigo-400/50 bg-indigo-500/30 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500/45"
        >
          <Plus className="h-4 w-4" />
          New campaign
        </button>
      </header>

      {err ? (
        <p className="mb-6 rounded-lg border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">
          {err}
        </p>
      ) : null}

      {/* Three columns -- drafts / awaiting send / recent sends. */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <DraftColumn
          title="Drafts"
          icon={<Mail className="h-4 w-4" />}
          drafts={draftsCol}
          loading={loading}
          onOpen={(d) => setEditing(d)}
          onApprove={(d) => void patchDraft(d.id, { status: "approved" })}
          onDiscard={(d) => void discardDraft(d.id)}
        />
        <DraftColumn
          title="Awaiting send"
          icon={<CheckCircle2 className="h-4 w-4" />}
          drafts={approvedCol}
          loading={loading}
          onOpen={(d) => setEditing(d)}
          onSend={(d) => void sendDraft(d.id)}
          onDiscard={(d) => void discardDraft(d.id)}
        />
        <DraftColumn
          title="Recent sends (7d)"
          icon={<Send className="h-4 w-4" />}
          drafts={sentCol}
          loading={loading}
          onOpen={(d) => setEditing(d)}
          readOnly
        />
      </div>

      {/* Templates strip. */}
      <section className="mt-12">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm uppercase tracking-[0.22em] text-white/55">Templates</h2>
          <button
            type="button"
            onClick={() => alert("Custom template editor lives at POST /api/outreach/templates -- inline editor lands in v9.4")}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/75 transition hover:border-indigo-400 hover:text-white"
          >
            + New template
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
          {templates.map((t) => (
            <article
              key={t.id}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-sm text-white/85"
            >
              <header className="mb-1 flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">{t.name}</h3>
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-white/55">
                  {t.use_case}
                </span>
              </header>
              <p className="text-xs text-white/55">slug: {t.slug}</p>
              {t.variables.length > 0 ? (
                <p className="mt-2 text-xs text-white/65">
                  variables: {t.variables.join(", ")}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      {/* Campaigns section -- progress bars for any campaign that's
          generated at least one draft. */}
      {campaigns.length > 0 ? (
        <section className="mt-12">
          <h2 className="mb-3 text-sm uppercase tracking-[0.22em] text-white/55">Campaigns</h2>
          <div className="space-y-3">
            {campaigns.map((c) => {
              const total = Math.max(1, c.recipients.length);
              const sent = c.drafts_sent;
              const approved = c.drafts_approved;
              const generated = c.drafts_generated;
              return (
                <article
                  key={c.id}
                  className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-sm text-white/85"
                >
                  <header className="mb-2 flex items-center justify-between">
                    <h3 className="text-sm font-medium text-white">{c.name}</h3>
                    <span className="text-[11px] text-white/55">
                      {c.status} - {formatAgo(c.created_at)}
                    </span>
                  </header>
                  <ProgressBar label="generated" value={generated} total={total} hue="indigo" />
                  <ProgressBar label="approved"  value={approved}  total={total} hue="amber" />
                  <ProgressBar label="sent"      value={sent}      total={total} hue="emerald" />
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {editing ? (
        <DraftEditor
          draft={editing}
          onClose={() => setEditing(null)}
          onSave={(patch) => patchDraft(editing.id, patch)}
          onSend={() => sendDraft(editing.id)}
          onRegenerate={() => regenerate(editing)}
          busy={busy}
        />
      ) : null}
    </section>
  );
}

type DraftColumnProps = {
  title: string;
  icon: React.ReactNode;
  drafts: OutreachDraft[];
  loading: boolean;
  onOpen: (d: OutreachDraft) => void;
  onApprove?: (d: OutreachDraft) => void;
  onSend?: (d: OutreachDraft) => void;
  onDiscard?: (d: OutreachDraft) => void;
  readOnly?: boolean;
};

function DraftColumn({
  title, icon, drafts, loading, onOpen, onApprove, onSend, onDiscard, readOnly,
}: DraftColumnProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-white/65">
          {icon} {title}
        </h2>
        <span className="text-[11px] text-white/45">{drafts.length}</span>
      </header>
      {loading ? (
        <p className="text-sm text-white/45">Loading...</p>
      ) : drafts.length === 0 ? (
        <p className="text-sm text-white/45">Nothing here yet.</p>
      ) : (
        <ul className="space-y-2">
          {drafts.map((d) => (
            <li
              key={d.id}
              className="rounded-lg border border-white/10 bg-black/20 p-3 transition hover:border-indigo-400/45"
            >
              <button
                type="button"
                onClick={() => onOpen(d)}
                className="block w-full text-left"
              >
                <p className="text-sm font-medium text-white">
                  {d.recipient.name || d.recipient.email}
                </p>
                <p className="text-xs text-white/55">{d.subject || "(no subject)"}</p>
                <p className="mt-1 text-[11px] text-white/45">
                  {d.recipient.email} - {formatAgo(d.sent_at || d.created_at)}
                </p>
              </button>
              {!readOnly ? (
                <div className="mt-2 flex items-center justify-end gap-1.5">
                  {onApprove ? (
                    <button
                      type="button"
                      onClick={() => onApprove(d)}
                      className="rounded-md border border-emerald-400/35 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-200 hover:bg-emerald-400/20"
                    >
                      Approve
                    </button>
                  ) : null}
                  {onSend ? (
                    <button
                      type="button"
                      onClick={() => onSend(d)}
                      className="rounded-md border border-indigo-400/45 bg-indigo-500/25 px-2 py-1 text-[11px] text-white hover:bg-indigo-500/40"
                    >
                      Send
                    </button>
                  ) : null}
                  {onDiscard ? (
                    <button
                      type="button"
                      onClick={() => onDiscard(d)}
                      className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-white/55 hover:border-rose-400/40 hover:text-rose-200"
                      aria-label="Discard"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </motion.section>
  );
}

function ProgressBar({
  label, value, total, hue,
}: { label: string; value: number; total: number; hue: "indigo" | "amber" | "emerald" }) {
  const pct = Math.min(100, Math.round((value / Math.max(1, total)) * 100));
  const hueClass =
    hue === "indigo" ? "bg-indigo-400/70" : hue === "amber" ? "bg-amber-400/70" : "bg-emerald-400/70";
  return (
    <div className="mb-1.5 last:mb-0">
      <div className="mb-0.5 flex items-center justify-between text-[11px] text-white/55">
        <span>{label}</span>
        <span>{value} / {total}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className={`h-full ${hueClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default Outreach;
