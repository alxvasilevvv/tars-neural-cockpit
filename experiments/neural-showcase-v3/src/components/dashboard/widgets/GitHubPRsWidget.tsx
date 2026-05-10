// SYNC: claude-w96-dashboard
import { useCallback, useEffect, useState } from "react";
import { GitPullRequest } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { WidgetFrame } from "../WidgetFrame";

interface PR { id: string | number; title: string; html_url: string; repo: string; user?: { login?: string }; }
interface Props { editMode?: boolean; onRemove?: () => void; }

export function GitHubPRsWidget({ editMode, onRemove }: Props) {
  const [items, setItems] = useState<PR[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/connectors/github/repos`);
      if (r.status === 404 || r.status === 412 || r.status === 401) { setNotConfigured(true); setItems([]); }
      else if (!r.ok) throw new Error(`HTTP ${r.status}`);
      else {
        const j = (await r.json()) as { repos?: { full_name: string; open_pulls?: PR[] }[]; pulls?: PR[] };
        // Either flat pulls list or nested per-repo. Aggregate either.
        let aggregated: PR[] = [];
        if (Array.isArray(j.pulls)) aggregated = j.pulls;
        else if (Array.isArray(j.repos)) {
          for (const repo of j.repos) {
            if (Array.isArray(repo.open_pulls)) {
              aggregated.push(...repo.open_pulls.map((p) => ({ ...p, repo: repo.full_name })));
            }
          }
        }
        setItems(aggregated);
        setNotConfigured(false);
      }
      setUpdatedAt(Date.now());
    } catch { setError("Can't reach backend - check connector."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <WidgetFrame title="GitHub PRs awaiting review" Icon={GitPullRequest} updatedAt={updatedAt} loading={loading} error={error} onRefresh={load} editMode={editMode} onRemove={onRemove}>
      {notConfigured ? (
        <p className="text-ink-3">GitHub not connected.</p>
      ) : items.length === 0 ? (
        <p className="text-ink-3">No PRs awaiting review.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 5).map((p) => (
            <li key={String(p.id)}>
              <a href={p.html_url} target="_blank" rel="noreferrer" className="block rounded px-1.5 py-1 hover:bg-line/40">
                <div className="font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">{p.repo}</div>
                <div className="truncate text-ink">{p.title}</div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
