/**
 * Pairing client (Phase L5 K3).
 *
 * Wraps `POST/GET /api/pairing/*` so the cockpit React components only
 * deal with strongly-typed shapes. The wire contract is pinned by
 * `docs/contracts/L5_PAIRING_DRAFT.md` and `tests/test_pairing_contract.py`
 * — every field below mirrors what the host emits.
 *
 * Visual / animation polish lives in the React components Claude owns;
 * this file is intentionally framework-free so vitest can exercise it
 * without a DOM.
 */

import { API_BASE } from "./api";

export type DeviceKind =
  | "desktop_macos"
  | "desktop_windows"
  | "mobile_ios"
  | "mobile_android";

export type PairingState =
  | "pending"
  | "accepted"
  | "rejected"
  | "expired"
  | "linked";

export interface BeginResponse {
  ok: true;
  trace_id: string;
  pair_id: string;
  accept_token: string;
  host_id: string;
  host_fingerprint: string;
  /** base64 X25519 long-term host pubkey. */
  host_public_key: string;
  expires_at: number;
}

export interface PairingStatus {
  ok: true;
  pair_id: string;
  state: PairingState;
  client_kind: DeviceKind;
  host_fingerprint: string;
  expires_at: number;
  device_id: string | null;
  rejected_reason: string | null;
  linked_at: number | null;
}

export interface PairedDevice {
  device_id: string;
  kind: DeviceKind;
  linked_at: number;
  last_seen_at: number;
  pair_id: string;
  /** base64 X25519 device pubkey (host knows the public half only). */
  public_key: string;
}

export interface IdentityStatus {
  ok: true;
  host_id: string;
  host_public_key: string;
  host_fingerprint: string;
  vault: {
    configured: boolean;
    loaded_from_disk: boolean;
    freshly_minted: boolean;
  };
  recovery_fingerprint: string | null;
}

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

const PAIRING_BASE = `${API_BASE}/api/pairing`;

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${PAIRING_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await safeError(res);
    throw new PairingError(detail, res.status);
  }
  return (await res.json()) as T;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${PAIRING_BASE}${path}`);
  if (!res.ok) {
    const detail = await safeError(res);
    throw new PairingError(detail, res.status);
  }
  return (await res.json()) as T;
}

async function safeError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      return String((body as { detail: unknown }).detail);
    }
  } catch {
    // fall through
  }
  return res.statusText || `HTTP ${res.status}`;
}

export class PairingError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "PairingError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------
// Fingerprint formatting
// ---------------------------------------------------------------------

/**
 * Render a host fingerprint for the operator. The host emits "AAAA-BBBB-CCCC"
 * already; this helper just re-asserts the format and provides a
 * consistent grouping for screen readers.
 */
export function formatFingerprint(value: string): string {
  const cleaned = value.toUpperCase().replace(/[^0-9A-Z]/g, "");
  if (cleaned.length === 0) return "";
  return cleaned.match(/.{1,4}/g)!.join("-");
}

/**
 * Side-by-side fingerprint comparison. Returns `true` when the two
 * fingerprints look identical to the operator (after normalisation).
 * The mobile device renders one and the host renders the other;
 * pairing only proceeds when this is true.
 */
export function fingerprintsMatch(a: string, b: string): boolean {
  return formatFingerprint(a) === formatFingerprint(b) && formatFingerprint(a) !== "";
}

// ---------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------

export async function beginPairing(input: {
  client_epk: string;
  kind: DeviceKind;
  pair_id?: string;
}): Promise<BeginResponse> {
  return postJson<BeginResponse>("/begin", input);
}

export async function acceptPairing(token: string): Promise<{
  ok: true;
  trace_id: string;
  pair_id: string;
  device_id: string;
}> {
  return postJson(`/accept/${encodeURIComponent(token)}`, {});
}

export async function rejectPairing(
  token: string,
  reason?: string,
): Promise<{ ok: true; pair_id: string }> {
  return postJson(`/reject/${encodeURIComponent(token)}`, { reason });
}

export async function pollPairingStatus(pair_id: string): Promise<PairingStatus> {
  return getJson<PairingStatus>(`/status?pair_id=${encodeURIComponent(pair_id)}`);
}

export async function listDevices(): Promise<{
  ok: true;
  count: number;
  devices: PairedDevice[];
}> {
  return getJson("/devices");
}

export async function revokeDevice(device_id: string): Promise<{
  ok: true;
  trace_id: string;
  device_id: string;
}> {
  return postJson("/revoke", { device_id });
}

export async function getIdentity(): Promise<IdentityStatus> {
  return getJson<IdentityStatus>("/identity");
}

// ---------------------------------------------------------------------
// QR payload helpers
// ---------------------------------------------------------------------

/**
 * Encode a begin-response into the QR payload the mobile companion
 * scans. The format is intentionally compact — base64url-encoded JSON
 * with the four pinning fields the device needs:
 *   pair_id, accept_token, host_id, host_public_key.
 *
 * The fingerprint is verified out-of-band (eyes-on screens), not via QR.
 */
export function encodeQrPayload(begin: BeginResponse): string {
  const compact = {
    v: 1,
    p: begin.pair_id,
    t: begin.accept_token,
    h: begin.host_id,
    k: begin.host_public_key,
    e: begin.expires_at,
  };
  return base64UrlEncode(JSON.stringify(compact));
}

export interface QrPayload {
  pair_id: string;
  accept_token: string;
  host_id: string;
  host_public_key: string;
  expires_at: number;
}

export function decodeQrPayload(raw: string): QrPayload {
  let parsed: unknown;
  try {
    parsed = JSON.parse(base64UrlDecode(raw));
  } catch (err) {
    throw new Error(`invalid QR payload: ${(err as Error).message}`);
  }
  if (
    !parsed ||
    typeof parsed !== "object" ||
    (parsed as { v?: unknown }).v !== 1
  ) {
    throw new Error("invalid QR payload: unsupported version");
  }
  const obj = parsed as Record<string, unknown>;
  for (const key of ["p", "t", "h", "k", "e"] as const) {
    if (typeof obj[key] === "undefined") {
      throw new Error(`invalid QR payload: missing ${key}`);
    }
  }
  return {
    pair_id: String(obj.p),
    accept_token: String(obj.t),
    host_id: String(obj.h),
    host_public_key: String(obj.k),
    expires_at: Number(obj.e),
  };
}

// ---------------------------------------------------------------------
// base64url helpers
// ---------------------------------------------------------------------

function base64UrlEncode(input: string): string {
  // Browser-safe: btoa expects latin-1; encodeURIComponent + unescape
  // gets us a UTF-8-safe path without a Buffer dependency.
  const utf8 = encodeURIComponent(input).replace(/%([0-9A-F]{2})/g, (_, p1) =>
    String.fromCharCode(parseInt(p1, 16)),
  );
  return btoa(utf8).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const padding = padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4));
  const decoded = atob(padded + padding);
  return decodeURIComponent(
    Array.from(decoded)
      .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
      .join(""),
  );
}
