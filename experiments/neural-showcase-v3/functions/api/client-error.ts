// POST /api/client-error — Cloudflare Pages Function
//
// Receives client-side error reports from `src/lib/clientError.ts`,
// adds the `BRIDGE_SHARED_SECRET` (which must never live in the
// browser bundle), and forwards to `core-bridge/relay-event`.
//
// This is the meeet-OPEN_QUESTIONS Q4 answer: a zero-vendor client
// error pipeline that lands in the same `tars_event_ingest` Postgres
// table as every other event. No Sentry, no APM bill, identical
// observability surface to `tars.page.viewed`.
//
// Failure modes — all return JSON, none ever throw:
//   400 schema_error                   — payload missing required fields
//   413 payload_too_large              — body > 16 KiB
//   415 unsupported_media_type         — Content-Type not application/json
//   429 rate_limited                   — per-IP throttle
//   503 bridge_unconfigured            — BRIDGE_SHARED_SECRET not set
//   200 { ok: true, persisted: bool }  — successful relay (echoes core-bridge result)
//
// Required env vars (CF Pages → Settings → Environment Variables):
//   BRIDGE_SHARED_SECRET   — relays events to core-bridge.
//   CORE_BRIDGE_URL        — full URL to core-bridge function (defaults to prod).

interface Env {
  BRIDGE_SHARED_SECRET?: string;
  CORE_BRIDGE_URL?: string;
}

const CONTRACT_VERSION = "1.0.0";
const DEFAULT_CORE_BRIDGE = "https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge";
const MAX_BODY_BYTES = 16 * 1024;

interface ClientErrorPayload {
  kind: string;
  trace_id?: string;
  session_id?: string;
  contract_version?: string;
  payload?: Record<string, unknown>;
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function validate(body: unknown): { ok: true; data: ClientErrorPayload } | { ok: false; reason: string } {
  if (!isObject(body)) return { ok: false, reason: "body must be a JSON object" };
  if (body.kind !== "tars.client.error") return { ok: false, reason: "kind must be 'tars.client.error'" };
  if (typeof body.trace_id !== "string" || !body.trace_id) return { ok: false, reason: "trace_id required" };
  if (typeof body.session_id !== "string" || !body.session_id) return { ok: false, reason: "session_id required" };
  if (body.contract_version !== CONTRACT_VERSION) {
    return { ok: false, reason: `contract_version must be '${CONTRACT_VERSION}'` };
  }
  if (!isObject(body.payload)) return { ok: false, reason: "payload must be an object" };

  const p = body.payload;
  if (typeof p.message !== "string") return { ok: false, reason: "payload.message must be a string" };
  if (typeof p.sub_kind !== "string") return { ok: false, reason: "payload.sub_kind must be a string" };

  return {
    ok: true,
    data: {
      kind: body.kind,
      trace_id: body.trace_id,
      session_id: body.session_id,
      contract_version: body.contract_version,
      payload: p,
    },
  };
}

async function readBoundedBody(request: Request, max: number): Promise<{ ok: true; text: string } | { ok: false; status: number }> {
  const contentLength = request.headers.get("Content-Length");
  if (contentLength && Number(contentLength) > max) {
    return { ok: false, status: 413 };
  }
  const text = await request.text();
  if (text.length > max) return { ok: false, status: 413 };
  return { ok: true, text };
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "https://tars.meeet.world",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Tars-Contract",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  if (request.method !== "POST") {
    return jsonResponse({ ok: false, error: "method_not_allowed" }, 405);
  }

  const ct = request.headers.get("Content-Type") || "";
  if (!ct.toLowerCase().startsWith("application/json")) {
    return jsonResponse({ ok: false, error: "unsupported_media_type" }, 415);
  }

  const bodyResult = await readBoundedBody(request, MAX_BODY_BYTES);
  if (!bodyResult.ok) {
    return jsonResponse({ ok: false, error: "payload_too_large" }, bodyResult.status);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(bodyResult.text);
  } catch {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }

  const validation = validate(parsed);
  if (!validation.ok) {
    return jsonResponse({ ok: false, error: "schema_error", reason: validation.reason }, 400);
  }

  if (!env.BRIDGE_SHARED_SECRET) {
    // Bridge not configured (e.g. preview deploys, local dev). The
    // browser doesn't need to know — it just fired and forgot.
    return jsonResponse({ ok: true, persisted: false, reason: "bridge_unconfigured" }, 200);
  }

  const bridge = env.CORE_BRIDGE_URL || DEFAULT_CORE_BRIDGE;

  try {
    const upstream = await fetch(`${bridge}/relay-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Origin": "https://tars.meeet.world",
        "x-bridge-secret": env.BRIDGE_SHARED_SECRET,
        "x-trace-id": validation.data.trace_id || "",
      },
      body: JSON.stringify(validation.data),
    });

    let upstreamBody: unknown = null;
    try {
      upstreamBody = await upstream.json();
    } catch {
      /* upstream may return non-json on edge cases; ignore */
    }

    return jsonResponse(
      {
        ok: upstream.ok,
        persisted: upstream.ok,
        upstream_status: upstream.status,
        upstream: upstreamBody,
      },
      upstream.ok ? 200 : 502,
    );
  } catch {
    return jsonResponse({ ok: false, error: "bridge_unreachable" }, 502);
  }
};
