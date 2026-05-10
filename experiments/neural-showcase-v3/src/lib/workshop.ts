// SYNC: claude-w80-fe-only
/**
 * Wave 80-A — Workshop API client.
 *
 * Thin wrapper around the new B2B-onboarding endpoints (Cursor is
 * shipping these in parallel). Every call returns either the live
 * response or, when the backend hasn't shipped yet (HTTP 404), a
 * `{ pending: true }` flag so the UI can fall through to its mock
 * preview state instead of crashing.
 *
 * Endpoints (all hitting `${API_BASE}`):
 *   POST /api/playbooks/synthesize  — natural-language → playbook JSON
 *   POST /api/playbooks             — persist a validated playbook
 *   GET  /api/playbooks             — list saved playbooks
 *   GET  /api/domains/{slug}/manifest — per-pack action manifest
 *   POST /api/agents/{id}/backtest  — historical replay
 *
 * Hand-off contract: `// SYNC: cursor-w80-be` markers in Cursor's
 * router files. Once both sides land, the `pending` paths become
 * dead code; nothing else changes.
 */

import { API_BASE } from "./api";

export interface PlaybookStep {
  id: string;
  domain: string;
  action: string;
  /** JSON-stringified args template, may contain `{{var}}` placeholders. */
  args?: Record<string, unknown>;
  description?: string;
}

export interface Playbook {
  id?: string;
  name: string;
  description: string;
  domain_pack?: string | null;
  steps: PlaybookStep[];
  /** When true, every step requires HIL confirmation before run. */
  requires_confirmation?: boolean;
  /** ISO timestamp when persisted. */
  created_at?: string;
  updated_at?: string;
}

export interface SynthesizeRequest {
  text: string;
  domain_pack?: string | null;
}

export type Pending<T> = { pending: true; reason: string } | { pending: false; value: T };

async function tryJSON<T>(req: () => Promise<Response>): Promise<Pending<T>> {
  try {
    const r = await req();
    if (r.status === 404) {
      return { pending: true, reason: "Backend feature pending — Cursor is shipping this." };
    }
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status} · ${text}`);
    }
    const value = (await r.json()) as T;
    return { pending: false, value };
  } catch (err) {
    // Network failure (sidecar offline) — surface as pending too so
    // the workshop shell renders, mirroring CockpitGate behaviour.
    if (err instanceof TypeError) {
      return { pending: true, reason: "Daemon offline — workshop running in mock mode." };
    }
    throw err;
  }
}

export async function synthesizePlaybook(
  req: SynthesizeRequest,
): Promise<Pending<{ playbook: Playbook }>> {
  return tryJSON<{ playbook: Playbook }>(() =>
    fetch(`${API_BASE}/api/playbooks/synthesize`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }),
  );
}

export async function savePlaybook(
  pb: Playbook,
): Promise<Pending<{ playbook: Playbook }>> {
  return tryJSON<{ playbook: Playbook }>(() =>
    fetch(`${API_BASE}/api/playbooks`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(pb),
    }),
  );
}

export async function listPlaybooks(): Promise<Pending<{ playbooks: Playbook[] }>> {
  return tryJSON<{ playbooks: Playbook[] }>(() => fetch(`${API_BASE}/api/playbooks`));
}

export interface BacktestRow {
  index: number;
  input: Record<string, unknown>;
  expected: string;
  actual: string;
  agreed: boolean;
}

export interface BacktestResult {
  ok: boolean;
  agent_id: string;
  total: number;
  agreed: number;
  agreement_rate: number;
  rows: BacktestRow[];
}

export async function backtestAgent(
  agentId: string,
  csv: string,
): Promise<Pending<BacktestResult>> {
  return tryJSON<BacktestResult>(() =>
    fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}/backtest`, {
      method: "POST",
      headers: { "content-type": "text/csv" },
      body: csv,
    }),
  );
}

/* ─── Mock fallbacks (used when `pending`) ───────────────────────── */

export const MOCK_PLAYBOOK: Playbook = {
  name: "Daily portfolio brief",
  description:
    "Every weekday at 09:00, fetch latest prices, summarize movements, and post the brief to Slack.",
  domain_pack: "traders",
  requires_confirmation: false,
  steps: [
    {
      id: "s1",
      domain: "traders",
      action: "fetch_prices",
      args: { tickers: ["AAPL", "WBTC", "ETH"] },
      description: "Pull last 24h price action.",
    },
    {
      id: "s2",
      domain: "research",
      action: "summarize",
      args: { seed: "{{s1.result}}", style: "executive" },
      description: "Distill into 3 bullet points.",
    },
    {
      id: "s3",
      domain: "notify",
      action: "send_slack",
      args: { channel: "#trading", text: "{{s2.result}}" },
      description: "Post to #trading.",
    },
  ],
};

export const MOCK_BACKTEST: BacktestResult = {
  ok: true,
  agent_id: "mock-agent",
  total: 24,
  agreed: 21,
  agreement_rate: 0.875,
  rows: [
    { index: 0, input: { ticker: "AAPL", t: "09:00" }, expected: "buy",  actual: "buy",  agreed: true },
    { index: 1, input: { ticker: "WBTC", t: "09:05" }, expected: "hold", actual: "buy",  agreed: false },
    { index: 2, input: { ticker: "ETH",  t: "09:10" }, expected: "sell", actual: "sell", agreed: true },
    { index: 3, input: { ticker: "SOL",  t: "09:15" }, expected: "hold", actual: "sell", agreed: false },
    { index: 4, input: { ticker: "AAPL", t: "10:00" }, expected: "hold", actual: "hold", agreed: true },
  ],
};
