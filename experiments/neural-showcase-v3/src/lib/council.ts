/**
 * Client + React hook for the TARS council orchestrator.
 *
 * The council is the multi-voice deliberation layer; this client
 * surfaces it to the cockpit so the operator can see the proposals
 * side by side.
 */

import { useCallback, useState } from "react";

import { API_BASE } from "./api";

export type CouncilMode = "single" | "dual_vote" | "n_vote";

export interface Proposal {
  model: string;
  stance: string;
  summary: string;
  actions_recommended: string[];
  confidence: number;
  rationale: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
}

export interface Deliberation {
  ok: boolean;
  prompt: string;
  context: Record<string, unknown>;
  mode: CouncilMode;
  voices: Proposal[];
  chosen: string;
  agreement: number;
  contradictions: string[];
  rationale: string;
  trace_id: string | null;
  decided_at: number;
}

export async function deliberate(
  prompt: string,
  context: Record<string, unknown>,
  mode: CouncilMode = "dual_vote",
): Promise<Deliberation> {
  const r = await fetch(`${API_BASE}/api/council/deliberate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt, context, mode }),
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} · ${text}`);
  }
  return r.json() as Promise<Deliberation>;
}

/**
 * Manual deliberation hook — exposes a `run` callback rather than
 * polling. Useful for cockpit panels where the operator triggers a
 * council read on demand.
 */
export function useDeliberation(): {
  deliberation: Deliberation | null;
  loading: boolean;
  error: string | null;
  run: (
    prompt: string,
    context: Record<string, unknown>,
    mode?: CouncilMode,
  ) => Promise<void>;
} {
  const [deliberation, setDeliberation] = useState<Deliberation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (prompt: string, context: Record<string, unknown>, mode: CouncilMode = "dual_vote") => {
      setLoading(true);
      setError(null);
      try {
        const out = await deliberate(prompt, context, mode);
        setDeliberation(out);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { deliberation, loading, error, run };
}
