/**
 * Client + React hook for the TARS playbook runner.
 *
 * Playbooks are JSON-defined multi-step action chains executed
 * server-side. This module covers list, fetch, run, and a manual
 * "run again" hook for cockpit panels.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";
import type { PolicyMode } from "./api";

export interface PlaybookStep {
  id: string;
  action: string;
  args: Record<string, unknown>;
  store_as: string | null;
  when: string | null;
  on_error: "stop" | "continue";
  parallel: boolean;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  tags: string[];
  on_block: "stop" | "continue";
  steps: PlaybookStep[];
}

export interface StepResult {
  id: string;
  action: string;
  ok: boolean;
  skipped: boolean;
  blocked: boolean;
  took_ms: number;
  result: Record<string, unknown> | null;
  error: string | null;
  confirmation_token: string | null;
}

export interface PlaybookRun {
  ok: boolean;
  playbook_id: string;
  trace_id: string | null;
  mode: PolicyMode;
  steps: StepResult[];
  context: Record<string, unknown>;
}

export async function listPlaybooks(): Promise<Playbook[]> {
  const r = await fetch(`${API_BASE}/api/playbooks`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { playbooks: Playbook[] };
  return d.playbooks ?? [];
}

export async function getPlaybook(id: string): Promise<Playbook> {
  const r = await fetch(`${API_BASE}/api/playbooks/${id}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { playbook: Playbook };
  return d.playbook;
}

export async function runPlaybook(
  id: string,
  opts: {
    mode?: PolicyMode;
    context?: Record<string, unknown>;
  } = {},
): Promise<PlaybookRun> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (opts.mode) headers["x-tars-policy-mode"] = opts.mode;
  const r = await fetch(`${API_BASE}/api/playbooks/${id}/run`, {
    method: "POST",
    headers,
    body: JSON.stringify({ context: opts.context ?? {} }),
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} · ${text}`);
  }
  return (await r.json()) as PlaybookRun;
}

/**
 * List playbooks once on mount and expose a refresh callback.
 */
export function usePlaybooks(): {
  playbooks: Playbook[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const list = await listPlaybooks();
      if (!cancelled.current) {
        setPlaybooks(list);
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
    return () => {
      cancelled.current = true;
    };
  }, [refresh]);

  return { playbooks, loading, error, refresh };
}

/**
 * Manual playbook runner hook — exposes a `run` callback.
 */
export function usePlaybookRun(): {
  run: PlaybookRun | null;
  loading: boolean;
  error: string | null;
  invoke: (
    id: string,
    opts?: { mode?: PolicyMode; context?: Record<string, unknown> },
  ) => Promise<void>;
} {
  const [run, setRun] = useState<PlaybookRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invoke = useCallback(
    async (
      id: string,
      opts: { mode?: PolicyMode; context?: Record<string, unknown> } = {},
    ) => {
      setLoading(true);
      setError(null);
      try {
        const out = await runPlaybook(id, opts);
        setRun(out);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { run, loading, error, invoke };
}
