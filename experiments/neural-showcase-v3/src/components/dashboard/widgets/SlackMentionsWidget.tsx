// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Hash } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface Mention { id: string; channel: string; user: string; text: string; ts: string; permalink?: string; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function SlackMentionsWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<Mention[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/connectors/slack/mentions`);
      if (r.status === 404 || r.status === 412 || r.status === 401) { setNotConfigured(true); setItems([]); }
      else if (!r.ok) throw new Error(`HTTP ${r.status}`);
      else {
        const j = (await r.json()) as { mentions?: Mention[] };
        setItems(Array.isArray(j.mentions) ? j.mentions : []);
        setNotConfigured(false);
      }
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Slack mentions" Icon={Hash} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {notConfigured ? (
        <p className="text-ink-3">Slack not connected.</p>
      ) : items.length === 0 ? (
        <p className="text-ink-3">No unread mentions.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 5).map((m) => (
            <li key={m.id}>
              <a href={m.permalink ?? "#"} target="_blank" rel="noreferrer" className="block rounded px-1.5 py-1 hover:bg-line/40">
                <div className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-[var(--brand-indigo)]">#{m.channel}</div>
                <div className="truncate text-ink">{m.user}: {m.text}</div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
