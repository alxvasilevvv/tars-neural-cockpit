/**
 * HelpButton — small `?` icon rendered in the top-right of complex
 * pages. Clicking it toggles a small dark popover that explains what
 * the page is for and how to drive it.
 *
 * Wave 112 — discoverability sweep. Used on /workshop, /dashboard,
 * /onboard/org, /reports, /marketplace, /compliance, /inbox,
 * /workspaces. Lighter than a full tour overlay (which the workshop
 * pages already have via WorkshopTutorial); the help button is a
 * passive escape hatch for "what is this surface?" questions.
 *
 * a11y: button has aria-expanded / aria-controls; popover is hidden
 * via `[hidden]` so screen readers don't announce stale content.
 * Pressing Escape or clicking outside closes it.
 *
 * No new dependencies — pure React + CSS variables already present
 * in the v3 design system.
 */

import { useEffect, useId, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";

export interface HelpButtonProps {
  /** Button aria-label + popover heading. */
  label: string;
  /** One- to three-paragraph body copy. Plain text. */
  body: string;
  /** Optional extra className on the wrapping span. */
  className?: string;
}

export function HelpButton({ label, body, className }: HelpButtonProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const popoverId = `help-${id}`;
  const wrapRef = useRef<HTMLSpanElement | null>(null);

  // Close on outside click + escape.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span
      ref={wrapRef}
      className={`relative inline-block ${className ?? ""}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={label}
        aria-expanded={open}
        aria-controls={popoverId}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-line/60 bg-bg-1/60 text-ink-3 transition-colors duration-150 hover:border-line-strong hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
      >
        <HelpCircle size={14} strokeWidth={1.7} aria-hidden />
      </button>
      <div
        id={popoverId}
        role="dialog"
        aria-label={label}
        hidden={!open}
        className="absolute right-0 top-9 z-30 w-[300px] rounded-md border border-line bg-bg-1/95 p-4 shadow-2xl backdrop-blur-md md:w-[360px]"
      >
        <div className="mb-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          help
        </div>
        <h3 className="mb-2 font-display text-[13px] font-semibold leading-tight text-ink">
          {label}
        </h3>
        <p className="text-[12px] leading-[1.55] text-ink-2">{body}</p>
      </div>
    </span>
  );
}

export default HelpButton;
