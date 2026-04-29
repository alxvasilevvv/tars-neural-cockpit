/**
 * Cockpit client for the multi-agent surface (Phase M1).
 *
 * Each agent is a thin configuration record (name + pack persona +
 * optional wallet binding); each task hits the council orchestrator
 * via /api/tasks/{id}/run on the backend. The cockpit only ever
 * speaks JSON over /api/agents/* and /api/tasks/*.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export type AgentStatus = "active" | "paused" | "archived";

export interface Agent {
  id: string;
  name: string;
  pack_slug: string;
  description: string;
  system_prompt: string | null;
  wallet_address: string | null;
  status: AgentStatus;
  created_at: number;
  updated_at: number;
}

export type TaskStatus =
  | "pending"
  | "running"
  | "awaiting_confirmation"
  | "done"
  | "failed"
  | "cancelled";

export interface TaskResult {
  chosen?: string;
  agreement?: number;
  cost_usd?: number | null;
  voices?: Array<{
    model: string;
    stance: string;
    confidence: number;
    summary: string;
  }>;
  [key: string]: unknown;
}

export interface AgentTask {
  id: string;
  agent_id: string;
  prompt: string;
  status: TaskStatus;
  result: TaskResult | null;
  error: string | null;
  trace_id: string | null;
  created_at: number;
  updated_at: number;
  completed_at: number | null;
}

export interface CreateAgentInput {
  name: string;
  pack_slug: string;
  description?: string;
  system_prompt?: string;
  wallet_address?: string;
  metadata?: Record<string, unknown>;
}

export interface PatchAgentInput {
  name?: string;
  description?: string;
  system_prompt?: string;
  wallet_address?: string;
  status?: AgentStatus;
  metadata?: Record<string, unknown>;
}

const AGENTS = `${API_BASE}/api/agents`;
const TASKS = `${API_BASE}/api/tasks`;

async function jsonOr<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status} · ${text}`);
  }
  return (await resp.json()) as T;
}

export async function listAgents(
  includeArchived = false,
): Promise<{ ok: boolean; count: number; agents: Agent[] }> {
  const qs = includeArchived ? "?include_archived=true" : "";
  return jsonOr(await fetch(`${AGENTS}${qs}`));
}

export async function getAgent(
  agentId: string,
): Promise<{ ok: boolean; agent: Agent }> {
  return jsonOr(await fetch(`${AGENTS}/${encodeURIComponent(agentId)}`));
}

export async function createAgent(
  input: CreateAgentInput,
): Promise<{ ok: boolean; agent: Agent }> {
  return jsonOr(
    await fetch(AGENTS, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function patchAgent(
  agentId: string,
  patch: PatchAgentInput,
): Promise<{ ok: boolean; agent: Agent }> {
  return jsonOr(
    await fetch(`${AGENTS}/${encodeURIComponent(agentId)}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    }),
  );
}

export async function listAgentTasks(
  agentId: string,
  status?: TaskStatus,
): Promise<{ ok: boolean; count: number; tasks: AgentTask[] }> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return jsonOr(
    await fetch(`${AGENTS}/${encodeURIComponent(agentId)}/tasks${qs}`),
  );
}

export async function queueTask(
  agentId: string,
  prompt: string,
  metadata: Record<string, unknown> = {},
): Promise<{ ok: boolean; task: AgentTask }> {
  return jsonOr(
    await fetch(`${AGENTS}/${encodeURIComponent(agentId)}/tasks`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt, metadata }),
    }),
  );
}

export async function runTask(
  taskId: string,
  councilMode: "single" | "dual_vote" | "n_vote" = "dual_vote",
): Promise<{ ok: boolean; task: AgentTask }> {
  return jsonOr(
    await fetch(`${TASKS}/${encodeURIComponent(taskId)}/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ council_mode: councilMode }),
    }),
  );
}

export async function setAutopilot(
  agentId: string,
  enabled: boolean,
): Promise<{ ok: boolean; agent: Agent; autopilot: boolean }> {
  return jsonOr(
    await fetch(
      `${AGENTS}/${encodeURIComponent(agentId)}/autopilot?enabled=${enabled}`,
      { method: "POST" },
    ),
  );
}

export async function autopilotTickNow(): Promise<{
  ok: boolean;
  agents_visited: number;
  tasks_run: number;
  tasks_failed: number;
}> {
  return jsonOr(
    await fetch(`${AGENTS}/autopilot/tick`, { method: "POST" }),
  );
}

export function isAutopilot(agent: Agent | null): boolean {
  if (!agent) return false;
  // The flag lives in the agent's metadata; we don't surface metadata
  // through the public API today, so this helper falls back to the
  // typed `metadata` column when present (set by the server via PATCH).
  const anyAgent = agent as Agent & { metadata?: Record<string, unknown> };
  return Boolean(anyAgent.metadata?.autopilot);
}

export async function cancelTask(
  taskId: string,
): Promise<{ ok: boolean; task: AgentTask }> {
  return jsonOr(
    await fetch(`${TASKS}/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
    }),
  );
}

export function useAgents(intervalMs = 0): {
  agents: Agent[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const out = await listAgents();
      if (!cancelled.current) {
        setAgents(out.agents);
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

  return { agents, loading, error, refresh };
}

/** Status badge → tailwind colour token. Pure helper, easy to vitest. */
export function statusBadgeClass(status: AgentStatus | TaskStatus): string {
  switch (status) {
    case "active":
    case "running":
    case "done":
      return "text-emerald-300 ring-emerald-400/40";
    case "paused":
    case "awaiting_confirmation":
    case "pending":
      return "text-amber-300 ring-amber-400/40";
    case "archived":
    case "cancelled":
      return "text-zinc-400 ring-zinc-500/30";
    case "failed":
      return "text-rose-300 ring-rose-400/40";
    default:
      return "text-zinc-300 ring-zinc-500/30";
  }
}
