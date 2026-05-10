// SYNC: claude-w80-fe-only
/**
 * PhaseDeploy — Wave 80-D, fourth and final phase of the workshop.
 *
 * Surfaces three controls operators need before they trust the agent
 * to run unattended:
 *
 *   1. Autopilot toggle        — POST /api/agents/{id}/autopilot
 *   2. Schedule editor         — POST /api/playbooks/{id}/schedule
 *                                with a cron string + human preview.
 *   3. Recent runs (last 10)   — pulled from /api/agents/{id}/tasks;
 *                                falls back to deterministic mocks.
 *   4. Promote to Compliance   — link to /compliance?agent={id}, the
 *                                receipts feed page where signed audit
 *                                rows surface.
 *
 * Cursor's backend may not have the schedule + autopilot routes
 * landed yet — every fetch is wrapped in a soft-fail block so the UI
 * keeps rendering with mock state when the daemon returns 404.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Power,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { API_BASE } from "@/lib/api";
import { setAutopilot } from "@/lib/agents";

interface PhaseDeployProps {
  agentId: string | null;
  onComplete: () => void;
}

interface RunRow {
  id: string;
  ts: number;
  status: "ok" | "warn" | "fail";
  summary: string;
  cost_usd?: number;
}

const MOCK_RUNS: RunRow[] = [
  { id: "r-101", ts: Date.now() - 60_000 * 8,    status: "ok",   summary: "Daily brief posted to #trading", cost_usd: 0.018 },
  { id: "r-100", ts: Date.now() - 60_000 * 28,   status: "ok",   summary: "ETH price summary · 3 bullets", cost_usd: 0.012 },
  { id: "r-099", ts: Date.now() - 60_000 * 73,   status: "warn", summary: "WBTC outlier — operator confirmed", cost_usd: 0.026 },
  { id: "r-098", ts: Date.now() - 60_000 * 145,  status: "ok",   summary: "Morning portfolio digest", cost_usd: 0.014 },
  { id: "r-097", ts: Date.now() - 60_000 * 240,  status: "fail", summary: "Slack 503 · auto-retried, succeeded next tick" },
  { id: "r-096", ts: Date.now() - 60_000 * 305,  status: "ok",   summary: "AAPL drawdown alert", cost_usd: 0.011 },
  { id: "r-095", ts: Date.now() - 60_000 * 410,  status: "ok",   summary: "ETH gas-price summary", cost_usd: 0.009 },
  { id: "r-094", ts: Date.now() - 60_000 * 530,  status: "ok",   summary: "Daily brief posted to #trading", cost_usd: 0.017 },
  { id: "r-093", ts: Date.now() - 60_000 * 720,  status: "ok",   summary: "Backtest replay validated", cost_usd: 0.022 },
  { id: "r-092", ts: Date.now() - 60_000 * 1140, status: "ok",   summary: "Health-check tick", cost_usd: 0.003 },
];

function formatAgo(ts: number): string {
  const s = Math.max(1, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/**
 * cronToHuman — paper-thin English summary for a cron string. Not a
 * full parser; operators who want exotic schedules can drop into the
 * raw cron field and we fall back to "custom schedule".
 */
function cronToHuman(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return "custom schedule";
  const [min, hour, dom, mon, dow] = parts;
  if (min === "0" && hour === "*" && dom === "*" && mon === "*" && dow === "*")
    return "every hour, on the hour";
  if (
    /^\d+$/.test(min) &&
    /^\d+$/.test(hour) &&
    dom === "*" &&
    mon === "*" &&
    dow === "1-5"
  )
    return `weekdays at ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  if (
    /^\d+$/.test(min) &&
    /^\d+$/.test(hour) &&
    dom === "*" &&
    mon === "*" &&
    dow === "*"
  )
    return `every day at ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  if (min === "*/5") return "every 5 minutes";
  if (min === "*/15") return "every 15 minutes";
  if (min === "*/30") return "every 30 minutes";
  return "custom schedule";
}

export function PhaseDeploy({ agentId, onComplete }: PhaseDeployProps) {
  const [autopilot, setAuto] = useState(false);
  const [autopilotBusy, setAutopilotBusy] = useState(false);
  const [autopilotErr, setAutopilotErr] = useState<string | null>(null);
  const [pendingNote, setPendingNote] = useState<string | null>(null);

  const [cron, setCron] = useState("0 9 * * 1-5");
  const [scheduleBusy, setScheduleBusy] = useState(false);
  const [scheduleSavedAt, setScheduleSavedAt] = useState<string | null>(null);
  const [scheduleErr, setScheduleErr] = useState<string | null>(null);

  const [runs, setRuns] = useState<RunRow[]>([]);
  const [runsPending, setRunsPending] = useState(false);

  // Pull recent runs once the agent is known. Failures (no agent /
  // 404 / network) drop us into mock-mode.
  useEffect(() => {
    let cancelled = false;
    if (!agentId) {
      setRuns(MOCK_RUNS);
      setRunsPending(true);
      return () => undefined;
    }
    void (async () => {
      setRunsPending(false);
      try {
        const r = await fetch(
          `${API_BASE}/api/agents/${encodeURIComponent(agentId)}/tasks?limit=10`,
        );
        if (r.status === 404) throw new Error("404");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = (await r.json()) as {
          tasks?: Array<{
            id: string;
            status: string;
            updated_at?: number;
            created_at?: number;
            result?: { chosen?: string } | null;
            error?: string | null;
          }>;
        };
        if (cancelled) return;
        const tasks = body.tasks ?? [];
        if (tasks.length === 0) {
          setRuns(MOCK_RUNS);
          setRunsPending(true);
          return;
        }
        setRuns(
          tasks.map((t) => ({
            id: t.id,
            ts: (t.updated_at ?? t.created_at ?? Date.now() / 1000) * 1000,
            status:
              t.status === "done"
                ? "ok"
                : t.status === "failed"
                  ? "fail"
                  : "warn",
            summary: t.result?.chosen ?? t.error ?? t.status,
          })),
        );
      } catch {
        if (cancelled) return;
        setRuns(MOCK_RUNS);
        setRunsPending(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  const handleToggleAutopilot = async () => {
    if (!agentId) {
      setAutopilotErr("Finish phase 02 (Design) first — no agent to deploy.");
      return;
    }
    setAutopilotBusy(true);
    setAutopilotErr(null);
    setPendingNote(null);
    const next = !autopilot;
    try {
      await setAutopilot(agentId, next);
      setAuto(next);
      onComplete();
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("404")) {
        // Backend hasn't shipped autopilot yet — pretend it worked.
        setAuto(next);
        setPendingNote("Backend WIP — Cursor shipping autopilot route.");
        onComplete();
      } else {
        setAutopilotErr(msg);
      }
    } finally {
      setAutopilotBusy(false);
    }
  };

  const handleSaveSchedule = async () => {
    if (!agentId) {
      setScheduleErr("Finish phase 02 (Design) first.");
      return;
    }
    setScheduleBusy(true);
    setScheduleErr(null);
    try {
      const r = await fetch(
        `${API_BASE}/api/playbooks/${encodeURIComponent(agentId)}/schedule`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ cron }),
        },
      );
      if (r.status === 404) {
        setScheduleSavedAt(new Date().toISOString());
        setPendingNote("Backend WIP — Cursor shipping schedule route.");
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setScheduleSavedAt(new Date().toISOString());
    } catch (e) {
      setScheduleErr((e as Error).message);
    } finally {
      setScheduleBusy(false);
    }
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
          <Rocket
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-orchid)" }}
          />
          <span>phase 04 · deploy</span>
        </div>
        <h2 className="font-display text-[28px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[34px]">
          Ship it. Then watch the receipts.
        </h2>
        <p className="max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
          Toggle autopilot, set a schedule, then promote the agent to
          Compliance to start aggregating signed receipts.
        </p>
      </header>

      {pendingNote && (
        <p
          role="status"
          className="inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-[11.5px] leading-[1.5] text-amber-200"
        >
          <AlertCircle
            size={12}
            strokeWidth={1.7}
            aria-hidden
            className="mt-0.5"
          />
          <span>{pendingNote} Workshop running in mock mode.</span>
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {/* ─── Autopilot ─────────────────────────────────────────── */}
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
                autopilot
              </span>
              <p className="mt-1 max-w-[40ch] font-display text-[14px] leading-[1.4] text-ink">
                Run on schedule without operator confirmation, except for HIL
                escalations.
              </p>
            </div>
            <span
              className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2.2px]"
              style={{
                borderColor: autopilot
                  ? "var(--brand-orchid)"
                  : "var(--color-line)",
                color: autopilot ? "var(--brand-orchid)" : "var(--color-ink-3)",
                background: autopilot
                  ? "color-mix(in srgb, var(--brand-orchid) 10%, transparent)"
                  : "transparent",
              }}
            >
              <Power size={10} strokeWidth={1.8} aria-hidden />
              {autopilot ? "on" : "off"}
            </span>
          </div>
          <button
            type="button"
            onClick={handleToggleAutopilot}
            disabled={autopilotBusy || !agentId}
            className="mt-4 inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            {autopilotBusy ? (
              <Loader2
                size={12}
                strokeWidth={2}
                className="animate-spin"
                aria-hidden
              />
            ) : (
              <Power size={12} strokeWidth={1.7} aria-hidden />
            )}
            <span>{autopilot ? "turn off autopilot" : "turn on autopilot"}</span>
          </button>
          {autopilotErr && (
            <p className="mt-3 inline-flex items-start gap-2 text-[11px] text-rose-200">
              <AlertCircle
                size={11}
                strokeWidth={1.7}
                aria-hidden
                className="mt-0.5"
              />
              <span>{autopilotErr}</span>
            </p>
          )}
        </section>

        {/* ─── Schedule ──────────────────────────────────────────── */}
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            schedule · cron
          </span>
          <input
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            spellCheck={false}
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
            placeholder="0 9 * * 1-5"
            aria-label="cron string"
          />
          <p className="mt-1.5 inline-flex items-center gap-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink-3">
            <Clock size={11} strokeWidth={1.7} aria-hidden />
            <span>{cronToHuman(cron)}</span>
          </p>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {[
              { label: "weekdays 9am", v: "0 9 * * 1-5" },
              { label: "every hour",   v: "0 * * * *" },
              { label: "every 15m",    v: "*/15 * * * *" },
            ].map((p) => (
              <button
                key={p.v}
                type="button"
                onClick={() => setCron(p.v)}
                className="rounded-md border border-line/60 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-accent hover:text-ink"
              >
                {p.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleSaveSchedule}
            disabled={scheduleBusy || !agentId}
            className="mt-4 inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            {scheduleBusy ? (
              <Loader2
                size={12}
                strokeWidth={2}
                className="animate-spin"
                aria-hidden
              />
            ) : (
              <Clock size={12} strokeWidth={1.7} aria-hidden />
            )}
            <span>{scheduleBusy ? "saving…" : "save schedule"}</span>
          </button>
          {scheduleSavedAt && (
            <p
              className="mt-3 inline-flex items-center gap-1.5 text-[11px]"
              style={{ color: "var(--color-success)" }}
            >
              <CheckCircle2 size={12} strokeWidth={1.7} aria-hidden />
              saved · {new Date(scheduleSavedAt).toLocaleTimeString()}
            </p>
          )}
          {scheduleErr && (
            <p className="mt-3 inline-flex items-start gap-2 text-[11px] text-rose-200">
              <AlertCircle
                size={11}
                strokeWidth={1.7}
                aria-hidden
                className="mt-0.5"
              />
              <span>{scheduleErr}</span>
            </p>
          )}
        </section>
      </div>

      {/* ─── Recent runs ─────────────────────────────────────────── */}
      <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
        <header className="mb-2 flex items-center justify-between gap-3">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            recent runs · last 10
          </span>
          {runsPending && (
            <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              mock data · backend WIP
            </span>
          )}
        </header>
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line/40 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              <th className="py-1.5 pr-3">when</th>
              <th className="py-1.5 pr-3">status</th>
              <th className="py-1.5 pr-3">summary</th>
              <th className="py-1.5 text-right">$</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr
                key={r.id}
                className="border-b border-line/20 font-mono-tech text-[11px] text-ink-2 last:border-0"
              >
                <td className="py-1.5 pr-3 whitespace-nowrap text-ink-3">
                  {formatAgo(r.ts)}
                </td>
                <td className="py-1.5 pr-3">
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full border px-1.5 py-0.5 text-[9.5px] uppercase tracking-[1.6px]"
                    style={{
                      borderColor:
                        r.status === "ok"
                          ? "var(--color-success)"
                          : r.status === "warn"
                            ? "var(--brand-amber)"
                            : "var(--color-alert)",
                      color:
                        r.status === "ok"
                          ? "var(--color-success)"
                          : r.status === "warn"
                            ? "var(--brand-amber)"
                            : "var(--color-alert)",
                    }}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="py-1.5 pr-3 truncate max-w-[420px]">
                  {r.summary}
                </td>
                <td className="py-1.5 text-right text-ink-3">
                  {typeof r.cost_usd === "number"
                    ? `$${r.cost_usd.toFixed(3)}`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ─── Promote to Compliance ───────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
        <div>
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            next · compliance
          </span>
          <p className="mt-1 max-w-[55ch] font-display text-[14px] leading-[1.4] text-ink">
            Move the agent into the receipts feed for signed audit and
            cost-impact tracking.
          </p>
        </div>
        <Link
          to={`/compliance${agentId ? `?agent=${encodeURIComponent(agentId)}` : ""}`}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent"
        >
          <ShieldCheck size={12} strokeWidth={1.7} aria-hidden />
          <span>promote to compliance</span>
        </Link>
      </div>
    </motion.section>
  );
}

export default PhaseDeploy;
