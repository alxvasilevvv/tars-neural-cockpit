// SYNC: claude-w80-fe-only
/**
 * <ComplianceLog /> — Wave 80-D
 *
 * Receipts feed table. Each row is a signed action from any agent in
 * the org: time, actor, action, resource, $-impact, signature
 * verified ✓/✗.  Designed to be drop-in for the Compliance route but
 * also reusable on a future per-agent `/agents/{id}/audit` panel.
 *
 * Filters live in <Compliance />; this component is purely
 * presentation. Click a row to expand JSON in-place — handy when an
 * auditor asks "what exactly did this action do?" and we don't want
 * a separate dialog.
 */

import { Fragment, useState } from "react";
import { ChevronRight, ShieldCheck, ShieldAlert } from "lucide-react";

export interface AuditRow {
  id: string;
  ts: number;
  actor: string;
  /** e.g. "playbook.run", "agent.score", "wallet.spend". */
  action: string;
  /** Free-form resource identifier — agent id, file path, ticker. */
  resource: string;
  /** Negative for spends, positive for credits, 0 for read-only. */
  cost_usd: number;
  /** Whether the receipt's ed25519 signature verifies against the
   *  recorded org pubkey. Comes from /api/audit/list. */
  sig_verified: boolean;
  /** Full JSON payload — shown when row is expanded. */
  payload?: Record<string, unknown>;
}

interface ComplianceLogProps {
  rows: AuditRow[];
  /** Loading flag for skeleton rendering. */
  loading?: boolean;
}

function fmtTime(ts: number): string {
  const d = new Date(ts);
  const today = new Date();
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();
  if (sameDay) return d.toLocaleTimeString();
  return d.toLocaleDateString() + " " + d.toLocaleTimeString();
}

export function ComplianceLog({ rows, loading = false }: ComplianceLogProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-6 text-center font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
        loading receipts…
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className="rounded-[12px] border border-dashed border-line/60 bg-bg-1/30 p-8 text-center">
        <p className="font-display text-[14px] text-ink">
          No receipts in the selected window.
        </p>
        <p className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink-3">
          Loosen the filters or check a wider time range.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[12px] border border-line/60 bg-bg-1/40">
      <table className="w-full border-collapse text-left">
        <thead className="bg-bg-2/40">
          <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
            <th className="px-3 py-2"></th>
            <th className="px-3 py-2">time</th>
            <th className="px-3 py-2">actor</th>
            <th className="px-3 py-2">action</th>
            <th className="px-3 py-2">resource</th>
            <th className="px-3 py-2 text-right">$</th>
            <th className="px-3 py-2 text-center">sig</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isOpen = expanded === r.id;
            return (
              <Fragment key={r.id}>
                <tr
                  onClick={() => setExpanded(isOpen ? null : r.id)}
                  className="cursor-pointer border-b border-line/20 font-mono-tech text-[11.5px] text-ink-2 transition-colors last:border-0 hover:bg-bg-2/40"
                >
                  <td className="px-3 py-1.5">
                    <ChevronRight
                      size={11}
                      strokeWidth={1.7}
                      aria-hidden
                      className={`text-ink-3 transition-transform ${
                        isOpen ? "rotate-90" : ""
                      }`}
                    />
                  </td>
                  <td className="px-3 py-1.5 whitespace-nowrap text-ink-3">
                    {fmtTime(r.ts)}
                  </td>
                  <td className="px-3 py-1.5 truncate max-w-[140px]">
                    {r.actor}
                  </td>
                  <td className="px-3 py-1.5">
                    <span
                      className="font-mono-tech text-[10.5px] uppercase tracking-[1.6px]"
                      style={{ color: actionAccent(r.action) }}
                    >
                      {r.action}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 truncate max-w-[280px] text-ink-3">
                    {r.resource}
                  </td>
                  <td
                    className="px-3 py-1.5 text-right font-mono-tech text-[11px]"
                    style={{
                      color:
                        r.cost_usd > 0
                          ? "var(--brand-amber)"
                          : r.cost_usd < 0
                            ? "var(--color-success)"
                            : "var(--color-ink-3)",
                    }}
                  >
                    {r.cost_usd === 0
                      ? "—"
                      : `${r.cost_usd > 0 ? "+" : ""}$${Math.abs(r.cost_usd).toFixed(3)}`}
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    {r.sig_verified ? (
                      <ShieldCheck
                        size={13}
                        strokeWidth={1.7}
                        aria-label="signature verified"
                        style={{ color: "var(--color-success)" }}
                      />
                    ) : (
                      <ShieldAlert
                        size={13}
                        strokeWidth={1.7}
                        aria-label="signature INVALID"
                        className="text-rose-300"
                      />
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="bg-bg-0/40">
                    <td colSpan={7} className="px-4 py-3">
                      <pre className="max-h-72 overflow-auto rounded-md border border-line/40 bg-bg-1/60 p-3 font-mono-tech text-[10.5px] leading-[1.55] text-ink-2">
{JSON.stringify(r.payload ?? r, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function actionAccent(action: string): string {
  if (action.startsWith("wallet")) return "var(--brand-amber)";
  if (action.startsWith("agent")) return "var(--brand-violet)";
  if (action.startsWith("playbook")) return "var(--brand-indigo)";
  if (action.startsWith("policy")) return "var(--color-alert)";
  return "var(--color-accent)";
}

export default ComplianceLog;
