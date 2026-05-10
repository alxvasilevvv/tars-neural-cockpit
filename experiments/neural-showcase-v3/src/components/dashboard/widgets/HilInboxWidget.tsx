// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface Pending { token: string; action_id: string; created_at: number; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function HilInboxWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<Pending[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      // /api/policy/pending is the canonical Wave 76 endpoint; /confirm/queue
      // is an alias kept in older surfaces. Prefer /pending.
      const r = await fetch(`${API_BASE}/api/policy/pending`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { pending?: Pending[] };
      setItems(Array.isArray(j.pending) ? j.pending : []);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="HIL inbox" Icon={ShieldAlert} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      <a href="/cockpit/policy" className="block rounded px-1.5 py-1 hover:bg-line/40">
        <div className="mb-2 text-[20px] font-display text-ink">{items.length}</div>
        <div className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">pending confirmations</div>
        {items.length > 0 ? (
          <ul className="mt-2 space-y-1 text-[11.5px]">
            {items.slice(0, 3).map((p) => (
              <li key={p.token} className="truncate text-ink-2">{p.action_id}</li>
            ))}
          </ul>
        ) : null}
      </a>
    </WidgetFrame>
  );
}
