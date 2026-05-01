// Cloudflare Pages Function — `/api/product/version`. Reduced view of
// the canonical downloads manifest defined in `./downloads.ts`. Mirrors
// the same source of truth (no remote fetch, no proxy loop).

import { corsHeaders, preflightResponse } from "../../_cors.ts";

const CONTRACT_VERSION = "1.0.0";
const PRODUCT = "tars";
const CHANNEL = "stable";
const SOURCE = "tars.meeet.world/pages-functions";

const LATEST_VERSION = "8.4.0";
const LATEST_RELEASED_AT = "2026-04-22T00:00:00Z";

const CACHE_HEADERS: Record<string, string> = {
  "cache-control": "public, max-age=30, s-maxage=60, stale-while-revalidate=300",
  "x-tars-source": "pages-functions:embedded",
  "x-tars-contract": CONTRACT_VERSION,
};

function jsonResponse(status: number, body: unknown, origin: string | null): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...CACHE_HEADERS,
      ...corsHeaders(origin),
    },
  });
}

function methodNotAllowed(origin: string | null): Response {
  return new Response(
    JSON.stringify({ ok: false, error: "method_not_allowed" }),
    {
      status: 405,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "allow": "GET, HEAD, OPTIONS",
        ...CACHE_HEADERS,
        ...corsHeaders(origin),
      },
    },
  );
}

export const onRequest: PagesFunction = async (context) => {
  const { request } = context;
  const origin = request.headers.get("Origin");

  if (request.method === "OPTIONS") {
    return preflightResponse(origin);
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    return methodNotAllowed(origin);
  }

  const body = {
    ok: true,
    product: PRODUCT,
    contract_version: CONTRACT_VERSION,
    channel: CHANNEL,
    version: LATEST_VERSION,
    released_at: LATEST_RELEASED_AT,
    source: SOURCE,
  };

  if (request.method === "HEAD") {
    return new Response(null, {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        ...CACHE_HEADERS,
        ...corsHeaders(origin),
      },
    });
  }

  return jsonResponse(200, body, origin);
};
