import { describe, expect, it } from "vitest";

import { statusBadgeClass } from "./agents";

describe("statusBadgeClass", () => {
  it("emerald for healthy states", () => {
    expect(statusBadgeClass("active")).toContain("emerald");
    expect(statusBadgeClass("done")).toContain("emerald");
    expect(statusBadgeClass("running")).toContain("emerald");
  });
  it("amber for waiting states", () => {
    expect(statusBadgeClass("paused")).toContain("amber");
    expect(statusBadgeClass("pending")).toContain("amber");
    expect(statusBadgeClass("awaiting_confirmation")).toContain("amber");
  });
  it("rose for failed", () => {
    expect(statusBadgeClass("failed")).toContain("rose");
  });
  it("zinc for terminal/quiet states", () => {
    expect(statusBadgeClass("archived")).toContain("zinc");
    expect(statusBadgeClass("cancelled")).toContain("zinc");
  });
});
