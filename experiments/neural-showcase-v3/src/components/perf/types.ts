// SYNC: claude-w108-perf
/**
 * Wave 108 — perf-dashboard envelope types.
 *
 * Mirrors the JSON returned by /api/perf/* (see web_extras/routers/perf.py).
 * Optional fields are typed as `| null` to match the backend's "available:
 * false" degradation path.
 */

export interface LatencyStats {
  op: string;
  count: number;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  max: number | null;
  avg: number | null;
}

export interface ConnectorHealthRow {
  name: string;
  label: string;
  configured: boolean;
  connected: boolean;
  env_vars: string[];
}

export interface ConnectorHealthEnvelope {
  ok: boolean;
  as_of: number;
  connectors: ConnectorHealthRow[];
}

export interface FailedDeliveryRow {
  id: string;
  webhook_id: string;
  event_type: string;
  last_error: string | null;
  last_status_code: number | null;
  attempts: number;
}

export interface WebhookStatsEnvelope {
  ok: boolean;
  available: boolean;
  reason?: string;
  window_s?: number;
  total?: number;
  success?: number;
  pending?: number;
  retrying?: number;
  failed?: number;
  failed_recent?: FailedDeliveryRow[];
  avg_signature_ms?: number | null;
}

export interface ReceiptIntegrityEnvelope {
  ok: boolean;
  available: boolean;
  reason?: string;
  day_iso?: string;
  today_count?: number;
  chain_valid?: boolean;
  chain_issues?: unknown[];
  merkle_root?: string | null;
  anchored_to_solana?: boolean;
  last_anchor_at?: number | null;
}

export interface SchedulerSummary {
  available: boolean;
  reason?: string;
  schedule_count?: number;
  enabled_count?: number;
  next_run_at?: number | null;
  next_run_in_s?: number | null;
  tick_interval_s?: number;
}

export interface JobsEnvelope {
  ok: boolean;
  scheduler: SchedulerSummary;
  reflection: { available: boolean; enabled: boolean; interval_s: number | null };
  autopilot: { available: boolean; enabled: boolean; tick_s: number | null };
}

export interface ResourceUsageEnvelope {
  ok: boolean;
  available: boolean;
  reason?: string;
  cpu_percent?: number;
  memory?: { total: number; used: number; available: number; percent: number };
  disk?: { tars_dir: string; total: number | null; used: number | null; free: number | null };
}

export interface PerfSummaryEnvelope {
  ok: boolean;
  as_of: number;
  window_s: number;
  latency: Record<string, LatencyStats>;
  connectors: ConnectorHealthEnvelope;
  webhooks: WebhookStatsEnvelope;
  receipts: ReceiptIntegrityEnvelope;
  jobs: JobsEnvelope;
  resources: ResourceUsageEnvelope;
}

// SYNC: cursor-wave-m6-cockpit
// /api/mcp/bridge/status — Wave M6 cockpit panel.

export interface MCPBridgeServerRow {
  name: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string | null;
  description?: string | null;
}

export interface MCPBridgeRegisteredPack {
  slug: string;
  name: string;
  tool_count: number;
  pooled: boolean;
}

export interface MCPBridgeCacheRow {
  server: string;
  status?: string; // "unreadable" when the cache file can't be parsed
  discovered_at?: string;
  age_seconds?: number;
  fresh?: boolean;
  tool_count?: number;
}

export interface MCPBridgePoolSession {
  name: string;
  age_seconds: number;
  idle_seconds: number;
  server_info: { name?: string; version?: string };
  tool_count?: number | string;
}

export interface MCPBridgePoolStats {
  count: number;
  sessions: MCPBridgePoolSession[];
  // Surfaced as `{error: ...}` if pool stats lookup blew up.
  error?: string;
}

export interface MCPBridgeStatusEnvelope {
  ok: boolean;
  available: boolean;
  reason?: string;
  as_of: number;
  servers?: MCPBridgeServerRow[];
  registered?: MCPBridgeRegisteredPack[];
  cache?: MCPBridgeCacheRow[];
  pool?: MCPBridgePoolStats | null;
}
