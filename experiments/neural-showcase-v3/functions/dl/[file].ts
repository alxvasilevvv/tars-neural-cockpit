// Cloudflare Pages Function — `/dl/<filename>` proxy for TARS desktop
// release binaries.
//
// Why this exists (B-017): the source repo
// `alxvasilevvv/tars-neural-cockpit` is private, so the canonical
// release URLs (`github.com/.../releases/download/v…/TARS_…`) return
// HTTP 404 to anonymous callers. The install funnel
// (`tars.meeet.world/install.sh` → `curl|bash`) needs anonymous
// downloads to work. This Function bridges the gap by holding a
// GitHub PAT with `repo:read` and proxying the binary while the repo
// stays private.
//
// Setup (operator, one-time):
//
//   1. GitHub → Settings → Developer settings → Personal access tokens
//      → Fine-grained tokens → Generate new
//      Repository: alxvasilevvv/tars-neural-cockpit
//      Permissions: Contents: Read-only
//   2. Cloudflare → Pages → tars-meeet → Settings → Environment
//      variables → Production → Add variable
//      Name: GITHUB_RELEASE_TOKEN
//      Type: Encrypt
//   3. Trigger a fresh Pages deploy.
//
// Until step 3 lands the Function returns a 503 with a clear hint so
// users see "install funnel temporarily down — operator must paste
// GITHUB_RELEASE_TOKEN" instead of an opaque 500.
//
// Allowlist of filenames lives in `ALLOWED_FILENAMES` below — every
// new release MUST add its asset names here, otherwise the proxy
// rejects the request with 404. Defends against using this Function
// as an open-relay for arbitrary paths in the GitHub repo.

interface Env {
  GITHUB_RELEASE_TOKEN?: string;
  // Override for tests / staging
  GITHUB_REPO?: string;
}

const DEFAULT_REPO = "alxvasilevvv/tars-neural-cockpit";
const GITHUB_API = "https://api.github.com";
const USER_AGENT = "tars-meeet-pages-dl-proxy/1.0";
const PROXY_CACHE_SECONDS = 300; // 5 min for redirect + asset listing.
const BODY_CACHE_SECONDS = 3600; // 1 h for binary body (release immutable).

// Strict allowlist — only filenames produced by the
// `release-desktop-tagged.yml` workflow for known release tags. New
// release? Add the assets here in the same PR that bumps the tag.
const ALLOWED_FILENAMES = new Set<string>([
  // v9.1.0 — current stable. Mac-only: the GitHub Actions
  // `release-desktop-tagged.yml` pipeline currently builds darwin
  // (.dmg + Tauri .app.tar.gz) only. Win/Linux pyoxidizer cross-targets
  // are postponed to v9.2 — see Wave 71-A backend reality pass.
  // v9.2 — re-add Win/Linux when pyoxidizer pipelines land.
  "TARS_9.1.0_aarch64.dmg",
  "TARS_9.1.0_x64.dmg",
  "TARS_aarch64.app.tar.gz",
  "latest.json", // Tauri updater channel manifest
  "latest.json.sig",
  // v8.4.0 — previous stable, kept for any pinned installers in the wild
  "TARS_8.4.0_aarch64.dmg",
  "TARS_8.4.0_x64.dmg",
  "TARS_8.4.0_x64-setup.exe",
  "TARS_8.4.0_x64_en-US.msi",
  "TARS_8.4.0_amd64.AppImage",
  "TARS_8.4.0_amd64.deb",
]);

// Map filename → release tag. Naming convention is `TARS_<version>_…`
// so we parse it out; `latest.json` always points at the newest tag.
const LATEST_TAG = "v9.1.0";

function tagForFilename(name: string): string | null {
  if (name === "latest.json" || name === "latest.json.sig") return LATEST_TAG;
  const m = name.match(/^TARS_(\d+\.\d+\.\d+)_/);
  if (!m) {
    // Tauri may emit a versionless app bundle (`TARS_aarch64.app.tar.gz`);
    // route those at the latest tag too.
    if (name.startsWith("TARS_") && name.endsWith(".app.tar.gz")) return LATEST_TAG;
    return null;
  }
  return `v${m[1]}`;
}

function noTokenResponse(): Response {
  return new Response(
    JSON.stringify({
      ok: false,
      error: "operator_action_required",
      message:
        "GITHUB_RELEASE_TOKEN is not set on this Pages deployment. The "
        + "tars-neural-cockpit repo is private (B-017), so anonymous "
        + "downloads need a server-side proxy. Operator: see "
        + "functions/dl/[file].ts header for one-time setup.",
      contact: "https://tars.meeet.world/install",
    }),
    {
      status: 503,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "retry-after": "300",
        "cache-control": "no-store",
      },
    },
  );
}

function notFoundResponse(filename: string): Response {
  return new Response(
    JSON.stringify({
      ok: false,
      error: "not_in_allowlist",
      message:
        `Filename ${JSON.stringify(filename)} is not in the proxy allowlist. `
        + "Either it's a typo, or a new release added an asset that has "
        + "not been wired into ALLOWED_FILENAMES yet.",
      see: "https://tars.meeet.world/api/product/downloads",
    }),
    {
      status: 404,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "public, max-age=60",
      },
    },
  );
}

interface GithubAsset {
  id: number;
  name: string;
  size: number;
  content_type: string;
  url: string; // API URL; needs auth
}

interface GithubRelease {
  tag_name: string;
  assets: GithubAsset[];
}

async function fetchAsset(
  env: Env,
  tag: string,
  filename: string,
): Promise<GithubAsset | null> {
  const repo = env.GITHUB_REPO || DEFAULT_REPO;
  const url = `${GITHUB_API}/repos/${repo}/releases/tags/${encodeURIComponent(tag)}`;
  const r = await fetch(url, {
    method: "GET",
    headers: {
      "accept": "application/vnd.github+json",
      "authorization": `Bearer ${env.GITHUB_RELEASE_TOKEN}`,
      "user-agent": USER_AGENT,
      "x-github-api-version": "2022-11-28",
    },
    cf: { cacheTtl: PROXY_CACHE_SECONDS, cacheEverything: true } as RequestInit["cf"],
  });
  if (!r.ok) return null;
  const release = (await r.json()) as GithubRelease;
  if (!release || !Array.isArray(release.assets)) return null;
  return release.assets.find((a) => a.name === filename) || null;
}

async function streamAsset(env: Env, asset: GithubAsset): Promise<Response> {
  // GitHub returns 302 to a signed S3 URL when called with octet-stream.
  // We follow the redirect implicitly (default), which copies the
  // binary body through the worker. The S3 URL is short-lived but
  // we let Cloudflare cache by content-hash via release immutability.
  const upstream = await fetch(asset.url, {
    method: "GET",
    headers: {
      "accept": "application/octet-stream",
      "authorization": `Bearer ${env.GITHUB_RELEASE_TOKEN}`,
      "user-agent": USER_AGENT,
      "x-github-api-version": "2022-11-28",
    },
    cf: { cacheTtl: BODY_CACHE_SECONDS, cacheEverything: true } as RequestInit["cf"],
    redirect: "follow",
  });

  if (!upstream.ok) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: "upstream_failed",
        upstream_status: upstream.status,
        message:
          "GitHub Releases proxy fetch failed. Check GITHUB_RELEASE_TOKEN "
          + "scope (needs Repository → Contents: Read-only on the private "
          + "repo) and that the token has not been revoked.",
      }),
      {
        status: 502,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "no-store",
        },
      },
    );
  }

  const headers = new Headers();
  // Forward the most useful headers; strip GitHub-specific ones.
  const ct = upstream.headers.get("content-type") || asset.content_type
    || "application/octet-stream";
  headers.set("content-type", ct);
  const cl = upstream.headers.get("content-length");
  if (cl) headers.set("content-length", cl);
  headers.set(
    "content-disposition",
    `attachment; filename="${asset.name.replace(/"/g, "")}"`,
  );
  headers.set(
    "cache-control",
    `public, max-age=${BODY_CACHE_SECONDS}, s-maxage=${BODY_CACHE_SECONDS}, immutable`,
  );
  headers.set("x-tars-source", "pages-functions:dl-proxy");

  return new Response(upstream.body, { status: 200, headers });
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { params, request, env } = context;
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response(
      JSON.stringify({ ok: false, error: "method_not_allowed" }),
      {
        status: 405,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "allow": "GET, HEAD",
        },
      },
    );
  }

  const filename = String(params?.file || "");
  if (!filename || !ALLOWED_FILENAMES.has(filename)) {
    return notFoundResponse(filename);
  }

  if (!env.GITHUB_RELEASE_TOKEN) {
    return noTokenResponse();
  }

  const tag = tagForFilename(filename);
  if (!tag) {
    // Shouldn't reach — allowlist guarantees a known shape — but keep
    // the diagnostic clean.
    return notFoundResponse(filename);
  }

  const asset = await fetchAsset(env, tag, filename);
  if (!asset) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: "asset_not_found_in_release",
        tag,
        filename,
        message:
          "GitHub release exists but no asset with this name. Either the "
          + "release-desktop-tagged.yml workflow renamed it, or the "
          + "ALLOWED_FILENAMES allowlist is ahead of the actual release.",
      }),
      {
        status: 404,
        headers: { "content-type": "application/json; charset=utf-8" },
      },
    );
  }

  if (request.method === "HEAD") {
    return new Response(null, {
      status: 200,
      headers: {
        "content-type": asset.content_type || "application/octet-stream",
        "content-length": String(asset.size),
        "x-tars-source": "pages-functions:dl-proxy",
      },
    });
  }

  return streamAsset(env, asset);
};

// Test-only exports — kept inside the module so vitest can import them
// without parsing TypeScript through ts-node.
export const __test = {
  ALLOWED_FILENAMES,
  LATEST_TAG,
  tagForFilename,
};
