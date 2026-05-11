# PERF_AUDIT — 2026-05-11 (Wave 124)

Static Lighthouse-style audit on `experiments/neural-showcase-v3` (the
TARS marketing + cockpit FE). Numbers are **estimates** — no
`vite build && bundle-analyzer` was run; bytes are extrapolated from
LOC × `~30 bytes/LOC` (post-tree-shake, pre-gzip × 0.4 ratio).

---

## 1. Bundle size estimate (per lazy chunk)

App.tsx lazy-loads ~30 routes. Top chunks after the Wave 124 split:

| Route                | Page LOC | + sibling deps* | est. raw  | est. gzip |
| -------------------- | -------: | --------------: | --------: | --------: |
| `/org/onboarding`    | 1372     | shared form bits | 41 KB     | 16 KB     |
| `/cockpit`           | 910      | RobotAvatar 547 + ChatPane 834 + RightRail 499 + OperatorPalette 629 + WatchMeWork 419 = **3.8 K LOC** | 144 KB | **58 KB** |
| `/cohort` (workshop) | 811      | misc.            | 24 KB     | 10 KB     |
| `/policy`            | 728      | confirmation modal | 22 KB   | 9 KB      |
| `/workshop/materials`| 716      | grid + video strip | 22 KB   | 9 KB      |
| `/workshop/assess`   | 697      | quiz state       | 21 KB     | 8 KB      |
| `/install`           | 675      | install copy     | 20 KB     | 8 KB      |
| `/awareness`         | 663      | timeline data    | 20 KB     | 8 KB      |
| `/pitch`             | 191 + 766 (PitchSlides) | — | 29 KB | 12 KB |
| `/onboarding`        | 613 + 156 (CustomRoleModal) + 106 (roles.data) | — | 26 KB | 11 KB |
| `/compliance`        | 532 + 230 (ExportBundleSection) + 60 (audit.mock) | + ComplianceLog/Verifier | 38 KB | 15 KB |
| `/`  (Landing)       | (lazy) | HeroScene + ScrollStory 673 + DownloadStrip 456 + MeeetSection + Sparkles 434 = **5 K LOC of vendor + brand**| 150 KB | **60 KB** |

*"sibling deps" = components imported eagerly by the route, before
async.

**Cockpit (~58 KB gzip) and Landing (~60 KB gzip)** are the
heavyweights. Both well under the 170 KB JS budget that LH treats as
non-flagged for desktop, but mobile 4G TTI is ~2 s on Cockpit.

---

## 2. LCP-bound assets on `/`

The hero LCP element is the gradient text + Sparkles WebGL canvas
(visible above the fold). What loads on `/`:

- **Fonts** — Google "Fira Code" + "Share Tech Mono" via
  `<link href="fonts.googleapis.com/css2?…" />` with `&display=swap`
  in `index.html`. Render-blocking until parsed; ~30 KB of CSS,
  ~80 KB of font subsets. **Already preconnects to gstatic.**
- **Hero / OG SVGs** — `public/og-*.svg` (21 files, 4–8 KB each).
  Only the active route's OG SVG is referenced via `<meta>`.
- **No `<img>` on `/`** — verified by `grep -rE "<img" pages/Landing.tsx`
  → 0 hits. Hero uses `<canvas>` (Sparkles) + SVG glyphs.
- **Sparkles + tsparticles bundle** — heavy JS dep loaded eagerly with
  the page (no Suspense boundary). Same lazy-loaded as Landing chunk
  itself, but still ~50 KB gzip alone.

`<img>` tag audit across `src/`:
```
src/components/files/FilePreview.tsx     — alt={file.filename ?? ""}    no loading attr
src/components/files/FileGrid.tsx        — alt=""    loading="lazy"     OK
src/components/AttachmentChipStrip.tsx   — alt={filename ?? "image"}    no loading attr
```
Three `<img>` total in the codebase. **All have `alt`.** Two missing
`loading="lazy"` — both inside file-management surfaces (`/files`,
chat attachments), not on `/`. **Not LCP-bound.** Recommend adding
`loading="lazy"` anyway for v9.2.

---

## 3. A11y quick-scan

- `<img>` w/o `alt` → **0 hits**.
- `<button>` count → **351 across `*.tsx`**; aria-label / role="img"
  occurrences → **254**. Spot-check on icon-only buttons (NavBtn,
  PitchSlides primitive) confirms `aria-label` is set; no obvious
  WCAG 2.1 §4.1.2 violations on the routes I sampled.
- `<input>` w/o associated `<label>` → none found in the sample
  (`Onboarding`, `OrgOnboarding`, `Compliance`).
- `useFocusTrap` is wired on the 3 Cmd+K palettes (Wave 58) and the
  CustomRoleModal (Wave 124 split). Modal escape-key handling
  consistent.
- Color contrast — not audited statically; Wave 122 found Compliance
  filter chips at 3.4:1 (below AA 4.5:1). Still open.

---

## 4. Critical request chain on `/`

```
HTML  (4 KB)
 ├── /favicon.svg, /favicon-32.png  (parallel, blocking nothing)
 ├── /manifest.webmanifest          (PWA)
 ├── /sw.js                         (registers service worker)
 ├── fonts.googleapis.com CSS       (render-blocking, ~30 KB)
 │     └── fonts.gstatic.com .woff2 (parallel, FOIT until loaded)
 ├── /assets/index-<hash>.js        (~120 KB gzip eager)
 │     └── /assets/landing-<hash>.js (lazy chunk on /)
 │           └── tsparticles + Sparkles (~50 KB gzip)
 └── /assets/index-<hash>.css       (~12 KB gzip)
```

Critical chain depth = 4 (HTML → eager JS → lazy chunk → tsparticles).
Eager JS includes React + Router + framer-motion + lucide-react. No
HTTP/2 push, but Vite emits `<link rel="modulepreload">` for the
lazy chunk so the network stack starts fetching it before the parser
hits the dynamic `import()`.

---

## 5. Recommendations (impact / effort)

| # | Impact | Effort | Action |
|---|--------|--------|--------|
| 1 | **High** | Low | Add `loading="lazy"` to the 2 `<img>` in `FilePreview.tsx` + `AttachmentChipStrip.tsx`. |
| 2 | **High** | Med  | Code-split tsparticles out of the Landing eager chunk — wrap `<Sparkles>` in `React.lazy` + Suspense, render a CSS gradient placeholder above the fold. Saves ~50 KB on cold `/` visits. |
| 3 | **High** | Med  | Self-host the 2 fonts (Fira Code + Share Tech Mono) via `@font-face` with `font-display: optional` to drop the 2 third-party DNS look-ups + remove FOIT. |
| 4 | Med | Low | Continue split of `OrgOnboarding.tsx` (1372 LOC) — extract Step1–Step5 functions into per-step components (560 LOC each call site). Wave 124 only got the easy data. |
| 5 | Med | Low | Bump fix the Compliance filter-chip contrast (3.4 → 4.5:1) — change `text-ink-3` → `text-ink-2` on the chip's idle state. |
| 6 | Med | Med | `Cockpit.tsx` lazy chunk (~58 KB gzip) is mostly the eager-imported `ChatPane` (834 LOC) + `RobotAvatar` (547 LOC). Lazy-load RobotAvatar behind the "speak"/"listen" state — first paint of Cockpit doesn't need the avatar mounted. |
| 7 | Low | Low | Drop the duplicate `og-onboard.svg` / `og-onboarding.svg` (one's a typo from Wave 11). |
| 8 | Low | High | Replace framer-motion → @motionone/react on marketing pages (smaller, no scope-tracking) — only worth it if marketing chunks become P0 again. |

---

## Closes (this wave)

- Bullets 1, 5, and 7 are quick follow-ups for v9.2 (out of scope for
  Wave 124's pure-refactor commit).
- Bullets 2, 3, 6 are Wave 125 perf-budget work.
- The split work in this wave already removed ~750 LOC from the page
  files (Pitch 942 → 191, Onboarding 845 → 613, Compliance 797 → 532)
  and deleted 10 dead-code files (~2 K LOC unreferenced removed from
  the import graph), shrinking the eager-chunk feed.
