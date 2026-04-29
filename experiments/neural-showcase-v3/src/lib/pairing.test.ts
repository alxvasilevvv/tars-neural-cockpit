/**
 * Vitest — pairing client (Phase L5 K3).
 *
 * We exercise:
 *   - Pure helpers (formatFingerprint, fingerprintsMatch).
 *   - QR encode / decode round-trip.
 *   - HTTP wrappers via a stubbed `fetch`.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  PairingError,
  acceptPairing,
  beginPairing,
  decodeQrPayload,
  encodeQrPayload,
  fingerprintsMatch,
  formatFingerprint,
  getIdentity,
  pollPairingStatus,
} from "./pairing";

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------

describe("formatFingerprint", () => {
  it("forces upper-case and 4-char groups", () => {
    expect(formatFingerprint("d3ba6d8ad882")).toBe("D3BA-6D8A-D882");
  });
  it("drops separators before regrouping", () => {
    expect(formatFingerprint("D3-BA6D-8A.D882")).toBe("D3BA-6D8A-D882");
  });
  it("returns empty on empty input", () => {
    expect(formatFingerprint("")).toBe("");
  });
});

describe("fingerprintsMatch", () => {
  it("matches case- and dash-insensitively", () => {
    expect(fingerprintsMatch("d3ba6d8ad882", "D3BA-6D8A-D882")).toBe(true);
  });
  it("rejects mismatches", () => {
    expect(fingerprintsMatch("D3BA-6D8A-D882", "ABCD-1234-5678")).toBe(false);
  });
  it("treats two empty values as non-match (defence in depth)", () => {
    expect(fingerprintsMatch("", "")).toBe(false);
  });
});

// ---------------------------------------------------------------------
// QR payload
// ---------------------------------------------------------------------

describe("encodeQrPayload + decodeQrPayload", () => {
  const begin = {
    ok: true as const,
    trace_id: "trc_x",
    pair_id: "5e40c57470f534bc",
    accept_token: "9f20ef353462ea44f896c2af7ecb9169",
    host_id: "9ebd45c6de53f838",
    host_fingerprint: "D3BA-6D8A-D882",
    host_public_key: "4iIXBeR6gsAbVLjgFm78boubCXI0dPQRlbaiojEO8hQ=",
    expires_at: 1777414621.785266,
  };

  it("round-trips the four pinning fields", () => {
    const encoded = encodeQrPayload(begin);
    const decoded = decodeQrPayload(encoded);
    expect(decoded).toEqual({
      pair_id: begin.pair_id,
      accept_token: begin.accept_token,
      host_id: begin.host_id,
      host_public_key: begin.host_public_key,
      expires_at: begin.expires_at,
    });
  });

  it("uses base64url (no '+', '/', or '=')", () => {
    const encoded = encodeQrPayload(begin);
    expect(encoded).not.toMatch(/[+/=]/);
  });

  it("rejects garbage payloads", () => {
    expect(() => decodeQrPayload("not-a-valid-base64")).toThrow();
    expect(() => decodeQrPayload(btoa("[]"))).toThrow(/unsupported version/);
  });
});

// ---------------------------------------------------------------------
// HTTP wrappers
// ---------------------------------------------------------------------

function mockFetch(
  status: number,
  body: unknown,
): vi.Mock {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: `HTTP ${status}`,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("beginPairing", () => {
  it("POSTs JSON and returns the typed body", async () => {
    const stub = mockFetch(200, {
      ok: true,
      trace_id: "trc",
      pair_id: "p",
      accept_token: "t",
      host_id: "h",
      host_fingerprint: "AA-BB-CC",
      host_public_key: "k",
      expires_at: 0,
    });
    const out = await beginPairing({
      client_epk: "ABCD",
      kind: "mobile_ios",
    });
    expect(out.pair_id).toBe("p");
    const [url, init] = stub.mock.calls[0];
    expect(String(url)).toContain("/api/pairing/begin");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      client_epk: "ABCD",
      kind: "mobile_ios",
    });
  });

  it("throws PairingError with detail message on 400", async () => {
    mockFetch(400, { detail: "invalid_client_epk: bad shape" });
    await expect(
      beginPairing({ client_epk: "x", kind: "mobile_ios" }),
    ).rejects.toBeInstanceOf(PairingError);
  });
});

describe("acceptPairing", () => {
  it("posts to /accept/<token>", async () => {
    const stub = mockFetch(200, {
      ok: true,
      trace_id: "trc",
      pair_id: "p",
      device_id: "dev_x",
    });
    const res = await acceptPairing("token-with/special chars");
    expect(res.device_id).toBe("dev_x");
    const [url] = stub.mock.calls[0];
    expect(String(url)).toContain(
      "/api/pairing/accept/token-with%2Fspecial%20chars",
    );
  });
});

describe("pollPairingStatus", () => {
  it("encodes pair_id in the query string", async () => {
    const stub = mockFetch(200, {
      ok: true,
      pair_id: "abc",
      state: "pending",
      client_kind: "mobile_ios",
      host_fingerprint: "A-B-C",
      expires_at: 0,
      device_id: null,
      rejected_reason: null,
      linked_at: null,
    });
    await pollPairingStatus("ab cd");
    const [url] = stub.mock.calls[0];
    expect(String(url)).toContain("pair_id=ab%20cd");
  });
});

describe("getIdentity", () => {
  it("returns the host identity status", async () => {
    mockFetch(200, {
      ok: true,
      host_id: "h",
      host_public_key: "pk",
      host_fingerprint: "A-B-C",
      vault: { configured: true, loaded_from_disk: false, freshly_minted: true },
      recovery_fingerprint: null,
    });
    const out = await getIdentity();
    expect(out.vault.freshly_minted).toBe(true);
    expect(out.recovery_fingerprint).toBeNull();
  });
});
