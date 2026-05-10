// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Receipt } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface ReceiptItem { id: string; action_id?: string; action?: string; created_at?: number; ts?: number; ok?: boolean; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function RecentReceiptsWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<ReceiptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/receipts?limit=10`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { receipts?: ReceiptItem[] };
      setItems(Array.isArray(j.receipts) ? j.receipts : []);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Recent receipts" Icon={Receipt} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {items.length === 0 ? (
        <p className="text-ink-3">No receipts yet.</p>
      ) : (
        <ul className="space-y-1">
          {items.slice(0, 8).map((r) => {
            const ts = (r.created_at ?? r.ts ?? 0) * (r.created_at && r.created_at > 1e12 ? 1 : 1000);
            const when = ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
            return (
              <li key={r.id} className="flex items-center justify-between rounded px-1.5 py-1 hover:bg-line/40">
                <span className="truncate text-ink">{r.action_id ?? r.action ?? r.id.slice(0, 12)}</span>
                <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{when}</span>
              </li>
            );
          })}
        </ul>
      )}
    </WidgetFrame>
  );
}
