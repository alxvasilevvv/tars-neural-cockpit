/**
 * i18n contract tests — Wave 72.
 *
 * The marketing surface is English-only after Wave 70 forced the
 * runtime locale and Wave 72 deleted the dead Russian dictionary.
 * The runtime indirection (``useT()`` / ``t()`` / ``useLocale()``)
 * is kept so a future locale can be re-added by extending
 * ``STRINGS_BY_LOCALE`` — the surrounding plumbing needs no change.
 *
 * Pins:
 * - The supported locales list contains exactly EN.
 * - ``t()`` returns the English string for a known key.
 * - Variable interpolation works.
 * - EN values are non-empty and have well-formed `{slot}` placeholders.
 */

import { describe, expect, it, beforeEach } from "vitest";
import {
  SUPPORTED_LOCALES,
  __testTables,
  _setLocaleForTests,
  t,
} from "./i18n";

beforeEach(() => {
  _setLocaleForTests("en");
});

describe("i18n.SUPPORTED_LOCALES", () => {
  it("is EN-only after Wave 72", () => {
    expect([...SUPPORTED_LOCALES]).toEqual(["en"]);
  });
});

describe("i18n.t() — English (only locale)", () => {
  it("returns the English string for a known key", () => {
    expect(t("hero.cta.cockpit")).toBe("Open cockpit");
  });

  it("interpolates variables", () => {
    expect(t("waitlist.position", { n: 1247 })).toContain("1247");
  });

  it("EN values are non-empty strings", () => {
    for (const [key, value] of Object.entries(__testTables.en)) {
      expect(value, `EN key ${key}`).toBeTypeOf("string");
      expect(value.trim().length, `EN key ${key} must not be blank`).toBeGreaterThan(0);
    }
  });

  it("preserves all interpolation slots in EN values", () => {
    const slot = /\{(\w+)\}/g;
    for (const [key, en] of Object.entries(__testTables.en)) {
      const slots = en.match(slot) || [];
      for (const s of slots) {
        expect(s, `key ${key} slot ${s}`).toMatch(/^\{\w+\}$/);
      }
    }
  });
});

describe("i18n.t() — locale label", () => {
  it("EN label", () => {
    _setLocaleForTests("en");
    expect(t("locale.label")).toBe("Language");
  });
});
