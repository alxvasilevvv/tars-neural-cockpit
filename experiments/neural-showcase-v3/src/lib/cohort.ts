// SYNC: claude-w89-fe-only
/**
 * Wave 89 — Workshop cohort facilitator dashboard data layer.
 *
 * Mock data shipped for facilitator demo before W2-PR2 backend lands.
 * When `/api/cohort/*` endpoints exist, swap mock fallback for real
 * (same hook contract). The `usePollAttendees`, `useCohortStream`,
 * and `broadcast` exports are designed to be drop-in replaceable —
 * the page never reaches into the mock generator directly.
 *
 * Mock data strategy:
 *   - 15 deterministic attendees with generic first names (no PII).
 *   - Phase distribution roughly mirrors a healthy Day-2 cohort:
 *     a few stragglers in Intake, the bulk in Design / Test, two
 *     early finishers in Deploy.
 *   - SSE event generator picks a random attendee + verb every
 *     2-5 seconds. Verbs are scoped to "things a facilitator would
 *     actually want to see" (started backtest, hit HIL gate, saved
 *     draft, deployed agent, errored on run).
 *   - All timestamps are computed at hook-mount so the dashboard is
 *     deterministic per page-load but feels live across refreshes.
 */

import { useEffect, useRef, useState } from "react";

// ── types ───────────────────────────────────────────────────────────

export type Phase = "intake" | "design" | "test" | "deploy";

export interface Attendee {
  id: string;
  name: string;
  email: string;
  phase: Phase;
  /** Free-form last action label (already i18n-fixed for the demo). */
  lastAction: string;
  /** Number of playbooks executed this session. */
  playbooksRun: number;
  /** Number of supervisor errors / failures observed. */
  errors: number;
  /** Minutes since last activity. */
  idleMin: number;
  /** ISO timestamp of last action — surfaced in side-panel timeline. */
  lastActionAt: string;
}

export type SSEEventKind =
  | "phase_advance"
  | "playbook_start"
  | "playbook_finish"
  | "hil_gate"
  | "error"
  | "broadcast_ack"
  | "join";

export interface CohortEvent {
  id: string;
  kind: SSEEventKind;
  attendeeId: string;
  attendeeName: string;
  message: string;
  /** ISO timestamp. */
  at: string;
}

export interface TimelineEntry {
  at: string;
  label: string;
  kind: SSEEventKind | "note";
}

// ── deterministic attendee fixtures ─────────────────────────────────

const FIRST_NAMES = [
  "Alice",
  "Bob",
  "Carol",
  "David",
  "Eve",
  "Frank",
  "Grace",
  "Henry",
  "Iris",
  "Julian",
  "Kira",
  "Leo",
  "Maya",
  "Noah",
  "Olive",
] as const;

const LAST_INITIALS = [
  "C.",
  "R.",
  "M.",
  "K.",
  "S.",
  "T.",
  "L.",
  "P.",
  "W.",
  "B.",
  "H.",
  "G.",
  "F.",
  "D.",
  "N.",
] as const;

// Phase distribution chosen so the four stat tiles surface meaningful
// percentages: ~13% intake, ~33% design, ~33% test, ~20% deploy. The
// remaining ~1% rounding is absorbed by the deploy bucket since
// "everyone's done" is the optimistic case.
const PHASE_FOR_INDEX: readonly Phase[] = [
  "intake",
  "intake",
  "design",
  "design",
  "design",
  "design",
  "design",
  "test",
  "test",
  "test",
  "test",
  "test",
  "deploy",
  "deploy",
  "deploy",
];

const LAST_ACTION_BY_PHASE: Record<Phase, string[]> = {
  intake: [
    "Filled intake survey",
    "Joined Slack workspace",
    "Started intake form",
  ],
  design: [
    "Saved agent draft",
    "Edited playbook spec",
    "Synthesized playbook from text",
    "Reviewed risk tier",
  ],
  test: [
    "Backtest started",
    "Backtest completed",
    "Hit HIL gate",
    "Inspected trace",
  ],
  deploy: [
    "Deployed agent",
    "Wired to broker sandbox",
    "Anchored receipt batch",
  ],
};

function deterministicAttendees(): Attendee[] {
  const now = Date.now();
  return FIRST_NAMES.map((first, i) => {
    const phase = PHASE_FOR_INDEX[i];
    const initial = LAST_INITIALS[i];
    const slug = first.toLowerCase();
    // Pseudo-random but deterministic per-row stats.
    const playbooksRun =
      phase === "intake" ? 0 : phase === "design" ? 1 : phase === "test" ? 3 : 5;
    // Two attendees carry visible errors so the alerts panel always
    // has something on stage during the demo.
    const errors = i === 1 ? 2 : i === 6 ? 3 : 0;
    // Idle minutes: cycle through 1, 4, 7, 12, 19 to give a realistic
    // spread — enough to sort meaningfully.
    const idleMin = [1, 7, 2, 4, 1, 12, 19, 3, 1, 5, 8, 2, 1, 14, 6][i];
    const actions = LAST_ACTION_BY_PHASE[phase];
    const lastAction = actions[i % actions.length];
    const lastActionAt = new Date(now - idleMin * 60_000).toISOString();
    return {
      id: `att-${i + 1}`,
      name: `${first} ${initial}`,
      email: `${slug}@workshop.demo`,
      phase,
      lastAction,
      playbooksRun,
      errors,
      idleMin,
      lastActionAt,
    };
  });
}

// ── derived stats ───────────────────────────────────────────────────

export interface CohortStats {
  total: number;
  activeNow: number;
  byPhase: Record<Phase, { count: number; pct: number }>;
}

export const ACTIVE_THRESHOLD_MIN = 5;

export function computeStats(rows: Attendee[]): CohortStats {
  const total = rows.length || 1;
  const byPhase: Record<Phase, { count: number; pct: number }> = {
    intake: { count: 0, pct: 0 },
    design: { count: 0, pct: 0 },
    test: { count: 0, pct: 0 },
    deploy: { count: 0, pct: 0 },
  };
  let activeNow = 0;
  for (const r of rows) {
    byPhase[r.phase].count += 1;
    if (r.idleMin <= ACTIVE_THRESHOLD_MIN) activeNow += 1;
  }
  for (const k of Object.keys(byPhase) as Phase[]) {
    byPhase[k].pct = Math.round((byPhase[k].count / total) * 100);
  }
  return { total, activeNow, byPhase };
}

// ── phase tint helpers ──────────────────────────────────────────────

export function phaseTint(phase: Phase): string {
  switch (phase) {
    case "intake":
      return "var(--brand-cyan)";
    case "design":
      return "var(--brand-violet)";
    case "test":
      return "var(--brand-indigo)";
    case "deploy":
      return "#22c55e"; // green-500
  }
}

export function phaseLabel(phase: Phase): string {
  switch (phase) {
    case "intake":
      return "Intake";
    case "design":
      return "Design";
    case "test":
      return "Test";
    case "deploy":
      return "Deploy";
  }
}

// ── mock SSE generator ──────────────────────────────────────────────

const VERB_BY_KIND: Record<SSEEventKind, (name: string) => string> = {
  phase_advance: (n) => `${n} advanced to next phase`,
  playbook_start: (n) => `${n} started a backtest`,
  playbook_finish: (n) => `${n} finished a playbook run`,
  hil_gate: (n) => `${n} hit HIL gate — awaiting confirm`,
  error: (n) => `${n} hit an error in latest run`,
  broadcast_ack: (n) => `${n} acknowledged broadcast`,
  join: (n) => `${n} joined the cohort`,
};

const EVENT_KINDS: SSEEventKind[] = [
  "playbook_start",
  "playbook_finish",
  "hil_gate",
  "error",
  "phase_advance",
  "join",
];

let _eventSeq = 0;

export function mockSSE(
  attendees: Attendee[],
  onEvent: (e: CohortEvent) => void,
): () => void {
  let stopped = false;
  function tick(): void {
    if (stopped) return;
    const att = attendees[Math.floor(Math.random() * attendees.length)];
    const kind = EVENT_KINDS[Math.floor(Math.random() * EVENT_KINDS.length)];
    _eventSeq += 1;
    onEvent({
      id: `evt-${_eventSeq}`,
      kind,
      attendeeId: att.id,
      attendeeName: att.name,
      message: VERB_BY_KIND[kind](att.name),
      at: new Date().toISOString(),
    });
    // 2-5s jitter — chosen so the right-rail stream feels alive without
    // turning into a Twitch chat.
    const next = 2000 + Math.floor(Math.random() * 3000);
    window.setTimeout(tick, next);
  }
  // Kick off after a short beat so the first event lands after the
  // page settles.
  const initial = window.setTimeout(tick, 800);
  return () => {
    stopped = true;
    window.clearTimeout(initial);
  };
}

// ── hooks ───────────────────────────────────────────────────────────

/**
 * Returns the cohort attendee list. Mock today; will swap to a fetch
 * against `GET /api/cohort/attendees` (with periodic poll) once the
 * backend ships. Hook contract is `{ rows, refresh, pending }`.
 */
export function usePollAttendees(): {
  rows: Attendee[];
  refresh: () => void;
  pending: boolean;
} {
  const [rows, setRows] = useState<Attendee[]>(() => deterministicAttendees());
  const [pending] = useState(true); // Mock backend is always "pending" until W2-PR2.
  const refresh = (): void => {
    // In real impl: re-fetch /api/cohort/attendees. Mock just regens
    // (but with the same deterministic seed, so visually identical —
    // swap to a real fetcher when backend lands).
    setRows(deterministicAttendees());
  };
  return { rows, refresh, pending };
}

/**
 * Live event stream for the right-rail activity feed. Mock today via
 * `mockSSE`; real impl will open `EventSource("/api/cohort/stream")`
 * and dispatch the same `CohortEvent` shape.
 */
export function useCohortStream(attendees: Attendee[]): CohortEvent[] {
  const [events, setEvents] = useState<CohortEvent[]>([]);
  const attendeesRef = useRef(attendees);
  attendeesRef.current = attendees;
  useEffect(() => {
    if (attendeesRef.current.length === 0) return;
    const stop = mockSSE(attendeesRef.current, (e) => {
      setEvents((prev) => [e, ...prev].slice(0, 40));
    });
    return stop;
  }, []);
  return events;
}

/**
 * Broadcast a message to the entire cohort. Mock POST today; will
 * fire `POST /api/cohort/broadcast` when backend lands. Returns
 * `{ ok: true }` on success, `{ ok: false, reason }` otherwise.
 */
export async function broadcast(
  message: string,
): Promise<{ ok: boolean; reason?: string }> {
  if (!message.trim()) {
    return { ok: false, reason: "Empty message." };
  }
  // Try real endpoint first. 404 → mock fallback (silent ack).
  try {
    const r = await fetch("/api/cohort/broadcast", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (r.status === 404) {
      // Backend not shipped yet — mock-ack so the UI behaves identically.
      await new Promise((resolve) => window.setTimeout(resolve, 280));
      return { ok: true };
    }
    if (!r.ok) {
      return { ok: false, reason: `HTTP ${r.status}` };
    }
    return { ok: true };
  } catch {
    // Network unreachable (file://, no dev backend) — mock-ack.
    await new Promise((resolve) => window.setTimeout(resolve, 280));
    return { ok: true };
  }
}

/**
 * Mark an attendee as needing facilitator help. Mock POST today; will
 * fire `POST /api/cohort/{id}/flag` once backend lands.
 */
export async function flagAttendee(
  attendeeId: string,
): Promise<{ ok: boolean; reason?: string }> {
  try {
    const r = await fetch(`/api/cohort/${attendeeId}/flag`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    });
    if (r.status === 404) {
      await new Promise((resolve) => window.setTimeout(resolve, 240));
      return { ok: true };
    }
    if (!r.ok) return { ok: false, reason: `HTTP ${r.status}` };
    return { ok: true };
  } catch {
    await new Promise((resolve) => window.setTimeout(resolve, 240));
    return { ok: true };
  }
}

// ── attendee detail timeline (mock) ─────────────────────────────────

/**
 * Build a deterministic 8-12 entry timeline for an attendee. Used by
 * `<AttendeeDetail />` side panel. Real impl will fetch from
 * `GET /api/cohort/{id}/timeline`.
 */
export function buildTimeline(attendee: Attendee): TimelineEntry[] {
  const now = Date.now();
  const idx = Number(attendee.id.split("-")[1] ?? 0);
  const phase = attendee.phase;
  // 8-12 entries; vary count slightly so the panel isn't uniform.
  const count = 8 + (idx % 5);
  const TEMPLATES: Array<[string, SSEEventKind | "note"]> = [
    ["Joined cohort", "join"],
    ["Filled intake form", "note"],
    ["Opened design canvas", "note"],
    ["Saved agent draft", "playbook_start"],
    ["Synthesized playbook from text", "note"],
    ["Reviewed risk tier", "note"],
    ["Started a backtest", "playbook_start"],
    ["Backtest completed", "playbook_finish"],
    ["Hit HIL gate", "hil_gate"],
    ["Acknowledged broadcast", "broadcast_ack"],
    ["Edited playbook step", "note"],
    ["Inspected trace", "note"],
  ];
  // If attendee is in deploy, append a deploy event at the head.
  const entries: TimelineEntry[] = [];
  for (let i = 0; i < count; i++) {
    const [label, kind] = TEMPLATES[i % TEMPLATES.length];
    entries.push({
      at: new Date(now - (count - i) * 7 * 60_000).toISOString(),
      label,
      kind,
    });
  }
  if (phase === "deploy") {
    entries.push({
      at: new Date(now - 2 * 60_000).toISOString(),
      label: "Deployed agent to sandbox",
      kind: "phase_advance",
    });
  }
  if (attendee.errors > 0) {
    entries.push({
      at: new Date(now - 4 * 60_000).toISOString(),
      label: `Errored on run (${attendee.errors} total)`,
      kind: "error",
    });
  }
  return entries;
}

// ── CSV export ──────────────────────────────────────────────────────

/**
 * Serialize the attendee table into CSV for the bottom-of-page
 * download button. Headers match the visible table columns.
 */
export function toCSV(rows: Attendee[]): string {
  const header = [
    "name",
    "email",
    "phase",
    "last_action",
    "playbooks_run",
    "errors",
    "idle_min",
    "last_action_at",
  ];
  const esc = (v: string | number): string => {
    const s = String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const lines = [header.join(",")];
  for (const r of rows) {
    lines.push(
      [
        esc(r.name),
        esc(r.email),
        esc(r.phase),
        esc(r.lastAction),
        esc(r.playbooksRun),
        esc(r.errors),
        esc(r.idleMin),
        esc(r.lastActionAt),
      ].join(","),
    );
  }
  return lines.join("\n");
}
