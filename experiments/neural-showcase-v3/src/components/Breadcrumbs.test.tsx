/**
 * Breadcrumbs — structural smoke tests.
 *
 * The full DOM render is exercised live in /workshop/enterprise; here we
 * lock the public surface (export shape + interface contract) so any
 * accidental rename or signature drift from a future a11y refactor
 * trips CI before it reaches the cockpit.
 *
 * Smoke-test mode (no @testing-library/react in the v3 surface — see
 * package.json devDependencies). When the upcoming Wave 84 wizard
 * introduces real interactive components, we'll add the testing-library
 * dep and graduate this file to a render() test.
 */

import { describe, expect, it } from "vitest";

import { Breadcrumbs, type BreadcrumbItem } from "@/components/Breadcrumbs";

describe("Breadcrumbs (smoke)", () => {
  it("exports a callable React component", () => {
    expect(Breadcrumbs).toBeTypeOf("function");
  });

  it("returns null for an empty items array (no nav rendered)", () => {
    // React 18 components can be invoked directly during smoke tests
    // because Breadcrumbs has no hooks.
    const result = Breadcrumbs({ items: [] });
    expect(result).toBeNull();
  });

  it("renders something for a non-empty items array", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", to: "/" },
      { label: "Workshop", to: "/workshop" },
      { label: "Enterprise" },
    ];
    const result = Breadcrumbs({ items });
    expect(result).not.toBeNull();
  });

  it("BreadcrumbItem leaf can omit `to`", () => {
    // Compile-time pin: leaf items render as plain text, so `to` is
    // optional. Runtime check is structural.
    const leaf: BreadcrumbItem = { label: "Current page" };
    expect(leaf.to).toBeUndefined();
    expect(leaf.label).toBe("Current page");
  });
});
