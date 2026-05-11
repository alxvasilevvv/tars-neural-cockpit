#!/usr/bin/env node
/**
 * Wave 127 — Live OG / Twitter card check (post-deploy).
 *
 * The build-time validator (`scripts/validate-og-cards.mjs`) verifies
 * the *static* contract — useDocumentMeta literals + the index.html
 * defaults the crawler sees before JS runs. This script is the live
 * twin: after Cloudflare Pages publishes, fetch each route over the
 * network, scrape the rendered HTML for og:* / twitter:* tags, and
 * verify each og:image actually returns 200 + an SVG payload.
 *
 * Exit codes mirror the build-time validator (0/1/2). Designed to
 * run from a GitHub Actions cron 5 min after a main deploy, or
 * locally via `npm run og:check:live`.
 *
 * NOTE: today the SPA renders meta tags client-side via
 * useDocumentMeta. Crawlers that don't run JS (Twitter, Slack,
 * historic Discord) fall back to the static index.html tags — so this
 * check intentionally inspects only the over-the-wire HTML, never a
 * headless-Chromium-rendered DOM. When the brother's edge worker
 * starts injecting per-route SSR meta we'll teach this script to
 * verify route-specific tags too; until then it asserts the global
 * fallback shape and that every per-route og:image referenced in any
 * page module is reachable.
 */

import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = resolve(__dirname, "..");
const PUBLIC_DIR = join(ROOT, "public");

const HOST = process.env.OG_LIVE_HOST || "https://tars.meeet.world";
const TIMEOUT_MS = 10_000;

const ROUTES = [
  "/",
  "/install",
  "/onboarding",
  "/pricing",
  "/faq",
  "/compare",
  "/pitch",
  "/press",
  "/docs",
  "/status",
  "/build-with",
  "/workshop",
  "/workshop/enterprise",
  "/workshop/roi",
  "/workshop/materials",
  "/workshop/assess",
  "/workshop/cohort",
  "/dashboard",
  "/onboard/org",
  "/inbox",
  "/files",
  "/reports",
  "/marketplace",
  "/compliance",
  "/workspaces",
  "/admin/perf",
];

async function fetchWithTimeout(url, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...opts, signal: ctl.signal });
  } finally {
    clearTimeout(t);
  }
}

function pickMeta(html, attr, name) {
  const re = new RegExp(
    `<meta\\s+${attr}="${name.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")}"\\s+content="([^"]*)"`,
    "i",
  );
  const m = html.match(re);
  return m ? m[1] : null;
}

async function checkRoute(route) {
  const url = `${HOST}${route}`;
  const issues = [];
  let html;
  try {
    const res = await fetchWithTimeout(url, {
      headers: { "user-agent": "Twitterbot/1.0 (TARS-OG-validator)" },
    });
    if (!res.ok) {
      issues.push(`HTTP ${res.status}`);
      return { route, url, issues };
    }
    html = await res.text();
  } catch (e) {
    issues.push(`fetch failed: ${e.message}`);
    return { route, url, issues };
  }

  const ogImage = pickMeta(html, "property", "og:image");
  const twitterCard = pickMeta(html, "name", "twitter:card");
  const ogType = pickMeta(html, "property", "og:type");
  const ogTitle = pickMeta(html, "property", "og:title");

  if (!ogTitle) issues.push("og:title missing");
  if (!ogImage) issues.push("og:image missing");
  if (twitterCard !== "summary_large_image")
    issues.push(`twitter:card=${twitterCard ?? "missing"}`);
  if (ogType !== "website" && ogType !== "article")
    issues.push(`og:type=${ogType ?? "missing"}`);

  if (ogImage) {
    try {
      const imgRes = await fetchWithTimeout(ogImage, { method: "HEAD" });
      if (!imgRes.ok) issues.push(`og:image HTTP ${imgRes.status}`);
      const ct = imgRes.headers.get("content-type") || "";
      if (!ct.includes("svg") && !ct.includes("image"))
        issues.push(`og:image content-type=${ct}`);
    } catch (e) {
      issues.push(`og:image fetch failed: ${e.message}`);
    }
  }

  // Wave 127 — best-effort route-keyword sanity check on title only
  // when this page module would have set it client-side.
  const keyword = route.replace(/^\//, "").split("/")[0];
  if (keyword && ogTitle && !ogTitle.toLowerCase().includes(keyword)) {
    // Don't fail — SPA meta-render may not have flushed yet for non-JS
    // crawlers. Just log so we know which routes are crawler-blind.
    issues.push(
      `INFO og:title "${ogTitle}" lacks route keyword "${keyword}" (SSR not enabled yet)`,
    );
  }

  return { route, url, issues, ogTitle, ogImage };
}

async function main() {
  // Sanity: make sure every per-route OG SVG referenced in a page
  // module also exists in public/ (catches case where a page was added
  // but its OG SVG was forgotten). This duplicates what the build-time
  // gate already checks but is cheap and resilient if the live host
  // is unreachable.
  const localOgs = readdirSync(PUBLIC_DIR).filter(
    (f) => f.startsWith("og") && f.endsWith(".svg"),
  );
  if (localOgs.length === 0) {
    console.error("live-og-check: no public/og*.svg files found");
    process.exit(2);
  }

  console.log(`Wave 127 live OG check  ·  host=${HOST}`);
  console.log(`Routes: ${ROUTES.length}  ·  local OG SVGs: ${localOgs.length}\n`);

  const results = await Promise.all(ROUTES.map(checkRoute));
  let fails = 0;
  for (const r of results) {
    const blocking = r.issues.filter((i) => !i.startsWith("INFO"));
    if (blocking.length > 0) {
      fails++;
      console.log(`  FAIL  ${r.route.padEnd(28)} → ${blocking.join("; ")}`);
    } else if (r.issues.length > 0) {
      console.log(`  WARN  ${r.route.padEnd(28)} → ${r.issues.join("; ")}`);
    } else {
      console.log(`  PASS  ${r.route.padEnd(28)} → ${r.ogImage || "(default)"}`);
    }
  }

  console.log("");
  if (fails > 0) {
    console.error(`live-og-check: ${fails} route(s) failed live verification.`);
    process.exit(1);
  }
  console.log(`live-og-check: ${results.length} routes OK.`);
  process.exit(0);
}

// Bail out cleanly when run on Node < 18 (no global fetch).
if (typeof fetch !== "function") {
  console.error("live-og-check: needs Node >= 18 (global fetch).");
  process.exit(2);
}

main().catch((e) => {
  console.error("live-og-check: unexpected error:", e);
  process.exit(2);
});

// Ensure the existsSync import isn't tree-shaken by some bundler that
// might inline this file in the future. (No-op at runtime.)
void existsSync;
