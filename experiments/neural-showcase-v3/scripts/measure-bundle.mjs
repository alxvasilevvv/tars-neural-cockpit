#!/usr/bin/env node
/**
 * Wave 128 — Bundle size gate.
 *
 * Measures gzipped sizes of build artefacts in `dist/`, compares them
 * against `bundlesize.config.json` budgets and the
 * `bundle-sizes-baseline.json` snapshot, and writes a Markdown summary
 * suitable for sticky PR comments.
 *
 * Why this exists:
 *   The W124 perf audit found three hot-spots — tsparticles eagerly
 *   loaded with the Landing route (~50 KB gzip), RobotAvatar 547 LOC
 *   eagerly bundled with Cockpit, and render-blocking Google Fonts.
 *   Without an automated gate, any PR can silently add another 50 KB
 *   and we only learn from user complaints. This script is the gate.
 *
 * Exit codes:
 *   0 — every budget within `max_gzip_kb` AND no regression beyond
 *       `fail_threshold_growth_pct` vs baseline. May still emit
 *       warnings (`::warning::` lines) for `warn_gzip_kb` overshoots.
 *   1 — at least one budget exceeded `max_gzip_kb` OR a tracked file
 *       grew more than `fail_threshold_growth_pct` % vs baseline.
 *   2 — script failed to run (no dist/, malformed config, etc.).
 *
 * Outputs:
 *   - stdout — human-readable table
 *   - dist/bundle-sizes.json     — current snapshot (consumed by CI to
 *                                  refresh baseline after main builds)
 *   - dist/bundle-size-summary.md — Markdown summary for sticky PR
 *                                   comment
 *
 * Zero deps — uses node:fs / node:path / node:zlib / node:util.glob.
 *
 * Usage:
 *   node scripts/measure-bundle.mjs [--baseline path]
 *
 * Local debug:
 *   npm run size:check     # build + measure
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve, basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const DIST = resolve(ROOT, "dist");
const CONFIG_PATH = resolve(ROOT, "bundlesize.config.json");
const BASELINE_PATH = resolve(ROOT, "bundle-sizes-baseline.json");
const SNAPSHOT_PATH = resolve(DIST, "bundle-sizes.json");
const SUMMARY_PATH = resolve(DIST, "bundle-size-summary.md");

function fail(msg, code = 2) {
  console.error(`[bundle-gate] ERROR: ${msg}`);
  process.exit(code);
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

if (!existsSync(CONFIG_PATH)) {
  fail(`config missing: ${CONFIG_PATH}`);
}

if (!existsSync(DIST)) {
  console.error("[bundle-gate] no dist/ — run `npm run build` first. Skipping (exit 0).");
  process.exit(0);
}

const config = readJson(CONFIG_PATH);
const FAIL_GROWTH_PCT = Number(config.fail_threshold_growth_pct ?? 10);

// ---- glob (minimal, single * inside basename only) -------------------
// We only support patterns of the shape "dist/<dir>/<prefix>*<suffix>"
// because Vite's hashed assets are always `<chunk>-<hash>.js`. Keeping
// the glob trivial avoids pulling in a dep.
function matchGlob(pattern) {
  const abs = resolve(ROOT, pattern);
  const dir = dirname(abs);
  const base = basename(abs);
  if (!existsSync(dir)) return [];
  const star = base.indexOf("*");
  if (star === -1) {
    return existsSync(abs) ? [abs] : [];
  }
  const prefix = base.slice(0, star);
  const suffix = base.slice(star + 1);
  return readdirSync(dir)
    .filter((name) => name.startsWith(prefix) && name.endsWith(suffix))
    .map((name) => join(dir, name))
    .filter((p) => statSync(p).isFile());
}

function gzipSizeKb(path) {
  const raw = readFileSync(path);
  const gz = gzipSync(raw, { level: 9 });
  return {
    raw_kb: +(raw.length / 1024).toFixed(2),
    gzip_kb: +(gz.length / 1024).toFixed(2),
  };
}

function pct(curr, base) {
  if (!base) return null;
  return +(((curr - base) / base) * 100).toFixed(1);
}

// ---- baseline lookup -------------------------------------------------
let baselineMap = new Map();
if (existsSync(BASELINE_PATH)) {
  try {
    const baseline = readJson(BASELINE_PATH);
    for (const entry of baseline.sizes ?? []) {
      baselineMap.set(entry.label, entry);
    }
  } catch (err) {
    console.error(`[bundle-gate] WARN: failed to parse baseline (${err.message}) — treating as empty.`);
  }
}

// ---- measure ---------------------------------------------------------
const results = [];
let anyHardFail = false;

for (const budget of config.budgets ?? []) {
  const matches = matchGlob(budget.path);
  if (matches.length === 0) {
    results.push({
      label: budget.label,
      path: budget.path,
      status: "missing",
      raw_kb: 0,
      gzip_kb: 0,
      max_gzip_kb: budget.max_gzip_kb,
      warn_gzip_kb: budget.warn_gzip_kb,
      delta_pct: null,
      baseline_gzip_kb: baselineMap.get(budget.label)?.gzip_kb ?? null,
      note: "no file matched glob (route may not exist yet)",
    });
    continue;
  }
  // Sum sizes if multiple matches (rare — usually 1 per chunk).
  let raw = 0;
  let gz = 0;
  const matchedFiles = [];
  for (const file of matches) {
    const sz = gzipSizeKb(file);
    raw += sz.raw_kb;
    gz += sz.gzip_kb;
    matchedFiles.push(basename(file));
  }
  raw = +raw.toFixed(2);
  gz = +gz.toFixed(2);
  const baseline = baselineMap.get(budget.label);
  const delta = pct(gz, baseline?.gzip_kb);

  let status = "ok";
  const reasons = [];
  if (gz > budget.max_gzip_kb) {
    status = "fail";
    anyHardFail = true;
    reasons.push(`exceeds budget ${budget.max_gzip_kb} KB gzip`);
  } else if (gz > budget.warn_gzip_kb) {
    status = "warn";
    reasons.push(`above warn threshold ${budget.warn_gzip_kb} KB gzip`);
  }
  if (delta !== null && delta > FAIL_GROWTH_PCT) {
    status = "fail";
    anyHardFail = true;
    reasons.push(`grew ${delta}% vs baseline (>${FAIL_GROWTH_PCT}%)`);
  }

  results.push({
    label: budget.label,
    path: budget.path,
    files: matchedFiles,
    status,
    raw_kb: raw,
    gzip_kb: gz,
    max_gzip_kb: budget.max_gzip_kb,
    warn_gzip_kb: budget.warn_gzip_kb,
    baseline_gzip_kb: baseline?.gzip_kb ?? null,
    delta_pct: delta,
    note: reasons.join("; ") || null,
  });
}

// ---- snapshot for baseline ------------------------------------------
const snapshot = {
  _meta: {
    generated: new Date().toISOString(),
    wave: 128,
    fail_threshold_growth_pct: FAIL_GROWTH_PCT,
  },
  sizes: results
    .filter((r) => r.status !== "missing")
    .map((r) => ({ label: r.label, gzip_kb: r.gzip_kb, raw_kb: r.raw_kb })),
};
mkdirSync(DIST, { recursive: true });
writeFileSync(SNAPSHOT_PATH, JSON.stringify(snapshot, null, 2) + "\n");

// ---- stdout table ----------------------------------------------------
function fmtRow(r) {
  const baseline = r.baseline_gzip_kb !== null ? `${r.baseline_gzip_kb} KB` : "—";
  const delta = r.delta_pct !== null ? `${r.delta_pct >= 0 ? "+" : ""}${r.delta_pct}%` : "—";
  return [
    r.status.padEnd(7),
    r.label.padEnd(22),
    `${r.gzip_kb} KB`.padEnd(11),
    `${r.max_gzip_kb} KB`.padEnd(8),
    baseline.padEnd(10),
    delta.padEnd(8),
    r.note ?? "",
  ].join(" | ");
}
console.log("\n[bundle-gate] Wave 128 — bundle size report");
console.log("status  | label                  | gzip        | max      | baseline   | delta    | note");
console.log("--------+------------------------+-------------+----------+------------+----------+-----");
for (const r of results) console.log(fmtRow(r));

// ---- markdown summary for PR comment ---------------------------------
function statusBadge(s) {
  return s === "ok" ? "OK" : s === "warn" ? "WARN" : s === "fail" ? "FAIL" : "MISSING";
}
const md = [];
md.push("## Bundle size report (Wave 128 gate)");
md.push("");
md.push(`Threshold: fail if any chunk grows more than **${FAIL_GROWTH_PCT}%** vs baseline OR exceeds its hard \`max_gzip_kb\` budget.`);
md.push("");
md.push("| Status | Chunk | Gzip | Max | Baseline | Delta | Note |");
md.push("|---|---|---:|---:|---:|---:|---|");
for (const r of results) {
  const baseline = r.baseline_gzip_kb !== null ? `${r.baseline_gzip_kb} KB` : "—";
  const delta = r.delta_pct !== null ? `${r.delta_pct >= 0 ? "+" : ""}${r.delta_pct}%` : "—";
  md.push(
    `| ${statusBadge(r.status)} | \`${r.label}\` | ${r.gzip_kb} KB | ${r.max_gzip_kb} KB | ${baseline} | ${delta} | ${r.note ?? ""} |`,
  );
}
md.push("");
md.push(anyHardFail
  ? "**Result: FAIL** — at least one budget breached. Either trim the regression or update `bundlesize.config.json` with a written justification in the PR description."
  : "**Result: OK** — every chunk within budget.");
md.push("");
md.push("<sub>Source: `experiments/neural-showcase-v3/scripts/measure-bundle.mjs` · baseline: `bundle-sizes-baseline.json`</sub>");
writeFileSync(SUMMARY_PATH, md.join("\n") + "\n");

// ---- exit ------------------------------------------------------------
if (anyHardFail) {
  console.error("\n[bundle-gate] FAIL — see table above; details in dist/bundle-size-summary.md");
  process.exit(1);
}
console.log("\n[bundle-gate] OK — all budgets within limits.");
process.exit(0);
