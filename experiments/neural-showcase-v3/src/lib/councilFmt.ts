/**
 * Pure helpers for the Council Debug page (`/cockpit/council`).
 *
 * Side-effect-free so the page stays a thin shell and the helpers
 * stay unit-testable without React / DOM / router infra.
 */

import type { Proposal } from "./council";

/** Stance label normalised to lowercase, trimmed. */
export function normaliseStance(stance: string | null | undefined): string {
  return String(stance ?? "").trim().toLowerCase();
}

/** Tailwind class + label for a stance pill. */
export interface StanceTone {
  cls: string;
  label: string;
}

export function stanceTone(stance: string | null | undefined): StanceTone {
  const s = normaliseStance(stance);
  switch (s) {
    case "risk_on":
    case "bullish":
    case "buy":
    case "long":
      return {
        cls: "border-line-strong text-[color:var(--color-success)]",
        label: s || "—",
      };
    case "risk_off":
    case "bearish":
    case "sell":
    case "short":
      return { cls: "border-alert/60 text-alert", label: s || "—" };
    case "neutral":
    case "hold":
      return { cls: "border-line text-ink-2", label: s || "—" };
    case "":
    case "unavailable":
      return { cls: "border-line text-ink-3", label: s || "—" };
    default:
      return { cls: "border-line-strong text-accent", label: s };
  }
}

/**
 * Render a [0..1] confidence as a percentage string with one
 * decimal of precision. NaN / out-of-range values clamp to a safe
 * "—" so the cockpit never prints "NaN%".
 */
export function fmtConfidencePct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const clamped = Math.max(0, Math.min(1, value));
  return `${(clamped * 100).toFixed(1)}%`;
}

/** Width fraction (0..1) for the confidence bar; clamped, NaN-safe. */
export function confidenceWidth(value: number | null | undefined): number {
  if (value == null || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

/**
 * Compute the highest-confidence voice in a deliberation and return
 * its model id. Used by the cockpit to mark the "winner" with a
 * subtle accent border. Falls back to the first voice when ties or
 * empty input.
 */
export function pickWinningVoice(voices: readonly Proposal[]): string | null {
  if (voices.length === 0) return null;
  let best: Proposal = voices[0]!;
  for (const v of voices) {
    if (v.confidence > best.confidence) best = v;
  }
  return best.model;
}

/**
 * Token / cost rollup over a deliberation's voices. Pure helper so
 * the cockpit can render an aggregate strip without wiring extra
 * state.
 */
export interface CouncilRollup {
  total_tokens_in: number;
  total_tokens_out: number;
  total_latency_ms: number;
  voice_count: number;
}

export function rollupVoices(voices: readonly Proposal[]): CouncilRollup {
  let tokens_in = 0;
  let tokens_out = 0;
  let latency = 0;
  for (const v of voices) {
    tokens_in += Number.isFinite(v.tokens_in) ? v.tokens_in : 0;
    tokens_out += Number.isFinite(v.tokens_out) ? v.tokens_out : 0;
    latency += Number.isFinite(v.latency_ms) ? v.latency_ms : 0;
  }
  return {
    total_tokens_in: tokens_in,
    total_tokens_out: tokens_out,
    total_latency_ms: latency,
    voice_count: voices.length,
  };
}

/** Format milliseconds; mirrors the trace-viewer convention. */
export function fmtLatencyMs(
  ms: number | null | undefined,
  units: { ms: string; s: string },
): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ${units.ms}`;
  return `${(ms / 1000).toFixed(2)} ${units.s}`;
}
