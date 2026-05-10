/**
 * Wave 116 — Defense layer 2: smoke-import every page module wired
 * into App.tsx and assert the named export is a callable React
 * component.
 *
 * Why this exists:
 *   App.tsx wires routes via
 *     `lazy(() => import("@/pages/Foo").then((m) => ({ default: m.Foo })))`
 *   If `Foo` is renamed/removed in the page file, the lazy() promise
 *   rejects at runtime with `m.Foo is undefined` and the route 500s.
 *   tsc cannot catch it because the `.then((m) => ({ default: m.Foo }))`
 *   reaches into a dynamic-import namespace.
 *
 *   Wave 114 was an even simpler variant: `<Workshop />` rendered with
 *   no lazy() declaration at all — caught by Defense 1 (the pre-build
 *   regex lint). Defense 2 (this file) adds the symmetric check on the
 *   page-export side: every page module that App.tsx lazy-imports must
 *   actually export the named symbol as a callable component.
 *
 * Pattern follows Wave 112 (`src/pages/Wave112.smoke.test.tsx`) — same
 * vitest, no @testing-library/react required (the v3 surface ships
 * without it). When a page is renamed, this test fails BEFORE deploy.
 *
 * If a new route is added to App.tsx, append a corresponding
 * `assertPage("Foo")` line below. The pre-build lint (Defense 1)
 * already prevents the App.tsx side from going stale.
 */

import { describe, expect, it } from "vitest";

const PAGE_EXPORTS: Record<string, string> = {
  // Marketing surface
  Landing: "@/pages/Landing",
  Cockpit: "@/pages/Cockpit",
  Planner: "@/pages/Planner",
  Traces: "@/pages/Traces",
  Policy: "@/pages/Policy",
  Council: "@/pages/Council",
  Awareness: "@/pages/Awareness",
  Install: "@/pages/Install",
  Onboarding: "@/pages/Onboarding",
  Privacy: "@/pages/Privacy",
  Terms: "@/pages/Terms",
  Security: "@/pages/Security",
  Pitch: "@/pages/Pitch",
  Press: "@/pages/Press",
  Docs: "@/pages/Docs",
  Status: "@/pages/Status",
  NotFound: "@/pages/NotFound",
  Roadmap: "@/pages/Roadmap",
  Changelog: "@/pages/Changelog",
  BuildWith: "@/pages/BuildWith",
  PricingPage: "@/pages/PricingPage",
  FAQPage: "@/pages/FAQPage",
  ComparePage: "@/pages/ComparePage",
  Settings: "@/pages/Settings",
  // Workshop family
  Workshop: "@/pages/Workshop",
  Compliance: "@/pages/Compliance",
  EnterpriseWorkshop: "@/pages/EnterpriseWorkshop",
  WorkshopROI: "@/pages/WorkshopROI",
  WorkshopMaterials: "@/pages/WorkshopMaterials",
  WorkshopAssess: "@/pages/WorkshopAssess",
  WorkshopCohort: "@/pages/WorkshopCohort",
  // Operator surfaces
  Dashboard: "@/pages/Dashboard",
  Schedules: "@/pages/Schedules",
  Outreach: "@/pages/Outreach",
  OrgOnboarding: "@/pages/OrgOnboarding",
  Inbox: "@/pages/Inbox",
  Files: "@/pages/Files",
  Reports: "@/pages/Reports",
  Marketplace: "@/pages/Marketplace",
  Bundles: "@/pages/Bundles",
  PerfDashboard: "@/pages/PerfDashboard",
  // Workspaces
  Workspaces: "@/pages/Workspaces",
  WorkspaceInviteAccept: "@/pages/Workspaces",
};

describe("Wave 116 — every App.tsx route resolves to a callable component", () => {
  for (const [exportName, modulePath] of Object.entries(PAGE_EXPORTS)) {
    it(`${exportName} (${modulePath}) — named export is a callable component`, async () => {
      const mod = await import(/* @vite-ignore */ modulePath);
      const exported = (mod as Record<string, unknown>)[exportName];
      // Identical contract to App.tsx's lazy:
      //   `(m) => ({ default: m.<exportName> })`
      // — the named export MUST exist and MUST be a function/component.
      expect(
        exported,
        `expected ${exportName} to be exported from ${modulePath}; got ${String(
          exported,
        )}. App.tsx will fail with "m.${exportName} is undefined" at runtime.`,
      ).toBeDefined();
      expect(
        typeof exported,
        `${exportName} from ${modulePath} must be a function (React component or forwardRef); got ${typeof exported}.`,
      ).toBe("function");
    });
  }

  // Ensure the App shell itself imports cleanly — catches any
  // top-level eager-import regression (a missing named import in
  // App.tsx would explode the whole bundle, not just a single route).
  it("App default export imports cleanly", async () => {
    const App = await import("@/App");
    expect(App.default).toBeTypeOf("function");
  });
});
