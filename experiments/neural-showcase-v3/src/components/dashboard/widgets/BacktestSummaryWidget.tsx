// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { LineChart } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface BTRow { agent_id: string; agent_name?: string; sharpe?: number; win_rate?: number; ran_at?: number; mocked?: boolean; }
interface Props { editMode?: boolean; onRemove?: () => void; }

const MOCK: BTRow[] = [
  { agent_id: "mr-01", agent_name: "Mean reversion (BTC/USDT)", sharpe: 1.42, win_rate: 0.58, ran_at: Date.now() - 1000 * 60 * 90, mocked: true },
  { agent_id: "mb-02", agent_name: "Momentum breakout (ETH)",   sharpe: 0.97, win_rate: 0.51, ran_at: Date.now() - 1000 * 60 * 60 * 4, mocked: true },
  { agent_id: "rv-03", agent_name: "Risk-vol scalper",          sharpe: 1.78, win_rate: 0.62, ran_at: Date.now() - 1000 * 60 * 60 * 19, mocked: true },
];

export function BacktestSummaryWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<BTRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      // Two-step: fetch agents, then last backtest per agent. Mock fallback when 404.
      const r = await fetch(`${API_BASE}/api/agents`);
      if (r.status === 404) {
        setItems(MOCK); setUpdatedAt(Date.now()); return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { agents?: { id: string; name?: string }[] };
      const agents = Array.isArray(j.agents) ? j.agents.slice(0, 3) : [];
      const rows: BTRow[] = [];
      for (const a of agents) {
        try {
          const rb = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(a.id)}/backtest/last`);
          if (rb.status === 404) continue;
          if (!rb.ok) continue;
          const jb = (await rb.json()) as { sharpe?: number; win_rate?: number; ran_at?: number };
          rows.push({ agent_id: a.id, agent_name: a.name, sharpe: jb.sharpe, win_rate: jb.win_rate, ran_at: jb.ran_at });
        } catch { /* per-agent failure non-fatal */ }
      }
      setItems(rows.length ? rows : MOCK);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Backtest summary" Icon={LineChart} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {items.length === 0 ? (
        <p className="text-ink-3">No backtests yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 3).map((b) => (
            <li key={b.agent_id} className="rounded border border-line/60 bg-bg-0/40 px-2 py-1.5">
              <div className="mb-1 flex items-baseline justify-between">
                <span className="truncate text-ink">{b.agent_name ?? b.agent_id}</span>
                {b.mocked ? <span className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-amber-400">mock</span> : null}
              </div>
              <div className="flex gap-4 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-3">
                <span>Sharpe <span className="text-ink">{b.sharpe?.toFixed(2) ?? "-"}</span></span>
                <span>Win <span className="text-ink">{b.win_rate ? `${(b.win_rate * 100).toFixed(0)}%` : "-"}</span></span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
