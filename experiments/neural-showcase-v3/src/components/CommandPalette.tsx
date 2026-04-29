/**
 * ⌘K command palette — global search across chunks / messages / traces.
 *
 * Design principles (Phase L8 functional pass — Claude owns the
 * visual polish):
 *
 * - Open with ⌘K / Ctrl-K from anywhere; close with Escape.
 * - Debounced search via `useDebouncedSearch` (220 ms).
 * - Keyboard-first: ↑/↓ to navigate, Enter to select.
 * - Each hit is a deep link — chunks/messages take you to the thread,
 *   trace hits surface the trace id for the meeet drilldown.
 * - Scope chips at the top let the operator restrict the search to
 *   one source.
 *
 * The palette renders nothing while closed (no overlay, no listeners
 * other than the global ⌘K hotkey).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  useDebouncedSearch,
  useGlobalShortcut,
  type SearchHit,
  type SearchScope,
} from "@/lib/search";

interface CommandPaletteProps {
  /** Called when the operator picks a result. */
  onSelect?: (hit: SearchHit) => void;
  /** Called when the operator picks a thread (after a chunk/message hit). */
  onJumpToThread?: (threadId: string, ref: SearchHit["ref"]) => void;
}

const SCOPES: { id: SearchScope; label: string }[] = [
  { id: "all", label: "all" },
  { id: "chunks", label: "files" },
  { id: "messages", label: "messages" },
  { id: "traces", label: "traces" },
];

export function CommandPalette({
  onSelect,
  onJumpToThread,
}: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const search = useDebouncedSearch({ initialScope: "all", topK: 14 });
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useGlobalShortcut("k", () => setOpen((prev) => !prev));

  // Reset on close.
  useEffect(() => {
    if (!open) {
      search.clear();
      setActiveIdx(0);
      return;
    }
    const handle = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(handle);
  }, [open, search]);

  // Keep the active index in bounds when results change.
  useEffect(() => {
    if (!search.result) {
      setActiveIdx(0);
      return;
    }
    if (activeIdx >= search.result.hits.length) {
      setActiveIdx(0);
    }
  }, [search.result, activeIdx]);

  const close = useCallback(() => setOpen(false), []);

  const choose = useCallback(
    (hit: SearchHit) => {
      onSelect?.(hit);
      const tid = hit.ref?.thread_id;
      if (tid && typeof tid === "string") {
        onJumpToThread?.(tid, hit.ref);
      }
      close();
    },
    [close, onJumpToThread, onSelect],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const hits = search.result?.hits ?? [];
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (hits.length) {
          setActiveIdx((idx) => (idx + 1) % hits.length);
        }
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        if (hits.length) {
          setActiveIdx((idx) => (idx - 1 + hits.length) % hits.length);
        }
        return;
      }
      if (e.key === "Enter") {
        if (hits[activeIdx]) {
          e.preventDefault();
          choose(hits[activeIdx]);
        }
      }
    },
    [search.result, activeIdx, close, choose],
  );

  if (!open) return null;

  const hits = search.result?.hits ?? [];

  return (
    <motion.div
      role="dialog"
      aria-label="search"
      onKeyDown={onKeyDown}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(2,4,12,0.72)] px-4 pt-[10vh] backdrop-blur-md"
      onClick={close}
    >
      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 8, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.99 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-xl overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65),0_0_0_1px_rgba(99,102,241,0.18)]"
        style={{
          // top hairline accent
          borderTopColor: "rgba(99,102,241,0.45)",
        }}
      >
        <header className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
          <span aria-hidden className="font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3">
            ⌘K
          </span>
          <input
            ref={inputRef}
            value={search.query}
            onChange={(e) => search.setQuery(e.target.value)}
            placeholder="search files · messages · traces…"
            aria-label="search query"
            className="flex-1 bg-transparent font-display text-[14px] tracking-[-0.005em] text-ink outline-none placeholder:text-ink-3"
          />
          <button
            type="button"
            onClick={close}
            className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-alert"
            aria-label="close palette"
          >
            esc
          </button>
        </header>

        <div className="flex flex-wrap items-center gap-2 border-b border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px]">
          <span className="text-ink-3">scope</span>
          {SCOPES.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => search.setScope(s.id)}
              className={`rounded-full border px-2 py-0.5 ${
                search.scope === s.id
                  ? "border-accent text-accent"
                  : "border-line/60 text-ink-2 hover:border-line hover:text-ink"
              }`}
            >
              {s.label}
              {search.result?.counts?.[
                s.id === "all" ? "chunks" : (s.id as "chunks" | "messages" | "traces")
              ] != null && s.id !== "all"
                ? ` · ${search.result.counts[s.id as "chunks" | "messages" | "traces"]}`
                : ""}
            </button>
          ))}
          {search.loading ? (
            <span className="ml-auto text-ink-3">searching…</span>
          ) : search.error ? (
            <span className="ml-auto text-alert">{search.error}</span>
          ) : null}
        </div>

        <div className="max-h-[55vh] overflow-y-auto">
          {!search.query.trim() ? (
            <Hints />
          ) : hits.length === 0 ? (
            <p className="px-4 py-6 text-center font-mono-tech text-[10.5px] text-ink-3">
              {search.loading ? "indexing…" : "no hits — try a different word"}
            </p>
          ) : (
            <ul role="listbox" aria-label="search results">
              {hits.map((hit, i) => (
                <li key={`${hit.kind}-${i}-${(hit.ref.chunk_id ?? hit.ref.msg_id ?? hit.ref.event_id) || i}`}>
                  <button
                    type="button"
                    onClick={() => choose(hit)}
                    onMouseEnter={() => setActiveIdx(i)}
                    className={`block w-full border-l-2 px-4 py-3 text-left transition-colors ${
                      i === activeIdx
                        ? "border-accent bg-accent/5"
                        : "border-transparent hover:bg-bg-2"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <KindBadge kind={hit.kind} />
                      <span className="font-display text-[13.5px] text-ink truncate flex-1">
                        {hit.title}
                      </span>
                      <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
                        {hit.score.toFixed(3)}
                      </span>
                    </div>
                    <p
                      className="mt-1 font-mono-tech text-[10.5px] leading-[1.55] text-ink-2 line-clamp-2"
                      // BM25 highlights: backend wraps matches in <mark>;
                      // we render with safe styled spans so they pop
                      // without dangerouslySetInnerHTML.
                    >
                      {renderHighlighted(hit.snippet)}
                    </p>
                    <RefLine hit={hit} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="flex items-center justify-between border-t border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
          <span>↑↓ navigate · ↵ open · esc close</span>
          <span>{search.result?.count ?? 0} hits</span>
        </footer>
      </motion.div>
    </motion.div>
  );
}

function KindBadge({ kind }: { kind: SearchHit["kind"] }) {
  const tone =
    kind === "chunk"
      ? "border-accent/60 text-accent"
      : kind === "message"
        ? "border-line text-ink-2"
        : "border-line/60 text-ink-3";
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] ${tone}`}
    >
      {kind}
    </span>
  );
}

function RefLine({ hit }: { hit: SearchHit }) {
  const ref = hit.ref || {};
  if (hit.kind === "chunk") {
    const file = (ref.filename as string | null) ?? "";
    const heading = (ref.heading as string | null) ?? "";
    const page = ref.page as number | null;
    const thread = (ref.thread_title as string | null) ?? "";
    return (
      <div className="mt-1 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
        {file}
        {heading ? ` · ${heading}` : ""}
        {page ? ` · p${page}` : ""}
        {thread ? ` · ${thread}` : ""}
      </div>
    );
  }
  if (hit.kind === "message") {
    return (
      <div className="mt-1 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
        {(ref.role as string) ?? ""} · {(ref.thread_title as string) ?? ""}
      </div>
    );
  }
  return (
    <div className="mt-1 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
      trace · {String(ref.trace_id ?? "—").slice(0, 24)}
      {ref.session_id ? ` · ses ${String(ref.session_id).slice(0, 12)}` : ""}
    </div>
  );
}

function Hints() {
  return (
    <div className="px-4 py-6 font-mono-tech text-[10.5px] leading-[1.6] uppercase tracking-[1.6px] text-ink-3">
      <p className="text-ink-2">⌘K · search across the cockpit</p>
      <ul className="mt-2 flex flex-col gap-1">
        <li>· files — every PDF / md / csv you've ingested</li>
        <li>· messages — operator + TARS turns across all threads</li>
        <li>· traces — meeet event payloads for debugging</li>
      </ul>
    </div>
  );
}

/**
 * Render BM25 snippet with `<mark>` highlights as styled spans.
 * Splits on `<mark>` / `</mark>` tags, alternating between plain text
 * and highlighted spans. Safe — no dangerouslySetInnerHTML, the input
 * is treated as text and only the explicit <mark> sentinels become
 * styling.
 */
function renderHighlighted(snippet: string) {
  if (!snippet) return null;
  const parts = snippet.split(/<mark>(.*?)<\/mark>/g);
  // Even indices = plain text; odd indices = highlighted text
  return parts.map((seg, i) => {
    if (!seg) return null;
    if (i % 2 === 0) {
      return <span key={i}>{seg}</span>;
    }
    return (
      <span
        key={i}
        className="rounded-[3px] px-[3px] py-px font-medium text-ink"
        style={{
          background: "color-mix(in srgb, var(--color-accent) 22%, transparent)",
          boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 38%, transparent)",
        }}
      >
        {seg}
      </span>
    );
  });
}

// Wrap mounted palette in AnimatePresence at usage site (Cockpit) so
// unmount transitions out cleanly.
export const CommandPaletteWithExit = ({
  onSelect,
  onJumpToThread,
}: CommandPaletteProps) => (
  <AnimatePresence>
    <CommandPalette onSelect={onSelect} onJumpToThread={onJumpToThread} />
  </AnimatePresence>
);
