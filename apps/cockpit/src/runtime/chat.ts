/*
 * runtime/chat.ts — thread send/load + optimistic strand append
 * (W309 step 1, brief §3.4).
 *
 * Server contract (see `web_extras/routers/chat.py`):
 *   - POST `/api/chat/threads` — create thread, returns `{ok, thread}`.
 *   - GET  `/api/chat/threads/{id}` — returns `{ok, thread, messages}`.
 *   - POST `/api/chat/threads/{id}/messages` — Server-Sent Events
 *     stream (`text/event-stream`). The orchestrator yields per-event
 *     SSE frames: `trace`, free-form assistant deltas, `error`,
 *     `stream.closed`.
 *
 * Brief note: the brief §3.4 said "wait for WS chat.message event →
 * reconcile" — that was based on the legacy SPA's contract. The
 * current sidecar streams the assistant turn back on the POST
 * response itself (SSE), not via the realtime WS bus. WS handles
 * cross-cutting events (policy gate, awareness) but not chat deltas.
 * SSE-on-POST is the right transport for MVP; we'll wire WS for
 * out-of-band chat events (typing indicators, multi-device sync) in
 * W310+ when those endpoints actually exist.
 *
 * Local optimistic UI:
 *   - user message appended with `status: 'sending'`
 *   - on POST 200 + first SSE frame → `status: 'delivered'`
 *   - assistant placeholder appended once the first content delta
 *     arrives, then text grows in place
 *   - on SSE `error` → assistant flipped to `status: 'failed'`
 *   - on network failure → user flipped to `status: 'failed'`
 *
 * Subscribers to `onChange()` get a synchronous tick after every
 * mutation; the entry script re-renders the strand from
 * `getMessages()` without diffing.
 */

import { api, getApiBase, ApiError } from "./api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | string;
  text: string;
  ts: number;
  status?: "sending" | "delivered" | "failed";
  trace_id?: string;
}

export interface ChatThread {
  id: string;
  title?: string | null;
  voice_persona_id?: string | null;
  [k: string]: unknown;
}

interface ChatState {
  thread: ChatThread | null;
  messages: ChatMessage[];
  onChange: Set<() => void>;
  inflight: AbortController | null;
}

const state: ChatState = {
  thread: null,
  messages: [],
  onChange: new Set(),
  inflight: null,
};

/** Subscribe to strand changes; returns the unsubscribe handle. */
export function onChange(cb: () => void): () => void {
  state.onChange.add(cb);
  return () => state.onChange.delete(cb);
}

function emit(): void {
  for (const cb of state.onChange) {
    try {
      cb();
    } catch (err) {
      console.warn("[chat] change handler failed", err);
    }
  }
}

export function getThread(): ChatThread | null {
  return state.thread;
}

export function getMessages(): ChatMessage[] {
  return [...state.messages];
}

export async function setup(
  opts: { threadId?: string } = {},
): Promise<void> {
  if (opts.threadId) {
    const res = await api<{
      ok: boolean;
      thread: ChatThread;
      messages: ChatMessage[];
    }>(`/api/chat/threads/${opts.threadId}`);
    state.thread = res.thread;
    // Keep the last 20 — brief §3.4 ("cockpit reload preserves
    // last 20 messages"). Server returns chronological; slice tail.
    state.messages = (res.messages ?? []).slice(-20);
  } else {
    const res = await api<{ ok: boolean; thread: ChatThread }>(
      "/api/chat/threads",
      { method: "POST", body: {} },
    );
    state.thread = res.thread;
    state.messages = [];
  }
  emit();
}

export function teardown(): void {
  if (state.inflight) {
    state.inflight.abort();
    state.inflight = null;
  }
  state.thread = null;
  state.messages = [];
  state.onChange.clear();
}

/**
 * Optimistically append the user message, POST to messages endpoint,
 * stream the SSE response into a growing assistant message. Resolves
 * when the stream closes (clean or errored).
 */
export async function send(text: string): Promise<void> {
  if (!state.thread) throw new Error("chat_no_thread");
  const trimmed = text.trim();
  if (!trimmed) return;

  const userMsg: ChatMessage = {
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    role: "user",
    text: trimmed,
    ts: Date.now() / 1000,
    status: "sending",
  };
  state.messages.push(userMsg);
  emit();

  const assistantMsg: ChatMessage = {
    id: `local-asst-${userMsg.id}`,
    role: "assistant",
    text: "",
    ts: Date.now() / 1000,
    status: "sending",
  };

  const ac = new AbortController();
  state.inflight = ac;

  let assistantStarted = false;
  let errored = false;

  try {
    const res = await fetch(
      `${getApiBase()}/api/chat/threads/${state.thread.id}/messages`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "text/event-stream",
        },
        body: JSON.stringify({ text: trimmed }),
        signal: ac.signal,
      },
    );

    if (!res.ok || !res.body) {
      throw new ApiError(
        res.status,
        await res.text().catch(() => ""),
        "/api/chat/threads/.../messages",
      );
    }

    // POST 200 + body present — user message is server-acked.
    userMsg.status = "delivered";
    emit();

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    // Streaming SSE parser: frames separated by blank line.
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      while (true) {
        const sep = buf.indexOf("\n\n");
        if (sep === -1) break;
        const frame = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        handleFrame(frame, assistantMsg, () => {
          if (!assistantStarted) {
            assistantStarted = true;
            state.messages.push(assistantMsg);
          }
          emit();
        });
      }
    }
  } catch (err) {
    errored = true;
    userMsg.status = "failed";
    if (assistantStarted) assistantMsg.status = "failed";
    console.warn("[chat] send failed", err);
    emit();
  } finally {
    state.inflight = null;
    if (!errored && assistantStarted) {
      assistantMsg.status = "delivered";
      emit();
    }
  }
}

function handleFrame(
  frame: string,
  asstAcc: ChatMessage,
  onUpdate: () => void,
): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    } else if (line.startsWith(":")) {
      /* SSE comment, ignore */
    }
  }
  const dataStr = dataLines.join("\n");
  if (!dataStr) return;

  let data: unknown;
  try {
    data = JSON.parse(dataStr);
  } catch {
    return;
  }
  const obj = (data ?? {}) as Record<string, unknown>;

  if (eventName === "trace" && typeof obj.trace_id === "string") {
    asstAcc.trace_id = obj.trace_id;
    onUpdate();
    return;
  }
  if (eventName === "error") {
    asstAcc.status = "failed";
    const err = typeof obj.error === "string" ? obj.error : "unknown";
    asstAcc.text = `${asstAcc.text}\n[error: ${err}]`;
    onUpdate();
    return;
  }
  if (eventName === "stream.closed") {
    return;
  }

  // Default: assistant content. Orchestrator emits a few shapes — accept
  // the common ones so we don't have to chase exact event names.
  const piece =
    (typeof obj.delta === "string" && obj.delta) ||
    (typeof obj.text === "string" && obj.text) ||
    (typeof obj.content === "string" && obj.content) ||
    "";
  if (piece) {
    asstAcc.text = asstAcc.text + piece;
    onUpdate();
  }
}
