import { describe, expect, it } from "vitest";

import {
  macOSKeychainAddCommand,
  VAULT_KEYCHAIN_ACCOUNT,
} from "./vault";

describe("macOSKeychainAddCommand", () => {
  it("matches the host keychain reader (account + service name = key)", () => {
    expect(macOSKeychainAddCommand("TARS_ANTHROPIC_API_KEY")).toBe(
      "security add-generic-password -a tars -s TARS_ANTHROPIC_API_KEY -w",
    );
  });

  it("allows a custom account label", () => {
    expect(macOSKeychainAddCommand("FOO", "other")).toBe(
      "security add-generic-password -a other -s FOO -w",
    );
    expect(VAULT_KEYCHAIN_ACCOUNT).toBe("tars");
  });

  it("trims the key name", () => {
    expect(macOSKeychainAddCommand("  X  ")).toBe(
      "security add-generic-password -a tars -s X -w",
    );
  });
});
