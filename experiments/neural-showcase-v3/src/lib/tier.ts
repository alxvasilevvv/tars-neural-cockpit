/**
 * Tier-gating client for the TARS cockpit.
 *
 * Pure consumer-side stub today: contract lives in
 * `docs/contracts/RECEIPT_LEDGER.md` (DRAFT v0.1). The producer side
 * (Lovable, `meeet.world` Edge Functions) is not live yet, so
 * `useTier()` returns the `free` tier and swallows fetch failures.
 * Once the producer endpoint goes live, flip `RESOLVE_TIER_URL`
 * below to point at it and the cockpit picks up the live tier
 * without further code changes.
 *
 * The `TIER_GATES` constant mirrors the matrix in
 * `docs/contracts/RECEIPT_LEDGER.md §1` so the cockpit can render
 * gated UI offline / in dev.
 */

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

// --------------------------------------------------------------------
// Types
// --------------------------------------------------------------------

export type TierSlug = "free" | "pro" | "business" | "lifetime";

export type TierSource = "receipt" | "default" | "promo";

export type TierFeature =
  // Modes / messages
  | "modes.chat_only"
  | "modes.all"
  | "messages.50_per_day"
  | "messages.500_per_day"
  | "messages.unlimited"
  // Pro tier
  | "background_tasks"
  | "morning_briefs"
  | "memory_reflection"
  // Business tier
  | "receipt_ledger"
  | "team_collaboration"
  | "share_links_utm"
  | "api_access"
  // Lifetime tier
  | "custom_persona_presets"
  | "early_access_features"
  | "priority_support";

/**
 * Frozen feature matrix per `docs/contracts/RECEIPT_LEDGER.md §1`.
 * Lovable's `/tars-tier` endpoint is expected to return the same
 * projection in `features[]`; this mirror lets the cockpit render
 * gated UI when the producer is offline / in dev.
 */
export const TIER_GATES: Record<TierSlug, readonly TierFeature[]> = {
  free: ["modes.chat_only", "messages.50_per_day"],
  pro: [
    "modes.all",
    "messages.500_per_day",
    "background_tasks",
    "morning_briefs",
    "memory_reflection",
  ],
  business: [
    "modes.all",
    "messages.unlimited",
    "background_tasks",
    "morning_briefs",
    "memory_reflection",
    "receipt_ledger",
    "team_collaboration",
    "share_links_utm",
    "api_access",
  ],
  lifetime: [
    "modes.all",
    "messages.unlimited",
    "background_tasks",
    "morning_briefs",
    "memory_reflection",
    "receipt_ledger",
    "team_collaboration",
    "share_links_utm",
    "api_access",
    "custom_persona_presets",
    "early_access_features",
    "priority_support",
  ],
} as const;

export interface TierResolution {
  ok: boolean;
  contract_version: string;
  operator_id: string | null;
  tier: TierSlug;
  tier_source: TierSource;
  active_receipt_id: string | null;
  expires_at: string | null;
  features: readonly TierFeature[];
}

/** Default resolution when the producer is offline / no operator JWT. */
export const FREE_TIER_RESOLUTION: TierResolution = {
  ok: true,
  contract_version: "0.1",
  operator_id: null,
  tier: "free",
  tier_source: "default",
  active_receipt_id: null,
  expires_at: null,
  features: TIER_GATES.free,
};

// --------------------------------------------------------------------
// Resolution rule mirror (Lovable side)
// --------------------------------------------------------------------

/**
 * Resolve a `TierSlug` from a list of receipts (mirror of the rule
 * in `docs/contracts/RECEIPT_LEDGER.md §3.3`). Pure helper —
 * exported for tests + an offline / cached client path.
 */
export interface ReceiptLike {
  tars_tier: TierSlug;
  status: "active" | "expired" | "cancelled" | "pending";
  expires_at: string | null;
  created_at: string;
}

export function resolveTierFromReceipts(
  receipts: readonly ReceiptLike[],
  now: Date = new Date(),
): { tier: TierSlug; tier_source: TierSource; active_receipt: ReceiptLike | null } {
  const nowMs = now.getTime();
  const active = receipts.filter((r) => {
    if (r.status !== "active") return false;
    if (r.expires_at == null) return true;
    const exp = Date.parse(r.expires_at);
    return Number.isFinite(exp) && exp > nowMs;
  });
  if (active.length === 0) {
    return { tier: "free", tier_source: "default", active_receipt: null };
  }
  // Most recent by created_at wins.
  const sorted = [...active].sort(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
  );
  return {
    tier: sorted[0].tars_tier,
    tier_source: "receipt",
    active_receipt: sorted[0],
  };
}

/**
 * Mirror of the projection in `docs/contracts/RECEIPT_LEDGER.md §1`.
 * The producer is expected to return the same feature list in
 * `features[]` so a cockpit running against a live producer never
 * reads `TIER_GATES` directly.
 */
export function featuresForTier(tier: TierSlug): readonly TierFeature[] {
  return TIER_GATES[tier];
}

export function tierAllows(
  resolution: TierResolution | null,
  feature: TierFeature,
): boolean {
  if (!resolution) return false;
  return resolution.features.includes(feature);
}

// --------------------------------------------------------------------
// Live client (stub today)
// --------------------------------------------------------------------

/**
 * Producer endpoint. `null` today so the cockpit short-circuits to
 * `FREE_TIER_RESOLUTION` without making a network request. Flip to
 * something like `"https://meeet.world/functions/v1/tars-tier"`
 * once Lovable lands the producer.
 *
 * Override at runtime via `VITE_TARS_TIER_URL` for staging /
 * preview deployments.
 */
export const RESOLVE_TIER_URL: string | null =
  ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_TARS_TIER_URL ?? null) || null;

/** Internal helper — exposed for tests only. */
export interface TierFetchOpts {
  url?: string | null;
  jwt?: string | null;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
}

export async function fetchTier(opts: TierFetchOpts = {}): Promise<TierResolution> {
  const url = opts.url ?? RESOLVE_TIER_URL;
  if (!url) return FREE_TIER_RESOLUTION;
  const fetcher = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { accept: "application/json" };
  if (opts.jwt) headers.authorization = `Bearer ${opts.jwt}`;
  try {
    const r = await fetcher(url, { headers, signal: opts.signal });
    if (!r.ok) return FREE_TIER_RESOLUTION;
    const raw = (await r.json()) as Partial<TierResolution>;
    return normaliseTierResolution(raw);
  } catch {
    return FREE_TIER_RESOLUTION;
  }
}

/** Validate + project producer payload into a typed resolution. */
export function normaliseTierResolution(raw: Partial<TierResolution>): TierResolution {
  const tier = isTierSlug(raw.tier) ? raw.tier : "free";
  const tier_source = isTierSource(raw.tier_source) ? raw.tier_source : "default";
  const features = Array.isArray(raw.features)
    ? raw.features.filter(isTierFeature)
    : TIER_GATES[tier];
  return {
    ok: raw.ok !== false,
    contract_version: typeof raw.contract_version === "string" ? raw.contract_version : "0.1",
    operator_id: typeof raw.operator_id === "string" ? raw.operator_id : null,
    tier,
    tier_source,
    active_receipt_id:
      typeof raw.active_receipt_id === "string" ? raw.active_receipt_id : null,
    expires_at: typeof raw.expires_at === "string" ? raw.expires_at : null,
    features,
  };
}

function isTierSlug(v: unknown): v is TierSlug {
  return v === "free" || v === "pro" || v === "business" || v === "lifetime";
}
function isTierSource(v: unknown): v is TierSource {
  return v === "receipt" || v === "default" || v === "promo";
}
function isTierFeature(v: unknown): v is TierFeature {
  return typeof v === "string" && v in featureToTier;
}

/** Quick lookup — every feature → minimum tier that includes it. */
export const featureToTier: Readonly<Record<TierFeature, TierSlug>> = (() => {
  const out: Record<string, TierSlug> = {};
  // Iterate in order of "least-to-most restrictive" so the *minimum*
  // tier wins.
  const order: TierSlug[] = ["free", "pro", "business", "lifetime"];
  for (const tier of order) {
    for (const f of TIER_GATES[tier]) {
      if (!(f in out)) out[f] = tier;
    }
  }
  return out as Readonly<Record<TierFeature, TierSlug>>;
})();

// --------------------------------------------------------------------
// React hook
// --------------------------------------------------------------------

export interface UseTierOpts {
  /** Override producer URL (otherwise read from `RESOLVE_TIER_URL`). */
  url?: string | null;
  /** Operator JWT from the meeet.world auth flow. */
  jwt?: string | null;
  /** Polling interval in ms; default 30 s. Set `0` to disable. */
  intervalMs?: number;
}

export interface UseTierState {
  resolution: TierResolution;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for the cockpit to read the operator's current tier. Always
 * returns a valid `resolution` (defaults to `FREE_TIER_RESOLUTION`)
 * — never `null` — so callers can render gated UI without
 * branch-on-null guards.
 */
export function useTier(opts: UseTierOpts = {}): UseTierState {
  const { url, jwt, intervalMs = 30_000 } = opts;
  const [resolution, setResolution] = useState<TierResolution>(FREE_TIER_RESOLUTION);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const cancelled = useRef(false);

  const refresh = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    cancelled.current = false;
    const controller = new AbortController();

    const tick = async () => {
      try {
        const out = await fetchTier({ url, jwt, signal: controller.signal });
        if (!cancelled.current) {
          setResolution(out);
          setError(null);
        }
      } catch (err) {
        if (!cancelled.current) setError(err as Error);
      } finally {
        if (!cancelled.current) setLoading(false);
      }
    };
    refresh.current = tick;
    void tick();

    let timer: ReturnType<typeof setInterval> | null = null;
    if (intervalMs > 0) {
      timer = setInterval(() => {
        void tick();
      }, intervalMs);
    }
    return () => {
      cancelled.current = true;
      controller.abort();
      if (timer) clearInterval(timer);
    };
  }, [url, jwt, intervalMs]);

  return {
    resolution,
    loading,
    error,
    refresh: () => refresh.current(),
  };
}

// --------------------------------------------------------------------
// Re-export the cockpit base URL so callers don't have to import api.ts
// just to know which host to hit. Tier resolution lives on
// meeet.world, but receipt sub-views may eventually shim through TARS.
// --------------------------------------------------------------------

export { API_BASE };
