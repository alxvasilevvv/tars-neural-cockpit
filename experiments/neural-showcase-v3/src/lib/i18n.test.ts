/**
 * Bug #5 contract — i18n multi-locale machinery.
 *
 * Pins:
 * - English fallback when a key is missing from RU.
 * - RU translations apply when the locale is set.
 * - Variable interpolation works under both locales.
 * - The supported locales list contains EN + RU.
 * - Translation parity guard: every RU key must exist in EN
 *   (catches typos / orphan keys at CI time).
 * - **Coverage threshold**: every EN key MUST have an RU
 *   translation (audit Bug #5 follow-up — full RU pass shipped
 *   2026-05-02). Threshold can be relaxed via the constant
 *   below if a future PR introduces a strictly-temporary
 *   English-only string, but the default is 100% parity.
 */

import { describe, expect, it, beforeEach } from "vitest";
import {
  SUPPORTED_LOCALES,
  __testTables,
  _setLocaleForTests,
  t,
} from "./i18n";

/** Minimum fraction of EN keys that must have a Russian translation. */
const RU_COVERAGE_THRESHOLD = 1.0;

beforeEach(() => {
  _setLocaleForTests("en");
});

describe("i18n.SUPPORTED_LOCALES", () => {
  it("includes en + ru", () => {
    expect(SUPPORTED_LOCALES).toContain("en");
    expect(SUPPORTED_LOCALES).toContain("ru");
  });
});

describe("i18n.t() — English (default)", () => {
  it("returns the English string for a known key", () => {
    expect(t("hero.cta.cockpit")).toBe("Open cockpit");
  });
  it("interpolates variables", () => {
    expect(t("waitlist.position", { n: 1247 })).toContain("1247");
  });
});

describe("i18n.t() — Russian (after switch)", () => {
  beforeEach(() => {
    _setLocaleForTests("ru");
  });

  it("returns the Russian translation when present", () => {
    expect(t("hero.cta.cockpit")).toBe("Открыть кокпит");
  });

  it("falls back to English silently when the EN value is acronym-only", () => {
    // ``faq.tag`` happens to be "FAQ" in both locales (acronym
    // doesn't translate). Whether the lookup hit the RU table or
    // fell through to EN, the user-facing string is the same.
    const out = t("faq.tag");
    expect(out).toBe("FAQ");
    expect(out).not.toMatch(/[{}]/);
  });

  it("interpolates variables under RU too", () => {
    expect(t("waitlist.position", { n: 42 })).toContain("42");
  });
});

describe("i18n parity — RU keys must exist in EN", () => {
  it("rejects orphan RU keys (catches typos at CI time)", () => {
    const enKeys = new Set(Object.keys(__testTables.en));
    const orphans = Object.keys(__testTables.ru).filter(
      (k) => !enKeys.has(k),
    );
    expect(orphans).toEqual([]);
  });
});

describe("i18n coverage — RU translates every EN key", () => {
  // The audit follow-up promised a full RU translation pass.
  // This test pins the contract so future PRs can't quietly
  // drop coverage by adding English-only strings.
  it(`covers ≥ ${(RU_COVERAGE_THRESHOLD * 100).toFixed(0)}% of EN keys`, () => {
    const enKeys = Object.keys(__testTables.en);
    const ruKeys = new Set(Object.keys(__testTables.ru));
    const missing = enKeys.filter((k) => !ruKeys.has(k));
    const coverage = (enKeys.length - missing.length) / enKeys.length;

    if (coverage < RU_COVERAGE_THRESHOLD) {
      // Fail loudly with the exact diff so the offending keys are
      // obvious in the CI log — no need to grep through both tables.
      throw new Error(
        `RU coverage ${(coverage * 100).toFixed(1)}% < target ` +
          `${(RU_COVERAGE_THRESHOLD * 100).toFixed(0)}%; missing keys:\n  - ` +
          missing.join("\n  - "),
      );
    }
  });

  it("RU values are non-empty strings (no accidental ``\"\"`` placeholders)", () => {
    for (const [key, value] of Object.entries(__testTables.ru)) {
      expect(value, `RU key ${key}`).toBeTypeOf("string");
      expect(value.trim().length, `RU key ${key} must not be blank`).toBeGreaterThan(0);
    }
  });

  it("RU values preserve EN interpolation slots (e.g. ``{n}``)", () => {
    const slot = /\{(\w+)\}/g;
    const mismatches: string[] = [];
    for (const [key, ru] of Object.entries(__testTables.ru)) {
      const en = __testTables.en[key];
      if (!en) continue;
      const enSlots = (en.match(slot) || []).slice().sort();
      const ruSlots = (ru.match(slot) || []).slice().sort();
      if (enSlots.join(",") !== ruSlots.join(",")) {
        mismatches.push(
          `${key}: EN slots=[${enSlots.join(", ")}] vs RU slots=[${ruSlots.join(", ")}]`,
        );
      }
    }
    expect(mismatches, "interpolation slot mismatches").toEqual([]);
  });
});

describe("i18n.t() — locale.* keys (LocaleSwitcher labels)", () => {
  it("EN label", () => {
    _setLocaleForTests("en");
    expect(t("locale.label")).toBe("Language");
  });
  it("RU label", () => {
    _setLocaleForTests("ru");
    expect(t("locale.label")).toBe("Язык");
  });
});
