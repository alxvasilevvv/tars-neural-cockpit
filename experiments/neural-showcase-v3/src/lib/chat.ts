/**
 * Chat client for the TARS conversation layer (Phase L1).
 *
 * Backend surface:
 *   POST   /api/chat/threads
 *   GET    /api/chat/threads
 *   GET    /api/chat/threads/{id}
 *   PATCH  /api/chat/threads/{id}
 *   DELETE /api/chat/threads/{id}
 *   GET    /api/chat/threads/{id}/messages
 *   POST   /api/chat/threads/{id}/messages    (returns SSE)
 *
 * The streaming POST is consumed via `streamChat` below — we hand-roll
 * the SSE parser instead of using `EventSource` because the endpoint is
 * a one-shot POST (EventSource only does GET).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE } from "./api";
import type { PolicyMode } from "./api";
import { getSessionId } from "./session";

export type ChatRole = "operator" | "tars" | "tool" | "system";

export interface ChatThread {
  id: string;
  title: string | null;
  pack_slug: string | null;
  project_id: string | null;
  created_at: number;
  updated_at: number;
  last_session_id: string | null;
  archived: boolean;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  role: ChatRole;
  content: string;
  created_at: number;
  trace_id: string | null;
  parent_msg_id: string | null;
  cost_usd: number | null;
  route: string | null;
  council_id: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  voice_model: string | null;
  extra: Record<string, unknown>;
}

export interface ChatToolCall {
  id: string;
  message_id: string;
  slug: string;
  action_id: string;
  args: Record<string, unknown>;
  status:
    | "pending"
    | "queued"
    | "allowed"
    | "completed"
    | "failed"
    | "cancelled";
  started_at: number;
  completed_at: number | null;
  policy_token: string | null;
  result: Record<string, unknown> | null;
  cost_usd: number | null;
  error: string | null;
  trace_id: string | null;
}

export type ChatStreamEventKind =
  | "message.started"
  | "context.retrieved"
  | "token"
  | "tool_call.proposed"
  | "tool_call.queued"
  | "tool_call.allowed"
  | "tool_call.completed"
  | "tool_call.failed"
  | "usage"
  | "message.completed"
  | "stream.closed"
  | "error";

export interface ChatAttachment {
  id: string;
  thread_id: string;
  message_id: string | null;
  mime: string;
  filename: string | null;
  bytes_total: number;
  char_count: number;
  extracted_text_preview: string;
  status: string;
  error: string | null;
  content_hash: string | null;
  created_at: number;
  meta: Record<string, unknown>;
}

export interface ChatSourceCitation {
  citation_id: string;
  chunk_id: string;
  attachment_id: string;
  filename: string | null;
  heading: string | null;
  page: number | null;
  score: number;
}

export interface RetrievedChunkRef {
  citation_id: string;
  score: number;
  rank_semantic: number | null;
  rank_keyword: number | null;
  chunk: {
    id: string;
    attachment_id: string;
    filename: string | null;
    mime: string | null;
    page: number | null;
    heading: string | null;
    ord: number;
    text: string;
  };
}

export interface ChatStreamEvent<T = Record<string, unknown>> {
  kind: ChatStreamEventKind;
  data: T;
}

// --------------------------------------------------------------------
// Thread CRUD
// --------------------------------------------------------------------

export async function createThread(opts: {
  title?: string;
  packSlug?: string;
  projectId?: string;
}): Promise<ChatThread> {
  const r = await fetch(`${API_BASE}/api/chat/threads`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      title: opts.title,
      pack_slug: opts.packSlug,
      project_id: opts.projectId,
    }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { thread: ChatThread };
  return body.thread;
}

export async function listThreads(opts: {
  archived?: boolean;
  packSlug?: string;
  projectId?: string;
  limit?: number;
} = {}): Promise<ChatThread[]> {
  const qs = new URLSearchParams();
  if (typeof opts.archived === "boolean")
    qs.set("archived", String(opts.archived));
  if (opts.packSlug) qs.set("pack_slug", opts.packSlug);
  if (opts.projectId) qs.set("project_id", opts.projectId);
  if (opts.limit) qs.set("limit", String(opts.limit));
  const r = await fetch(`${API_BASE}/api/chat/threads?${qs}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { threads: ChatThread[] };
  return body.threads;
}

export async function describeThread(threadId: string): Promise<{
  thread: ChatThread;
  messages: ChatMessage[];
}> {
  const r = await fetch(`${API_BASE}/api/chat/threads/${threadId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as { thread: ChatThread; messages: ChatMessage[] };
}

export async function patchThread(
  threadId: string,
  updates: Partial<{
    title: string | null;
    pack_slug: string | null;
    project_id: string | null;
    archived: boolean;
  }>,
): Promise<ChatThread> {
  const r = await fetch(`${API_BASE}/api/chat/threads/${threadId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return ((await r.json()) as { thread: ChatThread }).thread;
}

export async function archiveThread(threadId: string): Promise<ChatThread> {
  const r = await fetch(`${API_BASE}/api/chat/threads/${threadId}`, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return ((await r.json()) as { thread: ChatThread }).thread;
}

// --------------------------------------------------------------------
// Streaming POST
// --------------------------------------------------------------------

export interface StreamOptions {
  text: string;
  attachments?: { id: string; filename?: string; mime?: string }[];
  policyMode?: PolicyMode;
  sessionId?: string;
  signal?: AbortSignal;
  onEvent: (ev: ChatStreamEvent) => void;
}

export async function streamChat(
  threadId: string,
  opts: StreamOptions,
): Promise<void> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "text/event-stream",
    "x-tars-session-id": opts.sessionId ?? getSessionId(),
  };
  if (opts.policyMode) headers["x-tars-policy-mode"] = opts.policyMode;

  const r = await fetch(
    `${API_BASE}/api/chat/threads/${threadId}/messages`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        text: opts.text,
        attachments: opts.attachments ?? [],
      }),
      signal: opts.signal,
    },
  );
  if (!r.ok || !r.body) {
    throw new Error(`HTTP ${r.status}`);
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseSseBlock(raw);
      if (ev) opts.onEvent(ev);
    }
  }
  if (buffer.trim()) {
    const ev = parseSseBlock(buffer);
    if (ev) opts.onEvent(ev);
  }
}

function parseSseBlock(block: string): ChatStreamEvent | null {
  let event: ChatStreamEventKind | null = null;
  let dataLine = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() as ChatStreamEventKind;
    } else if (line.startsWith("data:")) {
      dataLine = line.slice(5).trim();
    }
  }
  if (!event) return null;
  let data: Record<string, unknown> = {};
  if (dataLine) {
    try {
      data = JSON.parse(dataLine);
    } catch {
      data = { raw: dataLine };
    }
  }
  return { kind: event, data };
}

// --------------------------------------------------------------------
// React hook: useChatThread
// --------------------------------------------------------------------

export interface ChatTurnState {
  /** The local optimistic operator message currently being streamed. */
  pendingOperator: ChatMessage | null;
  /** The assistant message we're building up token-by-token. */
  draftAssistant: ChatMessage | null;
  /** Tool-call cards proposed during this turn. */
  toolCalls: ChatToolCall[];
  /** Retrieved RAG chunks for this turn (from `context.retrieved`). */
  retrieved: RetrievedChunkRef[];
  /** ledger snapshot from the most recent `usage` event. */
  usage: {
    tokens_in: number;
    tokens_out: number;
    cost_usd: number | null;
    total_cost_usd: number | null;
    route: string | null;
    model: string | null;
  } | null;
}

const EMPTY_TURN: ChatTurnState = {
  pendingOperator: null,
  draftAssistant: null,
  toolCalls: [],
  retrieved: [],
  usage: null,
};

export interface ChatThreadHook {
  thread: ChatThread | null;
  messages: ChatMessage[];
  turn: ChatTurnState;
  busy: boolean;
  error: string | null;
  send: (text: string, opts?: { policyMode?: PolicyMode }) => Promise<void>;
  cancel: () => void;
  refresh: () => Promise<void>;
}

export function useChatThread(threadId: string | null): ChatThreadHook {
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [turn, setTurn] = useState<ChatTurnState>(EMPTY_TURN);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (!threadId) return;
    try {
      const desc = await describeThread(threadId);
      setThread(desc.thread);
      setMessages(desc.messages);
    } catch (exc) {
      setError(String((exc as Error)?.message ?? exc));
    }
  }, [threadId]);

  useEffect(() => {
    setMessages([]);
    setThread(null);
    setTurn(EMPTY_TURN);
    setError(null);
    if (!threadId) return;
    void refresh();
  }, [threadId, refresh]);

  const send = useCallback(
    async (text: string, opts: { policyMode?: PolicyMode } = {}) => {
      if (!threadId || !text.trim() || busy) return;
      setBusy(true);
      setError(null);
      const optimistic: ChatMessage = {
        id: `optimistic_${Date.now()}`,
        thread_id: threadId,
        role: "operator",
        content: text,
        created_at: Date.now() / 1000,
        trace_id: null,
        parent_msg_id: null,
        cost_usd: null,
        route: null,
        council_id: null,
        tokens_in: null,
        tokens_out: null,
        voice_model: null,
        extra: {},
      };
      setTurn({
        pendingOperator: optimistic,
        draftAssistant: null,
        toolCalls: [],
        retrieved: [],
        usage: null,
      });

      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await streamChat(threadId, {
          text,
          policyMode: opts.policyMode,
          signal: ctrl.signal,
          onEvent: (ev) => {
            setTurn((prev) => reduceTurn(prev, ev));
          },
        });
        // Re-fetch the canonical message list once the stream closes —
        // gives us proper IDs / timestamps / cost data instead of the
        // optimistic placeholder.
        await refresh();
        setTurn(EMPTY_TURN);
      } catch (exc) {
        if ((exc as Error)?.name === "AbortError") {
          setTurn(EMPTY_TURN);
          return;
        }
        setError(String((exc as Error)?.message ?? exc));
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [threadId, busy, refresh],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return useMemo(
    () => ({ thread, messages, turn, busy, error, send, cancel, refresh }),
    [thread, messages, turn, busy, error, send, cancel, refresh],
  );
}

function reduceTurn(prev: ChatTurnState, ev: ChatStreamEvent): ChatTurnState {
  if (ev.kind === "message.started") {
    const data = ev.data as {
      msg_id: string;
      thread_id: string;
      voice: string;
    };
    return {
      ...prev,
      draftAssistant: {
        id: data.msg_id,
        thread_id: data.thread_id,
        role: "tars",
        content: "",
        created_at: Date.now() / 1000,
        trace_id: null,
        parent_msg_id: null,
        cost_usd: null,
        route: null,
        council_id: null,
        tokens_in: null,
        tokens_out: null,
        voice_model: data.voice,
        extra: {},
      },
    };
  }
  if (ev.kind === "context.retrieved") {
    const chunks = ((ev.data as { chunks?: RetrievedChunkRef[] }).chunks ??
      []) as RetrievedChunkRef[];
    return { ...prev, retrieved: chunks };
  }
  if (ev.kind === "token") {
    const text = String((ev.data as { text?: string }).text ?? "");
    if (!prev.draftAssistant) return prev;
    return {
      ...prev,
      draftAssistant: {
        ...prev.draftAssistant,
        content: prev.draftAssistant.content + text,
      },
    };
  }
  if (
    ev.kind === "tool_call.proposed" ||
    ev.kind === "tool_call.queued" ||
    ev.kind === "tool_call.allowed" ||
    ev.kind === "tool_call.completed" ||
    ev.kind === "tool_call.failed"
  ) {
    const data = ev.data as {
      tool_call_id?: string;
      slug?: string;
      action_id?: string;
      args?: Record<string, unknown>;
      result?: Record<string, unknown>;
      reason?: string;
      policy_token?: string;
      error?: string;
    };
    const id = data.tool_call_id ?? "";
    const existing = prev.toolCalls.find((tc) => tc.id === id);
    const status: ChatToolCall["status"] =
      ev.kind === "tool_call.proposed"
        ? "pending"
        : ev.kind === "tool_call.queued"
          ? "queued"
          : ev.kind === "tool_call.allowed"
            ? "allowed"
            : ev.kind === "tool_call.completed"
              ? "completed"
              : "failed";
    const next: ChatToolCall = existing
      ? {
          ...existing,
          status,
          result: data.result ?? existing.result ?? null,
          policy_token: data.policy_token ?? existing.policy_token,
          error: data.error ?? existing.error,
          completed_at:
            ev.kind === "tool_call.completed" ||
            ev.kind === "tool_call.failed"
              ? Date.now() / 1000
              : existing.completed_at,
        }
      : {
          id,
          message_id: prev.draftAssistant?.id ?? "",
          slug: data.slug ?? "",
          action_id: data.action_id ?? "",
          args: data.args ?? {},
          status,
          started_at: Date.now() / 1000,
          completed_at: null,
          policy_token: data.policy_token ?? null,
          result: data.result ?? null,
          cost_usd: null,
          error: data.error ?? null,
          trace_id: null,
        };
    const others = prev.toolCalls.filter((tc) => tc.id !== id);
    return { ...prev, toolCalls: [...others, next] };
  }
  if (ev.kind === "usage") {
    const data = ev.data as {
      tokens_in?: number;
      tokens_out?: number;
      cost_usd?: number | null;
      total_cost_usd?: number | null;
      route?: string | null;
      model?: string;
    };
    return {
      ...prev,
      usage: {
        tokens_in: Number(data.tokens_in ?? 0),
        tokens_out: Number(data.tokens_out ?? 0),
        cost_usd: data.cost_usd ?? null,
        total_cost_usd: data.total_cost_usd ?? null,
        route: data.route ?? null,
        model: data.model ?? null,
      },
    };
  }
  return prev;
}
