/**
 * Recovery seed client (Phase L5 G1 / K3).
 *
 * Wraps `POST/GET /api/recovery/*`. The host owns the BIP-39 logic; the
 * cockpit's job is to render the seed, gate the operator on a "I have
 * written this down" affordance, and POST the typed-back phrase to
 * `/verify` so we can confirm the fingerprint matches.
 *
 * **NEVER** persist the mnemonic anywhere — clipboard, localStorage,
 * a screenshot. The audit event the host emits only carries the
 * 12-char fingerprint.
 */

import { API_BASE } from "./api";

export const WORD_COUNT = 24;

export interface GenerateResponse {
  ok: true;
  trace_id: string;
  mnemonic: string;
  fingerprint: string;
  word_count: number;
}

export interface VerifyResponse {
  ok: true;
  trace_id: string;
  fingerprint: string;
}

export interface WordlistInfo {
  ok: true;
  language: string;
  size: number;
  first: string;
  last: string;
  word_count: number;
}

export class RecoveryError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "RecoveryError";
    this.status = status;
  }
}

const RECOVERY_BASE = `${API_BASE}/api/recovery`;

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${RECOVERY_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      }
    } catch {
      /* ignore */
    }
    throw new RecoveryError(detail, res.status);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------
// HTTP wrappers
// ---------------------------------------------------------------------

export function generateSeed(): Promise<GenerateResponse> {
  return request<GenerateResponse>("/generate", { method: "POST" });
}

export function verifySeed(input: {
  mnemonic: string;
  passphrase?: string;
}): Promise<VerifyResponse> {
  return request<VerifyResponse>("/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mnemonic: input.mnemonic,
      passphrase: input.passphrase ?? null,
    }),
  });
}

export function getWordlistInfo(): Promise<WordlistInfo> {
  return request<WordlistInfo>("/wordlist/info", { method: "GET" });
}

// ---------------------------------------------------------------------
// UX helpers
// ---------------------------------------------------------------------

/**
 * Normalise the operator's typed-back mnemonic — collapse whitespace,
 * lower-case every word, drop trailing punctuation. The host normalises
 * server-side too, but we do it client-side so the verify-grid UI can
 * highlight obvious typos before hitting the network.
 */
export function normaliseMnemonic(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z\s-]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/** Split a 24-word mnemonic into a 4×6 grid for display. */
export function chunkMnemonic(
  mnemonic: string,
  rows: number = 4,
  cols: number = 6,
): string[][] {
  const words = normaliseMnemonic(mnemonic).split(" ");
  const expected = rows * cols;
  if (words.length !== expected) {
    throw new Error(
      `mnemonic has ${words.length} words; expected ${expected} for a ${rows}×${cols} grid`,
    );
  }
  const out: string[][] = [];
  for (let r = 0; r < rows; r++) {
    out.push(words.slice(r * cols, r * cols + cols));
  }
  return out;
}

/**
 * Compare two mnemonics for equality after normalisation. Used by the
 * "type it back" verify flow to short-circuit obvious mismatches before
 * we round-trip to the server.
 */
export function mnemonicsMatch(a: string, b: string): boolean {
  const na = normaliseMnemonic(a);
  const nb = normaliseMnemonic(b);
  return na !== "" && na === nb;
}

/**
 * "Did the operator actually write this down?" gate: returns `true` when
 * the typed-back string has at least one word per cell of the grid and
 * the canonical word count is met. Cheap UX check — strict validation
 * is the host's `/verify` job.
 */
export function isCompleteAttempt(input: string): boolean {
  return normaliseMnemonic(input).split(" ").length === WORD_COUNT;
}
