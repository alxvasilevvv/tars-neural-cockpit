# OG / Twitter Card Contract — `tars.meeet.world`

**Owner:** Claude · **Wave:** 127 · **Last update:** 2026-05-11

A broken share preview halves CTR on HN / Twitter / Reddit. This
contract pins the rules every route on `tars.meeet.world` must follow
and the gates that enforce them.

---

## 1. Required tags

Every route ships these meta tags (per-route via `useDocumentMeta`,
fallback static in `experiments/neural-showcase-v3/index.html`):

| Tag | Source | Rule |
| --- | --- | --- |
| `<title>` | `useDocumentMeta({ title })` + suffix | non-empty, **≤ 60 chars** including the ` · TARS · meeet.world` suffix |
| `meta[name="description"]` | `useDocumentMeta({ description })` | non-empty, **≤ 200 chars** |
| `meta[property="og:title"]` | mirrors `<title>` | required |
| `meta[property="og:description"]` | mirrors description | required |
| `meta[property="og:image"]` | `useDocumentMeta({ ogImage })` | absolute URL on `https://tars.meeet.world/`, file MUST exist in `public/` |
| `meta[property="og:image:width"]` | static, `1200` | constant |
| `meta[property="og:image:height"]` | static, `630` | constant |
| `meta[property="og:type"]` | static, `website` | `website` or `article` |
| `meta[property="og:url"]` | per route | absolute |
| `meta[property="og:site_name"]` | static, `TARS · meeet.world` | constant |
| `meta[name="twitter:card"]` | static, `summary_large_image` | constant |
| `meta[name="twitter:title"]` | mirrors `<title>` | required |
| `meta[name="twitter:description"]` | mirrors description | required |
| `meta[name="twitter:image"]` | mirrors `og:image` | required |
| `link[rel="canonical"]` | static | `https://tars.meeet.world/` |

The `useDocumentMeta` hook (in `experiments/neural-showcase-v3/src/lib/meta.ts`)
keeps `og:title`, `og:description`, `og:image`, `twitter:title`,
`twitter:description`, `twitter:image` in lock-step with the page
literals — agents only ever set the three primitives `title`,
`description`, `ogImage`.

---

## 2. Image dimensions

OG SVGs live in `experiments/neural-showcase-v3/public/og-*.svg`.

- **Required:** `width ≥ 1200` × `height ≥ 630` (Twitter
  `summary_large_image` minimum). The validator parses the opening
  `<svg>` tag for `width="..."` / `height="..."`, falling back to the
  `viewBox` width × height when explicit attributes are absent.
- All current files use `viewBox="0 0 1200 630" width="1200" height="630"`.

---

## 3. Per-route OG vs default

Per-route OG SVGs lift CTR vs the brand default `/og.svg`. The
build-time validator emits a non-blocking `INFO` warning when a route
falls back to `og.svg`, naming the closest sensible candidate
(`og-<slug>.svg` if it exists, otherwise `og-<slug>-*.svg` for nested
routes — e.g. `/workshop/enterprise` → `og-workshop-enterprise.svg`).

Existing per-route OG cards (Waves 11 / 44 / 83 / 112): home, cockpit,
install, onboarding, pitch, press, build-with, workshop,
workshop-enterprise, dashboard, compliance, marketplace, perf, files,
inbox, reports, workspaces, onboard, faq (default), pricing
(default), compare (default).

---

## 4. Adding a new route

1. **Wire `useDocumentMeta`** in the new page module:
   ```tsx
   useDocumentMeta({
     title: "Short headline",            // ≤ 40 chars to fit the suffix
     description: "Why this page matters in one sentence.",
     ogImage: "https://tars.meeet.world/og-mypage.svg",
   });
   ```
2. **Add the OG SVG** to `experiments/neural-showcase-v3/public/og-mypage.svg`.
   Copy any existing `og-*.svg` and re-letter the headline; keep the
   `viewBox="0 0 1200 630" width="1200" height="630"` header intact.
3. **Validate locally:**
   ```sh
   cd experiments/neural-showcase-v3
   npm run og:check         # build-time gate
   npm run og:check:live    # post-deploy gate (after main lands)
   ```
4. The CI workflow `tars-meeet-cloudflare-pages.yml` runs
   `og:check` automatically on every PR + push to main and **blocks**
   the deploy on any FAIL.

---

## 5. Validators

### `scripts/validate-og-cards.mjs` (build-time, blocking)

- Walks every route in `App.tsx` → finds the matching page module →
  extracts the `useDocumentMeta({...})` literal.
- Merges with `index.html` defaults.
- Validates against the rules in §1 + §2.
- **Exit codes:** `0` clean (warnings allowed), `1` at least one FAIL,
  `2` script failure.
- Wired into `.github/workflows/tars-meeet-cloudflare-pages.yml` as
  the **Wave 127 gate**, before the build step.

### `scripts/live-og-check.mjs` (post-deploy, advisory)

- Fetches every route over the network and parses the rendered HTML
  for `og:*` / `twitter:*` tags.
- HEADs each `og:image` URL — must return 200 + a `Content-Type` of
  `image/svg+xml` (or `image/*`).
- Run via `npm run og:check:live` locally, or as a 5-minute-after-deploy
  GitHub Actions cron.

### `src/lib/og-meta.ts` + `src/lib/og-meta.test.ts`

- Exports the threshold constants (`TITLE_MAX`, `DESC_MAX`,
  `IMG_MIN_W`, `IMG_MIN_H`, `CANONICAL_HOST`, `TITLE_SUFFIX`) plus
  pure helpers (`validateTitle`, `validateDescription`,
  `parseSvgDims`, `meetsImageDims`, `suggestOgSlug`,
  `isValidTwitterCard`, `isValidOgType`).
- Vitest covers each helper in `og-meta.test.ts` (~15 cases). The
  validator script and the unit tests share these exact constants so
  changing `TITLE_MAX` in one place flows to both gates.

---

## 6. Auto-fix patterns

The build-time validator surfaces actionable suggestions for the most
common failures:

| Failure | Suggestion shape |
| --- | --- |
| `title > 60 chars` | trimmed to fit `TITLE_MAX − suffix.length − 1` chars + `…` |
| `og:image file missing` | path of the closest matching `og-<slug>.svg` (else `og.svg`) |
| `og:image dims < 1200x630` | flagged FAIL — re-export at the right resolution |
| `twitter:card != summary_large_image` | hard-coded fix — set in `index.html` |

---

## 7. Wave history

- **Wave 11** (2026-04-?): added 13 per-route OG SVGs — landing,
  cockpit, install, onboarding, pricing, faq, compare.
- **Wave 44**: per-route OG cards for `/pricing`, `/faq`, `/compare`,
  `/onboarding`, `/press`.
- **Wave 83**: workshop OG SVG variants + sitemap polish.
- **Wave 112**: integration polish — added missing OG cards for
  workspaces, dashboard, files, inbox, marketplace, reports, perf.
- **Wave 127** *(this contract)*: build-time validator + CI gate +
  live check + unit tests + auto-fix suggestions for two existing
  overflow titles (`/workshop/enterprise`, `/workshop/materials`).
