/**
 * OperatorPalette — IDEAS #20.
 *
 * A second cockpit-only palette that complements the existing ⌘K
 * search palette (which queries chunks / messages / traces). This
 * one indexes the operator's *action surface*: domain packs, pack
 * actions, awareness sources, playbooks, and recently active
 * traces. Opens with `⌘.` / `Ctrl+.`. Mounted in `Cockpit.tsx`.
 *
 * Design rules:
 *   - Single overlay, dismiss with Escape or backdrop click.
 *   - Keyboard-first: ↑/↓ to navigate, ↵ to activate.
 *   - Group filter chips at the top; counts come from a pre-computed
 *     index so chip badges don't lie.
 *   - Activation routes by kind:
 *       * pack   → push `/cockpit?pack=<slug>` (deep-link)
 *       * trace  → push `/cockpit/traces?trace=<id>`
 *       * action → POST `/api/domains/<slug>/actions/<id>` (empty args)
 *       * awareness → GET `/api/domains/<slug>/awareness/<id>/snapshot`
 *       * playbook  → POST `/api/playbooks/<id>/run`
 *   - Destructive actions are routed through the policy gate
 *     automatically by the server; the palette just surfaces the
 *     blocked-on-confirm response with a "open the inbox to approve"
 *     toast and a deep-link.
 *
 * The index loader (`loadOperatorIndex`) is a thin async glue —
 * the heavy logic (scoring, group filter, recents, deep-links)
 * lives in `lib/operatorPalette.ts` and is independently unit-tested.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  ALL_GROUPS,
  emptyIndex,
  entryHref,
  filterByGroup,
  groupCounts,
  loadOperatorIndex,
  loadRecentIds,
  pickRecent,
  pushRecent,
  rankEntries,
  totalCount,
  type GroupFilter,
  type OperatorEntry,
  type OperatorIndex,
  type OperatorGroup,
} from "@/lib/operatorPalette";
import { invokeAction, snapshotAwareness } from "@/lib/api";
import { runPlaybook } from "@/lib/playbooks";
import { useT, type TKey } from "@/lib/i18n";
import { useFocusTrap } from "@/lib/useFocusTrap";

type ActivityState =
  | { kind: "idle" }
  | { kind: "busy"; entryId: string }
  | { kind: "result"; tone: "ok" | "warn" | "err"; message: string };

interface OperatorPaletteProps {
  /** Triggered on every successful action so the cockpit can surface a toast. */
  onToast?: (tone: "ok" | "warn" | "err", message: string) => void;
}

export function OperatorPalette({ onToast }: OperatorPaletteProps = {}) {
  const t = useT();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [groupFilter, setGroupFilter] = useState<GroupFilter>("all");
  const [activeIdx, setActiveIdx] = useState(0);
  const [index, setIndex] = useState<OperatorIndex>(() => emptyIndex());
  const [errors, setErrors] = useState<Record<OperatorGroup, string | null>>({
    packs: null,
    actions: null,
    playbooks: null,
    awareness: null,
    traces: null,
  });
  const [loading, setLoading] = useState(false);
  const [activity, setActivity] = useState<ActivityState>({ kind: "idle" });
  const [recentIds, setRecentIds] = useState<string[]>(() => loadRecentIds());

  const inputRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useFocusTrap(dialogRef, open);

  /** Deep-link from ⌘J jump palette — pre-fill query and open. */
  useEffect(() => {
    const onPrefill = (event: Event) => {
      const detail = (event as CustomEvent<{ query?: string }>).detail;
      const q = detail?.query;
      if (typeof q !== "string" || !q.trim()) return;
      setQuery(q.trim());
      setOpen(true);
      setGroupFilter("all");
    };
    window.addEventListener("tars:operator-palette-prefill", onPrefill);
    return () =>
      window.removeEventListener("tars:operator-palette-prefill", onPrefill);
  }, []);

  // --- Hotkey -------------------------------------------------------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      // ⌘. / Ctrl+. (period) — never collides with ⌘K (search).
      if (meta && e.key === ".") {
        e.preventDefault();
        setOpen(prev => !prev);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // --- Index loader -------------------------------------------------
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { index, errors } = await loadOperatorIndex({ traceLimit: 12 });
      setIndex(index);
      setErrors(errors);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    refresh();
  }, [open, refresh]);

  // Reset & focus on open
  useEffect(() => {
    if (!open) {
      setQuery("");
      setActiveIdx(0);
      setActivity({ kind: "idle" });
      return;
    }
    const id = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(id);
  }, [open]);

  // --- Filter + score ----------------------------------------------
  const groups = useMemo(() => {
    const filtered = filterByGroup(index, groupFilter);
    if (!query.trim()) {
      const recent = pickRecent(index, recentIds).filter(
        e => groupFilter === "all" || e.group === groupFilter,
      );
      const recentSet = new Set(recent.map(e => e.id));
      const rest = filtered.filter(e => !recentSet.has(e.id));
      const out: { name: string; entries: OperatorEntry[] }[] = [];
      if (recent.length) out.push({ name: "recent", entries: recent });
      // Group `rest` by entry.group preserving canonical order
      for (const g of ALL_GROUPS) {
        if (groupFilter !== "all" && groupFilter !== g) continue;
        const entries = rest.filter(e => e.group === g);
        if (entries.length) out.push({ name: g, entries });
      }
      return out;
    }
    const ranked = rankEntries(filtered, query);
    return ranked.length ? [{ name: "matches", entries: ranked }] : [];
  }, [index, query, groupFilter, recentIds]);

  const flat = useMemo(() => groups.flatMap(g => g.entries), [groups]);

  useEffect(() => {
    if (activeIdx >= flat.length) setActiveIdx(0);
  }, [flat.length, activeIdx]);

  // --- Activation ---------------------------------------------------
  const close = useCallback(() => setOpen(false), []);

  const finishWithResult = useCallback(
    (tone: "ok" | "warn" | "err", message: string) => {
      setActivity({ kind: "result", tone, message });
      onToast?.(tone, message);
      // Auto-close on a success or warn; keep open on hard errors so
      // the operator can read the message inline.
      if (tone === "ok" || tone === "warn") {
        window.setTimeout(() => setOpen(false), 350);
      }
    },
    [onToast],
  );

  const activate = useCallback(
    async (entry: OperatorEntry) => {
      pushRecent(entry.id);
      setRecentIds(loadRecentIds());

      const href = entryHref(entry);
      if (href) {
        navigate(href);
        close();
        return;
      }

      setActivity({ kind: "busy", entryId: entry.id });

      try {
        if (entry.kind === "action") {
          if (!entry.packSlug) {
            finishWithResult("err", "missing pack slug");
            return;
          }
          const r = await invokeAction(entry.packSlug, entry.resourceId, {});
          if (!r.ok) {
            const blocked =
              (r.result?.["confirmation_token"] as string | undefined) ?? null;
            if (blocked) {
              finishWithResult("warn", t("operator.palette.confirm.staged"));
              return;
            }
            finishWithResult(
              "err",
              t("operator.palette.invoked.fail", {
                message: String(r.result?.["error"] ?? "unknown"),
              }),
            );
            return;
          }
          finishWithResult(
            "ok",
            t("operator.palette.invoked.ok", { ms: r.took_ms ?? 0 }),
          );
          return;
        }

        if (entry.kind === "awareness") {
          if (!entry.packSlug) {
            finishWithResult("err", "missing pack slug");
            return;
          }
          const t0 = performance.now();
          await snapshotAwareness(entry.packSlug, entry.resourceId);
          finishWithResult(
            "ok",
            t("operator.palette.snapshot.ok", {
              ms: Math.round(performance.now() - t0),
            }),
          );
          return;
        }

        if (entry.kind === "playbook") {
          const t0 = performance.now();
          const run = await runPlaybook(entry.resourceId, {});
          // PlaybookRun groups status on steps — surface the first
          // blocked step (policy gate) before the first failed one
          // so operators get the actionable signal.
          const steps = run.steps ?? [];
          const blockedStep = steps.find(s => s.blocked);
          if (blockedStep) {
            finishWithResult("warn", t("operator.palette.run.blocked"));
            return;
          }
          if (!run.ok) {
            const failedStep = steps.find(s => !s.ok && !s.skipped);
            finishWithResult(
              "err",
              t("operator.palette.run.fail", {
                message: failedStep?.error ?? "unknown",
              }),
            );
            return;
          }
          finishWithResult(
            "ok",
            t("operator.palette.run.ok", {
              steps: steps.length,
              ms: Math.round(performance.now() - t0),
            }),
          );
          return;
        }

        // Pack / trace already handled by entryHref above.
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const tpl: TKey =
          entry.kind === "playbook"
            ? "operator.palette.run.fail"
            : entry.kind === "awareness"
              ? "operator.palette.snapshot.fail"
              : "operator.palette.invoked.fail";
        finishWithResult("err", t(tpl, { message }));
      }
    },
    [navigate, close, t, finishWithResult],
  );

  const onKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (flat.length) setActiveIdx(i => (i + 1) % flat.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (flat.length) setActiveIdx(i => (i - 1 + flat.length) % flat.length);
      } else if (e.key === "Enter") {
        if (flat[activeIdx]) {
          e.preventDefault();
          activate(flat[activeIdx]!);
        }
      }
    },
    [flat, activeIdx, activate],
  );

  // --- Render -------------------------------------------------------
  const counts = useMemo(() => groupCounts(index), [index]);
  const total = totalCount(index);
  const errorList = (Object.entries(errors) as [OperatorGroup, string | null][])
    .filter(([, msg]) => Boolean(msg))
    .map(([group, message]) =>
      t("operator.palette.error.detail", {
        group,
        message: String(message),
      }),
    );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label={t("operator.palette.title")}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(2,4,12,0.74)] px-4 pt-[10vh] backdrop-blur-md"
          onClick={close}
        >
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            onClick={e => e.stopPropagation()}
            onKeyDown={onKeyDown}
            initial={{ opacity: 0, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.99 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-2xl overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65)]"
            style={{ borderTopColor: "rgba(99,102,241,0.45)" }}
          >
            {/* Header */}
            <header className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
              <span
                aria-hidden
                className="font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3"
              >
                ⌘.
              </span>
              <input
                ref={inputRef}
                value={query}
                onChange={e => {
                  setQuery(e.target.value);
                  setActiveIdx(0);
                }}
                placeholder={t("operator.palette.placeholder")}
                aria-label={t("operator.palette.title")}
                className="flex-1 bg-transparent font-display text-[14px] tracking-[-0.005em] text-ink outline-none placeholder:text-ink-3"
              />
              <button
                type="button"
                onClick={refresh}
                disabled={loading}
                className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-accent disabled:opacity-50"
              >
                {loading
                  ? t("operator.palette.refreshing")
                  : t("operator.palette.refresh")}
              </button>
              <button
                type="button"
                onClick={close}
                className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-alert"
                aria-label="close"
              >
                esc
              </button>
            </header>

            {/* Group filter chips */}
            <div className="flex flex-wrap items-center gap-2 border-b border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px]">
              <button
                type="button"
                onClick={() => setGroupFilter("all")}
                className={`rounded-full border px-2 py-0.5 ${
                  groupFilter === "all"
                    ? "border-accent text-accent"
                    : "border-line/60 text-ink-2 hover:border-line hover:text-ink"
                }`}
              >
                {t("operator.palette.group.all")} · {total}
              </button>
              {ALL_GROUPS.map(g => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setGroupFilter(g)}
                  className={`rounded-full border px-2 py-0.5 ${
                    groupFilter === g
                      ? "border-accent text-accent"
                      : "border-line/60 text-ink-2 hover:border-line hover:text-ink"
                  }`}
                >
                  {t(`operator.palette.group.${g}` as TKey)} · {counts[g]}
                </button>
              ))}
              {loading ? (
                <span className="ml-auto text-ink-3">
                  {t("operator.palette.loading")}
                </span>
              ) : null}
            </div>

            {/* Error banner */}
            {errorList.length > 0 && (
              <div className="border-b border-alert/40 bg-alert/[0.06] px-4 py-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-alert">
                <p className="mb-1">{t("operator.palette.error")}</p>
                <ul className="list-disc pl-4">
                  {errorList.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Result strip (busy / outcome) */}
            {activity.kind === "busy" && (
              <div className="border-b border-line/40 px-4 py-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
                {t("operator.palette.invoking")}
              </div>
            )}
            {activity.kind === "result" && (
              <div
                className={`border-b px-4 py-2 font-mono-tech text-[10px] uppercase tracking-[1.6px] ${
                  activity.tone === "ok"
                    ? "border-line/40 text-accent"
                    : activity.tone === "warn"
                      ? "border-amber/40 text-amber"
                      : "border-alert/40 text-alert"
                }`}
              >
                {activity.message}
              </div>
            )}

            {/* List */}
            <div className="max-h-[55vh] overflow-y-auto">
              {loading && total === 0 ? (
                <p className="px-4 py-10 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
                  {t("operator.palette.loading")}
                </p>
              ) : flat.length === 0 ? (
                <div className="px-4 py-10 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
                  <p className="mb-1 text-ink-2">
                    {t("operator.palette.empty.title")}
                  </p>
                  <p>{t("operator.palette.empty.body")}</p>
                </div>
              ) : (
                groups.map(g => (
                  <section key={g.name}>
                    <div className="px-4 pt-3 pb-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                      {g.name === "recent"
                        ? t("operator.palette.recent")
                        : g.name === "matches"
                          ? null
                          : t(`operator.palette.group.${g.name}` as TKey)}
                    </div>
                    <ul role="listbox">
                      {g.entries.map(entry => {
                        const flatIdx = flat.indexOf(entry);
                        const active = flatIdx === activeIdx;
                        const busy =
                          activity.kind === "busy" &&
                          activity.entryId === entry.id;
                        return (
                          <li key={entry.id}>
                            <button
                              type="button"
                              onClick={() => activate(entry)}
                              onMouseEnter={() => setActiveIdx(flatIdx)}
                              className={`flex w-full items-center gap-3 border-l-2 px-4 py-2.5 text-left transition-colors ${
                                active
                                  ? "border-accent bg-accent/[0.06]"
                                  : "border-transparent hover:bg-bg-2"
                              }`}
                            >
                              <KindBadge entry={entry} t={t} />
                              <span className="flex-1 min-w-0">
                                <span className="block truncate font-display text-[13.5px] text-ink">
                                  {entry.title}
                                </span>
                                <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                                  {entry.hint}
                                </span>
                              </span>
                              <ActionLabel
                                entry={entry}
                                busy={busy}
                                t={t}
                              />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))
              )}
            </div>

            {/* Footer */}
            <footer className="flex items-center justify-between border-t border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              <span className="flex items-center gap-3">
                <span>{t("operator.palette.footer.nav")}</span>
                <span>{t("operator.palette.footer.invoke")}</span>
                <span>{t("operator.palette.footer.close")}</span>
              </span>
              <span>
                {t("operator.palette.footer.count", { n: flat.length })}
              </span>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function KindBadge({
  entry,
  t,
}: {
  entry: OperatorEntry;
  t: (k: TKey, vars?: Record<string, string | number>) => string;
}) {
  const tone =
    entry.kind === "pack"
      ? "border-accent/60 text-accent"
      : entry.kind === "action"
        ? entry.destructive
          ? "border-alert/60 text-alert"
          : "border-line text-ink-2"
        : entry.kind === "playbook"
          ? "border-line-strong text-ink-2"
          : entry.kind === "awareness"
            ? "border-line text-ink-2"
            : "border-line/60 text-ink-3";
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] ${tone}`}
    >
      {t(`operator.palette.kind.${entry.kind}` as TKey)}
      {entry.kind === "action" && entry.destructive
        ? ` · ${t("operator.palette.destructive")}`
        : ""}
    </span>
  );
}

function ActionLabel({
  entry,
  busy,
  t,
}: {
  entry: OperatorEntry;
  busy: boolean;
  t: (k: TKey, vars?: Record<string, string | number>) => string;
}) {
  if (busy) {
    if (entry.kind === "playbook") {
      return (
        <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-accent">
          {t("operator.palette.running")}
        </span>
      );
    }
    if (entry.kind === "awareness") {
      return (
        <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-accent">
          {t("operator.palette.snapshotting")}
        </span>
      );
    }
    return (
      <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-accent">
        {t("operator.palette.invoking")}
      </span>
    );
  }
  const label =
    entry.kind === "pack" || entry.kind === "trace"
      ? t("operator.palette.open")
      : entry.kind === "action"
        ? t("operator.palette.invoke")
        : entry.kind === "playbook"
          ? t("operator.palette.run")
          : t("operator.palette.snapshot");
  const arrow = entry.kind === "trace" ? "↗" : "→";
  return (
    <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
      {label} {arrow}
    </span>
  );
}
