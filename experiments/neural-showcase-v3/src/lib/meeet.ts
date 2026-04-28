/**
 * Client + React hook for the meeet durable bridge.
 *
 * Surfaces:
 * - /api/meeet/health → bridge state (ingest URL, store stats,
 *   last replay metadata).
 * - /api/meeet/events → newest-first event list with filters.
 * - /api/meeet/replay → manual flush trigger.
 *
 * The cockpit renders this as a "black box" panel with a small
 * status indicator and an event timeline.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export interface MeeetEvent {
  id: number;
  ts: number;
  trace_id: string;
  kind: string;
  source: string;
  contract_version: string;
  payload: Record<string, unknown>;
  pushed: boolean;
  pushed_at: number | null;
  last_error: string | null;
}

export interface MeeetStats {
  total: number;
  unpushed: number;
  first_ts: number | null;
  last_ts: number | null;
  db_path: string | null;
  enabled: boolean;
}

export interface LastReplay {
  enabled: boolean;
  pushed?: number;
  failed?: number;
  scanned?: number;
  remaining?: number;
  ran_at?: number;
}

export interface MeeetHealth {
  ok: boolean;
  client: {
    enabled: boolean;
    ingest_url: string | null;
    api_key_set: boolean;
    contract_version: string;
    source: string;
  };
  store: MeeetStats;
  last_replay: LastReplay | null;
}

export async function getMeeetHealth(): Promise<MeeetHealth> {
  const r = await fetch(`${API_BASE}/api/meeet/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<MeeetHealth>;
}

export async function listEvents(
  opts: {
    limit?: number;
    since?: number;
    trace_id?: string;
    kind?: string;
    only_unpushed?: boolean;
  } = {},
): Promise<MeeetEvent[]> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.since) params.set("since", String(opts.since));
  if (opts.trace_id) params.set("trace_id", opts.trace_id);
  if (opts.kind) params.set("kind", opts.kind);
  if (opts.only_unpushed) params.set("only_unpushed", "true");
  const qs = params.toString();
  const r = await fetch(
    `${API_BASE}/api/meeet/events${qs ? `?${qs}` : ""}`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { events: MeeetEvent[] };
  return d.events ?? [];
}

export async function replayNow(
  limit = 100,
): Promise<LastReplay> {
  const r = await fetch(
    `${API_BASE}/api/meeet/replay?limit=${limit}`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<LastReplay>;
}

export function useMeeetHealth(intervalMs = 5000): {
  health: MeeetHealth | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [health, setHealth] = useState<MeeetHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const out = await getMeeetHealth();
      if (!cancelled.current) {
        setHealth(out);
        setError(null);
      }
    } catch (e) {
      if (!cancelled.current) setError((e as Error).message);
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    cancelled.current = false;
    void refresh();
    if (intervalMs > 0) {
      const id = window.setInterval(refresh, intervalMs);
      return () => {
        cancelled.current = true;
        window.clearInterval(id);
      };
    }
    return () => {
      cancelled.current = true;
    };
  }, [refresh, intervalMs]);

  return { health, loading, error, refresh };
}

/**
 * Rolling event timeline — pulls every `intervalMs` (default 5s).
 * Pass `kind` or `traceId` to filter on the server side.
 */
export function useMeeetEvents(
  opts: {
    limit?: number;
    intervalMs?: number;
    kind?: string;
    traceId?: string;
    onlyUnpushed?: boolean;
  } = {},
): {
  events: MeeetEvent[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [events, setEvents] = useState<MeeetEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);
  const intervalMs = opts.intervalMs ?? 5000;

  const refresh = useCallback(async () => {
    try {
      const list = await listEvents({
        limit: opts.limit ?? 200,
        kind: opts.kind,
        trace_id: opts.traceId,
        only_unpushed: opts.onlyUnpushed,
      });
      if (!cancelled.current) {
        setEvents(list);
        setError(null);
      }
    } catch (e) {
      if (!cancelled.current) setError((e as Error).message);
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  }, [opts.limit, opts.kind, opts.traceId, opts.onlyUnpushed]);

  useEffect(() => {
    cancelled.current = false;
    void refresh();
    if (intervalMs > 0) {
      const id = window.setInterval(refresh, intervalMs);
      return () => {
        cancelled.current = true;
        window.clearInterval(id);
      };
    }
    return () => {
      cancelled.current = true;
    };
  }, [refresh, intervalMs]);

  return { events, loading, error, refresh };
}
