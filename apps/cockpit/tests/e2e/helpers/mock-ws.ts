/**
 * mock-ws.ts — replaces window.WebSocket with a deterministic stub.
 *
 * The cockpit voice runtime opens a WS to /ws/voice for bidirectional
 * audio events. For e2e behavioural smoke we don't need real audio —
 * we just need the open / message / close lifecycle to fire in order.
 *
 * This helper is intentionally minimal. Step-2 implementer can extend
 * with frame-injection if the spec needs to test reconnect / dropped-
 * frame handling.
 *
 * W310-c scaffold; W309 step 2 wires WS scenarios as they come up.
 */
import type { Page } from "@playwright/test";

export async function mockVoiceWebSocket(page: Page) {
  await page.addInitScript(() => {
    type Frame = string | ArrayBuffer | Blob | ArrayBufferView;
    type Listener = (ev: unknown) => void;

    class StubWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      static instances: StubWebSocket[] = [];

      readyState = StubWebSocket.CONNECTING;
      url: string;
      sent: Frame[] = [];
      private listeners: Record<string, Listener[]> = {};
      onopen: Listener | null = null;
      onmessage: Listener | null = null;
      onclose: Listener | null = null;
      onerror: Listener | null = null;

      constructor(url: string) {
        this.url = url;
        StubWebSocket.instances.push(this);
        queueMicrotask(() => {
          this.readyState = StubWebSocket.OPEN;
          const ev = new Event("open");
          this.onopen?.(ev);
          this.dispatch("open", ev);
        });
      }

      send(data: Frame) {
        this.sent.push(data);
      }

      close() {
        this.readyState = StubWebSocket.CLOSED;
        const ev = new CloseEvent("close", { code: 1000, reason: "stub" });
        this.onclose?.(ev);
        this.dispatch("close", ev);
      }

      addEventListener(type: string, fn: Listener) {
        (this.listeners[type] ??= []).push(fn);
      }
      removeEventListener(type: string, fn: Listener) {
        this.listeners[type] = (this.listeners[type] ?? []).filter((x) => x !== fn);
      }
      private dispatch(type: string, ev: unknown) {
        for (const fn of this.listeners[type] ?? []) fn(ev);
      }

      __injectMessage(data: unknown) {
        const payload = typeof data === "string" ? data : JSON.stringify(data);
        const ev = new MessageEvent("message", { data: payload });
        this.onmessage?.(ev);
        this.dispatch("message", ev);
      }
    }

    Object.defineProperty(window, "WebSocket", {
      configurable: true,
      writable: true,
      value: StubWebSocket,
    });
    Object.defineProperty(window, "__stubWs", {
      configurable: true,
      writable: true,
      value: StubWebSocket,
    });
  });
}
