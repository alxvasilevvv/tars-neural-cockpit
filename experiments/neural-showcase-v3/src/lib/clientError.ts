/**
 * Global client-error reporter for tars.meeet.world.
 *
 * Captures uncaught errors and unhandled promise rejections and pipes
 * them through `core-bridge → tars-ingest` as a `tars.client.error`
 * event so they land in the same `public.tars_event_ingest` table that
 * everything else writes to. This is the zero-vendor answer to
 * meeet-solana-state-941a6045 OPEN_QUESTIONS.md Q4 ("no Sentry, no APM"):
 * use the data path we already have.
 *
 * Behavior:
 *   - Same `tars_session_id` cookie is read passively from
 *     `document.cookie` so each error joins the user's journey.
 *   - Same `X-Tars-Trace-Id` header that Cloudflare middleware emits
 *     can't be read from the client (HttpOnly is set on the cookie,
 *     not the header), so we generate a per-error trace if absent.
 *   - Errors are rate-limited and de-duped client-side (10/min cap,
 *     identical signature suppressed for 60s) to avoid cost surprises
 *     when an infinite-loop bug ships.
 *   - We never include innerHTML, form values, or anything from
 *     localStorage/sessionStorage in the payload.
 *   - The reporter is a no-op on `localhost`, in tests, and inside
 *     the Tauri shell (which has its own crash reporting path).
 *
 * Failure mode: if the bridge POST fails, the error is silently
 * dropped. Reporting failures must never bubble back up into the
 * page.
 */

const CONTRACT_VERSION = "1.0.0";
const RATE_LIMIT_PER_MINUTE = 10;
const DEDUP_WINDOW_MS = 60_000;
const SESSION_COOKIE = "tars_session_id";
const PRODUCT_HOSTS = new Set([
  "tars.meeet.world",
  "meeet.world",
]);

interface ErrorSignature {
  message: string;
  source: string;
  line?: number;
  col?: number;
}

interface ReporterState {
  windowStart: number;
  windowCount: number;
  recentSignatures: Map<string, number>;
}

const state: ReporterState = {
  windowStart: 0,
  windowCount: 0,
  recentSignatures: new Map(),
};

function isProductionHost(): boolean {
  if (typeof window === "undefined") return false;
  return PRODUCT_HOSTS.has(window.location.hostname);
}

function isTauriShell(): boolean {
  if (typeof window === "undefined") return false;
  // The Tauri shell injects __TAURI__ on window. Tauri 2 also has
  // __TAURI_INTERNALS__. Either is sufficient.
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.__TAURI__ || w.__TAURI_INTERNALS__);
}

function readSessionId(): string {
  if (typeof document === "undefined") return "ses_anonymous";
  const cookies = document.cookie.split(";").map((c) => c.trim());
  const match = cookies.find((c) => c.startsWith(`${SESSION_COOKIE}=`));
  if (match) return match.slice(SESSION_COOKIE.length + 1);
  return "ses_anonymous";
}

function generateTraceId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `trace_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function signatureKey(sig: ErrorSignature): string {
  return [sig.message.slice(0, 200), sig.source, sig.line ?? "", sig.col ?? ""].join("::");
}

/**
 * Decide whether to actually emit an error event for this signature.
 * Combines the rolling rate limit (RATE_LIMIT_PER_MINUTE) with a
 * per-signature dedup window (DEDUP_WINDOW_MS).
 */
function shouldEmit(sig: ErrorSignature): boolean {
  const now = Date.now();

  if (now - state.windowStart > 60_000) {
    state.windowStart = now;
    state.windowCount = 0;
  }
  if (state.windowCount >= RATE_LIMIT_PER_MINUTE) return false;

  const key = signatureKey(sig);
  const lastSeen = state.recentSignatures.get(key);
  if (lastSeen !== undefined && now - lastSeen < DEDUP_WINDOW_MS) {
    return false;
  }

  state.windowCount += 1;
  state.recentSignatures.set(key, now);

  if (state.recentSignatures.size > 50) {
    const cutoff = now - DEDUP_WINDOW_MS;
    for (const [k, ts] of state.recentSignatures) {
      if (ts < cutoff) state.recentSignatures.delete(k);
    }
  }

  return true;
}

interface EmitInput {
  signature: ErrorSignature;
  stack?: string;
  kind: "error" | "unhandled_rejection";
  page: string;
  user_agent: string;
}

async function postEvent(input: EmitInput): Promise<void> {
  const traceId = generateTraceId();
  const sessionId = readSessionId();

  const body = JSON.stringify({
    kind: "tars.client.error",
    trace_id: traceId,
    session_id: sessionId,
    contract_version: CONTRACT_VERSION,
    payload: {
      sub_kind: input.kind,
      message: input.signature.message.slice(0, 500),
      source: input.signature.source.slice(0, 500),
      line: input.signature.line,
      col: input.signature.col,
      stack: input.stack ? input.stack.slice(0, 4000) : undefined,
      page: input.page,
      user_agent: input.user_agent.slice(0, 200),
    },
  });

  try {
    await fetch("/api/client-error", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tars-Contract": CONTRACT_VERSION,
      },
      body,
      keepalive: true,
      mode: "same-origin",
      credentials: "same-origin",
    });
  } catch {
    /* network failure — drop silently per spec */
  }
}

function handleErrorEvent(event: ErrorEvent): void {
  const sig: ErrorSignature = {
    message: String(event.message ?? "unknown error"),
    source: String(event.filename ?? ""),
    line: typeof event.lineno === "number" ? event.lineno : undefined,
    col: typeof event.colno === "number" ? event.colno : undefined,
  };
  if (!shouldEmit(sig)) return;

  void postEvent({
    signature: sig,
    stack: event.error instanceof Error ? event.error.stack : undefined,
    kind: "error",
    page: window.location.pathname + window.location.search,
    user_agent: navigator.userAgent,
  });
}

function handleRejectionEvent(event: PromiseRejectionEvent): void {
  const reason = event.reason;
  let message = "Unhandled promise rejection";
  let stack: string | undefined;

  if (reason instanceof Error) {
    message = reason.message || message;
    stack = reason.stack;
  } else if (typeof reason === "string") {
    message = reason;
  } else if (reason && typeof reason === "object") {
    try {
      message = JSON.stringify(reason).slice(0, 500);
    } catch {
      message = String(reason);
    }
  }

  const sig: ErrorSignature = {
    message,
    source: "promise",
  };
  if (!shouldEmit(sig)) return;

  void postEvent({
    signature: sig,
    stack,
    kind: "unhandled_rejection",
    page: window.location.pathname + window.location.search,
    user_agent: navigator.userAgent,
  });
}

/**
 * Install global handlers. Idempotent — calling more than once is a
 * no-op. Returns a cleanup function for tests.
 */
let installed = false;

export function installClientErrorReporter(): () => void {
  if (typeof window === "undefined") return () => {};
  if (installed) return () => {};
  if (!isProductionHost()) return () => {};
  if (isTauriShell()) return () => {};

  installed = true;
  window.addEventListener("error", handleErrorEvent);
  window.addEventListener("unhandledrejection", handleRejectionEvent);

  return () => {
    window.removeEventListener("error", handleErrorEvent);
    window.removeEventListener("unhandledrejection", handleRejectionEvent);
    installed = false;
  };
}

export const __test__ = {
  shouldEmit,
  signatureKey,
  state,
  reset() {
    state.windowStart = 0;
    state.windowCount = 0;
    state.recentSignatures.clear();
    installed = false;
  },
};
