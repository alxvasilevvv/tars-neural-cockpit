import { useEffect, useState } from "react";

/**
 * recentOps — track last N successful invocations in localStorage
 * so the operator can re-run with the same args via the cockpit's
 * Cmd+K palette or a quick "Recent" lozenge.
 *
 * Storage shape (`localStorage["tars-recent-ops"]`):
 *
 *   [
 *     { slug: "research", actionId: "summarise",
 *       args: "{\"ref\":\"arxiv:…\"}", at: 1735689600123 },
 *     ...
 *   ]
 *
 * Capacity: 5 entries, newest-first. Recording an op whose
 * (slug, actionId) matches an existing entry de-dupes — the older
 * entry is removed and the new one prepended (LRU).
 *
 * Pre-existing JSON blob is migrated forward by best-effort parse;
 * a corrupted payload resets to []. No tracking PII; we store the
 * literal `args` string the operator typed plus a timestamp.
 */

export interface RecentOp {
  slug: string;
  actionId: string;
  /** raw text, exactly what was in the invocation textarea */
  args: string;
  /** ms since epoch */
  at: number;
}

const KEY = "tars-recent-ops";
const CAP = 5;

type Listener = (list: RecentOp[]) => void;
const listeners = new Set<Listener>();

function read(): RecentOp[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((x): x is RecentOp =>
        x &&
        typeof x.slug === "string" &&
        typeof x.actionId === "string" &&
        typeof x.args === "string" &&
        typeof x.at === "number",
      )
      .slice(0, CAP);
  } catch {
    return [];
  }
}

function write(list: RecentOp[]) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, CAP)));
  } catch {
    /* quota / private mode */
  }
  for (const l of listeners) l(list);
}

/** Push a new op. De-dupes by (slug, actionId). */
export function recordOp(op: Omit<RecentOp, "at"> & { at?: number }) {
  const fresh: RecentOp = { ...op, at: op.at ?? Date.now() };
  const cur = read().filter(
    o => !(o.slug === fresh.slug && o.actionId === fresh.actionId),
  );
  write([fresh, ...cur]);
}

/** Clear the entire ring. Useful from Settings → "Forget recent ops". */
export function clearRecent() {
  write([]);
}

/** Read-only subscription. */
export function useRecentOps(): RecentOp[] {
  const [list, setList] = useState<RecentOp[]>(() => read());
  useEffect(() => {
    const fn: Listener = next => setList(next);
    listeners.add(fn);
    // Refresh once in case localStorage was mutated by another tab.
    setList(read());
    return () => {
      listeners.delete(fn);
    };
  }, []);
  return list;
}

/** Format "2 minutes ago", "12s ago", etc. */
export function ago(at: number, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - at) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
