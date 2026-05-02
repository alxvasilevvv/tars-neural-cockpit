/**
 * Search + observability client for Phase L8.
 *
 * Three endpoints, one client:
 *   POST /api/search                  unified hybrid search
 *   POST /api/search/{chunks|messages|traces}  scoped variants
 *   GET  /api/chat/threads/{id}/timeline       structured timeline
 *
 * The cockpit's ⌘K command palette is a thin wrapper around the
 * unified endpoint with debounced typing + arrow-key navigation +
 * a deep-link-style `onSelect` callback.
 *
 * ⌘J uses POST /api/search/jump (see `fetchJump`, `JumpPalette`).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE } from "./api";

export type SearchKind = "chunk" | "message" | "trace";
export type SearchScope = "all" | "chunks" | "messages" | "traces";

export interface SearchHit {
  kind: SearchKind;
  score: number;
  title: string;
  snippet: string;
  ref: Record<string, unknown> & {
    thread_id?: string;
    thread_title?: string | null;
    chunk_id?: string;
    msg_id?: string;
    attachment_id?: string;
    filename?: string | null;
    page?: number | null;
    heading?: string | null;
    role?: string;
    event_id?: number;
    trace_id?: string | null;
    session_id?: string | null;
  };
  rank_keyword: number | null;
  rank_semantic: number | null;
}

export interface SearchResult {
  query: string;
  scope: SearchScope;
  count: number;
  counts: Partial<Record<"chunks" | "messages" | "traces", number>>;
  hits: SearchHit[];
}

export async function unifiedSearch(
  query: string,
  opts: { scope?: SearchScope; topK?: number; signal?: AbortSignal } = {},
): Promise<SearchResult> {
  const r = await fetch(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      query,
      scope: opts.scope ?? "all",
      top_k: opts.topK ?? 12,
    }),
    signal: opts.signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as SearchResult & { ok: boolean };
  return {
    query: body.query,
    scope: body.scope,
    count: body.count,
    counts: body.counts ?? {},
    hits: body.hits ?? [],
  };
}

export async function searchChunks(
  query: string,
  opts: { topK?: number; threadId?: string; signal?: AbortSignal } = {},
): Promise<SearchHit[]> {
  const r = await fetch(`${API_BASE}/api/search/chunks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      query,
      top_k: opts.topK ?? 12,
      thread_id: opts.threadId,
    }),
    signal: opts.signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { hits: SearchHit[] };
  return body.hits ?? [];
}

export async function searchMessages(
  query: string,
  opts: {
    topK?: number;
    threadId?: string;
    role?: "operator" | "tars" | "tool";
    signal?: AbortSignal;
  } = {},
): Promise<SearchHit[]> {
  const r = await fetch(`${API_BASE}/api/search/messages`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      query,
      top_k: opts.topK ?? 12,
      thread_id: opts.threadId,
      role: opts.role,
    }),
    signal: opts.signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { hits: SearchHit[] };
  return body.hits ?? [];
}

// --------------------------------------------------------------------
// Cmd+J jump picker — POST /api/search/jump
// --------------------------------------------------------------------

export type JumpHitKind =
  | "thread"
  | "attachment"
  | "saved_search"
  | "pack"
  | "playbook";

export interface JumpHit {
  kind: JumpHitKind;
  id: string;
  label: string;
  sublabel: string;
  score: number;
  ref: Record<string, unknown>;
}

export interface JumpResult {
  ok: boolean;
  query: string;
  count: number;
  hits: JumpHit[];
}

export async function fetchJump(
  q: string,
  opts: { limit?: number; signal?: AbortSignal } = {},
): Promise<JumpResult> {
  const r = await fetch(`${API_BASE}/api/search/jump`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      q,
      limit: opts.limit ?? 24,
    }),
    signal: opts.signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as JumpResult;
}

export async function searchTraces(
  query: string,
  opts: { topK?: number; signal?: AbortSignal } = {},
): Promise<SearchHit[]> {
  const r = await fetch(`${API_BASE}/api/search/traces`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      query,
      top_k: opts.topK ?? 12,
    }),
    signal: opts.signal,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { hits: SearchHit[] };
  return body.hits ?? [];
}

// --------------------------------------------------------------------
// Timeline
// --------------------------------------------------------------------

export interface ThreadTimelineEntry {
  id: string;
  ts: number;
  kind: string;
  source: "message" | "tool_call" | "attachment" | "event";
  title: string;
  summary: string;
  payload: Record<string, unknown>;
}

export async function fetchThreadTimeline(
  threadId: string,
  opts: { limit?: number; signal?: AbortSignal } = {},
): Promise<ThreadTimelineEntry[]> {
  const qs = new URLSearchParams();
  if (opts.limit) qs.set("limit", String(opts.limit));
  const r = await fetch(
    `${API_BASE}/api/chat/threads/${threadId}/timeline?${qs}`,
    { signal: opts.signal },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { entries: ThreadTimelineEntry[] };
  return body.entries ?? [];
}

// --------------------------------------------------------------------
// React hook: useDebouncedSearch — drives the ⌘K palette
// --------------------------------------------------------------------

export interface SearchState {
  query: string;
  scope: SearchScope;
  loading: boolean;
  error: string | null;
  result: SearchResult | null;
}

export interface SearchControls extends SearchState {
  setQuery: (q: string) => void;
  setScope: (s: SearchScope) => void;
  refresh: () => void;
  clear: () => void;
}

export function useDebouncedSearch(opts: {
  initialScope?: SearchScope;
  topK?: number;
  delayMs?: number;
} = {}): SearchControls {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<SearchScope>(opts.initialScope ?? "all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const tokenRef = useRef(0);
  const delay = opts.delayMs ?? 220;
  const topK = opts.topK ?? 12;

  const fire = useCallback(
    (text: string, currentScope: SearchScope) => {
      const trimmed = text.trim();
      if (!trimmed) {
        setLoading(false);
        setError(null);
        setResult(null);
        return;
      }
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const myToken = ++tokenRef.current;
      setLoading(true);
      setError(null);
      unifiedSearch(trimmed, {
        scope: currentScope,
        topK,
        signal: ctrl.signal,
      })
        .then((res) => {
          if (myToken !== tokenRef.current) return;
          setResult(res);
          setLoading(false);
        })
        .catch((exc) => {
          if (myToken !== tokenRef.current) return;
          if ((exc as Error)?.name === "AbortError") return;
          setError(String((exc as Error)?.message ?? exc));
          setLoading(false);
        });
    },
    [topK],
  );

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResult(null);
      return undefined;
    }
    const handle = window.setTimeout(() => fire(trimmed, scope), delay);
    return () => window.clearTimeout(handle);
  }, [query, scope, delay, fire]);

  const refresh = useCallback(() => fire(query, scope), [fire, query, scope]);
  const clear = useCallback(() => {
    setQuery("");
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  return useMemo(
    () => ({
      query,
      scope,
      loading,
      error,
      result,
      setQuery,
      setScope,
      refresh,
      clear,
    }),
    [query, scope, loading, error, result, refresh, clear],
  );
}

// --------------------------------------------------------------------
// React hook: useGlobalShortcut — bind ⌘K / Ctrl-K to a callback.
// --------------------------------------------------------------------

export function useGlobalShortcut(
  key: string,
  onTrigger: () => void,
  opts: { withMeta?: boolean; withCtrl?: boolean } = {},
): void {
  const target = key.toLowerCase();
  const meta = opts.withMeta ?? true;
  const ctrl = opts.withCtrl ?? true;
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== target) return;
      const wantsMeta = meta && e.metaKey;
      const wantsCtrl = ctrl && e.ctrlKey;
      if (!(wantsMeta || wantsCtrl)) return;
      e.preventDefault();
      onTrigger();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [target, meta, ctrl, onTrigger]);
}

// --------------------------------------------------------------------
// React hook: useThreadTimeline
// --------------------------------------------------------------------

export interface ThreadTimelineHook {
  entries: ThreadTimelineEntry[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useThreadTimeline(
  threadId: string | null,
  opts: { autoRefreshMs?: number; limit?: number } = {},
): ThreadTimelineHook {
  const [entries, setEntries] = useState<ThreadTimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!threadId) {
      setEntries([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await fetchThreadTimeline(threadId, { limit: opts.limit });
      setEntries(list);
    } catch (exc) {
      setError(String((exc as Error)?.message ?? exc));
    } finally {
      setLoading(false);
    }
  }, [threadId, opts.limit]);

  useEffect(() => {
    void refresh();
    const interval = opts.autoRefreshMs ?? 0;
    if (interval <= 0 || !threadId) return undefined;
    const handle = window.setInterval(() => void refresh(), interval);
    return () => window.clearInterval(handle);
  }, [refresh, opts.autoRefreshMs, threadId]);

  return useMemo(
    () => ({ entries, loading, error, refresh }),
    [entries, loading, error, refresh],
  );
}
