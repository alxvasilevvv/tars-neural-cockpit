// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { Calendar } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface CalEvent {
  id: string;
  summary: string;
  start: string;
  end: string;
  location?: string;
}

interface Props { editMode?: boolean; onRemove?: () => void; }

export function CalendarTodayWidget({ editMode, onRemove }: Props) {
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/connectors/calendar/today`);
      if (r.status === 404 || r.status === 412 || r.status === 401) {
        setNotConfigured(true);
        setEvents([]);
      } else if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      } else {
        const j = (await r.json()) as { events?: CalEvent[] };
        setEvents(Array.isArray(j.events) ? j.events : []);
        setNotConfigured(false);
      }
      setUpdatedAt(Date.now());
    } catch {
      setError("Can't reach backend - check connector.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="Calendar today" Icon={Calendar} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {notConfigured ? (
        <p className="text-ink-3">Calendar not connected. Open Settings to wire it up.</p>
      ) : events.length === 0 ? (
        <p className="text-ink-3">No events today.</p>
      ) : (
        <ul className="space-y-1.5">
          {events.slice(0, 6).map((e) => {
            const t = new Date(e.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            return (
              <li key={e.id}>
                <a href="/cockpit" className="block rounded px-1.5 py-1 hover:bg-line/40">
                  <span className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{t}</span>
                  <span className="ml-2 text-ink">{e.summary}</span>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </WidgetFrame>
  );
}
