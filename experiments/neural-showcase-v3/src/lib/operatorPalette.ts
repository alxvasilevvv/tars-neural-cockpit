/**
 * Pure helpers for the Operator command palette
 * (`<OperatorPalette />`, opened with ⌘. / Ctrl+. on /cockpit).
 *
 * The palette is a fuzzy index over four operator surfaces that the
 * Phase L8 ⌘K search palette deliberately doesn't touch (search is
 * for chunks/messages/traces; this is for *taking action* on packs,
 * playbooks, awareness sources, and recently-active traces).
 *
 * This file is side-effect-free so the helpers stay unit-testable
 * without React / DOM / router infra. The page (`OperatorPalette.tsx`)
 * imports the loader functions and the scorer; the resource fetchers
 * here only adapt the existing `lib/api.ts` / `lib/playbooks.ts` /
 * `lib/meeet.ts` clients.
 */

import {
  listDomains,
  type DomainPack,
  type AwarenessSource,
  type DomainAction,
} from "./api";
import { listPlaybooks, type Playbook } from "./playbooks";
import { listTraces, type TraceSummary } from "./meeet";

/** Resource family the operator can jump to / invoke from the palette. */
export type OperatorEntryKind =
  | "pack"
  | "action"
  | "playbook"
  | "awareness"
  | "trace";

/**
 * Unified operator-resource shape. Pure data — every shaper writes
 * one of these and the palette renders them through a single switch.
 */
export interface OperatorEntry {
  /** Stable id within `kind` — used as the React key + recent-list key. */
  id: string;
  kind: OperatorEntryKind;
  /** Primary headline rendered in the row. */
  title: string;
  /** Hint line below the title; usually a slug / source / route. */
  hint: string;
  /** Lowercase blob the fuzzy scorer reads. Built once at shape time. */
  haystack: string;
  /** Pack slug for actions / awareness / playbooks (null on pack/trace). */
  packSlug: string | null;
  /** Action id, awareness source id, playbook id, or trace id. */
  resourceId: string;
  /** True when invocation routes through the policy gate. */
  destructive: boolean;
  /** Group label in the list (e.g. "packs", "playbooks"). */
  group: OperatorGroup;
  /** Original resource — escape hatch for the renderer. */
  raw: unknown;
}

export type OperatorGroup =
  | "packs"
  | "actions"
  | "playbooks"
  | "awareness"
  | "traces";

export const ALL_GROUPS: readonly OperatorGroup[] = [
  "packs",
  "actions",
  "playbooks",
  "awareness",
  "traces",
] as const;

/**
 * Snapshot of every operator-resource the palette can show. Loaded
 * once on open + refreshed on demand.
 */
export interface OperatorIndex {
  packs: OperatorEntry[];
  actions: OperatorEntry[];
  playbooks: OperatorEntry[];
  awareness: OperatorEntry[];
  traces: OperatorEntry[];
}

export function emptyIndex(): OperatorIndex {
  return { packs: [], actions: [], playbooks: [], awareness: [], traces: [] };
}

// --- Shapers (pure) -------------------------------------------------

export function shapePack(pack: DomainPack): OperatorEntry {
  const tags = [
    pack.slug,
    pack.short ?? "",
    pack.description ?? "",
    pack.audience ?? "",
    ...(pack.capabilities ?? []),
    ...(pack.composed_of ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return {
    id: `pack:${pack.slug}`,
    kind: "pack",
    title: pack.name || pack.slug,
    hint: pack.short ? pack.short : pack.slug,
    haystack: `${pack.name?.toLowerCase() ?? ""} ${tags}`,
    packSlug: pack.slug,
    resourceId: pack.slug,
    destructive: false,
    group: "packs",
    raw: pack,
  };
}

export function shapeAction(
  pack: DomainPack,
  action: DomainAction,
): OperatorEntry {
  const tags = [
    action.id,
    action.name ?? "",
    action.description ?? "",
    pack.slug,
    pack.short ?? "",
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const destructive = action.destructive === true;
  return {
    id: `action:${pack.slug}:${action.id}`,
    kind: "action",
    title: action.name || action.id,
    hint: `${pack.slug}.${action.id}${destructive ? " · destructive" : ""}`,
    haystack: tags,
    packSlug: pack.slug,
    resourceId: action.id,
    destructive,
    group: "actions",
    raw: action,
  };
}

export function shapeAwareness(
  pack: DomainPack,
  source: AwarenessSource,
): OperatorEntry {
  const tags = [
    source.id,
    source.name ?? "",
    source.description ?? "",
    source.kind ?? "",
    pack.slug,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return {
    id: `awareness:${pack.slug}:${source.id}`,
    kind: "awareness",
    title: source.name || source.id,
    hint: `${pack.slug} · ${source.kind || "source"}${
      source.live ? " · live" : ""
    }`,
    haystack: tags,
    packSlug: pack.slug,
    resourceId: source.id,
    destructive: false,
    group: "awareness",
    raw: source,
  };
}

export function shapePlaybook(playbook: Playbook): OperatorEntry {
  // Playbook ids are usually `<pack>.<name>` — split on the first dot
  // so the chip can render the pack badge cleanly without rebuilding
  // it server-side.
  const dot = playbook.id.indexOf(".");
  const packSlug = dot > 0 ? playbook.id.slice(0, dot) : null;
  const tags = [
    playbook.id,
    playbook.name ?? "",
    playbook.description ?? "",
    packSlug ?? "",
    ...(playbook.tags ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return {
    id: `playbook:${playbook.id}`,
    kind: "playbook",
    title: playbook.name || playbook.id,
    hint: packSlug ? `${packSlug} · playbook` : "playbook",
    haystack: tags,
    packSlug,
    resourceId: playbook.id,
    destructive: false,
    group: "playbooks",
    raw: playbook,
  };
}

export function shapeTrace(trace: TraceSummary): OperatorEntry {
  const route = trace.primary_route ?? "—";
  const cost =
    trace.total_cost_usd != null ? `$${trace.total_cost_usd.toFixed(4)}` : "$0";
  const tags = [
    trace.trace_id,
    route,
    trace.last_session_id ?? "",
    ...(trace.kinds ?? []),
    ...(trace.routes ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return {
    id: `trace:${trace.trace_id}`,
    kind: "trace",
    title: trace.trace_id.slice(0, 12),
    hint: `${route} · ${trace.event_count} ev · ${cost}`,
    haystack: tags,
    packSlug: null,
    resourceId: trace.trace_id,
    destructive: false,
    group: "traces",
    raw: trace,
  };
}

// --- Loaders --------------------------------------------------------

/**
 * Resolve the full operator index in one go. Each fetch is independent
 * — failures degrade gracefully (empty group + bubble the error to the
 * caller for a warning pill).
 */
export async function loadOperatorIndex(
  opts: { traceLimit?: number } = {},
): Promise<{ index: OperatorIndex; errors: Record<OperatorGroup, string | null> }> {
  const errors: Record<OperatorGroup, string | null> = {
    packs: null,
    actions: null,
    playbooks: null,
    awareness: null,
    traces: null,
  };
  const index = emptyIndex();
  const traceLimit = clampInt(opts.traceLimit ?? 12, 1, 50);

  // Domains feed both the packs group and the per-action / per-awareness
  // groups, so one fetch hydrates three lanes.
  let packs: DomainPack[] = [];
  try {
    packs = await listDomains();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.packs = msg;
    errors.actions = msg;
    errors.awareness = msg;
  }
  for (const pack of packs) {
    index.packs.push(shapePack(pack));
    for (const action of pack.actions ?? []) {
      index.actions.push(shapeAction(pack, action));
    }
    for (const source of pack.awareness ?? []) {
      index.awareness.push(shapeAwareness(pack, source));
    }
  }

  try {
    const playbooks = await listPlaybooks();
    for (const pb of playbooks) {
      index.playbooks.push(shapePlaybook(pb));
    }
  } catch (err) {
    errors.playbooks = err instanceof Error ? err.message : String(err);
  }

  try {
    const traces = await listTraces({ limit: traceLimit });
    for (const t of traces) {
      index.traces.push(shapeTrace(t));
    }
  } catch (err) {
    errors.traces = err instanceof Error ? err.message : String(err);
  }

  return { index, errors };
}

// --- Fuzzy scorer ---------------------------------------------------

/**
 * Lightweight in-order subsequence scorer with prefix bonuses. Mirrors
 * the Cmd+K landing palette so the operator gets identical typing
 * affordance across both surfaces. Pure / sync / total — never throws.
 */
export function fuzzyScore(entry: OperatorEntry, query: string): number {
  const q = (query ?? "").trim().toLowerCase();
  if (!q) return 0;
  const haystack = entry.haystack;
  if (!haystack) return 0;
  let last = -1;
  let score = 0;
  for (const ch of q) {
    const idx = haystack.indexOf(ch, last + 1);
    if (idx === -1) return 0;
    score += idx === last + 1 ? 3 : 1;
    last = idx;
  }
  const titleLc = entry.title.toLowerCase();
  if (titleLc.startsWith(q)) score += 30;
  if (haystack.includes(" " + q)) score += 6;
  if (entry.kind === "pack") score += 2;
  return score;
}

/**
 * Apply a query to a flat list of entries, returning the matches in
 * descending score with stable tie-break (preserves input order on
 * equal score).
 */
export function rankEntries(
  entries: readonly OperatorEntry[],
  query: string,
): OperatorEntry[] {
  const q = (query ?? "").trim();
  if (!q) return [...entries];
  return entries
    .map((entry, i) => ({ entry, score: fuzzyScore(entry, q), idx: i }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => (b.score - a.score) || (a.idx - b.idx))
    .map(({ entry }) => entry);
}

// --- Group filter ---------------------------------------------------

/** Group filter chip in the palette header. `null` = no filter. */
export type GroupFilter = OperatorGroup | "all";

export function filterByGroup(
  index: OperatorIndex,
  group: GroupFilter,
): OperatorEntry[] {
  if (group === "all") {
    // Default order matches ALL_GROUPS so the palette renders in a
    // predictable rhythm: packs → actions → playbooks → awareness → traces.
    return [
      ...index.packs,
      ...index.actions,
      ...index.playbooks,
      ...index.awareness,
      ...index.traces,
    ];
  }
  return [...index[group]];
}

/** Sum of every entry across the index. */
export function totalCount(index: OperatorIndex): number {
  return (
    index.packs.length +
    index.actions.length +
    index.playbooks.length +
    index.awareness.length +
    index.traces.length
  );
}

/** Per-group counts, useful for the chip badges. */
export function groupCounts(
  index: OperatorIndex,
): Record<OperatorGroup, number> {
  return {
    packs: index.packs.length,
    actions: index.actions.length,
    playbooks: index.playbooks.length,
    awareness: index.awareness.length,
    traces: index.traces.length,
  };
}

// --- Recents (localStorage) -----------------------------------------

const RECENT_KEY = "tars-operator-palette-recent";
const MAX_RECENT = 5;

export function loadRecentIds(): string[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr
      .filter((s): s is string => typeof s === "string")
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function pushRecent(id: string): string[] {
  const next = [id, ...loadRecentIds().filter(x => x !== id)].slice(
    0,
    MAX_RECENT,
  );
  if (typeof localStorage !== "undefined") {
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      /* private mode — silently ignore */
    }
  }
  return next;
}

export function pickRecent(
  index: OperatorIndex,
  recentIds: readonly string[],
): OperatorEntry[] {
  const flat = filterByGroup(index, "all");
  const byId = new Map(flat.map(e => [e.id, e] as const));
  const out: OperatorEntry[] = [];
  for (const id of recentIds) {
    const entry = byId.get(id);
    if (entry) out.push(entry);
  }
  return out;
}

// --- Misc -----------------------------------------------------------

function clampInt(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, Math.trunc(n)));
}

/** Resolve a deep-link path for a chosen entry (or `null` to invoke). */
export function entryHref(entry: OperatorEntry): string | null {
  switch (entry.kind) {
    case "trace":
      return `/cockpit/traces?trace=${encodeURIComponent(entry.resourceId)}`;
    case "pack":
      // Cockpit currently lives at /cockpit and renders the active pack
      // via the operator strip — surface the slug as a query so future
      // routes can pick it up; today the page falls through harmlessly.
      return `/cockpit?pack=${encodeURIComponent(entry.resourceId)}`;
    default:
      // actions / playbooks / awareness invoke through dedicated pickers
      // mounted by the palette itself.
      return null;
  }
}
