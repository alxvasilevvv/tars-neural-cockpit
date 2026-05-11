/**
 * ExportBundleSection — Wave 124 split out of /pages/Compliance.tsx
 * (was 797 LOC). Wave 104 audit-grade export bundle UI: list bundles,
 * generate new ones, verify signature/chain integrity.
 *
 * Pure refactor — no behavior change.
 */

import { useState } from "react";
import { Download, ShieldCheck } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { ExportBundleDialog } from "@/components/compliance/ExportBundleDialog";

interface BundleRow {
  id: string;
  started_at: number;
  completed_at?: number;
  since_iso: string;
  until_iso: string;
  output_path: string;
  status: string;
  manifest_hash: string;
  file_count: number;
  total_bytes: number;
  redacted: boolean;
  scope: string[];
}

interface VerifyResult {
  ok: boolean;
  signature_valid: boolean;
  file_count: number;
  manifest_hash: string;
  chain: { ok: boolean };
  errors?: string[];
}

function ExportBundleSection() {
  const [open, setOpen] = useState(false);
  const [bundles, setBundles] = useState<BundleRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/api/compliance/export/bundles`);
      if (!r.ok) {
        setBundles([]);
        return;
      }
      const j = await r.json();
      setBundles(Array.isArray(j.bundles) ? j.bundles : []);
    } catch {
      setBundles([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const handleVerify = async (file: File) => {
    setVerifyBusy(true);
    setVerifyResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${API_BASE}/api/compliance/export/verify`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as VerifyResult;
      setVerifyResult(j);
    } catch (e) {
      setVerifyResult({
        ok: false,
        signature_valid: false,
        file_count: 0,
        manifest_hash: "",
        chain: { ok: false },
        errors: [e instanceof Error ? e.message : String(e)],
      });
    } finally {
      setVerifyBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`delete bundle ${id}?`)) return;
    await fetch(`${API_BASE}/api/compliance/export/bundles/${id}`, {
      method: "DELETE",
    });
    void refresh();
  };

  return (
    <section
      aria-labelledby="export-bundle-heading"
      className="grid gap-4 rounded-[12px] border border-line/60 bg-bg-1/40 p-4"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            wave 104
          </p>
          <h3
            id="export-bundle-heading"
            className="mt-1 font-display text-[16px] leading-tight text-ink"
          >
            Audit-grade export bundle
          </h3>
          <p className="mt-1 font-mono-tech text-[10.5px] text-ink-3">
            single tarball with chain proof + signature for any auditor
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-accent/15 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:bg-accent/25"
        >
          <ShieldCheck size={12} strokeWidth={1.7} aria-hidden />
          generate bundle
        </button>
      </header>

      {/* Past exports table */}
      <div className="rounded-[10px] border border-line/60 bg-bg-0/30 p-3">
        <p className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
          past exports {loading ? "(loading…)" : `(${bundles.length})`}
        </p>
        {bundles.length === 0 ? (
          <p className="font-mono-tech text-[11px] text-ink-3">
            no exports yet
          </p>
        ) : (
          <table className="w-full font-mono-tech text-[11px]">
            <thead className="text-ink-3">
              <tr className="text-left">
                <th className="py-1 pr-2">id</th>
                <th className="py-1 pr-2">window</th>
                <th className="py-1 pr-2">files</th>
                <th className="py-1 pr-2">bytes</th>
                <th className="py-1 pr-2">redacted</th>
                <th className="py-1">actions</th>
              </tr>
            </thead>
            <tbody className="text-ink-2">
              {bundles.map((b) => (
                <tr key={b.id} className="border-t border-line/40">
                  <td className="py-1.5 pr-2 text-ink">{b.id}</td>
                  <td className="py-1.5 pr-2">
                    {b.since_iso.slice(0, 10)} → {b.until_iso.slice(0, 10)}
                  </td>
                  <td className="py-1.5 pr-2">{b.file_count}</td>
                  <td className="py-1.5 pr-2">
                    {(b.total_bytes / 1024).toFixed(1)} KB
                  </td>
                  <td className="py-1.5 pr-2">{b.redacted ? "yes" : "no"}</td>
                  <td className="py-1.5 flex gap-2">
                    <a
                      href={`${API_BASE}/api/compliance/export/bundles/${b.id}/download`}
                      className="text-ink underline-offset-2 hover:underline"
                    >
                      download
                    </a>
                    <button
                      type="button"
                      onClick={() => void handleDelete(b.id)}
                      className="text-red-300 hover:underline"
                    >
                      delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Verify external bundle */}
      <div className="rounded-[10px] border border-line/60 bg-bg-0/30 p-3">
        <p className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
          verify external bundle (auditor mode)
        </p>
        <input
          type="file"
          accept=".tar.gz,application/gzip"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleVerify(f);
          }}
          disabled={verifyBusy}
          className="font-mono-tech text-[11px] text-ink-2"
        />
        {verifyBusy && (
          <p className="mt-2 font-mono-tech text-[11px] text-ink-3">
            verifying…
          </p>
        )}
        {verifyResult && (
          <pre
            className="mt-2 max-h-48 overflow-auto rounded border border-line/60 bg-bg-0/60 p-2 font-mono-tech text-[10.5px]"
            style={{
              color: verifyResult.ok ? "var(--color-success)" : "var(--brand-amber)",
            }}
          >
            {JSON.stringify(verifyResult, null, 2)}
          </pre>
        )}
      </div>

      <ExportBundleDialog
        open={open}
        onClose={() => setOpen(false)}
        onCreated={() => {
          setOpen(false);
          void refresh();
        }}
      />
    </section>
  );
}

export default ExportBundleSection;
