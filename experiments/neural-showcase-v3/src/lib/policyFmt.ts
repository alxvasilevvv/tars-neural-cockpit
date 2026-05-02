/**
 * Pure helpers for the Policy Inbox page (`/cockpit/policy`).
 *
 * Side-effect-free so the page stays a thin shell on top of these,
 * and the helpers stay unit-testable without wiring React / DOM /
 * router infra into the test suite.
 */

import type { PendingConfirmation } from "./policy";

/** Statuses returned by the policy gate (see ``backend/core/policy``). */
export type ConfirmationStatus = PendingConfirmation["status"];

export const ALL_STATUSES: readonly ConfirmationStatus[] = [
  "pending",
  "confirmed",
  "cancelled",
  "expired",
  "failed",
] as const;

/**
 * Tone descriptor for a status pill (Tailwind class + label suitable
 * for the cockpit's status lozenge layer). Centralised here so every
 * surface that renders a confirmation status agrees on the colour.
 */
export interface StatusTone {
  cls: string;
  label: string;
}

export function statusTone(status: ConfirmationStatus): StatusTone {
  switch (status) {
    case "pending":
      return {
        cls: "border-line-strong text-[color:var(--brand-amber,#FBBF24)]",
        label: "pending",
      };
    case "confirmed":
      return {
        cls: "border-line-strong text-[color:var(--color-success)]",
        label: "confirmed",
      };
    case "cancelled":
      return { cls: "border-line text-ink-3", label: "cancelled" };
    case "expired":
      return { cls: "border-line text-ink-3", label: "expired" };
    case "failed":
      return { cls: "border-alert/60 text-alert", label: "failed" };
    default:
      return { cls: "border-line text-ink-3", label: String(status) };
  }
}

/**
 * Render a unix-seconds timestamp as a human-friendly relative
 * span ("5s ago", "12m ago", "3h ago", "2d ago"). Returns "—" for
 * null / NaN / non-positive values so the cockpit never prints
 * "NaN ago" in the operator's face.
 *
 * The optional ``now`` parameter (unix seconds) lets tests pin the
 * clock without globals. Production callers omit it.
 */
export function fmtAge(
  ts: number | null | undefined,
  now?: number,
): string {
  if (ts == null || !Number.isFinite(ts) || ts <= 0) return "—";
  const nowSec = now ?? Date.now() / 1000;
  const d = Math.max(0, Math.round(nowSec - ts));
  if (d < 1) return "just now";
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.round(d / 60)}m ago`;
  if (d < 86400) return `${Math.round(d / 3600)}h ago`;
  return `${Math.round(d / 86400)}d ago`;
}

/**
 * Time-to-expire helper. Returns a short human string ("12m left",
 * "expired", "2h left"). Used in the pending row so the operator
 * can prioritise tokens that are about to drop.
 */
export function fmtTimeLeft(
  expiresAt: number | null | undefined,
  now?: number,
): string {
  if (expiresAt == null || !Number.isFinite(expiresAt) || expiresAt <= 0) {
    return "no expiry";
  }
  const nowSec = now ?? Date.now() / 1000;
  const d = Math.round(expiresAt - nowSec);
  if (d <= 0) return "expired";
  if (d < 60) return `${d}s left`;
  if (d < 3600) return `${Math.round(d / 60)}m left`;
  if (d < 86400) return `${Math.round(d / 3600)}h left`;
  return `${Math.round(d / 86400)}d left`;
}

/**
 * Compare-by descending-creation-then-token sort comparator. The
 * backend's `/api/policy/pending` endpoint already returns
 * newest-first, but the cockpit re-sorts when tabs are merged or
 * the in-memory cache is stitched with optimistic updates.
 */
export function compareConfirmationsNewestFirst(
  a: PendingConfirmation,
  b: PendingConfirmation,
): number {
  if (a.created_at !== b.created_at) return b.created_at - a.created_at;
  return a.token < b.token ? 1 : a.token > b.token ? -1 : 0;
}

/**
 * Lightweight in-memory predicate for the free-text search box.
 * Matches against token / slug / action / requested_by /
 * trace_id substrings (case-insensitive).
 */
export function matchesQuery(
  c: PendingConfirmation,
  query: string,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystacks = [
    c.token,
    c.slug,
    c.action_id,
    `${c.slug}.${c.action_id}`,
    c.requested_by ?? "",
    c.trace_id ?? "",
  ];
  return haystacks.some((s) => s.toLowerCase().includes(q));
}
