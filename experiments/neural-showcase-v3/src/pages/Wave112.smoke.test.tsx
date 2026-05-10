/**
 * Wave 112 — discoverability sweep smoke tests.
 *
 * One smoke pin per page added in Waves 80-110. The v3 surface ships
 * without @testing-library/react; we exercise the page module at the
 * export-contract level (matches EnterpriseWorkshop.test.tsx).
 *
 * Each test catches accidental rename / removal of the named export
 * during refactors — App.tsx wires every page via
 * `lazy(() => import('@/pages/Foo').then((m) => ({ default: m.Foo })))`,
 * so a renamed export silently 500s the route at runtime; this test
 * trips first.
 */

import { describe, expect, it } from "vitest";

import { Workshop } from "@/pages/Workshop";
import { Compliance } from "@/pages/Compliance";
import { Dashboard } from "@/pages/Dashboard";
import { OrgOnboarding } from "@/pages/OrgOnboarding";
import { Inbox } from "@/pages/Inbox";
import { Files } from "@/pages/Files";
import { Reports } from "@/pages/Reports";
import { Marketplace } from "@/pages/Marketplace";
import { Workspaces } from "@/pages/Workspaces";
import { Bundles } from "@/pages/Bundles";
import { Schedules } from "@/pages/Schedules";
import { Outreach } from "@/pages/Outreach";
import { PerfDashboard } from "@/pages/PerfDashboard";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { HelpButton } from "@/components/HelpButton";

describe("Wave 112 — page export pins", () => {
  it("Workshop is a callable component", () => {
    expect(Workshop).toBeTypeOf("function");
    expect(Workshop.name).toBe("Workshop");
  });

  it("Compliance is a callable component", () => {
    expect(Compliance).toBeTypeOf("function");
    expect(Compliance.name).toBe("Compliance");
  });

  it("Dashboard is a callable component", () => {
    expect(Dashboard).toBeTypeOf("function");
    expect(Dashboard.name).toBe("Dashboard");
  });

  it("OrgOnboarding is a callable component", () => {
    expect(OrgOnboarding).toBeTypeOf("function");
    expect(OrgOnboarding.name).toBe("OrgOnboarding");
  });

  it("Inbox is a callable component", () => {
    expect(Inbox).toBeTypeOf("function");
    expect(Inbox.name).toBe("Inbox");
  });

  it("Files is a callable component", () => {
    expect(Files).toBeTypeOf("function");
    expect(Files.name).toBe("Files");
  });

  it("Reports is a callable component", () => {
    expect(Reports).toBeTypeOf("function");
    expect(Reports.name).toBe("Reports");
  });

  it("Marketplace is a callable component", () => {
    expect(Marketplace).toBeTypeOf("function");
    expect(Marketplace.name).toBe("Marketplace");
  });

  it("Workspaces is a callable component", () => {
    expect(Workspaces).toBeTypeOf("function");
    expect(Workspaces.name).toBe("Workspaces");
  });

  it("Bundles is a callable component", () => {
    expect(Bundles).toBeTypeOf("function");
    expect(Bundles.name).toBe("Bundles");
  });

  it("Schedules is a callable component", () => {
    expect(Schedules).toBeTypeOf("function");
    expect(Schedules.name).toBe("Schedules");
  });

  it("Outreach is a callable component", () => {
    expect(Outreach).toBeTypeOf("function");
    expect(Outreach.name).toBe("Outreach");
  });

  it("PerfDashboard is a callable component", () => {
    expect(PerfDashboard).toBeTypeOf("function");
    expect(PerfDashboard.name).toBe("PerfDashboard");
  });

  it("Breadcrumbs and HelpButton primitives are exported", () => {
    expect(Breadcrumbs).toBeTypeOf("function");
    expect(HelpButton).toBeTypeOf("function");
  });
});
