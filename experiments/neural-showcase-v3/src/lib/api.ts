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
  auth?: {
    keys: { key: string; source: string; available: boolean }[];
  };
  composite?: boolean;
  composed_of?: string[];
  /** From backend `DomainPack.to_dict()` — drives cockpit pack picker filtering. */
  deprecated?: boolean;
  deprecated_in_favor_of?: string | null;
}

export interface DomainManifestItem {
  slug: string;
  name: string;
  short: string;
  color: string;
  audience: string;
  capabilities: string[];
  composite: boolean;
  composed_of: string[];
  action_count: number;
  destructive_action_count: number;
  awareness_count: number;
  deprecated?: boolean;
  deprecated_in_favor_of?: string | null;
}

function isDeprecatedPack(p: DomainPack): boolean {
  return p.deprecated === true;
}

function isDeprecatedManifestItem(d: DomainManifestItem): boolean {
  return d.deprecated === true;
}

export interface InvokeResult {
  ok: boolean;
  slug: string;
  action: string;
  trace_id: string | null;
  took_ms: number;
  result: Record<string, unknown>;
}

export async function listDomains(
  opts: { includeDeprecated?: boolean } = {},
): Promise<DomainPack[]> {
  const r = await fetch(`${BASE}/api/domains`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = (await r.json()) as { domains: DomainPack[] };
  if (opts.includeDeprecated) return d.domains;
  return d.domains.filter(p => !isDeprecatedPack(p));
}

export async function getDomainManifest(
  opts: { includeDeprecated?: boolean } = {},
): Promise<{
  contract_version: string;
  count: number;
  domains: DomainManifestItem[];
}> {
  const r = await fetch(`${BASE}/api/domains/manifest`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const m = (await r.json()) as {
    contract_version: string;
    count: number;
    domains: DomainManifestItem[];
  };
  if (opts.includeDeprecated) return m;
  const filtered = m.domains.filter(d => !isDeprecatedManifestItem(d));
  return { ...m, count: filtered.length, domains: filtered };
}

// --- Entitlements / roles — `web_extras/routers/entitlements.py`, `roles.py`

export interface Entitlements {
  ok: boolean;
  tier: string;
  byo_enabled: boolean;
  upgraded_at?: number | string | null;
  caps: Record<string, unknown>;
  live: {
    spent_usd_24h: number;
    cap_usd_daily: number;
    remaining_usd: number;
    allowed_cloud: boolean;
    reason?: string;
  };
}

export async function getEntitlements(): Promise<Entitlements> {
  const r = await fetch(`${BASE}/api/entitlements`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/** Fire POST /api/roles/{slug}/activate — best-effort from onboarding / cockpit glue. */
export async function activateRole(slug: string): Promise<void> {
  const r = await fetch(
    `${BASE}/api/roles/${encodeURIComponent(slug)}/activate`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

/** POST /api/roles — synthesise a custom overlay role; caller usually activates next. */
export async function createCustomRole(payload: {
  name: string;
  description: string;
  backing_packs: string[];
}): Promise<{ slug: string }> {
  const r = await fetch(`${BASE}/api/roles`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const raw = (await r.json()) as { role?: { slug?: string } };
  const slug = raw.role?.slug;
  if (!slug) throw new Error("createCustomRole: response missing role.slug");
  return { slug };
}

export type PolicyMode = "autopilot" | "confirm" | "dry_run";

export async function invokeAction(
  slug: string,
  actionId: string,
  args: Record<string, unknown>,
  opts: { mode?: PolicyMode; traceId?: string; sessionId?: string } = {},
): Promise<InvokeResult> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (opts.mode) headers["x-tars-policy-mode"] = opts.mode;
  if (opts.traceId) headers["x-meeet-trace-id"] = opts.traceId;
  if (opts.sessionId) headers["x-tars-session-id"] = opts.sessionId;
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
