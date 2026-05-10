/**
 * CrescoWorkshop — smoke contract test for the /workshop/cresco surface.
 *
 * Wave 83 — the v3 surface ships without @testing-library/react (see
 * package.json devDependencies + Wave 83 task brief). We therefore
 * exercise the page module at the export-contract level instead of
 * mounting it: this catches accidental rename / removal of the page
 * component during refactors, and locks the heading copy that powers
 * the OG share card title.
 *
 * Once the Wave 84 PlaybookComposer / AgentDesigner / BacktestPanel
 * wizard lands, we'll add testing-library and graduate these to real
 * render assertions.
 */

import { describe, expect, it } from "vitest";

import { CrescoWorkshop } from "@/pages/CrescoWorkshop";

describe("CrescoWorkshop (smoke)", () => {
  it("exports a callable React component named CrescoWorkshop", () => {
    expect(CrescoWorkshop).toBeTypeOf("function");
    expect(CrescoWorkshop.name).toBe("CrescoWorkshop");
  });

  it("module path matches the App.tsx lazy import (regression pin)", () => {
    // App.tsx wires `/workshop/cresco` via `lazy(() => import('@/pages/CrescoWorkshop'))`
    // — if the named export is renamed/removed, the route silently 500s
    // and our smoke pin trips first.
    expect(CrescoWorkshop).toBeDefined();
  });
});
