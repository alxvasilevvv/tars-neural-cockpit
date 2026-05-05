import { useEffect, useRef, useState } from "react";
import { getHealth } from "@/lib/api";

/**
 * useSidecarStatus — listens to the Tauri desktop sidecar lifecycle
 * events emitted by `desktop/src-tauri/src/sidecar.rs`. Browser
 * builds skip the listener entirely (gated by `__TAURI_INTERNALS__`).
 *
 * Schema source of truth: `desktop/src-tauri/sidecar-events.schema.json`.
 *
 * States:
 *   - "unknown"  — runtime not Tauri OR no event seen yet (cold load).
 *                  Cockpit should still try the API; this state means
 *                  "we have no extra info to add".
 *   - "starting" — Tauri runtime detected but no `started` event yet.
 *                  After ~5s without resolution, escalate to "failed".
 *   - "ready"    — `desktop.sidecar.started` received. Cockpit can
 *                  trust the local 127.0.0.1:8765 backend.
 *   - "failed"   — `desktop.sidecar.failed` received OR cold-load
 *                  timeout. Surface a banner with diagnostic detail.
 *   - "exited"   — `desktop.sidecar.exited` received unexpectedly
 *                  (i.e. backend crashed mid-session). Same as failed
 *                  for UI purposes but distinct for telemetry.
 */
export type SidecarStatus =
  | "unknown"
  | "starting"
  | "ready"
  | "failed"
  | "exited";

export interface SidecarStartedPayload {
  pid: number;
  port: number;
  took_ms: number;
  binary?: string;
  mode?: "pyoxidizer" | "python" | "external";
}

export interface SidecarFailedPayload {
  stage: "spawn" | "health_timeout" | "early_exit";
  error: string;
  took_ms: number;
  pid?: number | null;
}

export interface SidecarExitedPayload {
  pid: number;
  ran_ms: number;
  exit_code?: number | null;
  signal?: string | null;
}

export interface SidecarState {
  status: SidecarStatus;
  /** Last successful start (when status === "ready"). */
  started?: SidecarStartedPayload;
  /** Last failure (when status === "failed"). */
  failed?: SidecarFailedPayload;
  /** Last exit (when status === "exited"). */
  exited?: SidecarExitedPayload;
}

const COLD_LOAD_TIMEOUT_MS = 8_000;
const HEARTBEAT_INTERVAL_MS = 30_000;
const HEARTBEAT_FAIL_BUDGET = 2;

export function useSidecarStatus(): SidecarState {
  const [state, setState] = useState<SidecarState>(() => ({
    status: "unknown",
  }));
  const consecFails = useRef(0);

  useEffect(() => {
    const isTauri =
      typeof window !== "undefined" &&
      typeof (window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ !==
        "undefined";
    if (!isTauri) return; // browser build — keep "unknown".

    let mounted = true;
    let coldTimer: ReturnType<typeof setTimeout> | null = null;
    const offFns: Array<() => void> = [];

    setState({ status: "starting" });

    // Cold-load timeout: if no `started` arrives in 8s, escalate. The
    // sidecar polls health every 250 ms with a 15 s ceiling on the
    // Rust side, so 8 s is a soft warn before the hard fail.
    coldTimer = setTimeout(() => {
      if (!mounted) return;
      setState((s) =>
        s.status === "starting"
          ? {
              status: "failed",
              failed: {
                stage: "health_timeout",
                error: "no started event in 8s — backend may not be running",
                took_ms: COLD_LOAD_TIMEOUT_MS,
                pid: null,
              },
            }
          : s,
      );
    }, COLD_LOAD_TIMEOUT_MS);

    (async () => {
      try {
        const { listen } = await import("@tauri-apps/api/event");

        const offStarted = await listen<SidecarStartedPayload>(
          "desktop.sidecar.started",
          (e) => {
            if (!mounted) return;
            if (coldTimer) {
              clearTimeout(coldTimer);
              coldTimer = null;
            }
            setState({ status: "ready", started: e.payload });
          },
        );
        const offFailed = await listen<SidecarFailedPayload>(
          "desktop.sidecar.failed",
          (e) => {
            if (!mounted) return;
            if (coldTimer) {
              clearTimeout(coldTimer);
              coldTimer = null;
            }
            setState({ status: "failed", failed: e.payload });
          },
        );
        const offExited = await listen<SidecarExitedPayload>(
          "desktop.sidecar.exited",
          (e) => {
            if (!mounted) return;
            // Clean shutdown on app quit also fires this — UI doesn't
            // need to react. We surface only unexpected exits (mid-
            // session) because the app window is still open.
            setState({ status: "exited", exited: e.payload });
          },
        );

        offFns.push(offStarted, offFailed, offExited);
      } catch (err) {
        // @tauri-apps/api missing or load failed — treat as unknown
        // so the cockpit doesn't render alarming red banners.
        console.warn("[tars] sidecar listener init failed:", err);
        if (!mounted) return;
        setState({ status: "unknown" });
        if (coldTimer) {
          clearTimeout(coldTimer);
          coldTimer = null;
        }
      }
    })();

    return () => {
      mounted = false;
      if (coldTimer) clearTimeout(coldTimer);
      offFns.forEach((off) => {
        try {
          off();
        } catch {
          /* ignore */
        }
      });
    };
  }, []);

  // Wave 61 heartbeat — defense-in-depth on top of the Rust watcher.
  // The Rust watcher catches when the child PID exits, but it can't
  // detect a hung/zombie sidecar where the process is alive but
  // `/health` stops responding. Once we're in "ready", ping every
  // 30s; flip to "exited" after `HEARTBEAT_FAIL_BUDGET` consecutive
  // failures. Resets the counter on any success. Cheap (one HEAD-
  // sized request per 30s) and quietly stops when we leave "ready".
  useEffect(() => {
    if (state.status !== "ready") {
      consecFails.current = 0;
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const h = await getHealth();
        if (cancelled) return;
        if (h && (h.ok === true || h.status === "ok" || h.status === "ready")) {
          consecFails.current = 0;
          return;
        }
        // 2xx but unexpected shape — don't penalise; backend may be
        // mid-deploy. Reset.
        consecFails.current = 0;
      } catch {
        if (cancelled) return;
        consecFails.current += 1;
        if (consecFails.current >= HEARTBEAT_FAIL_BUDGET) {
          setState({
            status: "exited",
            exited: {
              pid: 0, // unknown — heartbeat-derived
              ran_ms: 0,
              exit_code: null,
              signal: "heartbeat_lost",
            },
          });
        }
      }
    };
    const id = setInterval(tick, HEARTBEAT_INTERVAL_MS);
    // Don't fire immediately — the "ready" event already proved health.
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [state.status]);

  return state;
}
