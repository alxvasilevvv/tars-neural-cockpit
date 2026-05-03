// Cloudflare Pages Function — same-origin canonical TARS downloads
// manifest. Source of truth lives here (in code, version-controlled,
// shipped with each Pages deploy) rather than in a Supabase function,
// because the previous design had a circular dependency: the Supabase
// `tars-downloads` function used `https://tars.meeet.world/api/product/
// downloads` as its upstream, which is *this* function once the
// subdomain went live, leading to an infinite proxy loop.
//
// Contract: `docs/contracts/TARS_SUBDOMAIN.md` §4 + matches the shape
// returned by the legacy Supabase fallback so existing clients
// (`fetchTarsDownloadsManifest` in src/lib/downloads.ts and the QA
// agent's `_validate_manifest`) continue to work unchanged.
//
// To publish a new release:
//   1. Update RELEASES below.
//   2. Bump the top-level `released_at` to the new release timestamp.
//   3. Deploy via wrangler / Pages CI.

import { corsHeaders, preflightResponse } from "../../_cors.ts";

interface Env {
  TARS_DOWNLOADS_OVERRIDE_URL?: string;
}

const CONTRACT_VERSION = "1.0.0";
const PRODUCT = "tars";
const CHANNEL = "stable";
const SOURCE = "tars.meeet.world/pages-functions";

interface Artifact {
  os: "macos" | "windows" | "linux";
  arch: "arm64" | "x64" | "x86_64" | "universal";
  kind: "dmg" | "exe" | "appimage" | "deb" | "rpm" | "tarball";
  filename: string;
  url: string;
  size_bytes?: number | null;
  sha256?: string | null;
  signature_url?: string | null;
}

interface Release {
  version: string;
  channel: string;
  released_at: string;
  notes: string;
  artifacts: Artifact[];
}

interface DownloadsManifest {
  ok: true;
  product: string;
  contract_version: string;
  channel: string;
  released_at: string;
  source: string;
  releases: Release[];
}

// Artifact URLs must point at real binaries (GitHub Releases), not
// tars.meeet.world/* paths — static hosting serves SPA HTML for unknown
// paths (B-001 / PB_19). Names match Tauri v8.4.0 assets on
// alxvasilevvv/tars-neural-cockpit/releases/tag/v8.4.0.
const GH_V840 =
  "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0";

const RELEASES: Release[] = [
  {
    version: "8.4.0",
    channel: "stable",
    released_at: "2026-04-22T00:00:00Z",
    notes:
      "Stability + observability pass. Tauri shell SecurityError eliminated, x-trace-id propagated end-to-end; installers hosted on GitHub Releases (same tag).",
    artifacts: [
      {
        os: "macos",
        arch: "arm64",
        kind: "dmg",
        filename: "TARS_8.4.0_aarch64.dmg",
        url: `${GH_V840}/TARS_8.4.0_aarch64.dmg`,
      },
      {
        os: "windows",
        arch: "x64",
        kind: "exe",
        filename: "TARS_8.4.0_x64-setup.exe",
        url: `${GH_V840}/TARS_8.4.0_x64-setup.exe`,
      },
      {
        os: "linux",
        arch: "x64",
        kind: "appimage",
        filename: "TARS_8.4.0_amd64.AppImage",
        url: `${GH_V840}/TARS_8.4.0_amd64.AppImage`,
      },
    ],
  },
];

const CACHE_HEADERS: Record<string, string> = {
  "cache-control": "public, max-age=30, s-maxage=60, stale-while-revalidate=300",
  "x-tars-source": "pages-functions:embedded",
  "x-tars-contract": CONTRACT_VERSION,
};

function manifest(): DownloadsManifest {
  return {
    ok: true,
    product: PRODUCT,
    contract_version: CONTRACT_VERSION,
    channel: CHANNEL,
    released_at: RELEASES[0]?.released_at ?? "1970-01-01T00:00:00Z",
    source: SOURCE,
    releases: RELEASES,
  };
}

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

async function loadFromOverride(env: Env): Promise<DownloadsManifest | null> {
  if (!env.TARS_DOWNLOADS_OVERRIDE_URL) return null;
  // Optional escape hatch: if we ever want to flip the source of truth
  // back to a remote URL (e.g. R2 object), set this Pages env var. The
  // override is only honored when it returns a JSON body that matches
  // the contract. Any error → silently fall back to embedded.
  try {
    const r = await fetch(env.TARS_DOWNLOADS_OVERRIDE_URL, {
      method: "GET",
      headers: { accept: "application/json" },
      // Avoid hammering self if someone misconfigures it back to this URL.
      redirect: "manual",
    });
    if (!r.ok) return null;
    const body = (await r.json()) as Partial<DownloadsManifest>;
    if (
      body &&
      body.ok === true &&
      typeof body.product === "string" &&
      typeof body.contract_version === "string" &&
      Array.isArray(body.releases)
    ) {
      return body as DownloadsManifest;
    }
    return null;
  } catch {
    return null;
  }
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const origin = request.headers.get("Origin");

  if (request.method === "OPTIONS") {
    return preflightResponse(origin);
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    return methodNotAllowed(origin);
  }

  const override = await loadFromOverride(env);
  const body = override ?? manifest();

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
