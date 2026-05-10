// SYNC: claude-w80-fe-only
/**
 * PhaseTest — backtest the agent against historical CSV.
 *
 * Operator drops a CSV (or pastes content). We POST to
 * /api/agents/{id}/backtest; backend returns rows with expected vs.
 * actual + an aggregate agreement rate. We render a compact bar +
 * surface diverging rows (agreed=false) for review.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FlaskConical, Loader2, Play, Upload, AlertCircle } from "lucide-react";
import {
  backtestAgent,
  MOCK_BACKTEST,
  type BacktestResult,
} from "@/lib/workshop";

interface PhaseTestProps {
  agentId: string | null;
  onComplete: (result: BacktestResult) => void;
}

const SAMPLE_CSV = `ticker,t,expected
AAPL,09:00,buy
WBTC,09:05,hold
ETH,09:10,sell
SOL,09:15,hold
AAPL,10:00,hold`;

export function PhaseTest({ agentId, onComplete }: PhaseTestProps) {
  const [csv, setCsv] = useState<string>(SAMPLE_CSV);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [pendingNote, setPendingNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setResult(null);
    setPendingNote(null);
    setErr(null);
  }, [agentId]);

  const handleRun = async () => {
    if (!agentId) {
      setErr("No agent selected — finish phase 02 (Design) first.");
      return;
    }
    setBusy(true);
    setErr(null);
    setPendingNote(null);
    try {
      const out = await backtestAgent(agentId, csv);
      if (out.pending) {
        setPendingNote(out.reason);
        const fake = { ...MOCK_BACKTEST, agent_id: agentId };
        setResult(fake);
        onComplete(fake);
      } else {
        setResult(out.value);
        onComplete(out.value);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleFile = async (file: File) => {
    const text = await file.text();
    setCsv(text);
  };

  return (
    <motion.section
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="grid gap-6"
    >
      <header className="grid gap-2">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <FlaskConical
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-cyan)" }}
          />
          <span>phase 03 · test</span>
        </div>
        <h2 className="font-display text-[28px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[34px]">
          Backtest before you trust autopilot.
        </h2>
        <p className="max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
          Drop a CSV of historical inputs + expected decisions. We replay the
          agent and surface every row where it disagreed with you.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-[1fr_280px]">
        <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              CSV input
            </span>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line/60 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-accent">
              <Upload size={10} strokeWidth={1.8} aria-hidden />
              <span>load file</span>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleFile(f);
                }}
                className="hidden"
              />
            </label>
          </div>
          <textarea
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
            rows={10}
            spellCheck={false}
            className="w-full resize-y rounded-md border border-line/40 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
              {agentId ? `agent · ${agentId.slice(0, 12)}…` : "no agent"}
            </span>
            <button
              type="button"
              onClick={handleRun}
              disabled={busy || !csv.trim()}
              className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:border-accent disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={11} strokeWidth={2} className="animate-spin" aria-hidden />
              ) : (
                <Play size={11} strokeWidth={1.8} aria-hidden />
              )}
              <span>{busy ? "running…" : "run backtest"}</span>
            </button>
          </div>
          {err && (
            <p className="mt-3 inline-flex items-start gap-2 rounded-md border border-rose-400/30 bg-rose-400/[0.06] px-2.5 py-1.5 text-[11px] leading-[1.5] text-rose-200">
              <AlertCircle size={11} strokeWidth={1.7} aria-hidden className="mt-0.5" />
              <span>{err}</span>
            </p>
          )}
          {pendingNote && (
            <p className="mt-3 inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-2.5 py-1.5 text-[11px] leading-[1.5] text-amber-200">
              <AlertCircle size={11} strokeWidth={1.7} aria-hidden className="mt-0.5" />
              <span>{pendingNote} Workshop UI works in mock mode.</span>
            </p>
          )}
        </div>

        <aside className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            Result
          </span>
          {!result ? (
            <p className="mt-3 font-mono-tech text-[11px] text-ink-3">
              run a backtest to see the agreement rate and diverging rows.
            </p>
          ) : (
            <>
              <div className="mt-3">
                <div className="flex items-baseline gap-2">
                  <span
                    className="font-display text-[34px] leading-none text-ink"
                    style={{ color: "var(--brand-cyan)" }}
                  >
                    {Math.round(result.agreement_rate * 100)}%
                  </span>
                  <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                    agreement
                  </span>
                </div>
                <p className="mt-1 font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink-3">
                  {result.agreed} / {result.total} rows
                </p>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full border border-line/40 bg-bg-0/60">
                <div
                  className="h-full"
                  style={{
                    width: `${Math.round(result.agreement_rate * 100)}%`,
                    background:
                      "linear-gradient(90deg, var(--brand-indigo), var(--brand-cyan))",
                  }}
                />
              </div>
            </>
          )}
        </aside>
      </div>

      {result && (
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <header className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            Diverging rows · {result.rows.filter((r) => !r.agreed).length}
          </header>
          {result.rows.filter((r) => !r.agreed).length === 0 ? (
            <p className="font-mono-tech text-[10.5px] text-ink-3">
              no divergence — agent matched expected on every row.
            </p>
          ) : (
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
                  <th className="py-1.5 pr-3">#</th>
                  <th className="py-1.5 pr-3">input</th>
                  <th className="py-1.5 pr-3">expected</th>
                  <th className="py-1.5">actual</th>
                </tr>
              </thead>
              <tbody>
                {result.rows
                  .filter((r) => !r.agreed)
                  .map((r) => (
                    <tr
                      key={r.index}
                      className="border-b border-line/20 font-mono-tech text-[11px] text-ink-2 last:border-0"
                    >
                      <td className="py-1.5 pr-3 text-ink-3">{r.index}</td>
                      <td className="py-1.5 pr-3 truncate max-w-[260px]">
                        {JSON.stringify(r.input)}
                      </td>
                      <td className="py-1.5 pr-3" style={{ color: "var(--brand-cyan)" }}>
                        {r.expected}
                      </td>
                      <td className="py-1.5 text-rose-300">{r.actual}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </motion.section>
  );
}
