// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Workflow } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface Run { id: string; playbook_id: string; ok?: boolean; ran_at?: number; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function PlaybookRunsWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/playbooks/runs?limit=5`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { runs?: Run[] };
      setItems(Array.isArray(j.runs) ? j.runs : []);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Recent playbook runs" Icon={Workflow} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {items.length === 0 ? (
        <p className="text-ink-3">No recent runs.</p>
      ) : (
        <ul className="space-y-1">
          {items.slice(0, 5).map((r) => {
            const when = r.ran_at ? new Date(r.ran_at * (r.ran_at > 1e12 ? 1 : 1000)).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
            return (
              <li key={r.id}>
                <a href="/cockpit/planner" className="flex items-center justify-between rounded px-1.5 py-1 hover:bg-line/40">
                  <span className="flex items-center gap-2">
                    <span className={`h-1.5 w-1.5 rounded-full ${r.ok === false ? "bg-red-500" : "bg-emerald-500"}`} />
                    <span className="truncate text-ink">{r.playbook_id}</span>
                  </span>
                  <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{when}</span>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </WidgetFrame>
  );
}
