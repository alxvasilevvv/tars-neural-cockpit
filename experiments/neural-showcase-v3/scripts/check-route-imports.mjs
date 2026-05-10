#!/usr/bin/env node
/**
 * Wave 116 — Pre-build route-import sanity check.
 *
 * Walks `src/App.tsx` and verifies that every JSX identifier rendered
 * inside a `<Route element={...}>` (and a few related JSX wrappers we
 * use, like Suspense+Component) has a matching `lazy(() => import(...))`
 * declaration, a top-level ES `import { Foo }`, or a function/const
 * declaration in the same module.
 *
 * Why this exists:
 *   tsc happily passes JSX where the identifier is undefined at runtime
 *   ("ReferenceError: Foo is not defined") because ANY uppercase JSX
 *   identifier is treated as a component reference; only the runtime
 *   sees the missing binding. Wave 113/114 shipped a 500 on /workshop
 *   because `<Workshop />` had no `lazy(...)` line. Wave 116 adds this
 *   guard so the same class of bug never reaches prod again.
 *
 * Exit codes:
 *   0  — every route component has a matching declaration.
 *   1  — at least one route references an undefined identifier; the
 *        report lists each (route element, missing identifier).
 *
 * Usage:
 *   node scripts/check-route-imports.mjs
 *
 * Wired into `prebuild` in package.json so `npm run build` blocks on it.
 *
 * No deps — plain regex over App.tsx text. AST would be more robust but
 * the App.tsx surface is small + stable + the regex is conservative
 * (false positives are surfaced, never silently swallowed).
 */

import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP_TSX = resolve(__dirname, "..", "src", "App.tsx");

if (!existsSync(APP_TSX)) {
  console.error(`[route-imports] App.tsx not found at ${APP_TSX}`);
  process.exit(2);
}

const src = readFileSync(APP_TSX, "utf8");

// 1. Collect every identifier that's "in scope" inside App.tsx.
//    We accept any of:
//      - `const Foo = lazy(...)`
//      - `const Foo = ...` / `let Foo = ...`
//      - `function Foo(...)`
//      - `import { Foo } from "..."` (named, possibly aliased: `Foo as Bar`)
//      - `import Foo from "..."` (default)
//      - `import * as Foo from "..."`
const declared = new Set();

// Reserved JSX intrinsics + framework primitives we treat as "always available"
// (lower-case JSX tags are intrinsic HTML and aren't checked anyway, but a few
// upper-case names are framework-provided in-scope by react-router-dom etc.).
const ALWAYS_OK = new Set([
  "Routes",
  "Route",
  "Suspense",
  "Navigate",
  "Outlet",
  "Fragment",
  // Framer-motion shorthand `motion.div` — handled separately (dot access).
]);

// const/let/var X = ...
for (const m of src.matchAll(/\b(?:const|let|var)\s+([A-Z][A-Za-z0-9_]*)\s*=/g)) {
  declared.add(m[1]);
}
// function X(...)
for (const m of src.matchAll(/\bfunction\s+([A-Z][A-Za-z0-9_]*)\s*\(/g)) {
  declared.add(m[1]);
}
// import { X, Y as Z } from "..."
for (const m of src.matchAll(/import\s*\{([^}]+)\}\s*from\s*["'][^"']+["']/g)) {
  for (const raw of m[1].split(",")) {
    const part = raw.trim();
    if (!part) continue;
    // `Foo as Bar` → take Bar (the in-scope binding)
    const aliasMatch = part.match(/\bas\s+([A-Z][A-Za-z0-9_]*)\s*$/);
    if (aliasMatch) {
      declared.add(aliasMatch[1]);
    } else {
      const name = part.replace(/^type\s+/, "").trim();
      if (/^[A-Z][A-Za-z0-9_]*$/.test(name)) declared.add(name);
    }
  }
}
// import X from "..."
for (const m of src.matchAll(/import\s+([A-Z][A-Za-z0-9_]*)\s+from\s*["'][^"']+["']/g)) {
  declared.add(m[1]);
}
// import * as X from "..."
for (const m of src.matchAll(/import\s+\*\s+as\s+([A-Z][A-Za-z0-9_]*)\s+from\s*["'][^"']+["']/g)) {
  declared.add(m[1]);
}

// 2. Collect every JSX identifier referenced in a route slot.
//    Pattern: `<Identifier ... />` or `<Identifier ...>` inside a
//    `<Route element={...}>`. We grab ALL JSX identifiers in the file
//    and let the declared-set filter; this catches the Wave 114 bug
//    even if the missing component is rendered outside an explicit
//    `<Route element={...}>` (e.g. inside <CockpitGate><Suspense>...).
const jsxRefs = new Map(); // identifier -> first line number

const lines = src.split("\n");
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  // `<Foo` not followed by another word char — stops `<Foobar` from
  // collapsing into `<Foo`. Also skip closing tags `</Foo>`.
  for (const m of line.matchAll(/<([A-Z][A-Za-z0-9_]*)\b/g)) {
    const name = m[1];
    if (!jsxRefs.has(name)) jsxRefs.set(name, i + 1);
  }
}

// 3. Diff: anything referenced in JSX but neither declared nor in the
//    always-available set is a bug.
const missing = [];
for (const [name, lineNo] of jsxRefs) {
  if (declared.has(name)) continue;
  if (ALWAYS_OK.has(name)) continue;
  missing.push({ name, lineNo });
}

if (missing.length === 0) {
  console.log(
    `[route-imports] OK — ${jsxRefs.size} JSX identifier(s) checked, ` +
      `${declared.size} declarations found, 0 unresolved.`,
  );
  process.exit(0);
}

console.error(
  `[route-imports] FAIL — ${missing.length} JSX identifier(s) referenced ` +
    `in ${APP_TSX.split("/").slice(-2).join("/")} but never declared/imported:`,
);
for (const { name, lineNo } of missing) {
  console.error(
    `  - <${name} /> at line ${lineNo} — add a matching ` +
      `\`const ${name} = lazy(() => import("@/pages/${name}").then((m) => ({ default: m.${name} })))\` ` +
      `or \`import { ${name} } from "...";\` declaration.`,
  );
}
console.error(
  `\n[route-imports] This is the Wave 114 class of bug — JSX accepts any ` +
    `uppercase identifier, so tsc passes, but the route 500s at runtime ` +
    `with "ReferenceError: <name> is not defined". Fix the declaration before merging.`,
);
process.exit(1);
