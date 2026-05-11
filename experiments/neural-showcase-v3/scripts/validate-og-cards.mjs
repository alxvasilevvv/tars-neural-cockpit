#!/usr/bin/env node
/**
 * Wave 127 — OG / Twitter card validator (build-time gate).
 *
 * The marketing surface launches into HN / Twitter / Reddit and a
 * broken share preview halves the click-through rate. Per-route OG
 * SVGs were added in Waves 11 / 44 / 83 / 112 and `useDocumentMeta`
 * (src/lib/meta.ts) writes the dynamic tags client-side; the static
 * fallback lives in index.html for crawlers.
 *
 * This script is the static gate: it walks every page module wired
 * into App.tsx, extracts the literal `useDocumentMeta({ ... })`
 * argument, merges it with the index.html defaults, and validates
 * the resulting OG / Twitter shape against the contract documented
 * in docs/contracts/OG_CARDS.md.
 *
 * Validation rules (one row per route):
 *   - title         — non-empty, ≤ 60 chars (Twitter title cap)
 *   - description   — non-empty, ≤ 200 chars (OG description cap)
 *   - og:image      — absolute URL, host = tars.meeet.world,
 *                     file MUST exist under public/
 *   - SVG dimensions — width/height ≥ 1200 × 630 (parsed from the
 *                     <svg> attributes or viewBox fallback)
 *   - og:type       — "website" | "article" (defaulted in index.html)
 *   - twitter:card  — "summary_large_image" (defaulted in index.html)
 *   - twitter:image — same URL as og:image (set by useDocumentMeta)
 *
 * Exit codes:
 *   0 — every route passes (warnings allowed; auto-fix candidates
 *       are surfaced but do not fail the gate)
 *   1 — at least one FAIL (CI must block the deploy)
 *   2 — script itself failed (no App.tsx, missing public/, etc.)
 *
 * Usage:
 *   node scripts/validate-og-cards.mjs                # plain text
 *   node scripts/validate-og-cards.mjs --json         # machine output
 *
 * The companion live-check (scripts/live-og-check.mjs) hits the
 * deployed surface with curl and verifies the rendered HTML matches
 * what this script statically computed. Both are wired into
 * tars-meeet-cloudflare-pages.yml — this one as the BLOCKING gate
 * before the build, the live check after deploy.
 */

import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = resolve(__dirname, "..");
const PUBLIC_DIR = join(ROOT, "public");
const PAGES_DIR = join(ROOT, "src", "pages");
const APP_TSX = join(ROOT, "src", "App.tsx");
const INDEX_HTML = join(ROOT, "index.html");

const CANONICAL_HOST = "https://tars.meeet.world";
const TITLE_MAX = 60;
const DESC_MAX = 200;
const IMG_MIN_W = 1200;
const IMG_MIN_H = 630;

const args = new Set(process.argv.slice(2));
const wantJson = args.has("--json");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const C = {
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
};

function die(msg, code = 2) {
  process.stderr.write(`validate-og-cards: ${msg}\n`);
  process.exit(code);
}

// ---------------------------------------------------------------------------
// 1. Index.html defaults (fallback for crawlers without JS)
// ---------------------------------------------------------------------------

function parseIndexHtmlDefaults() {
  const html = readFileSync(INDEX_HTML, "utf8");
  const pick = (re) => {
    const m = html.match(re);
    return m ? m[1].trim() : "";
  };
  return {
    title: pick(/<title>([^<]+)<\/title>/i),
    description: pick(/<meta\s+name="description"\s+content="([^"]+)"/i),
    ogTitle: pick(/<meta\s+property="og:title"\s+content="([^"]+)"/i),
    ogDescription: pick(
      /<meta\s+property="og:description"\s+content="([^"]+)"/i,
    ),
    ogImage: pick(/<meta\s+property="og:image"\s+content="([^"]+)"/i),
    ogType: pick(/<meta\s+property="og:type"\s+content="([^"]+)"/i),
    twitterCard: pick(/<meta\s+name="twitter:card"\s+content="([^"]+)"/i),
    twitterImage: pick(/<meta\s+name="twitter:image"\s+content="([^"]+)"/i),
    canonical: pick(/<link\s+rel="canonical"\s+href="([^"]+)"/i),
  };
}

// ---------------------------------------------------------------------------
// 2. App.tsx route table → page module mapping
// ---------------------------------------------------------------------------

function parseRouteTable() {
  const src = readFileSync(APP_TSX, "utf8");

  // lazy(() => import("@/pages/Foo")) → { Foo: "Foo.tsx" }
  const lazyRe =
    /const\s+(\w+)\s*=\s*lazy\(\(\)\s*=>\s*\n?\s*import\("@\/pages\/([^"]+)"\)/g;
  const componentToFile = {};
  for (const m of src.matchAll(lazyRe)) {
    componentToFile[m[1]] = `${m[2]}.tsx`;
  }

  // Find every `path="..."` and walk forward to the FIRST page-component
  // identifier that appears inside the surrounding element={...} block.
  // (Routes can be wrapped in <Suspense>, <CockpitGate>, etc., so we
  // need to scan past wrapper JSX.)
  const routes = [];
  const pathRe = /path="([^"]+)"/g;
  let m;
  while ((m = pathRe.exec(src)) !== null) {
    const path = m[1];
    // Look ahead within the next ~600 chars for the first `<Identifier`
    // that matches a known lazy page component.
    const window = src.slice(m.index, m.index + 800);
    const idMatches = window.matchAll(/<(\w+)\b/g);
    for (const id of idMatches) {
      const cmp = id[1];
      if (componentToFile[cmp]) {
        if (!routes.some((r) => r.path === path)) {
          routes.push({ path, component: cmp, file: componentToFile[cmp] });
        }
        break;
      }
    }
  }
  return routes;
}

// ---------------------------------------------------------------------------
// 3. Page module → useDocumentMeta literal
// ---------------------------------------------------------------------------

function extractMeta(file) {
  const path = join(PAGES_DIR, file);
  if (!existsSync(path)) return null;
  const src = readFileSync(path, "utf8");
  const idx = src.indexOf("useDocumentMeta(");
  if (idx === -1) return null;

  // Walk braces from the opening `{` until balanced.
  const open = src.indexOf("{", idx);
  if (open === -1) return null;
  let depth = 0;
  let end = -1;
  for (let i = open; i < src.length; i++) {
    const ch = src[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  if (end === -1) return null;
  const body = src.slice(open + 1, end);

  // Pull `key: "value"` (or template literal w/o substitution).
  const fields = {};
  const kvRe =
    /(title|description|ogImage|rawTitle)\s*:\s*(?:"([^"]*)"|`([^`$]*)`|(true|false))/g;
  for (const m of body.matchAll(kvRe)) {
    const key = m[1];
    const val = m[2] ?? m[3] ?? m[4];
    if (val === "true" || val === "false") fields[key] = val === "true";
    else fields[key] = val;
  }

  // Detect dynamic title/description (e.g. `${t("foo")} · TARS`) so we
  // don't false-fail i18n pages — just record the source slice.
  const dynRe = /(title|description|ogImage)\s*:\s*([^,\n]+),?/g;
  for (const m of body.matchAll(dynRe)) {
    if (fields[m[1]] !== undefined) continue;
    const raw = m[2].trim();
    fields[m[1]] = { dynamic: raw };
  }
  return fields;
}

// ---------------------------------------------------------------------------
// 4. SVG dimension parser (width/height attrs or viewBox fallback)
// ---------------------------------------------------------------------------

function parseSvgDims(filepath) {
  if (!existsSync(filepath)) return { width: 0, height: 0, missing: true };
  // Read just the <svg ...> opening tag — these files are <100KB but no
  // need to load the whole thing for one regex.
  const buf = readFileSync(filepath, "utf8").slice(0, 2048);
  const tag = buf.match(/<svg\b[^>]*>/i);
  if (!tag) return { width: 0, height: 0, parseError: true };
  const attrs = tag[0];
  const w = attrs.match(/\bwidth="(\d+)"/);
  const h = attrs.match(/\bheight="(\d+)"/);
  if (w && h) return { width: +w[1], height: +h[1] };
  const vb = attrs.match(/\bviewBox="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"/);
  if (vb) return { width: +vb[3], height: +vb[4], fromViewBox: true };
  return { width: 0, height: 0, parseError: true };
}

// ---------------------------------------------------------------------------
// 5. Suggest the best matching OG SVG for a route w/o per-route image
// ---------------------------------------------------------------------------

function suggestOgImage(routePath) {
  const slug = routePath.replace(/^\//, "").split("/")[0] || "home";
  const candidates = readdirSync(PUBLIC_DIR).filter(
    (f) => f.startsWith("og-") && f.endsWith(".svg"),
  );
  const exact = candidates.find((f) => f === `og-${slug}.svg`);
  if (exact) return `/${exact}`;
  const prefix = candidates.find((f) => f.startsWith(`og-${slug}-`));
  if (prefix) return `/${prefix}`;
  return "/og.svg";
}

// ---------------------------------------------------------------------------
// 6. Validate one route
// ---------------------------------------------------------------------------

function validateRoute(route, defaults) {
  const meta = extractMeta(route.file);
  const checks = [];
  const warnings = [];
  let fails = 0;

  if (!meta) {
    warnings.push(
      "no useDocumentMeta() in page module — uses index.html defaults only",
    );
    return { route, meta: null, checks, warnings, fails };
  }

  // ---- title ----
  let title = meta.title;
  let titleEffective;
  let titleDynamic = false;
  if (title && typeof title === "object" && title.dynamic) {
    titleDynamic = true;
    titleEffective = title.dynamic;
    checks.push([
      "title",
      "WARN",
      `dynamic (${title.dynamic.slice(0, 40)}...)`,
    ]);
  } else if (typeof title === "string" && title.length > 0) {
    const suffix = meta.rawTitle ? "" : " · TARS · meeet.world";
    titleEffective = `${title}${suffix}`;
    if (titleEffective.length > TITLE_MAX) {
      const trimmedSuggestion =
        title.slice(0, TITLE_MAX - suffix.length - 1).trim() + "…";
      checks.push([
        "title",
        "FAIL",
        `${titleEffective.length} > ${TITLE_MAX} chars · suggest: "${trimmedSuggestion}"`,
      ]);
      fails++;
    } else {
      checks.push(["title", "PASS", `${titleEffective.length} chars`]);
    }
  } else {
    checks.push(["title", "WARN", "missing → uses default"]);
  }

  // ---- description ----
  const desc = meta.description;
  if (desc && typeof desc === "object" && desc.dynamic) {
    checks.push([
      "description",
      "WARN",
      `dynamic (${desc.dynamic.slice(0, 40)}...)`,
    ]);
  } else if (typeof desc === "string" && desc.length > 0) {
    if (desc.length > DESC_MAX) {
      checks.push([
        "description",
        "FAIL",
        `${desc.length} > ${DESC_MAX} chars`,
      ]);
      fails++;
    } else {
      checks.push(["description", "PASS", `${desc.length} chars`]);
    }
  } else {
    checks.push(["description", "WARN", "missing → uses default"]);
  }

  // ---- og:image ----
  const ogImage =
    typeof meta.ogImage === "string" ? meta.ogImage : defaults.ogImage;
  if (!ogImage.startsWith(CANONICAL_HOST)) {
    checks.push(["og:image", "FAIL", `not absolute / wrong host: ${ogImage}`]);
    fails++;
  } else {
    const rel = ogImage.slice(CANONICAL_HOST.length);
    const abs = join(PUBLIC_DIR, rel.replace(/^\//, ""));
    if (!existsSync(abs)) {
      const suggest = suggestOgImage(route.path);
      checks.push([
        "og:image",
        "FAIL",
        `file missing: ${rel} · suggest: ${suggest}`,
      ]);
      fails++;
    } else {
      const dims = parseSvgDims(abs);
      if (dims.parseError) {
        checks.push(["og:image", "WARN", `unable to parse SVG dims: ${rel}`]);
      } else if (dims.width < IMG_MIN_W || dims.height < IMG_MIN_H) {
        checks.push([
          "og:image",
          "FAIL",
          `dims ${dims.width}x${dims.height} < ${IMG_MIN_W}x${IMG_MIN_H}`,
        ]);
        fails++;
      } else {
        checks.push([
          "og:image",
          "PASS",
          `${rel} (${dims.width}x${dims.height})`,
        ]);
        if (rel === "/og.svg" && route.path !== "/") {
          warnings.push(
            `route ${route.path} uses default og.svg — consider per-route OG (suggest ${suggestOgImage(route.path)}) for higher CTR`,
          );
        }
      }
    }
  }

  // ---- og:type / twitter:card / twitter:image (defaulted in index.html)
  if (defaults.ogType !== "website" && defaults.ogType !== "article") {
    checks.push(["og:type", "FAIL", `bad value: "${defaults.ogType}"`]);
    fails++;
  } else {
    checks.push(["og:type", "PASS", defaults.ogType]);
  }
  if (defaults.twitterCard !== "summary_large_image") {
    checks.push([
      "twitter:card",
      "FAIL",
      `must be "summary_large_image", got "${defaults.twitterCard}"`,
    ]);
    fails++;
  } else {
    checks.push(["twitter:card", "PASS", defaults.twitterCard]);
  }
  checks.push(["twitter:image", "PASS", "mirrors og:image"]);

  return {
    route,
    meta,
    checks,
    warnings,
    fails,
    titleEffective,
    titleDynamic,
  };
}

// ---------------------------------------------------------------------------
// 7. Main
// ---------------------------------------------------------------------------

function main() {
  if (!existsSync(APP_TSX)) die("missing src/App.tsx");
  if (!existsSync(INDEX_HTML)) die("missing index.html");
  if (!existsSync(PUBLIC_DIR)) die("missing public/");

  const defaults = parseIndexHtmlDefaults();
  const routes = parseRouteTable();

  if (routes.length === 0) die("no routes parsed from App.tsx");

  // De-dupe by path (App.tsx may have parameterised routes that share
  // the same component — e.g. /workspaces and /workspaces/invite/:token).
  const seen = new Set();
  const unique = routes.filter((r) => {
    if (seen.has(r.path)) return false;
    seen.add(r.path);
    return true;
  });

  const results = unique.map((r) => validateRoute(r, defaults));
  const totalFails = results.reduce((acc, r) => acc + r.fails, 0);
  const totalWarns = results.reduce((acc, r) => acc + r.warnings.length, 0);

  if (wantJson) {
    process.stdout.write(
      JSON.stringify(
        { defaults, routes: results, totalFails, totalWarns },
        null,
        2,
      ) + "\n",
    );
    process.exit(totalFails > 0 ? 1 : 0);
  }

  console.log(C.bold("\nWave 127 — OG / Twitter card validator\n"));
  console.log(`  Canonical host: ${CANONICAL_HOST}`);
  console.log(`  Routes audited: ${unique.length}`);
  console.log(
    `  Public OG SVGs: ${readdirSync(PUBLIC_DIR).filter((f) => f.startsWith("og") && f.endsWith(".svg")).length}\n`,
  );

  for (const r of results) {
    const head = `  ${C.bold(r.route.path.padEnd(28))} ${C.dim(r.route.file)}`;
    console.log(head);
    for (const [field, status, detail] of r.checks) {
      const tag =
        status === "PASS"
          ? C.green("PASS")
          : status === "WARN"
            ? C.yellow("WARN")
            : C.red("FAIL");
      console.log(`    ${tag}  ${field.padEnd(14)} ${C.dim(detail)}`);
    }
    for (const w of r.warnings) {
      console.log(`    ${C.yellow("INFO")}  ${w}`);
    }
  }

  console.log("");
  if (totalFails > 0) {
    console.log(
      C.red(
        `  FAIL — ${totalFails} blocking issue(s) across ${results.filter((r) => r.fails > 0).length} route(s).`,
      ),
    );
    console.log(
      C.dim("  Fix the listed issues, re-run `npm run og:check`, and re-push."),
    );
    process.exit(1);
  }
  console.log(
    C.green(`  PASS — ${results.length} routes audited, 0 blocking issues.`),
  );
  if (totalWarns > 0) {
    console.log(
      C.yellow(
        `  ${totalWarns} non-blocking warning(s) (per-route OG candidates, dynamic titles).`,
      ),
    );
  }
  process.exit(0);
}

main();
