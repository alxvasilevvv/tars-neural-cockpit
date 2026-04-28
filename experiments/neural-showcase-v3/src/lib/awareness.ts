/**
 * Live awareness SSE client.
 *
 * Subscribes to /api/awareness/stream and emits parsed events. Returns
 * a disposer that closes the underlying EventSource.
 */

import { API_BASE } from "@/lib/api";

export interface AwarenessHello {
  kind: "hello";
  ts: number;
  service: string;
  trace_id: string | null;
  version: string;
  domains: string[];
  interval_s: number;
}

export interface AwarenessPulse {
  kind: "system.pulse";
  ts: number;
  tick: number;
  cpu: number;
  ram: number;
  uptime_s: number;
}

export interface AwarenessHeartbeat {
  kind: "domain.heartbeat";
  ts: number;
  tick: number;
  slug: string;
  armed: boolean;
  queue_depth: number;
}

export interface AwarenessBye {
  kind: "bye";
  ts: number;
  reason: string;
  ticks?: number;
}

export type AwarenessEvent =
  | AwarenessHello
  | AwarenessPulse
  | AwarenessHeartbeat
  | AwarenessBye;

export interface AwarenessHandlers {
  onEvent?: (e: AwarenessEvent) => void;
  onError?: (err: Event) => void;
  onOpen?: () => void;
}

export function subscribeAwareness({
  onEvent,
  onError,
  onOpen,
}: AwarenessHandlers): () => void {
  const url = `${API_BASE}/api/awareness/stream`;
  const es = new EventSource(url);
  es.onopen = () => onOpen?.();
  es.onerror = (err) => onError?.(err);
  es.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as AwarenessEvent;
      onEvent?.(data);
    } catch {
      // Bad frame, ignore.
    }
  };
  return () => es.close();
}
