/**
 * Client + React hook for the TARS policy gate (destructive-action
 * confirmation queue). Backed by FastAPI at /api/policy/*.
 *
 * The cockpit uses this to render:
 * - a pending-confirmations panel (one row per token waiting),
 * - a "recent" tab with resolved/expired/cancelled tokens,
 * - inline confirm/cancel buttons that hit the resolve endpoint.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export interface PendingConfirmation {
  token: string;
  slug: string;
  action_id: string;
  args: Record<string, unknown>;
  created_at: number;
  expires_at: number;
  status: "pending" | "confirmed" | "cancelled" | "expired" | "failed";
  resolved_at: number | null;
  result: Record<string, unknown> | null;
  trace_id: string | null;
  requested_by: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} · ${text}`);
  }
  return r.json() as Promise<T>;
}

export async function listPending(): Promise<PendingConfirmation[]> {
  const d = await getJson<{ pending: PendingConfirmation[] }>(
    "/api/policy/pending",
  );
  return d.pending ?? [];
}

export async function listRecent(
  limit = 50,
): Promise<PendingConfirmation[]> {
  const d = await getJson<{ recent: PendingConfirmation[] }>(
    `/api/policy/recent?limit=${limit}`,
  );
  return d.recent ?? [];
}

export async function confirmToken(
  token: string,
): Promise<Record<string, unknown>> {
  return postJson(`/api/policy/confirm/${token}`);
}

export async function cancelToken(
  token: string,
): Promise<Record<string, unknown>> {
  return postJson(`/api/policy/cancel/${token}`);
}

export async function expireStale(): Promise<{ expired: number }> {
  return postJson("/api/policy/expire");
}

/**
 * Polls /pending every `intervalMs` (default 4s). Returns the current
 * list, an error if any, plus a `refresh` callback for explicit pulls.
 */
export function usePendingConfirmations(
  intervalMs = 4000,
): {
  pending: PendingConfirmation[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [pending, setPending] = useState<PendingConfirmation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const list = await listPending();
      if (!cancelled.current) {
        setPending(list);
        setError(null);
      }
    } catch (e) {
      if (!cancelled.current) {
        setError((e as Error).message);
      }
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

  return { pending, loading, error, refresh };
}
