/**
 * <BrandHairline /> — the meeet brand-triad sweep used at the top of
 * every dialog, card, divider, and modal. Single source of truth for
 * what was 6× duplicated `linear-gradient(90deg, transparent 0%, …)`
 * declarations across the marketing surface.
 *
 * Variants:
 *   "absolute"  — for cards / panels with `relative overflow-hidden`
 *   "static"    — for inline dividers between sections
 *   "sticky"    — full-width route-transition ribbon (RouteTransition
 *                 already owns its own — listed for parity)
 *
 * Always 1px tall (HTML). The 2px variant is reserved for SVG / print
 * (see public/og-*.svg).
 */

interface BrandHairlineProps {
  variant?: "absolute" | "static";
  /** Optional className to position absolute hairlines (top, inset-x, …) */
  className?: string;
}

export function BrandHairline({
  variant = "absolute",
  className = "",
}: BrandHairlineProps) {
  if (variant === "static") {
    return (
      <div
        aria-hidden
        className={`h-px w-full ${className}`}
        style={{ background: "var(--brand-sweep)" }}
      />
    );
  }
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-x-0 top-0 h-px ${className}`}
      style={{ background: "var(--brand-sweep)" }}
    />
  );
}
