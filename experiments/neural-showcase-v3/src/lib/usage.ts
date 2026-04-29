/**
 * Cost / token usage client for the TARS cockpit.
 *
 * Backed by `/api/usage` which derives rollups from the meeet event store.
 * Polling-friendly (cheap reads, zero network hits when ingest is offline).
 */

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export interface UsageBucket {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms_total: number;
}

export interface UsageRollup {
  total_calls: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  by_model: Record<string, UsageBucket>;
  by_route: Record<string, UsageBucket>;
  by_session: Record<string, UsageBucket>;
}

export interface UsageLine {
  ts: number;
  trace_id: string | null;
  session_id: string | null;
  route: string | null;
  model: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number | null;
  kind: string;
}

export interface UsagePrices {
  [model: string]: { input_per_mtok: number; output_per_mtok: number };
}

export async function getUsageRollup(opts: {
  sessionId?: string;
  since?: number;
  limit?: number;
} = {}): Promise<UsageRollup> {
  const qs = new URLSearchParams();
  if (opts.sessionId) qs.set("session_id", opts.sessionId);
  if (opts.since != null) qs.set("since", String(opts.since));
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  const r = await fetch(`${API_BASE}/api/usage?${qs.toString()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { ok: boolean; rollup: UsageRollup };
  return d.rollup;
}

export async function getUsageLines(opts: {
  sessionId?: string;
  since?: number;
  limit?: number;
  traceId?: string;
} = {}): Promise<UsageLine[]> {
  const qs = new URLSearchParams();
  if (opts.sessionId) qs.set("session_id", opts.sessionId);
  if (opts.traceId) qs.set("trace_id", opts.traceId);
  if (opts.since != null) qs.set("since", String(opts.since));
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  const r = await fetch(`${API_BASE}/api/usage/lines?${qs.toString()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { lines: UsageLine[] };
  return d.lines;
}

export async function getUsagePrices(): Promise<UsagePrices> {
  const r = await fetch(`${API_BASE}/api/usage/prices`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { prices: UsagePrices };
  return d.prices;
}

/**
 * Polling hook for the cockpit usage strip.
 * Defaults to 8s — meeet events are cheap, but we still want to feel live.
 */
export function useUsageRollup(opts: {
  intervalMs?: number;
  sessionId?: string;
  paused?: boolean;
} = {}) {
  const { intervalMs = 8_000, sessionId, paused } = opts;
  const [data, setData] = useState<UsageRollup | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      if (paused) return;
      try {
        const out = await getUsageRollup({ sessionId });
        if (!cancelled.current) {
          setData(out);
          setError(null);
        }
      } catch (err) {
        if (!cancelled.current) setError(err as Error);
      } finally {
        if (!cancelled.current) setLoading(false);
        if (!cancelled.current) {
          timer = setTimeout(tick, intervalMs);
        }
      }
    }
    tick();
    return () => {
      cancelled.current = true;
      if (timer) clearTimeout(timer);
    };
  }, [intervalMs, sessionId, paused]);

  return { data, error, loading };
}
