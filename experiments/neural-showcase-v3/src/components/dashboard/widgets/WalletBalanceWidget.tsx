// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Wallet } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface WInfo { id: string; chain: string; address: string; label?: string; balance?: number | string; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function WalletBalanceWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<WInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/wallet`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { wallets?: WInfo[] };
      setItems(Array.isArray(j.wallets) ? j.wallets : []);
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Wallet balance" Icon={Wallet} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {items.length === 0 ? (
        <p className="text-ink-3">No wallets yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 4).map((w) => (
            <li key={w.id}>
              <a href="/cockpit" className="block rounded px-1.5 py-1 hover:bg-line/40">
                <div className="flex items-baseline justify-between">
                  <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{w.chain}</span>
                  <span className="text-ink">{w.balance ?? "-"}</span>
                </div>
                <div className="truncate font-mono-tech text-[10px] text-ink-3">{w.label ?? w.address.slice(0, 14)}...</div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
