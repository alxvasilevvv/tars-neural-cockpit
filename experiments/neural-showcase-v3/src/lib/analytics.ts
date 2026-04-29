/**
 * analytics — batched event tracker for the TARS marketing surface.
 *
 * Event-name contract (per docs/contracts/TARS_SUBDOMAIN.md §7):
 *
 *   tars.page.view        — every route change
 *   tars.click.<id>       — explicit conversion clicks
 *                           (install_copy, download_mac, cta_cockpit, …)
 *   tars.api.<name>       — outbound API call lifecycle
 *                           (downloads_manifest_ok, health_fail, …)
 *
 * The implementation is endpoint-agnostic. Until brother stands up
 * `/api/log` on tars.meeet.world, events are buffered to localStorage
 * (capped at 200) so we don't lose pre-launch data; once the endpoint
 * shows up it will drain.
 *
 * We never attach PII. The session_id is an opaque random string
 * stored in `tars-session-id` (regenerated on tab open). All events
 * include a monotonically-increasing `seq` so the brother can re-order
 * if our batch arrives out of order.
 */

const ENDPOINT = "/api/log"; // proxied via /api/* per Vite dev + meeet.world prod
const BUFFER_KEY = "tars-analytics-buffer";
const SESSION_KEY = "tars-session-id";
const FLUSH_DEBOUNCE_MS = 1500;
const MAX_BUFFER = 200;
const MAX_BATCH = 25;
const PRODUCT = "tars";

let seq = 0;
let pendingFlush: ReturnType<typeof setTimeout> | null = null;

export interface TrackEvent {
  /** Fully-qualified name, e.g. "tars.click.install_copy". */
  name: string;
  /** Optional structured payload — keep flat & primitive. */
  props?: Record<string, string | number | boolean | null | undefined>;
}

interface QueuedEvent extends TrackEvent {
  ts: number;
  seq: number;
  session: string;
  page: string;
  ref: string;
  product: string;
}

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    return parsed as T;
  } catch {
    return fallback;
  }
}

function getSession(): string {
  if (typeof sessionStorage === "undefined") return "anon";
  let s = sessionStorage.getItem(SESSION_KEY);
  if (!s) {
    s = `s_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
    try {
      sessionStorage.setItem(SESSION_KEY, s);
    } catch {
      /* private mode */
    }
  }
  return s;
}

function loadBuffer(): QueuedEvent[] {
  if (typeof localStorage === "undefined") return [];
  return safeParse<QueuedEvent[]>(localStorage.getItem(BUFFER_KEY), []);
}

function saveBuffer(buf: QueuedEvent[]) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(
      BUFFER_KEY,
      JSON.stringify(buf.slice(-MAX_BUFFER)),
    );
  } catch {
    /* quota — drop silently */
  }
}

function scheduleFlush() {
  if (pendingFlush) return;
  pendingFlush = setTimeout(() => {
    pendingFlush = null;
    void flush();
  }, FLUSH_DEBOUNCE_MS);
}

async function flush(): Promise<void> {
  const buf = loadBuffer();
  if (!buf.length) return;
  const batch = buf.slice(0, MAX_BATCH);
  try {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });
    if (res.ok) {
      // Successful drain: keep only events that weren't in this batch.
      saveBuffer(buf.slice(batch.length));
      // If more remain, schedule the next batch.
      if (buf.length > batch.length) scheduleFlush();
    }
  } catch {
    // Endpoint missing pre-launch — keep the buffer for later.
  }
}

/** Public — emit a tracked event. Non-blocking. */
export function track(event: TrackEvent): void {
  if (typeof window === "undefined") return;
  const queued: QueuedEvent = {
    ...event,
    ts: Date.now(),
    seq: ++seq,
    session: getSession(),
    page: window.location.pathname + window.location.search,
    ref: typeof document !== "undefined" ? document.referrer : "",
    product: PRODUCT,
  };
  const buf = loadBuffer();
  buf.push(queued);
  saveBuffer(buf);
  scheduleFlush();
}

/** Convenience for click events. */
export function trackClick(id: string, props?: TrackEvent["props"]): void {
  track({ name: `tars.click.${id}`, props });
}

/** Convenience for page views — call from a useEffect on route change. */
export function trackPageView(path: string): void {
  track({ name: "tars.page.view", props: { path } });
}

/** Convenience for outbound API lifecycle. */
export function trackApi(
  name: string,
  outcome: "ok" | "fail",
  props?: TrackEvent["props"],
): void {
  track({ name: `tars.api.${name}_${outcome}`, props });
}

/**
 * Best-effort flush before the page unloads. Uses sendBeacon when
 * available so the request survives the navigation.
 */
function beforeUnloadFlush() {
  if (typeof navigator === "undefined" || !navigator.sendBeacon) return;
  const buf = loadBuffer();
  if (!buf.length) return;
  const blob = new Blob([JSON.stringify({ events: buf.slice(0, MAX_BATCH) })], {
    type: "application/json",
  });
  const sent = navigator.sendBeacon(ENDPOINT, blob);
  if (sent) saveBuffer(buf.slice(MAX_BATCH));
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", beforeUnloadFlush);
  // Drain on page show (covers bfcache restores).
  window.addEventListener("pageshow", () => scheduleFlush());
}
