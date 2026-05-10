// SYNC: claude-w104-fe
/**
 * <ExportBundleDialog /> — Wave 104
 *
 * Modal dialog for kicking off an audit-grade compliance bundle.
 * Date range pickers + scope checkboxes + redact-PII toggle. POSTs
 * to /api/compliance/export/bundle. HIL-gated: a 412/428 response
 * is surfaced verbatim so the caller can mint a confirm token in
 * the cockpit and retry.
 */

import { useId, useState } from "react";
import { Loader2, ShieldCheck, X } from "lucide-react";
import { API_BASE } from "@/lib/api";

const SCOPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "receipts", label: "receipts (chain + merkle)" },
  { value: "cohort", label: "cohort + attendees" },
  { value: "connectors", label: "connector activity" },
  { value: "hil", label: "HIL approval log" },
  { value: "outreach", label: "outreach drafts/sends" },
  { value: "files", label: "files manifest" },
  { value: "wallet", label: "wallet audit" },
  { value: "org", label: "org info + invites" },
  { value: "playbooks", label: "playbook runs" },
  { value: "agents", label: "agent definitions" },
  { value: "webhooks", label: "webhooks in/out" },
  { value: "blobs", label: "include file BLOBS (large)" },
];

const ALL_DEFAULT = SCOPE_OPTIONS
  .map((o) => o.value)
  .filter((v) => v !== "blobs");

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoIso(n: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

export interface ExportBundleDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (bundle: { id: string; output_path: string }) => void;
}

export function ExportBundleDialog({
  open,
  onClose,
  onCreated,
}: ExportBundleDialogProps) {
  const titleId = useId();
  const [since, setSince] = useState<string>(daysAgoIso(30));
  const [until, setUntil] = useState<string>(todayIso());
  const [scope, setScope] = useState<string[]>(ALL_DEFAULT);
  const [redact, setRedact] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<{ id: string; path: string } | null>(null);

  if (!open) return null;

  const toggleScope = (val: string) => {
    setScope((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val],
    );
  };

  const handleGenerate = async () => {
    setBusy(true);
    setErr(null);
    setDone(null);
    try {
      const r = await fetch(`${API_BASE}/api/compliance/export/bundle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          since,
          until,
          scope,
          redact_pii: redact,
        }),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "");
        throw new Error(`HTTP ${r.status} ${text || r.statusText}`);
      }
      const json = (await r.json()) as { id: string; output_path: string };
      setDone({ id: json.id, path: json.output_path });
      onCreated?.(json);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-[640px] rounded-[14px] border border-line/70 bg-bg-1 p-6 shadow-2xl">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              wave 104 — audit bundle
            </p>
            <h2
              id={titleId}
              className="mt-1 font-display text-[20px] leading-tight text-ink"
            >
              Generate compliance export
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="close"
            className="rounded-md p-1 text-ink-3 transition-colors hover:text-ink"
          >
            <X size={16} strokeWidth={1.7} />
          </button>
        </header>

        <div className="grid gap-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1.5">
              <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
                since
              </span>
              <input
                type="date"
                value={since}
                onChange={(e) => setSince(e.target.value)}
                className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
              />
            </label>
            <label className="grid gap-1.5">
              <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
                until
              </span>
              <input
                type="date"
                value={until}
                onChange={(e) => setUntil(e.target.value)}
                className="rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
              />
            </label>
          </div>

          <fieldset className="grid gap-2 rounded-[10px] border border-line/60 bg-bg-0/30 p-3">
            <legend className="px-1 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              scope
            </legend>
            <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
              {SCOPE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-2 font-mono-tech text-[11.5px] text-ink-2"
                >
                  <input
                    type="checkbox"
                    checked={scope.includes(opt.value)}
                    onChange={() => toggleScope(opt.value)}
                    className="accent-[color:var(--color-accent)]"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="flex items-center justify-between rounded-[10px] border border-line/60 bg-bg-0/30 px-4 py-3">
            <div>
              <p className="font-mono-tech text-[11.5px] text-ink">
                Redact PII before export
              </p>
              <p className="mt-0.5 font-mono-tech text-[10px] text-ink-3">
                emails / phones / IPs / cards → [REDACTED:type:hash]
              </p>
            </div>
            <input
              type="checkbox"
              checked={redact}
              onChange={(e) => setRedact(e.target.checked)}
              className="h-4 w-4 accent-[color:var(--color-accent)]"
            />
          </label>

          {err && (
            <p
              role="alert"
              className="rounded-md border border-red-400/40 bg-red-500/[0.06] px-3 py-2 font-mono-tech text-[11px] text-red-200"
            >
              {err}
            </p>
          )}

          {done && (
            <p
              role="status"
              className="rounded-md border border-emerald-400/40 bg-emerald-500/[0.06] px-3 py-2 font-mono-tech text-[11px] text-emerald-200"
            >
              bundle generated · id: {done.id}
              <br />
              path: {done.path}
            </p>
          )}

          <div className="mt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-line/60 bg-bg-2/40 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 transition-colors hover:border-line-strong"
            >
              cancel
            </button>
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={busy || scope.length === 0 || !since || !until}
              className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-accent/15 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:bg-accent/25 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={12} strokeWidth={1.7} className="animate-spin" aria-hidden />
              ) : (
                <ShieldCheck size={12} strokeWidth={1.7} aria-hidden />
              )}
              {busy ? "generating…" : "generate"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExportBundleDialog;
