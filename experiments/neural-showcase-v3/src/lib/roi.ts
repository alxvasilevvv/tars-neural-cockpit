/**
 * roi.ts — Wave 84 — pure ROI math for the Workshop ROI calculator.
 *
 * Used by `<WorkshopROI />` (`src/pages/WorkshopROI.tsx`). All
 * functions are referentially-transparent so they can be unit-tested
 * directly without React (a future `src/lib/roi.test.ts` is intended).
 *
 * Pricing assumptions are pinned in `TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH`
 * — keep this in sync with the Pricing page Business tier ($99 / seat /
 * month) and `STRINGS_EN["pricing.tier.business.priceSub"]`.
 */
export const TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH = 99;
export const WEEKS_PER_YEAR = 52;
export const MONTHS_PER_YEAR = 12;

/** All four sliders + dropdowns expressed as one input bundle. */
export interface RoiInput {
  /** People on the team (1..50). */
  teamSize: number;
  /** Fully-loaded $/hour for an average team member. Free-form positive. */
  hourlyRate: number;
  /** Hours per week each person spends on automatable work (1..40). */
  hoursPerWeek: number;
  /** % of those hours TARS handles (0..1). 0.6 = 60%. */
  automationRate: number;
}

export interface RoiResult {
  /** Hours saved across the whole team per week. */
  hoursSavedPerWeek: number;
  /** Annualised dollar value of those hours. */
  annualSavingUsd: number;
  /** Annual TARS Business cost ($99 × seats × 12). */
  annualTarsCostUsd: number;
  /** Net ROI as a percentage — (saving − cost) / cost × 100. */
  netRoiPercent: number;
  /** Weeks of saving needed to recover the annual cost. */
  paybackWeeks: number;
}

/**
 * Clamp an input to a sane numeric window. Defensive against `NaN`
 * arriving from unparsed inputs (`<input type="number">` returns ""
 * which becomes `NaN` under `Number()`).
 */
function clamp(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

/**
 * Normalise the four-field bundle into the legal range. Keeps the
 * page renderable even if a slider somehow emits an out-of-range
 * value (e.g. via the URL hash `?team=999`).
 */
export function normaliseInput(raw: Partial<RoiInput>): RoiInput {
  return {
    teamSize: clamp(Math.round(raw.teamSize ?? 5), 1, 50),
    hourlyRate: clamp(raw.hourlyRate ?? 300, 1, 100_000),
    hoursPerWeek: clamp(raw.hoursPerWeek ?? 10, 1, 40),
    automationRate: clamp(raw.automationRate ?? 0.6, 0.05, 0.99),
  };
}

/**
 * Compute every metric the page surfaces. Pure — same input always
 * yields the same output. No `Date.now()`, no Math.random.
 */
export function computeRoi(raw: Partial<RoiInput>): RoiResult {
  const input = normaliseInput(raw);
  const hoursSavedPerWeek =
    input.teamSize * input.hoursPerWeek * input.automationRate;
  const annualSavingUsd = hoursSavedPerWeek * WEEKS_PER_YEAR * input.hourlyRate;
  const annualTarsCostUsd =
    input.teamSize * TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH * MONTHS_PER_YEAR;
  // Avoid divide-by-zero — annualTarsCost is always > 0 because
  // teamSize is clamped to ≥1, but the explicit guard documents intent.
  const netRoiPercent =
    annualTarsCostUsd > 0
      ? ((annualSavingUsd - annualTarsCostUsd) / annualTarsCostUsd) * 100
      : 0;
  // Weekly saving (never zero because hoursPerWeek ≥ 1, rate ≥ 1,
  // automationRate ≥ 0.05). Convert annualTarsCost / weeklySaving.
  const weeklySaving = hoursSavedPerWeek * input.hourlyRate;
  const paybackWeeks =
    weeklySaving > 0 ? annualTarsCostUsd / weeklySaving : Infinity;
  return {
    hoursSavedPerWeek,
    annualSavingUsd,
    annualTarsCostUsd,
    netRoiPercent,
    paybackWeeks,
  };
}

/**
 * Three preset scenarios surfaced as one-click buttons. Numbers are
 * realistic for the early-access cohort (Cresco / CARF / 3V / Crypto
 * Fund) — small / mid / large quant teams. All produce positive ROI
 * inside year 1 (the verification spec requires this).
 */
export interface RoiPreset {
  id: "small" | "mid" | "large";
  /** Long form — used in the i18n button label. */
  labelKey: "roi.preset.small" | "roi.preset.mid" | "roi.preset.large";
  input: RoiInput;
}

export const ROI_PRESETS: readonly RoiPreset[] = [
  {
    id: "small",
    labelKey: "roi.preset.small",
    input: {
      teamSize: 5,
      hourlyRate: 300,
      hoursPerWeek: 10,
      automationRate: 0.6,
    },
  },
  {
    id: "mid",
    labelKey: "roi.preset.mid",
    input: {
      teamSize: 15,
      hourlyRate: 500,
      hoursPerWeek: 12,
      automationRate: 0.6,
    },
  },
  {
    id: "large",
    labelKey: "roi.preset.large",
    input: {
      teamSize: 40,
      hourlyRate: 1000,
      hoursPerWeek: 14,
      automationRate: 0.65,
    },
  },
] as const;

/** Hourly-rate preset buttons surfaced under the rate slider. */
export const HOURLY_RATE_PRESETS: readonly number[] = [50, 150, 300, 500, 1000];

/**
 * Format a USD amount as a short string — `$1.2M`, `$340K`, `$842`.
 * Used for big-number animated displays.
 */
export function formatUsd(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `$${(n / 1_000).toFixed(1)}K`;
  if (abs >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

/** Format a percentage — `1,240%` / `92%` / `-12%`. */
export function formatPercent(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n).toLocaleString("en-US")}%`;
}

/** Format weeks — fractional below 4, integer otherwise. */
export function formatWeeks(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (n < 1) return `${(n * 7).toFixed(1)} days`;
  if (n < 4) return `${n.toFixed(1)} wks`;
  return `${Math.round(n)} wks`;
}

/** Format hours — short integer, no decimals at this scale. */
export function formatHours(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return Math.round(n).toLocaleString("en-US");
}
