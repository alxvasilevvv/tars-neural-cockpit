// SYNC: claude-w129-cowork
/**
 * Wave 129 — Cowork data layer.
 *
 * Talks to the backend `backend/core/cowork/` module via the brother's
 * core-bridge HTTP surface. Endpoints:
 *
 *   POST  /api/cowork/sessions                 — create
 *   GET   /api/cowork/sessions                 — list
 *   GET   /api/cowork/sessions/:slug           — fetch by slug
 *   POST  /api/cowork/sessions/:id/members     — join
 *   POST  /api/cowork/sessions/:id/heartbeat   — presence ping
 *   POST  /api/cowork/sessions/:id/cursor      — publish cursor
 *   POST  /api/cowork/sessions/:id/handoff     — create handoff
 *   POST  /api/cowork/handoff/:token/accept    — accept handoff
 *   GET   /api/cowork/sessions/:id/stream      — SSE stream
 *
 * Until brother wires those endpoints, the hooks fall back to a tiny
 * deterministic in-memory mock so the page is demo-able offline. The
 * contract (return shapes + hook names) is stable — when the backend
 * ships, only the fetch URLs swap, no page-level changes needed.
 */

import { useEffect, useRef, useState } from "react";

// ── types ──────────────────────────────────────────────────────────

export type SessionStatus = "live" | "paused" | "ended";
export type MemberRole = "owner" | "editor" | "viewer";

export interface CoworkSession {
  id: string;
  name: string;
  slug: string;
  owner_user_id: string;
  status: SessionStatus;
  created_at: number;
  ended_at: number | null;
  workspace_id: string | null;
  metadata: Record<string, unknown>;
}

export interface CoworkMember {
  id: string;
  session_id: string;
  display_name: string;
  user_id: string | null;
  email: string | null;
  role: MemberRole;
  color: string | null;
  joined_at: number;
  last_seen_at: number;
}

export interface CoworkPresence {
  member_id: string;
  last_seen_at: number;
  typing: boolean;
  focus_path: string | null;
}

export interface CoworkCursor {
  id: string;
  session_id: string;
  member_id: string;
  path: string;
  line: number;
  col: number;
  selection: { end_line: number; end_col: number } | null;
  updated_at: number;
}

export type CoworkEventType =
  | "agent.frame"
  | "presence"
  | "cursor"
  | "chat"
  | "handoff.created"
  | "handoff.accepted"
  | "handoff.revoked"
  | "session.ended"
  | "heartbeat";

export interface CoworkEvent {
  id: string;
  type: CoworkEventType;
  occurred_at: number;
  data: Record<string, unknown>;
}

// ── deterministic mock so the page is demo-able offline ────────────

const MOCK_MEMBERS: CoworkMember[] = [
  {
    id: "cm_alice",
    session_id: "cw_demo",
    display_name: "Alice",
    user_id: "u_alice",
    email: "alice@example.com",
    role: "owner",
    color: "#6366F1",
    joined_at: Date.now() / 1000 - 1200,
    last_seen_at: Date.now() / 1000,
  },
  {
    id: "cm_bob",
    session_id: "cw_demo",
    display_name: "Bob",
    user_id: "u_bob",
    email: "bob@example.com",
    role: "editor",
    color: "#8B5CF6",
    joined_at: Date.now() / 1000 - 800,
    last_seen_at: Date.now() / 1000 - 4,
  },
  {
    id: "cm_carol",
    session_id: "cw_demo",
    display_name: "Carol",
    user_id: "u_carol",
    email: null,
    role: "viewer",
    color: "#06B6D4",
    joined_at: Date.now() / 1000 - 400,
    last_seen_at: Date.now() / 1000 - 11,
  },
];

const MOCK_SESSION: CoworkSession = {
  id: "cw_demo",
  name: "Weekly review",
  slug: "weekly-review-demo01",
  owner_user_id: "u_alice",
  status: "live",
  created_at: Date.now() / 1000 - 1800,
  ended_at: null,
  workspace_id: null,
  metadata: { demo: true },
};

const MOCK_EVENT_VERBS: { type: CoworkEvent["type"]; label: string }[] = [
  { type: "agent.frame", label: "drafted plan section" },
  { type: "agent.frame", label: "ran research search" },
  { type: "agent.frame", label: "summarized findings" },
  { type: "cursor", label: "moved cursor" },
  { type: "chat", label: "added a comment" },
  { type: "agent.frame", label: "executed playbook step" },
];

let mockEvCounter = 0;
function generateMockEvent(): CoworkEvent {
  const verb = MOCK_EVENT_VERBS[mockEvCounter % MOCK_EVENT_VERBS.length];
  const member = MOCK_MEMBERS[mockEvCounter % MOCK_MEMBERS.length];
  mockEvCounter += 1;
  return {
    id: `ev_mock_${mockEvCounter}`,
    type: verb.type,
    occurred_at: Date.now() / 1000,
    data: {
      member_id: member.id,
      member_name: member.display_name,
      label: verb.label,
    },
  };
}

// ── fetch helpers (real path, fall back to mock on error) ──────────

const BASE = "/api/cowork";

async function tryFetch<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ── high-level API ─────────────────────────────────────────────────

export async function fetchSession(
  slug: string,
): Promise<CoworkSession | null> {
  const real = await tryFetch<CoworkSession>(`${BASE}/sessions/${slug}`);
  if (real) return real;
  // Mock fallback: only return the demo session for the demo slug.
  if (slug === MOCK_SESSION.slug || slug === "demo") return MOCK_SESSION;
  return null;
}

export async function listMembers(sessionId: string): Promise<CoworkMember[]> {
  const real = await tryFetch<{ members: CoworkMember[] }>(
    `${BASE}/sessions/${sessionId}/members`,
  );
  if (real?.members) return real.members;
  return MOCK_MEMBERS;
}

export async function listSessions(): Promise<CoworkSession[]> {
  const real = await tryFetch<{ sessions: CoworkSession[] }>(`${BASE}/sessions`);
  if (real?.sessions) return real.sessions;
  return [MOCK_SESSION];
}

export async function publishCursor(
  sessionId: string,
  body: {
    member_token: string;
    path: string;
    line: number;
    col: number;
    selection?: { end_line: number; end_col: number };
  },
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/sessions/${sessionId}/cursor`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function heartbeat(
  sessionId: string,
  body: {
    member_token: string;
    typing?: boolean;
    focus_path?: string;
  },
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/sessions/${sessionId}/heartbeat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function createHandoff(
  sessionId: string,
  body: { from_user_id: string; to_email?: string },
): Promise<{ token: string; expires_at: number } | null> {
  try {
    const res = await fetch(`${BASE}/sessions/${sessionId}/handoff`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as { token: string; expires_at: number };
  } catch {
    // Mock — gives the UI something to render even offline.
    const token = `mock_${Math.random().toString(36).slice(2, 14)}`;
    return { token, expires_at: Date.now() / 1000 + 15 * 60 };
  }
}

export async function acceptHandoff(
  token: string,
  accepted_by_user_id: string,
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/handoff/${token}/accept`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ accepted_by_user_id }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── hooks ──────────────────────────────────────────────────────────

/**
 * Live stream of cowork events for a session. Real backend exposes
 * SSE at `/api/cowork/sessions/:id/stream`; we fall back to a
 * deterministic mock generator at 2.5 s cadence when SSE fails.
 *
 * Returns a buffer of the last 40 events; older ones are evicted.
 */
export function useCoworkStream(sessionId: string | null) {
  const [events, setEvents] = useState<CoworkEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const mockTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    // Try real SSE first.
    let usingSse = false;
    try {
      // EventSource is unavailable in some non-browser test envs (jsdom).
      if (typeof EventSource !== "undefined") {
        const es = new EventSource(`${BASE}/sessions/${sessionId}/stream`);
        esRef.current = es;
        usingSse = true;
        es.onmessage = (msg) => {
          if (cancelled) return;
          try {
            const ev = JSON.parse(msg.data) as CoworkEvent;
            setEvents((prev) => [...prev.slice(-39), ev]);
          } catch {
            /* drop malformed frame */
          }
        };
        es.onerror = () => {
          // SSE error — fall through to mock so the demo keeps moving.
          es.close();
          esRef.current = null;
          if (!cancelled && !mockTimer.current) startMockStream();
        };
      }
    } catch {
      /* fall through */
    }
    if (!usingSse) startMockStream();

    function startMockStream() {
      if (mockTimer.current) return;
      mockTimer.current = setInterval(() => {
        if (cancelled) return;
        setEvents((prev) => [...prev.slice(-39), generateMockEvent()]);
      }, 2500);
    }

    return () => {
      cancelled = true;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (mockTimer.current) {
        clearInterval(mockTimer.current);
        mockTimer.current = null;
      }
    };
  }, [sessionId]);

  return events;
}

/**
 * Heartbeat ticker — pings the session every 10 s so other members
 * see the user as present. Cheap no-op if the backend is offline
 * (the request just fails silently).
 */
export function useHeartbeat(
  sessionId: string | null,
  memberToken: string | null,
) {
  useEffect(() => {
    if (!sessionId || !memberToken) return;
    let cancelled = false;
    const tick = () => {
      if (cancelled) return;
      void heartbeat(sessionId, { member_token: memberToken });
    };
    tick();
    const id = setInterval(tick, 10_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sessionId, memberToken]);
}

/**
 * Returns a memoised relative-time formatter ("3s ago", "1m ago", …).
 * Used by PresenceBar + event log.
 */
export function fmtRelative(at: number, now: number = Date.now() / 1000): string {
  const diff = Math.max(0, now - at);
  if (diff < 5) return "just now";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

/**
 * Returns true if a member's `last_seen_at` is within the live window.
 * Mirrors the backend `PRESENCE_TTL_S = 25 s` constant.
 */
export function isLive(last_seen_at: number, nowSec = Date.now() / 1000): boolean {
  return nowSec - last_seen_at < 25;
}

// ── re-exports used by Cowork page ──────────────────────────────────

export const COWORK_MOCK = {
  session: MOCK_SESSION,
  members: MOCK_MEMBERS,
};
