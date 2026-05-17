/*
 * runtime/ws.ts — single WebSocket manager for the TARS realtime bus
 * (W309 step 1).
 *
 * Server contract (see `web_extras/routers/realtime.py`):
 *   - Endpoint: `${apiBase.replace(/^http/, 'ws')}/api/realtime`
 *   - Protocol: `tars.realtime.v1` (advertised in the `hello` envelope).
 *   - Server pushes JSON envelopes: `{type, data?, ts}`.
 *   - First message after connect is `{type: 'hello', topics, heartbeat_interval_s, protocol}`.
 *   - Client subscribes via `{op: 'subscribe', topics: [...]}` / mirror op.
 *   - Server sends `{type: 'heartbeat'}` every N seconds (server-driven).
 *
 * Reconnect strategy: exponential backoff `1s → 30s` with full jitter
 * (Marc Brooker's "Exponential Backoff and Jitter"). Reset on any
 * successful `open`. Close codes:
 *   1000 — clean shutdown (teardown). Don't reconnect.
 *   1006 — abnormal (network drop, sidecar restart). Reconnect.
 *   4001 — reserved for auth-fail. Emit synthetic `auth_fail` event,
 *          stop the loop, let caller surface a CTA.
 *
 * Singleton at the module level: only one WS per cockpit session.
 * Multiple consumers attach handlers via `on()` / `onStatus()`.
 */

export type WsStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";

export interface WsEnvelope {
  type: string;
  data?: unknown;
  ts?: number;
  [k: string]: unknown;
}

type Handler = (env: WsEnvelope) => void;
type StatusHandler = (status: WsStatus) => void;

const BACKOFF_MIN_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;

function getWsUrl(): string {
  try {
    const override = window.localStorage.getItem("TARS_WS_URL");
    if (override && override.trim()) return override.trim();
  } catch {
    /* private mode */
  }
  // Derive from API base so both knobs move together when the
  // operator points the cockpit at a remote daemon.
  let base = "http://127.0.0.1:8765";
  try {
    const apiOverride = window.localStorage.getItem("TARS_API_URL");
    if (apiOverride && apiOverride.trim()) {
      base = apiOverride.trim().replace(/\/+$/, "");
    }
  } catch {
    /* */
  }
  return `${base.replace(/^http/, "ws")}/api/realtime`;
}

export class WsManager {
  private ws: WebSocket | null = null;
  private status: WsStatus = "idle";
  private handlers = new Map<string, Set<Handler>>();
  private statusHandlers = new Set<StatusHandler>();
  private wantOpen = false;
  private attempt = 0;
  private retryTimer: number | null = null;
  private subscribedTopics = new Set<string>();

  setup(initialTopics: string[] = []): void {
    for (const t of initialTopics) this.subscribedTopics.add(t);
    // Idempotency: a second setup() (HMR, accidental re-boot, future
    // navigation re-entry) must not orphan the prior socket. If a
    // socket is alive or a retry is already scheduled, just merge the
    // new topic set into the running session and return.
    if (
      this.wantOpen &&
      (this.ws !== null || this.retryTimer !== null)
    ) {
      // Forward any newly-added topics to the live socket.
      if (this.ws && this.ws.readyState === WebSocket.OPEN && initialTopics.length) {
        try {
          this.ws.send(
            JSON.stringify({ op: "subscribe", topics: initialTopics }),
          );
        } catch {
          /* ignored */
        }
      }
      return;
    }
    this.wantOpen = true;
    this.connect();
  }

  teardown(): void {
    this.wantOpen = false;
    if (this.retryTimer !== null) {
      window.clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close(1000, "teardown");
      } catch {
        /* */
      }
      this.ws = null;
    }
    this.setStatus("closed");
  }

  on(type: string, handler: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) {
      set = new Set();
      this.handlers.set(type, set);
    }
    set.add(handler);
    return () => set!.delete(handler);
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    // Emit current synchronously so the UI doesn't flash through
    // an "idle" state before the first transition.
    handler(this.status);
    return () => this.statusHandlers.delete(handler);
  }

  getStatus(): WsStatus {
    return this.status;
  }

  subscribe(topics: string[]): void {
    for (const t of topics) this.subscribedTopics.add(t);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ op: "subscribe", topics }));
    }
  }

  unsubscribe(topics: string[]): void {
    for (const t of topics) this.subscribedTopics.delete(t);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ op: "unsubscribe", topics }));
    }
  }

  private connect(): void {
    if (!this.wantOpen) return;
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");

    let ws: WebSocket;
    try {
      ws = new WebSocket(getWsUrl());
    } catch (err) {
      console.warn("[ws] construct failed", err);
      this.scheduleRetry();
      return;
    }
    this.ws = ws;

    ws.addEventListener("open", () => {
      // Teardown may have landed while we were in CONNECTING — abort
      // cleanly so the status badge doesn't flicker green-then-closed.
      if (!this.wantOpen) {
        try {
          ws.close(1000, "teardown_during_connect");
        } catch {
          /* ignored */
        }
        return;
      }
      this.attempt = 0;
      this.setStatus("open");
      if (this.subscribedTopics.size) {
        ws.send(
          JSON.stringify({
            op: "subscribe",
            topics: [...this.subscribedTopics],
          }),
        );
      }
    });

    ws.addEventListener("message", (evt) => {
      let env: WsEnvelope;
      try {
        env = JSON.parse(String(evt.data));
      } catch {
        return;
      }
      this.dispatch(env);
    });

    ws.addEventListener("close", (evt) => {
      this.ws = null;
      if (!this.wantOpen) {
        this.setStatus("closed");
        return;
      }
      if (evt.code === 4001) {
        this.dispatch({
          type: "auth_fail",
          data: { reason: evt.reason },
        });
        this.setStatus("closed");
        return;
      }
      this.scheduleRetry();
    });

    ws.addEventListener("error", () => {
      // The close handler does the actual reconnection bookkeeping;
      // `error` always fires before `close` on browser WebSocket.
    });
  }

  private scheduleRetry(): void {
    this.attempt += 1;
    const ceiling = Math.min(
      BACKOFF_MIN_MS * 2 ** (this.attempt - 1),
      BACKOFF_MAX_MS,
    );
    // Full jitter — see brief §3.2 (reconnect exp backoff 1s → 30s).
    const delay = Math.floor(Math.random() * ceiling);
    this.setStatus("reconnecting");
    this.retryTimer = window.setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, delay);
  }

  private setStatus(s: WsStatus): void {
    if (this.status === s) return;
    this.status = s;
    for (const h of this.statusHandlers) {
      try {
        h(s);
      } catch (err) {
        console.warn("[ws] status handler failed", err);
      }
    }
  }

  private dispatch(env: WsEnvelope): void {
    const set = this.handlers.get(env.type);
    if (!set) return;
    for (const h of set) {
      try {
        h(env);
      } catch (err) {
        console.warn(`[ws] handler for "${env.type}" failed`, err);
      }
    }
  }
}

// Module-level singleton — only one WS per cockpit session.
let _instance: WsManager | null = null;

export function ws(): WsManager {
  if (!_instance) _instance = new WsManager();
  return _instance;
}
