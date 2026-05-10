/**
 * <TutorialTooltip /> — Wave 92
 *
 * Reusable overlay tooltip for the workshop tutorial walkthrough.
 *
 * Two render modes:
 *
 *   1. Anchored (anchor !== null) — popover positioned next to a DOM
 *      ref, with a backdrop dim + cutout around the anchor so the
 *      attached UI element reads as the focal point of the step.
 *      Auto-flips top/bottom/left/right based on viewport space.
 *
 *   2. Centred (anchor === null) — modal card in the middle of the
 *      viewport, used for "welcome" / "final" steps that don't have
 *      a DOM target.
 *
 * Accessibility:
 *   - role="dialog" + aria-modal="true" + aria-labelledby
 *   - focus trap via useFocusTrap (Tab/Shift+Tab cycles within)
 *   - Esc skips entire tour (caller wires onSkip)
 *   - Enter advances (default form submit on Next button)
 *   - Touch-friendly: every interactive control ≥44px high
 *
 * Style constraints (Wave 92 spec):
 *   - Brand tokens (success-green for Next per workshop pillar accent)
 *   - Defensive `initial: opacity: 1` motion (Wave 70 pattern)
 *   - Polypill positioning, not fixed top/bottom
 */

import { motion } from "framer-motion";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useFocusTrap } from "@/lib/useFocusTrap";

/** Side the popover prefers — auto-flipped if there's no room. */
type Side = "top" | "bottom" | "left" | "right";

/** Box describing where the spotlight cutout / arrow should sit. */
interface AnchorRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface TutorialTooltipProps {
  /**
   * Element the tooltip points at. Pass `null` for a centred
   * intro/outro card with no anchor.
   */
  anchor: HTMLElement | null;
  /** Step heading (also used for aria-labelledby). */
  title: string;
  /** Body copy — one or two short sentences. */
  body: string;
  /** Step number (1-indexed). */
  step: number;
  /** Total number of steps. */
  total: number;
  /** Advance handler (or finish if last step). */
  onNext: () => void;
  /** Skip handler — abandons the tour. */
  onSkip: () => void;
  /** Back button handler — omitted on step 0. */
  onPrev?: () => void;
  /** Optional override for Next button label (defaults vary by position). */
  nextLabel?: string;
  /**
   * Optional CTA after the Next button — e.g. "Pick a starter" on
   * the final step which navigates somewhere instead of just closing.
   */
  primaryHref?: string;
  primaryLabel?: string;
}

/** Minimal padding from viewport edges so the popover never clips. */
const VIEWPORT_PAD = 12;
/** Gap between the anchor element and the popover. */
const ANCHOR_GAP = 12;
/** Spotlight cutout radius. */
const SPOTLIGHT_RADIUS = 10;
/** Approximate popover dimensions used for positioning math. */
const POPOVER_W = 360;
const POPOVER_H = 220;

function readRect(el: HTMLElement | null): AnchorRect | null {
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

/** Pick the side with the most room. */
function pickSide(rect: AnchorRect, vw: number, vh: number): Side {
  const above = rect.top;
  const below = vh - (rect.top + rect.height);
  const leftSpace = rect.left;
  const rightSpace = vw - (rect.left + rect.width);
  // Prefer right/bottom for natural left-to-right reading flow.
  const candidates: Array<[Side, number]> = [
    ["right", rightSpace >= POPOVER_W + ANCHOR_GAP ? rightSpace + 1000 : rightSpace],
    ["bottom", below >= POPOVER_H + ANCHOR_GAP ? below + 800 : below],
    ["left", leftSpace >= POPOVER_W + ANCHOR_GAP ? leftSpace + 600 : leftSpace],
    ["top", above >= POPOVER_H + ANCHOR_GAP ? above + 400 : above],
  ];
  candidates.sort((a, b) => b[1] - a[1]);
  return candidates[0][0];
}

function computePosition(
  rect: AnchorRect,
  side: Side,
  vw: number,
  vh: number,
): { top: number; left: number } {
  let top = 0;
  let left = 0;
  switch (side) {
    case "right":
      top = rect.top + rect.height / 2 - POPOVER_H / 2;
      left = rect.left + rect.width + ANCHOR_GAP;
      break;
    case "left":
      top = rect.top + rect.height / 2 - POPOVER_H / 2;
      left = rect.left - POPOVER_W - ANCHOR_GAP;
      break;
    case "bottom":
      top = rect.top + rect.height + ANCHOR_GAP;
      left = rect.left + rect.width / 2 - POPOVER_W / 2;
      break;
    case "top":
      top = rect.top - POPOVER_H - ANCHOR_GAP;
      left = rect.left + rect.width / 2 - POPOVER_W / 2;
      break;
  }
  // Clamp to viewport.
  top = Math.max(VIEWPORT_PAD, Math.min(top, vh - POPOVER_H - VIEWPORT_PAD));
  left = Math.max(VIEWPORT_PAD, Math.min(left, vw - POPOVER_W - VIEWPORT_PAD));
  return { top, left };
}

export function TutorialTooltip({
  anchor,
  title,
  body,
  step,
  total,
  onNext,
  onSkip,
  onPrev,
  nextLabel,
  primaryHref,
  primaryLabel,
}: TutorialTooltipProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  const [rect, setRect] = useState<AnchorRect | null>(() => readRect(anchor));
  const [viewport, setViewport] = useState({
    vw: typeof window !== "undefined" ? window.innerWidth : 1280,
    vh: typeof window !== "undefined" ? window.innerHeight : 800,
  });

  // Track anchor position — re-read on layout/scroll/resize so the
  // popover sticks even if the page shifts (sticky rails, etc.).
  useLayoutEffect(() => {
    setRect(readRect(anchor));
  }, [anchor]);

  useEffect(() => {
    if (!anchor) return;
    const update = () => {
      setRect(readRect(anchor));
      setViewport({ vw: window.innerWidth, vh: window.innerHeight });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [anchor]);

  // Esc skips the entire tour (a11y spec).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onSkip();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSkip]);

  // Scroll the anchor into view so the spotlight isn't off-screen.
  useEffect(() => {
    if (anchor) {
      try {
        anchor.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
      } catch {
        /* older browsers — skip */
      }
    }
  }, [anchor]);

  const position = useMemo(() => {
    if (!rect) return null;
    const side = pickSide(rect, viewport.vw, viewport.vh);
    return { side, ...computePosition(rect, side, viewport.vw, viewport.vh) };
  }, [rect, viewport]);

  const isCentred = !rect;
  const labelId = `tutorial-step-${step}`;

  const nextText =
    nextLabel ?? (step >= total ? "Finish" : "Next");

  return (
    <div
      className="fixed inset-0 z-[110]"
      // Defensive — always opaque-ish so framer never blanks the layer.
      style={{ pointerEvents: "auto" }}
    >
      {/* Backdrop dim + spotlight cutout */}
      <BackdropWithCutout rect={rect} />

      {/* Popover */}
      <motion.div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelId}
        tabIndex={-1}
        initial={{ opacity: 1, y: 0, scale: 1 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="absolute grid grid-rows-[auto_1fr_auto] overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 text-ink shadow-[0_30px_120px_rgba(0,0,0,0.65)] focus:outline-none"
        style={
          isCentred
            ? {
                width: `min(${POPOVER_W}px, calc(100vw - ${VIEWPORT_PAD * 2}px))`,
                left: "50%",
                top: "50%",
                transform: "translate(-50%, -50%)",
              }
            : {
                width: `min(${POPOVER_W}px, calc(100vw - ${VIEWPORT_PAD * 2}px))`,
                top: position?.top ?? 0,
                left: position?.left ?? 0,
              }
        }
      >
        {/* Header row */}
        <header className="flex items-center justify-between border-b border-line/60 px-5 py-3">
          <span
            className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
            style={{ color: "var(--color-success)" }}
          >
            Workshop tour · {step} of {total}
          </span>
          <button
            type="button"
            onClick={onSkip}
            aria-label="Skip workshop tutorial"
            className="grid h-11 min-w-[44px] items-center rounded-md px-2 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink"
          >
            Skip
          </button>
        </header>

        {/* Body */}
        <div className="px-5 py-5">
          <h2
            id={labelId}
            className="mb-2 font-display text-[18px] leading-[1.2] tracking-[-0.005em] text-ink"
          >
            {title}
          </h2>
          <p className="text-[13px] leading-[1.55] text-ink-2">{body}</p>
        </div>

        {/* Footer — Back / Next / primary CTA */}
        <footer className="flex items-center justify-between gap-2 border-t border-line/60 px-5 py-3">
          <div className="flex items-center gap-1.5" aria-hidden>
            {Array.from({ length: total }).map((_, i) => (
              <span
                key={i}
                className="h-1.5 w-1.5 rounded-full transition-all"
                style={{
                  background:
                    i + 1 === step
                      ? "var(--color-success)"
                      : "var(--color-line-strong)",
                  transform: i + 1 === step ? "scale(1.3)" : "scale(1)",
                }}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            {onPrev && step > 1 && (
              <button
                type="button"
                onClick={onPrev}
                className="inline-flex h-11 min-w-[44px] items-center justify-center rounded-md border border-line bg-transparent px-3 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
              >
                Back
              </button>
            )}
            {primaryHref ? (
              <a
                href={primaryHref}
                onClick={() => onNext()}
                className="inline-flex h-11 min-w-[44px] items-center justify-center rounded-md px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-white transition-opacity hover:opacity-95"
                style={{
                  background: "var(--color-success)",
                  boxShadow: "0 6px 22px rgba(16,185,129,0.35)",
                }}
              >
                {primaryLabel ?? nextText}
              </a>
            ) : (
              <button
                type="button"
                onClick={onNext}
                autoFocus
                className="inline-flex h-11 min-w-[44px] items-center justify-center rounded-md px-4 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-white transition-opacity hover:opacity-95"
                style={{
                  background: "var(--color-success)",
                  boxShadow: "0 6px 22px rgba(16,185,129,0.35)",
                }}
              >
                {nextText}
              </button>
            )}
          </div>
        </footer>
      </motion.div>
    </div>
  );
}

/**
 * Backdrop dim with a rounded-rect cutout around the anchor so the
 * highlighted UI element appears un-dimmed. Falls back to a solid
 * dim layer when there's no anchor (centred intro/outro).
 *
 * Implementation note: we render two divs — a full-screen dim layer,
 * and a transparent "punch" sitting exactly over the anchor with a
 * box-shadow that paints the dim everywhere except the anchor itself.
 * Avoids SVG masks (cheaper at runtime, plays nice with dark-theme).
 */
function BackdropWithCutout({ rect }: { rect: AnchorRect | null }) {
  if (!rect) {
    return (
      <motion.div
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="absolute inset-0"
        style={{ background: "rgba(2,4,12,0.78)", backdropFilter: "blur(6px)" }}
        aria-hidden
      />
    );
  }
  return (
    <>
      <motion.div
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="absolute inset-0"
        style={{ background: "rgba(2,4,12,0.55)", backdropFilter: "blur(2px)" }}
        aria-hidden
      />
      <div
        aria-hidden
        className="absolute pointer-events-none rounded-[10px]"
        style={{
          top: rect.top - 6,
          left: rect.left - 6,
          width: rect.width + 12,
          height: rect.height + 12,
          borderRadius: SPOTLIGHT_RADIUS,
          // Box-shadow large enough to cover any viewport, painting
          // dim everywhere except the cutout. Plus a subtle ring so
          // the highlighted element reads as "selected".
          boxShadow:
            "0 0 0 9999px rgba(2,4,12,0.55), inset 0 0 0 1.5px rgba(16,185,129,0.45)",
        }}
      />
    </>
  );
}
