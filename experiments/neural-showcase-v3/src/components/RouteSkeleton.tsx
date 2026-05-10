import { BrandHairline } from "@/components/BrandHairline";

/**
 * <RouteSkeleton /> — brand-aware loading scaffold for lazy routes.
 * Replaces the previous "loading…" text fallback in <Suspense/>. Each
 * variant matches the layout grammar of its target route so the swap
 * to real content doesn't shift.
 *
 * Variants:
 *   "default"  — generic centered card
 *   "legal"    — top hairline + eyebrow + h1 + 12 paragraph rows
 *   "hero"     — heading + subline + command bar + CTA row
 *   "cockpit"  — left rail + main grid + right detail
 *   "wide"     — single full-width card with title + grid (Pitch, Press)
 *
 * Animation: a single pulse on `.skel` ribbons via @keyframes already
 * inlined here — no global keyframe additions, no JS.
 */

type Variant = "default" | "legal" | "hero" | "cockpit" | "wide" | "narrow";

const styles = (
  <style>{`
    .skel {
      background: linear-gradient(
        90deg,
        var(--color-bg-1) 0%,
        var(--color-bg-2) 50%,
        var(--color-bg-1) 100%
      );
      background-size: 200% 100%;
      animation: skel-shimmer 1.6s ease-in-out infinite;
      border-radius: 6px;
    }
    @keyframes skel-shimmer {
      0%, 100% { background-position: 200% 0; }
      50%      { background-position: -200% 0; }
    }
    @media (prefers-reduced-motion: reduce) {
      .skel { animation: none; opacity: 0.55; }
    }
  `}</style>
);

function Bar({
  w = "100%",
  h = 12,
  className = "",
}: {
  w?: string;
  h?: number;
  className?: string;
}) {
  return (
    <div
      className={`skel ${className}`}
      style={{ width: w, height: h }}
      aria-hidden
    />
  );
}

export function RouteSkeleton({ variant = "default" }: { variant?: Variant }) {
  return (
    <div
      role="status"
      aria-label="loading"
      aria-live="polite"
      className="relative min-h-[60vh]"
    >
      {styles}
      <BrandHairline />

      {variant === "legal" && (
        <div className="mx-auto max-w-[920px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
          <Bar w="120px" h={11} />
          <div className="mt-3" />
          <Bar w="62%" h={56} />
          <div className="mt-12 space-y-4">
            <Bar w="100%" h={12} />
            <Bar w="96%" h={12} />
            <Bar w="88%" h={12} />
            <Bar w="92%" h={12} />
            <Bar w="40%" h={12} />
          </div>
          <div className="mt-12 space-y-4">
            <Bar w="100%" h={12} />
            <Bar w="80%" h={12} />
            <Bar w="92%" h={12} />
            <Bar w="55%" h={12} />
          </div>
        </div>
      )}

      {variant === "hero" && (
        <div className="mx-auto max-w-[1180px] px-6 pt-24 md:px-12 md:pt-28">
          <div className="mx-auto mb-9 flex w-fit">
            <Bar w="220px" h={28} className="rounded-full" />
          </div>
          <div className="mx-auto mb-3 max-w-[800px] space-y-3 text-center">
            <Bar w="60%" h={68} className="mx-auto" />
            <Bar w="44%" h={68} className="mx-auto" />
          </div>
          <div className="mx-auto mt-7 mb-10 max-w-[440px]">
            <Bar w="100%" h={12} />
          </div>
          <div className="mx-auto mt-10 max-w-[720px] space-y-3">
            <Bar w="100%" h={56} />
            <Bar w="100%" h={88} />
          </div>
          <div className="mx-auto mt-12 flex w-fit gap-3">
            <Bar w="160px" h={48} />
            <Bar w="170px" h={48} />
          </div>
        </div>
      )}

      {variant === "cockpit" && (
        <div className="grid min-h-[70vh] grid-cols-1 gap-6 px-6 pt-14 md:grid-cols-[260px_1fr_320px] md:px-12">
          <div className="space-y-3">
            <Bar w="60%" h={14} />
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
          </div>
          <div className="space-y-3">
            <Bar w="40%" h={20} />
            <Bar w="100%" h={220} />
            <Bar w="100%" h={120} />
          </div>
          <div className="space-y-3">
            <Bar w="50%" h={14} />
            <Bar w="100%" h={140} />
            <Bar w="100%" h={80} />
          </div>
        </div>
      )}

      {variant === "wide" && (
        <div className="mx-auto max-w-[1280px] px-6 pt-14 md:px-12 md:pt-20">
          <Bar w="160px" h={11} />
          <div className="mt-4" />
          <Bar w="55%" h={56} />
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            <Bar w="100%" h={180} />
            <Bar w="100%" h={180} />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <Bar w="100%" h={120} />
            <Bar w="100%" h={120} />
            <Bar w="100%" h={120} />
          </div>
        </div>
      )}

      {variant === "narrow" && (
        <div className="mx-auto max-w-[640px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
          <Bar w="120px" h={11} />
          <div className="mt-4" />
          <Bar w="92%" h={6} className="rounded-full" />
          <div className="mt-10 space-y-4">
            <Bar w="68%" h={32} />
            <Bar w="100%" h={14} />
            <Bar w="86%" h={14} />
          </div>
          <div className="mt-12 grid grid-cols-5 gap-3">
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
            <Bar w="100%" h={56} />
          </div>
        </div>
      )}

      {variant === "default" && (
        <div className="mx-auto flex min-h-[50vh] max-w-[480px] flex-col items-center justify-center gap-3 px-6">
          <Bar w="80%" h={28} />
          <Bar w="60%" h={12} />
          <Bar w="70%" h={12} />
        </div>
      )}

      <span className="sr-only">loading…</span>
    </div>
  );
}
