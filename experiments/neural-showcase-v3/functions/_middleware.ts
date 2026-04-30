// Cloudflare Pages Functions middleware (runs on the edge before
// every request). Implements the cookie / session contract described
// in `docs/contracts/TARS_SUBDOMAIN.md` §5 and the analytics emit
// contract in §6.
//
// Behaviour:
//   1. Issue `tars_session_id` cookie on first anonymous visit
//      (UUID4, Domain=.meeet.world, 30 day TTL, httpOnly, Secure,
//      SameSite=Lax). Re-emits on expiry.
//   2. Generate `x-trace-id` if missing, propagate downstream.
//   3. Best-effort emit `tars.page.viewed` event to the meeet ingest
//      pipeline — relays through `core-bridge` so meeet.world owns
//      the data, not TARS. Skipped if `BRIDGE_SHARED_SECRET` is not
//      configured (graceful degrade — page still renders).
//   4. Echo `X-Tars-Contract: 1.0.0` header.
//
// Required env vars (Pages → Settings → Environment Variables):
//   BRIDGE_SHARED_SECRET   — relays events to core-bridge.
//   CORE_BRIDGE_URL        — full URL to core-bridge function (defaults to prod).
//
// Pages preview deploys (PR deploys, *.pages.dev) skip cookie
// issuing because the parent domain mismatch breaks Domain=.meeet.world.
// Production binding `tars.meeet.world` activates the full path.

interface Env {
  BRIDGE_SHARED_SECRET?: string;
  CORE_BRIDGE_URL?: string;
}

const COOKIE_NAME = "tars_session_id";
const COOKIE_TTL_SECONDS = 30 * 24 * 60 * 60; // 30 days
const PARENT_DOMAIN = ".meeet.world";
const CONTRACT_VERSION = "1.0.0";
const DEFAULT_CORE_BRIDGE = "https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge";

function generateUuidV4(): string {
  // crypto.randomUUID is available on the CF Workers runtime.
  return crypto.randomUUID();
}

function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("Cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function isProductionHost(url: URL): boolean {
  return url.hostname === "tars.meeet.world";
}

function isHtmlRequest(request: Request): boolean {
  const accept = request.headers.get("Accept") || "";
  return accept.includes("text/html");
}

async function emitPageViewed(
  env: Env,
  request: Request,
  url: URL,
  traceId: string,
  sessionId: string,
): Promise<void> {
  if (!env.BRIDGE_SHARED_SECRET) return;
  const bridge = env.CORE_BRIDGE_URL || DEFAULT_CORE_BRIDGE;
  const payload = {
    kind: "tars.page.viewed",
    trace_id: traceId,
    session_id: sessionId,
    contract_version: CONTRACT_VERSION,
    payload: {
      path: url.pathname,
      host: url.hostname,
      referer: request.headers.get("Referer") || null,
      ua: (request.headers.get("User-Agent") || "").slice(0, 256),
      country: request.headers.get("CF-IPCountry") || null,
      source: "tars_subdomain_edge",
    },
  };

  try {
    // Fire-and-forget. waitUntil is provided by the platform context.
    await fetch(`${bridge}/relay-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Origin": "https://tars.meeet.world",
        "x-bridge-secret": env.BRIDGE_SHARED_SECRET,
        "x-trace-id": traceId,
      },
      body: JSON.stringify(payload),
    });
  } catch {
    // Edge analytics is best-effort. Swallow — never break the page.
  }
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, next, env } = context;
  const url = new URL(request.url);

  let sessionId = readCookie(request, COOKIE_NAME);
  const isNewSession = !sessionId;
  if (isNewSession) sessionId = generateUuidV4();

  const incomingTraceId = request.headers.get("x-trace-id");
  const traceId = incomingTraceId || generateUuidV4();

  // Continue to the static asset / SPA handler.
  const upstream = await next();
  const response = new Response(upstream.body, upstream);
  response.headers.set("X-Tars-Contract", CONTRACT_VERSION);
  response.headers.set("X-Tars-Trace-Id", traceId);

  // Issue / refresh the visitor cookie.
  if (isNewSession && isProductionHost(url)) {
    response.headers.append(
      "Set-Cookie",
      [
        `${COOKIE_NAME}=${sessionId}`,
        `Domain=${PARENT_DOMAIN}`,
        `Path=/`,
        `Max-Age=${COOKIE_TTL_SECONDS}`,
        "HttpOnly",
        "Secure",
        "SameSite=Lax",
      ].join("; "),
    );
  }

  // Best-effort fire `tars.page.viewed` for HTML navigation requests.
  // Static assets and API proxies do not emit page views.
  if (isHtmlRequest(request) && sessionId) {
    context.waitUntil(emitPageViewed(env, request, url, traceId, sessionId));
  }

  return response;
};
