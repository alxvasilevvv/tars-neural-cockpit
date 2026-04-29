import { toast } from "@/lib/toast";

/**
 * errorReporter — converts uncaught browser errors into operator-
 * grade toasts. Privacy-aware:
 *   - Never sends anywhere on the network. Stack traces stay in the
 *     browser, the operator sees a brief surface-level message, the
 *     real one is logged to `console.error` for devtools.
 *   - Throttled by message hash (5s) so a re-render loop can't spam
 *     the toast bus.
 *   - Best-effort de-noise: TS-runtime "Script error." with no
 *     stack info (cross-origin script tag) is dropped.
 *
 * Wired once from `src/main.tsx` after the SW registration block.
 */

const RECENT = new Map<string, number>();
const THROTTLE_MS = 5000;

function shouldEmit(key: string): boolean {
  const now = Date.now();
  const last = RECENT.get(key);
  if (last != null && now - last < THROTTLE_MS) return false;
  RECENT.set(key, now);
  // Compact periodic GC so the map never grows unbounded.
  if (RECENT.size > 64) {
    for (const [k, t] of RECENT) {
      if (now - t > THROTTLE_MS * 4) RECENT.delete(k);
    }
  }
  return true;
}

function shortMessage(raw: unknown): string {
  if (raw instanceof Error) {
    const m = raw.message?.trim();
    return m && m.length > 0 ? m : raw.name || "Unknown error";
  }
  if (typeof raw === "string") return raw.trim();
  if (raw && typeof raw === "object") {
    const m = (raw as { message?: unknown }).message;
    if (typeof m === "string") return m;
  }
  return "Unknown error";
}

export function installErrorReporter() {
  if (typeof window === "undefined") return;

  const onError = (event: ErrorEvent) => {
    const msg = shortMessage(event.error ?? event.message);
    if (!msg || msg === "Script error.") return; // cross-origin opaque
    if (!shouldEmit(msg)) return;
    // eslint-disable-next-line no-console
    console.error("[tars] uncaught:", event.error ?? event.message, event);
    toast.error(prettify(msg), {
      hint: "uncaught · see devtools console",
      duration: 7500,
    });
  };

  const onRejection = (event: PromiseRejectionEvent) => {
    const msg = shortMessage(event.reason);
    if (!msg) return;
    if (!shouldEmit(`P:${msg}`)) return;
    // eslint-disable-next-line no-console
    console.error("[tars] unhandled rejection:", event.reason);
    toast.error(prettify(msg), {
      hint: "unhandled promise · see devtools console",
      duration: 7500,
    });
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
}

/** Trim stack-y prefixes and absurd whitespace before showing in a toast. */
function prettify(msg: string): string {
  // Drop "ChunkLoadError:" / "TypeError:" prefix — pure noise for users.
  const cleaned = msg
    .replace(/^[A-Z][A-Za-z]*Error:\s*/, "")
    .replace(/\s+at\s.+$/, "")
    .trim();
  return cleaned.length > 140 ? cleaned.slice(0, 137) + "…" : cleaned;
}
