/*
 * runtime/api.ts — typed fetch wrapper + vault status hook (W309 step 1).
 *
 * One narrow surface for every REST call the cockpit makes to the
 * TARS sidecar (FastAPI under `web_extras/app.py`, default bind
 * `http://127.0.0.1:8765` per `serve.py`). All endpoints return
 * `{ok: boolean, ...}` envelopes by convention (see
 * `web_extras/routers/*.py`); `api()` surfaces `ok === false` as an
 * `ApiError` instead of resolving the promise.
 *
 * Knobs (in priority order):
 *   - `window.localStorage.TARS_API_URL` (operator override, debugging)
 *   - `DEFAULT_API_BASE` (http://127.0.0.1:8765, matches sidecar bind)
 *
 * CSP `connect-src` is already opened to `http://127.0.0.1:8765` and
 * `ws://127.0.0.1:8765` in `desktop/src-tauri/tauri.conf.json`, so
 * the Tauri shell can talk to the sidecar without extra plumbing.
 * `vite dev` (port 5174) calling 8765 will hit CORS unless the
 * operator exports `TARS_CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174`
 * before booting the daemon; production Tauri does not need this.
 *
 * Note on the brief's `runtime/api.ts` consumer (§3.5 — vault status
 * hook): co-located with the wrapper as `vaultStatus()` rather than
 * a separate file. Keeps the module count at the brief's 5.
 */

export const DEFAULT_API_BASE = "http://127.0.0.1:8765";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
    public readonly endpoint: string,
  ) {
    super(`[api] ${endpoint} → ${status}: ${JSON.stringify(detail)}`);
  }
}

export function getApiBase(): string {
  try {
    const override = window.localStorage.getItem("TARS_API_URL");
    if (override && override.trim()) {
      return override.trim().replace(/\/+$/, "");
    }
  } catch {
    /* localStorage may throw in private-browsing mode — fall back. */
  }
  return DEFAULT_API_BASE;
}

export interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function api<T = unknown>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const url = `${getApiBase()}${path.startsWith("/") ? "" : "/"}${path}`;
  const init: RequestInit = {
    method: opts.method ?? "GET",
    headers: {
      "content-type": "application/json",
      ...(opts.headers ?? {}),
    },
    signal: opts.signal,
  };
  if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err) {
    // Network failure (sidecar down, DNS, etc.) — surface as a
    // typed error so callers can branch on `err.status === 0`.
    throw new ApiError(0, { network: String(err) }, path);
  }

  const ct = res.headers.get("content-type") ?? "";
  const isJson = ct.includes("application/json");

  if (!res.ok) {
    const detail = isJson
      ? await res.json().catch(() => null)
      : await res.text();
    throw new ApiError(res.status, detail, path);
  }

  if (!isJson) {
    // Caller asked for a non-JSON endpoint via `api()` — return the
    // blob. Most binary callers should use `apiBinary()` directly.
    return (await res.blob()) as unknown as T;
  }

  const data = await res.json();
  if (
    data &&
    typeof data === "object" &&
    "ok" in data &&
    (data as { ok: unknown }).ok === false
  ) {
    throw new ApiError(res.status, data, path);
  }
  return data as T;
}

/**
 * Variant for endpoints that return raw bytes (e.g. `/api/voice/speak`
 * returns audio). Skips the `ok` envelope check; the caller receives
 * the raw `Response` and decides how to consume (blob, headers, etc.).
 */
export async function apiBinary(
  path: string,
  body: unknown,
  extraHeaders: Record<string, string> = {},
): Promise<Response> {
  const url = `${getApiBase()}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...extraHeaders },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail, path);
  }
  return res;
}

// ---------------------------------------------------------------------
// Vault status hook (brief §3.5 — `runtime/api.ts` consumer).
// ---------------------------------------------------------------------

export interface VaultKey {
  key: string;
  /** "env" | "keychain" | "missing" — see `backend/core/vault.py`. */
  source: string;
  available: boolean;
}

export interface VaultStatus {
  keys: VaultKey[];
}

export async function vaultStatus(): Promise<VaultStatus> {
  const res = await api<{ ok: boolean; keys: VaultKey[] }>("/api/vault/status");
  return { keys: res.keys ?? [] };
}

/**
 * Convenience: is the ElevenLabs key present in the vault? Used to
 * gate the "Add ElevenLabs key" CTA on cockpit mount.
 */
export function hasElevenLabsKey(status: VaultStatus): boolean {
  return status.keys.some(
    (k) => k.key === "elevenlabs" && k.available === true,
  );
}
