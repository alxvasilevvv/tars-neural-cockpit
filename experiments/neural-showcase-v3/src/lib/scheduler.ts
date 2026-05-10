// SYNC: claude-w97-scheduler
/**
 * scheduler.ts — thin REST client for the Wave 97 scheduler engine.
 *
 * All endpoints live under /api/scheduler/*. The cron engine is a
 * pure-stdlib parser on the backend (no croniter dep), so the
 * `validateCron` helper round-trips to it for both validation and
 * the next-5-runs preview.
 */

import { API_BASE } from "@/lib/api";

export interface Schedule {
  id: string;
  playbook_id: string;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  last_run_at: number | null;
  next_run_at: number | null;
  last_status: string | null;
  max_concurrent: number;
  args: Record<string, unknown>;
  created_at: number;
}

export interface RunRecord {
  id: string;
  schedule_id: string;
  started_at: number;
  finished_at: number | null;
  status: string;
  output_summary: string | null;
  trace_id: string | null;
  duration_ms: number | null;
}

export interface CronValidation {
  valid: boolean;
  expression?: string;
  timezone?: string;
  next_5_runs?: string[];
  error?: string;
}

/** POST /api/scheduler/validate-cron — server-side validation + preview. */
export async function validateCron(
  expression: string,
  timezone: string = "UTC",
): Promise<CronValidation> {
  try {
    const r = await fetch(`${API_BASE}/api/scheduler/validate-cron`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ expression, timezone }),
    });
    if (!r.ok) return { valid: false, error: `HTTP ${r.status}` };
    return (await r.json()) as CronValidation;
  } catch (e) {
    return { valid: false, error: (e as Error).message };
  }
}

/** GET /api/scheduler/schedules */
export async function listSchedules(playbookId?: string): Promise<Schedule[]> {
  const qs = playbookId
    ? `?playbook_id=${encodeURIComponent(playbookId)}`
    : "";
  const r = await fetch(`${API_BASE}/api/scheduler/schedules${qs}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { schedules?: Schedule[] };
  return body.schedules ?? [];
}

/** POST /api/scheduler/schedules */
export async function createSchedule(payload: {
  playbook_id: string;
  cron_expression: string;
  timezone?: string;
  args?: Record<string, unknown>;
  max_concurrent?: number;
  enabled?: boolean;
}): Promise<Schedule> {
  const r = await fetch(`${API_BASE}/api/scheduler/schedules`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { schedule: Schedule };
  return body.schedule;
}

/** PATCH /api/scheduler/schedules/{id} */
export async function patchSchedule(
  id: string,
  updates: Partial<{
    cron_expression: string;
    timezone: string;
    enabled: boolean;
    args: Record<string, unknown>;
    max_concurrent: number;
  }>,
): Promise<Schedule> {
  const r = await fetch(
    `${API_BASE}/api/scheduler/schedules/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(updates),
    },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { schedule: Schedule };
  return body.schedule;
}

/** DELETE /api/scheduler/schedules/{id} */
export async function deleteSchedule(id: string): Promise<void> {
  const r = await fetch(
    `${API_BASE}/api/scheduler/schedules/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

/** POST /api/scheduler/schedules/{id}/run-now */
export async function runScheduleNow(id: string): Promise<unknown> {
  const r = await fetch(
    `${API_BASE}/api/scheduler/schedules/${encodeURIComponent(id)}/run-now`,
    { method: "POST" },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as unknown;
}

/** GET /api/scheduler/schedules/{id}/history?limit=N */
export async function fetchHistory(
  id: string,
  limit: number = 20,
): Promise<RunRecord[]> {
  const r = await fetch(
    `${API_BASE}/api/scheduler/schedules/${encodeURIComponent(id)}/history?limit=${limit}`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { runs?: RunRecord[] };
  return body.runs ?? [];
}

/** Convenience: POST /api/playbooks/{id}/schedule */
export async function schedulePlaybook(
  playbookId: string,
  payload: {
    cron: string;
    timezone?: string;
    args?: Record<string, unknown>;
    enabled?: boolean;
  },
): Promise<Schedule> {
  const r = await fetch(
    `${API_BASE}/api/playbooks/${encodeURIComponent(playbookId)}/schedule`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { schedule: Schedule };
  return body.schedule;
}
