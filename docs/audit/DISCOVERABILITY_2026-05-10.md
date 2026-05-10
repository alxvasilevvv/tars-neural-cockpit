# Discoverability Matrix — 2026-05-10 (Wave 112)

Audit of every Wave 80–110 route across six discoverability surfaces.
Status legend: `Y` = present, `+` = added in Wave 112, `B2B` = surfaced
via the new Nav B2B dropdown rather than a top-level link, `usermenu`
= reserved for future user-menu placement.

## Pages added Waves 80–110

| Route | Sitemap | Nav | Cmd+K | Breadcrumbs | OG | i18n | Test |
|---|---|---|---|---|---|---|---|
| /workshop | + | + B2B | + | + | + (og-workshop) | Y (en strings) | + |
| /workshop/enterprise | + | n/a (canonical /workshop) | + | Y | Y (og-workshop-enterprise) | Y | Y |
| /workshop/roi | Y | n/a | Y | Y | + (og-workshop) | Y | n |
| /workshop/materials | Y | n/a | Y | Y | Y (og-workshop) | Y | n |
| /workshop/assess | Y | n/a | Y | Y | + (og-workshop) | Y | n |
| /workshop/cohort | Y | n/a | Y | Y | + (og-workshop) | Y | n |
| /workshop/cresco | redirect → /workshop/enterprise (verified Wave 112) |
| /compliance | + | + B2B | + | + | + (og-compliance) | Y | + |
| /dashboard | Y | Y B2B | Y | Y | + (og-dashboard) | Y | + |
| /onboard/org | Y | Y (Set up org pill, conditional) + B2B | Y | Y | + (og-onboard) | Y | + |
| /inbox | Y | Y B2B | Y | Y | + (og-inbox) | Y | + |
| /files | + | Y B2B | Y | Y | + (og-files) | Y | + |
| /reports | Y | Y B2B | Y | Y | + (og-reports) | Y | + |
| /marketplace | Y | Y B2B (Marketplace) | Y | Y | + (og-marketplace) | Y | + |
| /admin/perf | Y | Y B2B (Perf) | Y | Y | + (og-perf) | Y | + |
| /workspaces | Y | Y B2B + WorkspaceSwitcher | Y | + | + (og-workspaces) | Y | + |
| /workspaces/invite/:token | n/a (per-token deep link) | n/a | n/a | n/a | + (og-workspaces) | Y | covered |
| /bundles | + | Y B2B | Y | Y | + (og-marketplace) | Y | + |
| /bundles/:id | n/a (per-bundle deep link) | n/a | Y (per-bundle actions) | Y (parent) | inherits | Y | covered |
| /schedules | + | Y B2B | + | Y | + (og-perf) | Y | + |
| /outreach | + | Y B2B | Y | Y | + (og-inbox) | Y | + |

## Fixes applied

1. **OG SVGs created (9):** og-dashboard, og-onboard, og-reports,
   og-marketplace, og-compliance, og-inbox, og-files, og-workspaces,
   og-perf — all 1200×630, dark bg, brand gradient text, single icon,
   matching the og-workshop-enterprise template.
2. **Per-page `useDocumentMeta` ogImage wired (16 pages):** Workshop,
   WorkshopROI, WorkshopAssess, WorkshopCohort, Compliance, Dashboard,
   OrgOnboarding, Inbox, Files, Reports, Marketplace, PerfDashboard,
   Workspaces (+ invite-accept fork), Bundles, Schedules, Outreach.
3. **Sitemap appended (8 routes):** workshop, workshop/enterprise,
   compliance, onboard/org (mirrored), files, bundles, schedules,
   outreach.
4. **Cmd+K palette appended (4 routes):** workshop, workshop/enterprise,
   compliance, schedules.
5. **Breadcrumbs added (3 pages):** Workshop, Compliance, Workspaces
   (the rest already had them from Wave 96+).
6. **Reports / Marketplace breadcrumb `href:` typo → `to:`** so the
   `<Link>` actually navigates instead of typing as `unknown`.
7. **Nav.tsx B2B dropdown:** thirteen B2B operator routes consolidated
   behind one menu (`B2B` button with chevron + HIL pending badge).
   Top-level links now Cockpit / Pricing / Compare / FAQ + Install +
   workspace switcher — five entries plus utility, fits 1280px wide.
8. **Help (?) buttons:** added to /workshop, /dashboard, /onboard/org,
   /reports, /marketplace, /compliance, /inbox, /workspaces via new
   `<HelpButton>` primitive (top-right popover, click-out + escape
   close, a11y-correct aria-expanded/controls).
9. **Cresco redirect verified:** `<Route path="/workshop/cresco"
   element={<Navigate to="/workshop/enterprise" replace />} />` still
   in App.tsx (no regression).

## Test counts per Wave 80–110 module

(`async def test_` + `def test_`, grepped under `tests/`.)

| Module | Tests |
|---|---|
| algotrade | 90 |
| outreach | 51 |
| scheduler | 42 |
| workspaces | 42 |
| webhooks | 37 |
| cohort | 37 |
| marketplace | 24 |
| compliance | 23 |
| reports | 22 |
| files | 15 |
| bundles | 14 |
| perf | 9 |
| autopilot | 8 |

Frontend-only modules (workshop, onboard, inbox, dashboard) lack
backend tests by design — Wave 112 added Vitest export pins in
`src/pages/Wave112.smoke.test.tsx` (14 pins, one per Wave 80-110
page + the two new shared primitives).

## Verifications

- `tsc --noEmit` → 0 errors.
- Python AST sweep over `backend/core` → 0 fail.
- Cresco → enterprise redirect present in `src/App.tsx:470-473`.
- Every Wave 80-110 route resolves through `<title>` via
  `useDocumentMeta` and `<meta og:image>` via `setMeta("og:image", …)`.
