/**
 * ⌘J / Ctrl+J jump palette — navigation over threads, attachments,
 * saved searches, packs, and playbooks via POST /api/search/jump.
 *
 * Complements ⌘K (content search). Playbook / saved-search picks
 * pre-fill the operator palette (⌘.) so the operator can run or
 * adjust without an automatic POST from here.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  fetchJump,
  useGlobalShortcut,
  type JumpHit,
  type JumpHitKind,
} from "@/lib/search";
import { useFocusTrap } from "@/lib/useFocusTrap";

function JumpKindBadge({ kind }: { kind: JumpHitKind }) {
  const tone =
    kind === "thread"
      ? "border-accent/60 text-accent"
      : kind === "attachment"
        ? "border-line-strong text-ink-2"
        : kind === "saved_search"
          ? "border-line text-ink-2"
          : kind === "pack"
            ? "border-line/60 text-amber"
            : "border-line/60 text-ink-3";
  const label =
    kind === "saved_search"
      ? "saved"
      : kind === "playbook"
        ? "playbook"
        : kind;
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.6px] ${tone}`}
    >
      {label}
    </span>
  );
}

export function JumpPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<JumpHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reqToken = useRef(0);

  useGlobalShortcut("j", () => setOpen((p) => !p));

  // WCAG 2.1.2 — Tab must not escape to background while open.
  useFocusTrap(dialogRef, open);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setHits([]);
      setError(null);
      setLoading(false);
      setActiveIdx(0);
      abortRef.current?.abort();
      return;
    }
    const t = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const trimmed = query.trim();
    const delay = trimmed ? 160 : 0;
    const handle = window.setTimeout(() => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const my = ++reqToken.current;
      setLoading(true);
      setError(null);
      fetchJump(trimmed, { limit: 28, signal: ctrl.signal })
        .then((res) => {
          if (my !== reqToken.current) return;
          setHits(res.hits ?? []);
          setLoading(false);
        })
        .catch((exc: unknown) => {
          if (my !== reqToken.current) return;
          if ((exc as Error)?.name === "AbortError") return;
          setError(String((exc as Error)?.message ?? exc));
          setHits([]);
          setLoading(false);
        });
    }, delay);
    return () => window.clearTimeout(handle);
  }, [open, query]);

  useEffect(() => {
    if (activeIdx >= hits.length) setActiveIdx(0);
  }, [hits.length, activeIdx]);

  const activate = useCallback(
    (hit: JumpHit) => {
      switch (hit.kind) {
        case "thread":
          window.dispatchEvent(
            new CustomEvent("tars:open-thread", { detail: { threadId: hit.id } }),
          );
          break;
        case "attachment": {
          const tid = hit.ref.thread_id;
          if (typeof tid === "string" && tid) {
            window.dispatchEvent(
              new CustomEvent("tars:open-thread", { detail: { threadId: tid } }),
            );
          }
          break;
        }
        case "pack":
          navigate(`/cockpit?pack=${encodeURIComponent(hit.id)}`);
          break;
        case "playbook":
        case "saved_search": {
          const qPref =
            hit.kind === "saved_search" && typeof hit.ref.query === "string"
              ? hit.ref.query
              : hit.id;
          window.dispatchEvent(
            new CustomEvent("tars:operator-palette-prefill", {
              detail: { query: qPref },
            }),
          );
          break;
        }
        default:
          break;
      }
      close();
    },
    [close, navigate],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (hits.length) setActiveIdx((i) => (i + 1) % hits.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        if (hits.length) setActiveIdx((i) => (i - 1 + hits.length) % hits.length);
        return;
      }
      if (e.key === "Enter" && hits[activeIdx]) {
        e.preventDefault();
        activate(hits[activeIdx]);
      }
    },
    [hits, activeIdx, close, activate],
  );

  if (!open) return null;

  return (
    <motion.div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="jump"
      tabIndex={-1}
      onKeyDown={onKeyDown}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-[52] flex items-start justify-center bg-[rgba(2,4,12,0.72)] px-4 pt-[10vh] backdrop-blur-md"
      onClick={close}
    >
      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 8, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.99 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-xl overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65),0_0_0_1px_rgba(52,211,153,0.16)]"
        style={{ borderTopColor: "rgba(52,211,153,0.35)" }}
      >
        <header className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
          <span aria-hidden className="font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-3">
            ⌘J
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="jump to thread · file · pack · playbook…"
            aria-label="jump query"
            className="flex-1 bg-transparent font-display text-[14px] tracking-[-0.005em] text-ink outline-none placeholder:text-ink-3"
          />
          <button
            type="button"
            onClick={close}
            className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-alert"
            aria-label="close jump palette"
          >
            esc
          </button>
        </header>

        <div className="max-h-[55vh] overflow-y-auto">
          {!query.trim() && !loading && hits.length === 0 && !error ? (
            <p className="px-4 py-6 font-mono-tech text-[10.5px] leading-[1.6] uppercase tracking-[1.6px] text-ink-3">
              Recents load on open — type to fuzzy-match threads, attachments,
              saved searches, packs, playbooks.
            </p>
          ) : null}
          {error ? (
            <p className="px-4 py-6 text-center font-mono-tech text-[10.5px] text-alert" role="alert">
              {error}
            </p>
          ) : null}
          {!error && hits.length === 0 && !loading && query.trim() ? (
            <p className="px-4 py-6 text-center font-mono-tech text-[10.5px] text-ink-3">
              no matches
            </p>
          ) : null}
          {hits.length > 0 ? (
            <ul role="listbox" aria-label="jump targets">
              {hits.map((hit, i) => (
                <li key={`${hit.kind}-${hit.id}-${i}`}>
                  <button
                    type="button"
                    onClick={() => activate(hit)}
                    onMouseEnter={() => setActiveIdx(i)}
                    className={`block w-full border-l-2 px-4 py-3 text-left transition-colors ${
                      i === activeIdx
                        ? "border-accent bg-accent/5"
                        : "border-transparent hover:bg-bg-2"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <JumpKindBadge kind={hit.kind} />
                      <span className="flex-1 truncate font-display text-[13.5px] text-ink">
                        {hit.label}
                      </span>
                      <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.6px] text-ink-3">
                        {hit.score.toFixed(3)}
                      </span>
                    </div>
                    <p className="mt-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                      {hit.sublabel}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {loading ? (
            <p className="px-4 py-3 font-mono-tech text-[10.5px] text-ink-3">loading…</p>
          ) : null}
        </div>

        <footer className="flex items-center justify-between border-t border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
          <span>↑↓ navigate · ↵ open · esc close</span>
          <span>{hits.length} rows</span>
        </footer>
      </motion.div>
    </motion.div>
  );
}
