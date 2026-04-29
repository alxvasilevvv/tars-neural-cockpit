/**
 * AuroraBackground — Aceternity-style top-down aurora.
 *
 * Two layered conic gradients that drift slowly across the top
 * 60% of the section. Single component, single backdrop — replaces
 * the four-layer stack (sparkles + beams + grid + spotlights) with
 * something disciplined that won't fight the foreground type.
 *
 * Pure CSS animations, GPU-friendly. Inherits brand triad.
 */

interface Props {
  className?: string;
  /** When true, renders darker — for use over already bright sections. */
  subdued?: boolean;
  /** When true, mounts a subtle radial mask so foreground type stays legible. */
  mask?: boolean;
}

export function AuroraBackground({ className, subdued, mask = true }: Props) {
  const opacity = subdued ? 0.45 : 0.85;

  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ""}`}
    >
      {/* Layer 1 — wide indigo + violet plume */}
      <div
        className="absolute inset-0"
        style={{
          opacity,
          background: `
            radial-gradient(ellipse 70% 45% at 30% 0%, rgba(99,102,241,0.55) 0%, transparent 55%),
            radial-gradient(ellipse 55% 35% at 75% 12%, rgba(139,92,246,0.45) 0%, transparent 55%),
            radial-gradient(ellipse 35% 25% at 50% 4%, rgba(6,182,212,0.32) 0%, transparent 55%)
          `,
          filter: "blur(40px) saturate(1.05)",
          animation: "auroraDriftA 22s ease-in-out infinite alternate",
          willChange: "transform",
        }}
      />

      {/* Layer 2 — narrow cyan accent that drifts the opposite way */}
      <div
        className="absolute inset-0"
        style={{
          opacity: opacity * 0.72,
          background: `
            radial-gradient(ellipse 30% 18% at 60% 8%, rgba(6,182,212,0.45) 0%, transparent 55%),
            radial-gradient(ellipse 22% 14% at 25% 14%, rgba(139,92,246,0.28) 0%, transparent 55%)
          `,
          filter: "blur(60px)",
          animation: "auroraDriftB 28s ease-in-out infinite alternate",
          willChange: "transform",
        }}
      />

      {/* Subtle vertical fade so the bottom 50% reads as space, not sky */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, transparent 30%, rgba(0,0,0,0.55) 70%, rgba(0,0,0,0.95) 100%)",
        }}
      />

      {/* Centre legibility mask — soft hole where foreground content sits */}
      {mask && (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 38% 32% at 50% 48%, rgba(0,0,0,0.55) 0%, transparent 70%)",
          }}
        />
      )}

      <style>{`
        @keyframes auroraDriftA {
          0%   { transform: translate3d(-1.5%, 0, 0) scale(1); }
          50%  { transform: translate3d(1.2%, -0.4%, 0) scale(1.04); }
          100% { transform: translate3d(2%, 0.5%, 0) scale(1.02); }
        }
        @keyframes auroraDriftB {
          0%   { transform: translate3d(2%, 0.4%, 0) scale(1.05); }
          50%  { transform: translate3d(-1.5%, -0.2%, 0) scale(1); }
          100% { transform: translate3d(-2%, 0.6%, 0) scale(1.03); }
        }
        @media (prefers-reduced-motion: reduce) {
          [class*="aurora"], [class*="aurora"] * { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
