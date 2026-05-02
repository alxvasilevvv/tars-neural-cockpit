/**
 * Pure helpers for the Awareness Explorer page (`/cockpit/awareness`).
 *
 * The page is a thin shell over `listDomains()` + `snapshotAwareness()`
 * and these helpers; everything DOM / React / router lives in
 * `pages/Awareness.tsx`.
 */

import type { AwarenessSource } from "./api";

/** Tailwind class + label for an awareness kind chip. */
export interface KindTone {
  cls: string;
  label: string;
}

/**
 * Map a backend awareness `kind` to an accent. The four shipped kinds
 * are `stream` / `poll` / `webhook` / `local` — anything else falls
 * through to the neutral border so the page never crashes on unknown
 * sources.
 */
export function kindTone(kind: string | null | undefined): KindTone {
  const k = String(kind ?? "").trim().toLowerCase();
  switch (k) {
    case "stream":
      return { cls: "border-accent/60 text-accent", label: "stream" };
    case "poll":
      return { cls: "border-line-strong text-ink-2", label: "poll" };
    case "webhook":
      return { cls: "border-amber/60 text-amber", label: "webhook" };
    case "local":
      return { cls: "border-line text-ink-2", label: "local" };
    default:
      return { cls: "border-line text-ink-3", label: k || "—" };
  }
}

/** Pretty-print a snapshot took_ms value; mirrors the trace viewer convention. */
export function fmtTookMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/** "23 s ago" / "4 min ago" / "—" — small relative-time formatter. */
export function fmtAgo(
  ts: number | null | undefined,
  now: number = Date.now(),
): string {
  if (ts == null || !Number.isFinite(ts)) return "—";
  const ms = ts > 1e12 ? ts : ts * 1000; // tolerate seconds vs ms
  const diff = Math.max(0, now - ms);
  if (diff < 1000) return "just now";
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s} s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return `${d} d ago`;
}

/**
 * Snapshot envelope returned by `/api/domains/<slug>/awareness/<id>/snapshot`.
 * Mirrors the FastAPI shape (`web_extras/routers/domains.py`).
 */
export interface SnapshotEnvelope {
  ok: boolean;
  slug: string;
  source_id: string;
  kind: string;
  trace_id?: string | null;
  took_ms?: number | null;
  data?: unknown;
  error?: string | null;
  hint?: string | null;
}

/**
 * Per-source render state held by the page. `loading` for the in-flight
 * fetch, `lastFetchedAt` (ms epoch) for the "fetched X ago" badge.
 */
export interface SnapshotState {
  loading: boolean;
  lastFetchedAt: number | null;
  envelope: SnapshotEnvelope | null;
  error: string | null;
}

export function emptySnapshotState(): SnapshotState {
  return {
    loading: false,
    lastFetchedAt: null,
    envelope: null,
    error: null,
  };
}

/**
 * Stable storage key for a (slug, source_id) tuple. Used as the
 * dictionary key in the per-page snapshot map.
 */
export function snapshotKey(slug: string, sourceId: string): string {
  return `${slug}::${sourceId}`;
}

/**
 * Filter awareness sources by a free-text query (matches name, id,
 * kind, or description case-insensitively). Empty query echoes input.
 */
export function filterAwareness(
  sources: readonly AwarenessSource[],
  query: string,
): AwarenessSource[] {
  const q = (query ?? "").trim().toLowerCase();
  if (!q) return [...sources];
  return sources.filter(s => {
    const blob = [
      s.id,
      s.name ?? "",
      s.description ?? "",
      s.kind ?? "",
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return blob.includes(q);
  });
}

/**
 * Render the snapshot data as a stable, pretty-printed JSON string.
 * Returns `""` for null/undefined so the page can branch on truthiness
 * (avoids the "null" / "undefined" literal showing up in the UI).
 */
export function prettyJson(value: unknown): string {
  if (value == null) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * Read a `?slug=…` query param and validate it against the loaded
 * pack list. Falls back to the first pack when the query is missing
 * or stale (e.g. operator typed a slug that no longer exists).
 */
export function pickSlug(
  packSlugs: readonly string[],
  paramSlug: string | null | undefined,
): string | null {
  if (packSlugs.length === 0) return null;
  if (paramSlug && packSlugs.includes(paramSlug)) return paramSlug;
  return packSlugs[0] ?? null;
}

/**
 * Sum every awareness source across packs — drives the header
 * "N sources across M packs" line.
 */
export function totalSourceCount(
  packs: readonly { awareness?: readonly AwarenessSource[] }[],
): number {
  let n = 0;
  for (const p of packs) {
    n += (p.awareness ?? []).length;
  }
  return n;
}

/**
 * How many awareness sources in the pack carry a live fetcher (i.e.
 * snapshot endpoint will return real data, not the
 * `fetcher_unavailable` envelope).
 */
export function liveSourceCount(
  sources: readonly AwarenessSource[] | undefined | null,
): number {
  if (!sources) return 0;
  let n = 0;
  for (const s of sources) {
    if (s.live) n += 1;
  }
  return n;
}
