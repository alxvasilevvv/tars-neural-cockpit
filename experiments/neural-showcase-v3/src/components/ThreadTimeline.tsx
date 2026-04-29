/**
 * <ThreadTimeline /> — collapsible per-thread observability feed.
 *
 * Polish (Claude design pass):
 *   - vertical spine running through every entry
 *   - group-by-hour with sticky tiny labels
 *   - source-specific icons for at-a-glance scanning
 *   - smooth fade/slide on new entries when the timeline auto-refreshes
 *
 * Functional contract is unchanged — still consumes
 * `useThreadTimeline()` from `@/lib/search` and obeys the polling
 * interval set by Cursor.
 */

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronRight,
  Hash,
  Wrench,
  Paperclip,
  Activity,
} from "lucide-react";

import { useThreadTimeline, type ThreadTimelineEntry } from "@/lib/search";

interface ThreadTimelineProps {
  threadId: string | null;
  defaultOpen?: boolean;
}

const SOURCE_META: Record<
  ThreadTimelineEntry["source"],
  { label: string; tone: string; Icon: typeof Hash }
> = {
  message:    { label: "MSG",  tone: "var(--color-accent)",       Icon: Hash },
  tool_call:  { label: "TOOL", tone: "var(--color-meeet-cyan, #06B6D4)", Icon: Wrench },
  attachment: { label: "ATT",  tone: "var(--color-meeet-violet, #8B5CF6)", Icon: Paperclip },
  event:      { label: "EV",   tone: "var(--color-ink-2)",        Icon: Activity },
};

interface Group {
  hourKey: string;
  hourLabel: string;
  entries: ThreadTimelineEntry[];
}

export function ThreadTimeline({
  threadId,
  defaultOpen = false,
}: ThreadTimelineProps) {
  const [open, setOpen] = useState(defaultOpen);
  const tl = useThreadTimeline(open ? threadId : null, {
    autoRefreshMs: 6000,
    limit: 200,
  });

  const counts = useMemo(() => {
    const c = { message: 0, tool_call: 0, attachment: 0, event: 0 };
    for (const e of tl.entries) {
      c[e.source] = (c[e.source] || 0) + 1;
    }
    return c;
  }, [tl.entries]);

  // Group entries by hour for at-a-glance pacing
  const groups: Group[] = useMemo(() => {
    const out: Group[] = [];
    let current: Group | null = null;
    for (const e of tl.entries) {
      const d = new Date(e.ts * 1000);
      const hk = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}`;
      if (!current || current.hourKey !== hk) {
        current = {
          hourKey: hk,
          hourLabel: d.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
          }).replace(/:\d{2}$/, ":00"),
          entries: [],
        };
        out.push(current);
      }
      current.entries.push(e);
    }
    return out;
  }, [tl.entries]);

  return (
    <section className="mt-3 overflow-hidden rounded-[10px] border border-line bg-bg-1/60">
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        aria-expanded={open}
        className="group flex w-full items-center justify-between gap-3 px-4 py-2.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:text-ink"
      >
        <span className="flex items-center gap-2.5">
          {open ? (
            <ChevronDown size={11} strokeWidth={2} className="opacity-70" />
          ) : (
            <ChevronRight size={11} strokeWidth={2} className="opacity-70" />
          )}
          <span className="text-ink">timeline</span>
          {open ? (
            <span className="text-ink-3">
              · {counts.message} msg · {counts.tool_call} tool ·{" "}
              {counts.attachment} att · {counts.event} ev
            </span>
          ) : (
            <span className="text-ink-3">· tap to expand</span>
          )}
        </span>
        {open && tl.loading && (
          <span className="text-ink-3">refreshing…</span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t border-line"
          >
            <div className="relative px-4 py-3">
              {tl.error && (
                <p className="font-mono-tech text-[10.5px] text-alert">
                  timeline · {tl.error}
                </p>
              )}
              {tl.loading && tl.entries.length === 0 && !tl.error && (
                <p className="font-mono-tech text-[10.5px] text-ink-3">indexing…</p>
              )}
              {!tl.loading && tl.entries.length === 0 && !tl.error && (
                <p className="font-mono-tech text-[10.5px] text-ink-3">
                  no events on this thread yet.
                </p>
              )}

              {groups.length > 0 && (
                <div className="relative">
                  {/* Vertical spine */}
                  <span
                    aria-hidden
                    className="absolute left-[55px] top-1 bottom-1 w-px"
                    style={{
                      background:
                        "linear-gradient(to bottom, transparent 0%, var(--color-line-strong) 12%, var(--color-line-strong) 88%, transparent 100%)",
                    }}
                  />

                  {groups.map(group => (
                    <div key={group.hourKey} className="relative pb-1">
                      {/* Hour label */}
                      <div className="sticky top-0 z-10 -ml-4 mb-1 inline-block rounded-r-md bg-bg-1/85 py-0.5 pl-4 pr-3 font-mono-tech text-[9px] uppercase tracking-[2.4px] text-ink-3 backdrop-blur-sm">
                        {group.hourLabel}
                      </div>

                      <ol className="flex flex-col gap-1 font-mono-tech text-[10.5px]">
                        <AnimatePresence initial={false}>
                          {group.entries.map(entry => {
                            const meta = SOURCE_META[entry.source];
                            const Icon = meta.Icon;
                            return (
                              <motion.li
                                key={entry.id}
                                layout
                                initial={{ opacity: 0, x: -4 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                                className="relative grid grid-cols-[60px_22px_1fr] items-baseline gap-2"
                              >
                                <time
                                  className="text-ink-3"
                                  dateTime={String(entry.ts)}
                                >
                                  {fmtTime(entry.ts)}
                                </time>
                                {/* Spine dot + icon glyph */}
                                <span
                                  aria-hidden
                                  className="relative grid h-5 w-5 place-items-center self-center rounded-full bg-bg-1"
                                  style={{
                                    boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${meta.tone} 45%, transparent)`,
                                    color: meta.tone,
                                  }}
                                  title={entry.source}
                                >
                                  <Icon size={10} strokeWidth={1.8} />
                                </span>
                                <span className="flex min-w-0 items-baseline gap-2 truncate">
                                  <span className="truncate text-ink">{entry.title}</span>
                                  {entry.summary && (
                                    <span className="truncate text-ink-3">
                                      · {entry.summary}
                                    </span>
                                  )}
                                </span>
                              </motion.li>
                            );
                          })}
                        </AnimatePresence>
                      </ol>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function fmtTime(ts: number): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
