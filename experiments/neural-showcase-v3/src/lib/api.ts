/**
 * Thin client for the TARS cockpit backend (FastAPI in web_extras/app.py).
 * Default base URL is http://127.0.0.1:8765 — overridable via VITE_TARS_API.
 */

const BASE =
  (import.meta.env.VITE_TARS_API as string | undefined) ||
  "http://127.0.0.1:8765";

export interface DomainAction {
  id: string;
  name: string;
  description: string;
  schema: Record<string, unknown>;
  destructive?: boolean;
}

export interface AwarenessSource {
  id: string;
  name: string;
  description: string;
  kind: string;
  config: Record<string, unknown>;
  live?: boolean;
}

export interface DomainPack {
  slug: string;
  name: string;
  short: string;
  description: string;
  color: string;
  capabilities: string[];
  audience: string;
  actions: DomainAction[];
  awareness: AwarenessSource[];
}

export interface InvokeResult {
  ok: boolean;
  slug: string;
  action: string;
  trace_id: string | null;
  took_ms: number;
  result: Record<string, unknown>;
}

export async function listDomains(): Promise<DomainPack[]> {
  const r = await fetch(`${BASE}/api/domains`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { domains: DomainPack[] };
  return d.domains;
}

export type PolicyMode = "autopilot" | "confirm" | "dry_run";

export async function invokeAction(
  slug: string,
  actionId: string,
  args: Record<string, unknown>,
  opts: { mode?: PolicyMode; traceId?: string } = {},
): Promise<InvokeResult> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (opts.mode) headers["x-tars-policy-mode"] = opts.mode;
  if (opts.traceId) headers["x-meeet-trace-id"] = opts.traceId;
  const r = await fetch(
    `${BASE}/api/domains/${slug}/actions/${actionId}`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(args),
    },
  );
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} · ${text}`);
  }
  return (await r.json()) as InvokeResult;
}

export async function snapshotAwareness(
  slug: string,
  sourceId: string,
  args: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  const qs = Object.keys(args).length
    ? `?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(args).map(([k, v]) => [k, String(v)]),
        ),
      ).toString()}`
    : "";
  const r = await fetch(
    `${BASE}/api/domains/${slug}/awareness/${sourceId}/snapshot${qs}`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getHealth(): Promise<{
  ok: boolean;
  uptime_s: number;
  meeet_ingest: boolean;
}> {
  const r = await fetch(`${BASE}/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export const API_BASE = BASE;
