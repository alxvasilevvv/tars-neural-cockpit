/**
 * Pure helpers for ``<CockpitGate />``.
 *
 * The runtime detection is intentionally split out from the React
 * component so vitest can pin the contract without having to mount
 * the whole gate (which pulls in framer-motion + a large
 * lazy-imported cockpit). The component imports these helpers
 * directly so there's a single source of truth.
 *
 * Bug audit 2026-05-04 — added with the gate so the upgrade
 * upsell can never regress the "always render the cockpit when
 * the daemon answers in <1s" guarantee.
 */

const PREVIEW_FLAG_KEY = "tars.web.preview";

export interface WindowLike {
  __TAURI_INTERNALS__?: unknown;
  __TAURI__?: unknown;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/**
 * True when the runtime is a Tauri shell (desktop app), false when
 * it's a plain browser. Both Tauri 1.x (``__TAURI__``) and 2.x
 * (``__TAURI_INTERNALS__``) are honoured because the desktop shell
 * may pin either depending on the build channel.
 */
export function isInsideTauri(win?: WindowLike | null): boolean {
  if (!win) return false;
  return Boolean(win.__TAURI_INTERNALS__ || win.__TAURI__);
}

/** Read the operator's "show me the read-only preview" flag. */
export function readPreviewFlag(storage?: StorageLike | null): boolean {
  if (!storage) return false;
  try {
    return storage.getItem(PREVIEW_FLAG_KEY) === "1";
  } catch {
    return false;
  }
}

/** Persist (or clear) the operator's preview-mode opt-in. */
export function setPreviewFlag(
  value: boolean,
  storage?: StorageLike | null,
): void {
  if (!storage) return;
  try {
    if (value) {
      storage.setItem(PREVIEW_FLAG_KEY, "1");
    } else {
      storage.removeItem(PREVIEW_FLAG_KEY);
    }
  } catch {
    // Private mode / quota — silently swallow.
  }
}

/** The exported key, mostly for tests so the magic string isn't duplicated. */
export const __PREVIEW_FLAG_KEY = PREVIEW_FLAG_KEY;
