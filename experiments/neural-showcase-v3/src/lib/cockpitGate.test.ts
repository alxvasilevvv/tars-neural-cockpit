/**
 * Pin the runtime detection used by ``<CockpitGate />`` (Bug
 * audit 2026-05-04). The gate is on every /cockpit* route, so a
 * regression here either silently breaks the desktop cockpit
 * (false negative — opens the upgrade card inside the Tauri
 * shell) or silently breaks the upgrade flow (false positive —
 * tries to render the broken cockpit in the browser).
 */

import { describe, expect, it } from "vitest";
import {
  __PREVIEW_FLAG_KEY,
  isInsideTauri,
  readPreviewFlag,
  setPreviewFlag,
  type StorageLike,
  type WindowLike,
} from "./cockpitGate";

function makeMemoryStorage(initial: Record<string, string> = {}): StorageLike {
  const store: Record<string, string> = { ...initial };
  return {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => {
      store[k] = v;
    },
    removeItem: (k) => {
      delete store[k];
    },
  };
}

describe("isInsideTauri", () => {
  it("returns false when window is null/undefined", () => {
    expect(isInsideTauri()).toBe(false);
    expect(isInsideTauri(null)).toBe(false);
  });

  it("returns false on a plain browser window", () => {
    const win: WindowLike = {};
    expect(isInsideTauri(win)).toBe(false);
  });

  it("returns true when Tauri 2.x __TAURI_INTERNALS__ is present", () => {
    const win: WindowLike = { __TAURI_INTERNALS__: { invoke: () => {} } };
    expect(isInsideTauri(win)).toBe(true);
  });

  it("returns true when legacy Tauri 1.x __TAURI__ is present", () => {
    const win: WindowLike = { __TAURI__: {} };
    expect(isInsideTauri(win)).toBe(true);
  });

  it("returns true if either marker is set (forward + backward compat)", () => {
    const both: WindowLike = { __TAURI_INTERNALS__: {}, __TAURI__: {} };
    expect(isInsideTauri(both)).toBe(true);
  });

  it("ignores falsy marker values", () => {
    const win: WindowLike = {
      __TAURI_INTERNALS__: undefined,
      __TAURI__: null,
    };
    expect(isInsideTauri(win)).toBe(false);
  });
});

describe("readPreviewFlag / setPreviewFlag round-trip", () => {
  it("returns false when storage is null", () => {
    expect(readPreviewFlag(null)).toBe(false);
  });

  it("returns false when the key is missing", () => {
    expect(readPreviewFlag(makeMemoryStorage())).toBe(false);
  });

  it("returns true once setPreviewFlag(true) has been called", () => {
    const storage = makeMemoryStorage();
    setPreviewFlag(true, storage);
    expect(readPreviewFlag(storage)).toBe(true);
  });

  it("clears the flag with setPreviewFlag(false)", () => {
    const storage = makeMemoryStorage({ [__PREVIEW_FLAG_KEY]: "1" });
    expect(readPreviewFlag(storage)).toBe(true);
    setPreviewFlag(false, storage);
    expect(readPreviewFlag(storage)).toBe(false);
  });

  it("treats values other than the literal '1' as false", () => {
    expect(
      readPreviewFlag(makeMemoryStorage({ [__PREVIEW_FLAG_KEY]: "true" })),
    ).toBe(false);
    expect(
      readPreviewFlag(makeMemoryStorage({ [__PREVIEW_FLAG_KEY]: "" })),
    ).toBe(false);
  });

  it("tolerates a throwing storage (private mode)", () => {
    const throwing: StorageLike = {
      getItem: () => {
        throw new Error("private mode");
      },
      setItem: () => {
        throw new Error("private mode");
      },
      removeItem: () => {
        throw new Error("private mode");
      },
    };
    expect(readPreviewFlag(throwing)).toBe(false);
    // Should also not propagate when toggling.
    expect(() => setPreviewFlag(true, throwing)).not.toThrow();
    expect(() => setPreviewFlag(false, throwing)).not.toThrow();
  });

  it("pins the storage key so existing operators don't lose their flag", () => {
    expect(__PREVIEW_FLAG_KEY).toBe("tars.web.preview");
  });
});
