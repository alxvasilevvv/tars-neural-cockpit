/*
 * runtime/tauri.ts — IPC helpers, no-op outside the Tauri shell (W309 step 1).
 *
 * The cockpit ships into two surfaces:
 *   1. Tauri WKWebView (production, `desktop/src-tauri/`) — loads the
 *      built bundle via `frontendDist`; the `__TAURI__` global is
 *      injected before any user script runs.
 *   2. `vite dev` browser tab on port 5174 — no Tauri globals; any
 *      `invoke()` call is a no-op so the cockpit boots clean for
 *      design / interaction debugging without the desktop app.
 *
 * Module exports stay branch-free for callers: `invokeTauri()` returns
 * `undefined` outside Tauri instead of throwing, so chat / voice
 * runtime can safely poke at native IPC without sprinkling guards.
 *
 * No Tauri SDK import — the global is detected at runtime. Adding
 * `@tauri-apps/api` here would inflate the bundle by ~12 KB for one
 * helper. The native side currently doesn't expose any commands the
 * cockpit needs at MVP; this file establishes the seam so W310+ can
 * add screen-share / file-drop / clipboard plumbing without touching
 * every consumer.
 */

interface TauriGlobal {
  invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
  // Tauri 2.x moved the invoke surface under `.core`.
  core?: {
    invoke: (
      cmd: string,
      args?: Record<string, unknown>,
    ) => Promise<unknown>;
  };
}

declare global {
  interface Window {
    __TAURI__?: TauriGlobal;
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauri(): boolean {
  return (
    typeof window !== "undefined" &&
    (window.__TAURI__ !== undefined ||
      window.__TAURI_INTERNALS__ !== undefined)
  );
}

export async function invokeTauri<T = unknown>(
  cmd: string,
  args?: Record<string, unknown>,
): Promise<T | undefined> {
  if (!isTauri()) return undefined;
  const t = window.__TAURI__;
  const fn = t?.invoke ?? t?.core?.invoke;
  if (!fn) return undefined;
  try {
    return (await fn(cmd, args)) as T;
  } catch (err) {
    // Surface IPC errors as console warnings only — caller is
    // expected to treat undefined / failure as "feature unavailable".
    console.warn(`[tauri] invoke('${cmd}') failed`, err);
    return undefined;
  }
}
