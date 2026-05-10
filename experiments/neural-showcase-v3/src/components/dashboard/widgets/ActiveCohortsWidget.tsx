// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface Att { id: string; phase?: string; }
interface Props { editMode?: boolean; onRemove?: () => void; }

const PHASES = ["intake", "design", "test", "deploy"] as const;

export function ActiveCohortsWidget({ editMode, onRemove }: Props) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/cohort/attendees`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { attendees?: Att[] };
      const att = Array.isArray(j.attendees) ? j.attendees : [];
      const c: Record<string, number> = {};
      for (const a of att) {
        const p = (a.phase ?? "intake").toLowerCase();
        c[p] = (c[p] ?? 0) + 1;
      }
      setCounts(c); setTotal(att.length);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Active cohorts" Icon={Users} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {total === 0 ? (
        <p className="text-ink-3">No active cohort.</p>
      ) : (
        <a href="/workshop/cohort" className="block rounded px-1.5 py-1 hover:bg-line/40">
          <div className="mb-2 text-[14px] text-ink">{total} attendees</div>
          <dl className="grid grid-cols-2 gap-1.5 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
            {PHASES.map((p) => (
              <div key={p} className="flex justify-between rounded border border-line/40 bg-bg-0/40 px-1.5 py-1">
                <dt>{p}</dt>
                <dd className="text-ink">{counts[p] ?? 0}</dd>
              </div>
            ))}
          </dl>
        </a>
      )}
    </WidgetFrame>
  );
}
