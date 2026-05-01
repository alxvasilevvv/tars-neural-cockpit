// Shared CORS allowlist for `/api/product/*` Pages Functions.
//
// Contract (`docs/contracts/TARS_SUBDOMAIN.md` §4) requires
// `Access-Control-Allow-Origin: https://meeet.world` so Lovable's
// marketing surface can render the same downloads/version widget that
// `tars.meeet.world` does. Same-origin XHR from the SPA on
// `tars.meeet.world` is unaffected (browsers skip CORS for it), but we
// echo the origin back when allowed so that explicit `Origin` headers
// from server-to-browser proxies do not get blocked.
//
// We deliberately echo the *requested* `Origin` (when on the allowlist)
// rather than a fixed string so that the response is cache-safe and
// the `Vary: Origin` header keeps Cloudflare from serving the wrong
// allow-origin to the wrong caller.

const ALLOWED_ORIGINS = new Set([
  "https://meeet.world",
  "https://tars.meeet.world",
  // Pages preview deploys (PR builds) live on *.pages.dev — we allow
  // the canonical project subdomain so Lovable's preview branches can
  // call the manifest from a draft deploy.
  "https://tars-meeet.pages.dev",
]);

const ALLOWED_METHODS = "GET, HEAD, OPTIONS";
const ALLOWED_HEADERS = "Content-Type, Accept, x-trace-id";
const PREFLIGHT_MAX_AGE = "600"; // 10 minutes; preflights are cheap.

export function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  return ALLOWED_ORIGINS.has(origin);
}

export function corsHeaders(origin: string | null): Record<string, string> {
  if (!isAllowedOrigin(origin)) {
    return { vary: "Origin" };
  }
  return {
    "access-control-allow-origin": origin as string,
    "access-control-allow-methods": ALLOWED_METHODS,
    "access-control-allow-headers": ALLOWED_HEADERS,
    "access-control-expose-headers": "x-tars-contract, x-tars-source",
    "access-control-max-age": PREFLIGHT_MAX_AGE,
    vary: "Origin",
  };
}

export function preflightResponse(origin: string | null): Response {
  if (!isAllowedOrigin(origin)) {
    // Still answer the preflight, but without permissive headers — the
    // browser will block the actual request, which is the desired
    // behaviour for unknown origins.
    return new Response(null, {
      status: 204,
      headers: { vary: "Origin" },
    });
  }
  return new Response(null, {
    status: 204,
    headers: corsHeaders(origin),
  });
}

// Test-only export so we can assert the constant from a typed script
// without parsing the file textually.
export const CORS_ALLOWLIST = Array.from(ALLOWED_ORIGINS);
