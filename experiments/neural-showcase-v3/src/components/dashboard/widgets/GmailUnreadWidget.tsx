// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface Thread { id: string; from: string; subject: string; snippet?: string; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function GmailUnreadWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/connectors/gmail/threads?query=is%3Aunread`);
      if (r.status === 404 || r.status === 412 || r.status === 401) { setNotConfigured(true); setItems([]); }
      else if (!r.ok) throw new Error(`HTTP ${r.status}`);
      else {
        const j = (await r.json()) as { threads?: Thread[] };
        setItems(Array.isArray(j.threads) ? j.threads : []);
        setNotConfigured(false);
      }
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Gmail unread" Icon={Mail} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {notConfigured ? (
        <p className="text-ink-3">Gmail not connected.</p>
      ) : items.length === 0 ? (
        <p className="text-ink-3">Inbox zero.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 5).map((t) => (
            <li key={t.id}>
              <a href="https://mail.google.com" target="_blank" rel="noreferrer" className="block rounded px-1.5 py-1 hover:bg-line/40">
                <div className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{t.from}</div>
                <div className="truncate text-ink">{t.subject}</div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
